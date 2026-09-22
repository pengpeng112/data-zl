"""Per-target transactional executor for dictionary sync (112 A2/A3；200 D04—D07).

Single-target shared-connection / shared-transaction: ALL actions for one target
run on ONE connection and are committed together (or rolled back together).

Server-side only:
- It never accepts client-supplied SQL / target / connection string / action.
- It reads an approved plan + its actions from the platform DB, verifies the
  content hash, then rebuilds SQL **from the approved v3 snapshot** (200 D02) —
  not from current platform rows; mid-flight value changes are rejected by
  verify_plan_integrity before any write connection is opened.

200 号整改要点：
- D04：按动作类型先分支——stop 不再进入 INSERT 存在检查（不再读错参数名
  后跳过 UPDATE）；已停用回读一致记 no_op，缺失/多行阻断。
- D05：INSERT 存在命中时按业务键读回待写字段做规范化比对——一致 no_op、
  不一致 conflict（整包阻断，不自动改 UPDATE）；不再把零写入伪装成新增成功。
- D06：动作/计划写回 execution 轴状态；摘要与 run/outbox 关联。
- D07：源端已提交而平台结果落库失败 → run 标 unknown_commit + reconcile
  提示，禁止盲重放。
- T19：JHEMR 术式停用的共享标准码复核——仍有其他在用院内术式映射同一
  国标码时不停用标准目录，并注明原因。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping
from ..models.dict_medical_push import (
    DictMedicalPushAction,
    DictMedicalPushPlan,
    DictMedicalPushRun,
)
from ..models.asset_system import AssetDataSource
from ..models.governance_base import AssetActionExecutor
from ..core.config import settings
from .dict_medical_push import (
    CODE_SETS,
    SNAPSHOT_VERSION,
    row_from_snapshot,
    verify_plan_integrity,
)
from .medical_code_push import (
    _open_write_connection,
    _resolve_serial_from_whitelisted_sequence,
    _run_write_on_conn,
    _run_select_on_conn,
    _whitelisted_serial_sequence,
    build_his_diagnosis_insert,
    build_his_infectious_sync,
    ACTION_SYNC_INFECTIOUS,
    build_his_operation_insert,
    build_jhemr_diagnosis_contrast_insert,
    build_jhemr_diagnosis_dict_insert,
    build_jhemr_jhdict_icd_insert,
    build_jhemr_operation_contrast_insert,
    build_jhemr_operation_dict_code_insert,
    build_jhemr_operation_dict_insert,
    build_stop_action,
    readback_actions_on_conn,
    TARGET_HIS,
    TARGET_JHEMR,
    validate_push_sql,
)
from .data_masking import sanitize_text

logger = logging.getLogger(__name__)


def _target_source(db: Session, target_system: str, *, his_source_code: str, jhemr_source_code: str) -> AssetDataSource:
    if target_system == TARGET_HIS:
        source_code = his_source_code
    elif target_system == TARGET_JHEMR:
        source_code = jhemr_source_code
    else:
        raise HTTPException(status_code=400, detail="unsupported target_system")
    if not source_code:
        raise HTTPException(status_code=400, detail="source_code required for apply")
    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise HTTPException(status_code=400, detail=f"source_code not found: {source_code}")
    return source


# ---------------------------------------------------------------------------
# 200 T19：共享国标术式复核
# ---------------------------------------------------------------------------

def _other_active_items_sharing_national_code(
    db: Session, *, national_code: str, excluding_local_code: str
) -> list[str]:
    """是否仍有其他在用（active）院内术式映射到同一国标码。"""
    sets = CODE_SETS["operation"]
    mappings = db.scalars(
        select(DictMedicalCodeMapping).where(
            DictMedicalCodeMapping.category_code == "operation",
            DictMedicalCodeMapping.from_code_set == sets["local"],
            DictMedicalCodeMapping.to_code_set == sets["national"],
            DictMedicalCodeMapping.to_item_code == national_code,
        )
    ).all()
    local_codes = [m.from_item_code for m in mappings if m.from_item_code != excluding_local_code]
    if not local_codes:
        return []
    active = db.scalars(
        select(DictMedicalCodeItem).where(
            DictMedicalCodeItem.category_code == "operation",
            DictMedicalCodeItem.code_set_code == sets["local"],
            DictMedicalCodeItem.status == "active",
            DictMedicalCodeItem.item_code.in_(local_codes),
        )
    ).all()
    return sorted({i.item_code for i in active})


# ---------------------------------------------------------------------------
# 200 D02：worker 按已审快照重建白名单 SQL
# ---------------------------------------------------------------------------

def _rebuild_actions(
    db: Session,
    plan: DictMedicalPushPlan,
    target_system: str,
    *,
    hospital_no: str,
    include_jhdict: bool = True,
) -> list[dict[str, Any]]:
    """Rebuild validated SQL actions for one target **from the approved snapshot**.

    值来自审批时冻结的快照（D02），不是执行时的当前平台行；当前值变化由
    verify_plan_integrity 在打开写连接前拦截。老版 insert/stop 快照（无 v3
    完整绑定）要求重新生成计划，禁止静默补哈希继续写。
    """
    stored = list(
        db.scalars(
            select(DictMedicalPushAction).where(
                DictMedicalPushAction.plan_id == plan.id,
                DictMedicalPushAction.target_system == target_system,
            )
        ).all()
    )
    for a in stored:
        payload = a.payload or {}
        if a.action_type in ("insert", "stop") and payload.get("snapshot_version") != SNAPSHOT_VERSION:
            raise HTTPException(
                status_code=409,
                detail="legacy plan snapshot: plan predates complete-snapshot binding; regenerate the plan",
            )
    actions: list[dict[str, Any]] = []
    for a in sorted(stored, key=lambda x: (x.item_code, x.action_type)):
        payload = a.payload or {}
        row = row_from_snapshot(payload)
        snapshot_hospital = payload.get("hospital_no") or hospital_no
        if a.action_type == ACTION_SYNC_INFECTIOUS:
            if target_system != TARGET_HIS or plan.category_code != "diagnosis":
                raise HTTPException(status_code=409, detail="invalid infectious sync target/category")
            # 快照值即冻结值（196 已验证语义）；名称为空表示"将清空"。
            actions.append(_push_to_dict(build_his_infectious_sync(row)))
            continue
        if a.action_type == "stop":
            stop = build_stop_action(
                category_code=plan.category_code,
                target_system=target_system,
                item_code=row["local_code"],
                item_name=row["local_name"],
                hospital_no=snapshot_hospital,
            )
            actions.append(_push_to_dict(stop))
            # JHEMR 术式：关联停用标准码目录前必须复核共享关系（T19）。
            if target_system == TARGET_JHEMR and plan.category_code == "operation" and row.get("national_code"):
                sharing = _other_active_items_sharing_national_code(
                    db, national_code=row["national_code"], excluding_local_code=row["local_code"]
                )
                if sharing:
                    # 共享标准码：不停用标准目录，院内术式行照常停用并注明。
                    actions[-1]["meta"] = {
                        **(actions[-1].get("meta") or {}),
                        "shared_standard_code_skipped": {
                            "national_code": row["national_code"],
                            "still_used_by": sharing,
                            "reason": "标准码仍被其他在用院内术式引用，未停用标准目录",
                        },
                    }
                else:
                    code_stop = build_stop_action(
                        category_code=plan.category_code,
                        target_system=target_system,
                        item_code=row["national_code"],
                        item_name=row.get("national_name") or row["local_name"],
                        hospital_no=snapshot_hospital,
                        target_table="jhemr.operation_dict_code",
                    )
                    actions.append(_push_to_dict(code_stop))
            continue
        # insert：全部字段取自 v3 快照。
        if target_system == TARGET_HIS:
            if plan.category_code == "diagnosis":
                actions.append(_push_to_dict(build_his_diagnosis_insert(row)))
            else:
                act = build_his_operation_insert(row)
                if len(row["local_code"]) > 16:
                    act.plan_status = "blocked"
                    act.reason = f"OPERATION_CODE length {len(row['local_code'])} > 16"
                actions.append(_push_to_dict(act))
        else:
            if plan.category_code == "diagnosis":
                actions.append(_push_to_dict(build_jhemr_diagnosis_dict_insert(row, snapshot_hospital)))
                if include_jhdict:
                    actions.append(_push_to_dict(build_jhemr_jhdict_icd_insert(row, snapshot_hospital, serial_no=None)))
                contrast = build_jhemr_diagnosis_contrast_insert(row)
                if contrast:
                    actions.append(_push_to_dict(contrast))
            else:
                actions.append(_push_to_dict(build_jhemr_operation_dict_insert(row, snapshot_hospital)))
                code_act = build_jhemr_operation_dict_code_insert(row, snapshot_hospital)
                if code_act:
                    actions.append(_push_to_dict(code_act))
                contrast = build_jhemr_operation_contrast_insert(row)
                if contrast:
                    actions.append(_push_to_dict(contrast))
    return actions


def _push_to_dict(act: Any) -> dict[str, Any]:
    return {
        "action_id": act.action_id,
        "action_type": act.action_type,
        "target_system": act.target_system,
        "target_table": act.target_table,
        "item_code": act.item_code,
        "item_name": act.item_name,
        "sql_dialect": act.sql_dialect,
        "sql": act.sql,
        "params": act.params,
        "plan_status": act.plan_status,
        "reason": act.reason,
        "meta": act.meta,
    }


# ---------------------------------------------------------------------------
# 200 D05：INSERT 存在命中的字段级读回比对
# ---------------------------------------------------------------------------

def _norm(value: Any) -> str:
    """规范化比较：NULL/空串等价，去首尾空白，数值转字符串。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


_PROBE_SPECS: dict[str, dict[str, Any]] = {
    # table -> {key_params: [...], fields: [(param_key, column)], stop_column}
    "COMM.DIAGNOSIS_DICT": {
        "key_sql": "DIAGNOSIS_CODE = :code",
        "fields": [("diagnosis_name", "DIAGNOSIS_NAME")],
        "stop_column": "STOP_FLAG",
    },
    "COMM.OPERATION_DICT": {
        "key_sql": "OPERATION_CODE = :code",
        "fields": [("operation_name", "OPERATION_NAME")],
        "stop_column": "STOP_FLAG",
    },
    "jhemr.diagnosis_dict": {
        "key_sql": "diagnosis_code = %(code)s AND hospital_no = %(hospital_no)s",
        "fields": [("diagnosis_name", "diagnosis_name")],
        "stop_column": "isstop",
    },
    "jhemr.operation_dict": {
        "key_sql": "operation_code = %(code)s AND hospital_no = %(hospital_no)s",
        "fields": [("operation_name", "operation_name")],
        "stop_column": "isstop",
    },
    "jhemr.operation_dict_code": {
        "key_sql": "operation_code = %(code)s",
        "fields": [("operation_name", "operation_name")],
        "stop_column": "isstop",
    },
    "jhemr.diagnosis_contrast_dict": {
        "key_sql": "diagnosis_code = %(code)s AND classify = %(classify)s",
        "fields": [("std_code", "diagnosis_code_standard")],
        "stop_column": None,
    },
    "jhemr.operation_contrast_dict": {
        "key_sql": "operation_code = %(code)s AND classify = %(classify)s",
        "fields": [("std_code", "operation_code_standard")],
        "stop_column": None,
    },
    "jhemr.jhdict_icd_vs_clinic": {
        "key_sql": "diagnosis_code = %(code)s AND hospital_no = %(hospital_no)s",
        "fields": [("clinic_name", "clinic_diagnosis_name")],
        "stop_column": None,
    },
}


def _probe_key_params(act: dict[str, Any]) -> dict[str, Any] | None:
    """INSERT 动作的业务键绑定参数；取不到说明动作形态异常（阻断）。"""
    params = dict(act.get("params") or {})
    table = act.get("target_table") or ""
    if table in {"COMM.DIAGNOSIS_DICT", "COMM.OPERATION_DICT"}:
        code = params.get("diagnosis_code") or params.get("operation_code")
        return {"code": code} if code else None
    if table == "jhemr.diagnosis_dict":
        return {"code": params.get("diagnosis_code"), "hospital_no": params.get("hospital_no")}
    if table in {"jhemr.operation_dict", "jhemr.jhdict_icd_vs_clinic"}:
        return {"code": params.get("operation_code") or params.get("diagnosis_code"), "hospital_no": params.get("hospital_no")}
    if table == "jhemr.operation_dict_code":
        return {"code": params.get("operation_code")}
    if table == "jhemr.diagnosis_contrast_dict":
        return {"code": params.get("diagnosis_code"), "classify": params.get("classify")}
    if table == "jhemr.operation_contrast_dict":
        return {"code": params.get("operation_code"), "classify": params.get("classify")}
    return None


def _existing_row_compare(
    conn: Any,
    dialect: str,
    act: dict[str, Any],
) -> str:
    """INSERT 存在探针：absent / no_op / conflict（D05）。

    命中已存在行时读回业务键 + 待写内容字段做规范化比对：
    一致 → no_op；不一致或目标行已停用（主字典表）→ conflict。
    """
    table = act.get("target_table") or ""
    spec = _PROBE_SPECS.get(table)
    key_params = _probe_key_params(act)
    if spec is None or key_params is None or not all(v is not None for v in key_params.values()):
        raise HTTPException(status_code=409, detail=f"existence probe unavailable for {table}; refusing write")
    fields = spec["fields"]
    columns = ", ".join([f"{col} AS f{i}" for i, (_, col) in enumerate(fields)])
    select_list = columns + (f", {spec['stop_column']} AS stopped" if spec["stop_column"] else "")
    if dialect == "oracle":
        sql = f"SELECT {select_list} FROM {table} WHERE {spec['key_sql']} AND ROWNUM <= 2"
    else:
        sql = f"SELECT {select_list} FROM {table} WHERE {spec['key_sql']} LIMIT 2"
    rows = _run_select_on_conn(conn, dialect, sql, key_params)
    if not rows:
        return "absent"
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=f"conflict: target {table} has multiple rows for the business key; manual review required",
        )
    existing = rows[0]
    params = dict(act.get("params") or {})
    if spec["stop_column"]:
        stopped = _norm(existing.get("stopped"))
        if stopped not in ("", "0"):
            raise HTTPException(
                status_code=409,
                detail=f"conflict: {table} already has a stopped row with this code; manual review required",
            )
    diffs = []
    for i, (param_key, _col) in enumerate(fields):
        want = _norm(params.get(param_key))
        got = _norm(existing.get(f"f{i}"))
        if want != got:
            diffs.append(param_key)
    if diffs:
        raise HTTPException(
            status_code=409,
            detail=f"conflict: {table} existing row differs on {', '.join(diffs)}; regenerate or resolve manually",
        )
    return "no_op"


def _stop_state_after_zero_rows(conn: Any, dialect: str, act: dict[str, Any]) -> str:
    """stop 更新 0 行后的回读：已停用一致 → no_op；缺失 → 阻断（D04）。"""
    from .medical_code_push import build_readback_select

    table = act.get("target_table") or ""
    built = build_readback_select(table, dialect=dialect, action_type="stop")
    if built is None:
        raise HTTPException(status_code=409, detail=f"stop readback unavailable for {table}")
    sql, meta = built
    params = dict(act.get("params") or {})
    bind: dict[str, Any] = {"code": params.get("code") or act.get("item_code")}
    if meta.get("needs_hospital"):
        hospital_no = params.get("hospital_no") or (act.get("meta") or {}).get("hospital_no")
        if not hospital_no:
            raise HTTPException(status_code=409, detail=f"stop readback for {table} requires hospital_no")
        bind["hospital_no"] = hospital_no
    if meta.get("needs_classify"):
        bind["classify"] = params.get("classify")
    rows = _run_select_on_conn(conn, dialect, sql, bind)
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=f"stop target row missing in {table}/{bind.get('code')}; refusing silent no-op",
        )
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=f"stop target has {len(rows)} rows in {table}/{bind.get('code')}; conflict",
        )
    stopped_raw = rows[0].get("stopped")
    try:
        stopped = int(stopped_raw) if stopped_raw is not None else 0
    except (TypeError, ValueError):
        stopped = 0
    if stopped == 1:
        return "no_op"
    raise HTTPException(
        status_code=409,
        detail=f"stop update affected 0 rows but row still active in {table}/{bind.get('code')}",
    )


def _run_target_transaction(
    conn: Any,
    dialect: str,
    actions: list[dict[str, Any]],
    *,
    row_counts: dict[str, int],
    outcomes: dict[str, str] | None = None,
) -> None:
    """Execute all validated actions for one target on a shared connection.

    200 D04/D05：
    - 先按 action_type 分支；stop 不进入 INSERT 存在检查；
    - INSERT 存在命中做字段级比对（no_op/conflict），不再 SELECT 1 跳过；
    - outcomes 记录 inserted/no_op/updated/stopped，供 D06 状态回写与
      "零写入 ≠ 新增成功"的诚实计数。
    No commit here; caller decides commit vs rollback after ALL actions succeed.
    """
    outcomes = outcomes if outcomes is not None else {}
    for act in actions:
        action_type = act.get("action_type")
        target_table = act.get("target_table") or ""
        sql = act.get("sql") or ""
        params = dict(act.get("params") or {})
        key = act.get("action_id") or act.get("item_code")

        if action_type == ACTION_SYNC_INFECTIOUS:
            sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
            if dialect != "oracle" or act.get("target_system") != TARGET_HIS or params.get("code") != act.get("item_code"):
                raise HTTPException(status_code=409, detail="invalid infectious sync scope")
            before = _run_select_on_conn(
                conn, dialect,
                "SELECT DIAGNOSIS_NAME_CRB AS crb_name FROM COMM.DIAGNOSIS_DICT "
                "WHERE DIAGNOSIS_CODE = :code AND ROWNUM <= 2",
                {"code": params["code"]},
            )
            if len(before) != 1:
                raise HTTPException(status_code=409, detail="infectious sync requires exactly one existing HIS diagnosis")
            old_value = before[0].get("crb_name")
            act.setdefault("meta", {})["before_value"] = old_value
            if old_value == params.get("crb_name"):
                row_counts[key] = 0
                outcomes[key] = "no_op"
                continue
            params["old_crb_name"] = old_value
            count = _run_write_on_conn(conn, dialect, sql, params)
            if count != 1:
                raise HTTPException(status_code=409, detail="infectious sync row count/concurrent change conflict")
            row_counts[key] = count
            outcomes[key] = "updated"
            continue

        if action_type == "stop":
            # D04：单项 stop 不走任何 INSERT 存在查重；精确业务键 UPDATE，
            # 0 行时回读状态分辨 no_op（已停用一致）与缺失（阻断）。
            sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
            count = _run_write_on_conn(conn, dialect, sql, params)
            row_counts[key] = count
            if count == 1:
                outcomes[key] = "stopped"
                continue
            if count > 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"stop affected {count} rows in {target_table}; refusing multi-row stop",
                )
            outcomes[key] = _stop_state_after_zero_rows(conn, dialect, act)
            continue

        # INSERT：存在命中 → 字段级比对（D05）。
        state = _existing_row_compare(conn, dialect, act)
        if state == "no_op":
            row_counts[key] = 0
            outcomes[key] = "no_op"
            continue

        needs_serial = target_table == "jhemr.jhdict_icd_vs_clinic" and params.get("serial_no") is None
        if act.get("plan_status") == "blocked" and not needs_serial:
            raise HTTPException(status_code=409, detail="target package contains blocked action")
        sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
        if target_table == "jhemr.jhdict_icd_vs_clinic" and params.get("serial_no") is None:
            seq = _whitelisted_serial_sequence()
            if not seq:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "jhemr.jhdict_icd_vs_clinic needs serial_no; "
                        "no DBA-whitelisted sequence is configured"
                    ),
                )
            params["serial_no"] = _resolve_serial_from_whitelisted_sequence(conn, dialect, seq)
            sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
        row_counts[key] = _run_write_on_conn(conn, dialect, sql, params)
        outcomes[key] = "inserted"


def _actions_requiring_readback(
    actions: list[dict[str, Any]], row_counts: dict[str, int]
) -> list[dict[str, Any]]:
    """Return only actions that changed a row in the current transaction."""
    return [
        action for action in actions
        if (row_counts.get(action.get("action_id") or action.get("item_code"), 0) != 0
            or action.get("action_type") == ACTION_SYNC_INFECTIOUS)
    ]


def _require_infectious_executor(db: Session, source: AssetDataSource) -> None:
    """Dedicated registration must be approved separately; never auto-seeded."""
    executor = db.scalar(select(AssetActionExecutor).where(
        AssetActionExecutor.executor_code == "his_diagnosis_infectious_sync"
    ))
    if (executor is None or not executor.enabled or not executor.require_approval
            or executor.execution_mode != "sync_executor"
            or executor.target_system_code != TARGET_HIS
            or executor.target_source_code != source.source_code
            or executor.sql_or_endpoint_ref != "COMM.DIAGNOSIS_DICT.DIAGNOSIS_NAME_CRB"
            or (source.system_code or "").upper() not in {"HIS", TARGET_HIS}
            or (source.db_type or "").lower() != "oracle"):
        raise HTTPException(status_code=403, detail="infectious sync executor not registered/enabled for this source and field")


# ---------------------------------------------------------------------------
# 200 D06：动作/计划执行状态回写
# ---------------------------------------------------------------------------

def _update_action_and_plan_status(
    db: Session,
    plan: DictMedicalPushPlan,
    target_system: str,
    *,
    run_id: int | None,
    outcomes: dict[str, str],
    generated: list[dict[str, Any]],
    failed_reason: str | None = None,
) -> None:
    """把本目标执行结果回写到动作与计划执行轴（D06）。

    generated 子动作按 (item_code, action_type) 归并到存储动作行；全部
    no_op → no_op，存在 inserted/updated/stopped → succeeded，失败路径
    由调用方标 failed/conflict。执行轴不破坏授权轴（plan.status 保持
    approved，worker 的前提不被终态覆盖）。
    """
    stored = db.scalars(
        select(DictMedicalPushAction).where(
            DictMedicalPushAction.plan_id == plan.id,
            DictMedicalPushAction.target_system == target_system,
        )
    ).all()
    now = datetime.now(timezone.utc)
    by_item: dict[str, DictMedicalPushAction] = {}
    for a in stored:
        by_item.setdefault(a.item_code, a)
    for gen in generated:
        item_code = gen.get("item_code")
        row = by_item.get(item_code)
        if row is None:
            continue
        outcome = outcomes.get(gen.get("action_id") or item_code)
        if failed_reason:
            row.status = "failed"
            row.error_masked = sanitize_text(failed_reason)[:500]
        elif outcome in {"no_op"}:
            row.status = "no_op"
        elif outcome:
            row.status = "succeeded"
        if run_id is not None:
            row.run_id = run_id
        row.executed_at = now
    # 计划执行轴：按本计划全部 run 汇总。
    runs = db.scalars(
        select(DictMedicalPushRun).where(DictMedicalPushRun.plan_id == plan.id)
    ).all()
    if runs:
        statuses = {r.status for r in runs}
        if any(s in {"failed", "unknown_commit"} for s in statuses):
            plan.execution_status = "partial" if any(r.status == "succeeded" for r in runs) else (
                "unknown_commit" if statuses == {"unknown_commit"} else "failed"
            )
        elif statuses == {"succeeded"}:
            plan.execution_status = "succeeded"
        elif "running" in statuses:
            plan.execution_status = "running"
        else:
            plan.execution_status = sorted(statuses)[0]
    plan.updated_at = now


def dispatch_target(
    db: Session,
    plan: DictMedicalPushPlan,
    target_system: str,
    *,
    his_source_code: str,
    jhemr_source_code: str,
    operator: str | None = None,
    hospital_no: str = "49557032X",
) -> dict[str, Any]:
    """Dispatch ONE approved plan target under a shared connection/transaction.

    Commits only if every action in the target succeeded; else rolls back the
    whole target transaction (no partial multi-table writes).
    """
    # 112 A2 / 114 + 200 D07：executor 边界同样失败关闭。
    if not settings.dict_medical_push_enabled:
        plan.execution_status = plan.execution_status or "queued"
        return {"target_system": target_system, "status": "disabled", "reason": "APP_DICT_MEDICAL_PUSH_ENABLED=false"}
    if not (settings.dict_medical_push_confirmation_token or "").strip():
        return {"target_system": target_system, "status": "disabled", "reason": "medical push confirmation gate is not configured"}
    if plan.status != "approved":
        raise HTTPException(status_code=409, detail="only approved plans may be dispatched")
    if plan.expires_at:
        expires = plan.expires_at if plan.expires_at.tzinfo else plan.expires_at.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="approved plan has expired")
    if target_system not in (plan.target_systems or []):
        raise HTTPException(status_code=409, detail="target is not part of approved plan")
    if target_system not in {TARGET_HIS, TARGET_JHEMR}:
        raise HTTPException(status_code=400, detail="unsupported target_system")
    if not verify_plan_integrity(db, plan):
        plan.execution_status = "stale_snapshot"
        db.commit()
        raise HTTPException(status_code=409, detail="plan content hash mismatch")
    actions = _rebuild_actions(db, plan, target_system, hospital_no=hospital_no)
    hard_blocked = [
        a for a in actions
        if a.get("plan_status") == "blocked"
        and not (a.get("target_table") == "jhemr.jhdict_icd_vs_clinic" and (a.get("params") or {}).get("serial_no") is None)
    ]
    if hard_blocked:
        plan.execution_status = "blocked"
        db.commit()
        return {"target_system": target_system, "status": "blocked", "blocked_actions": len(hard_blocked)}
    runnable = actions
    if not runnable:
        return {"target_system": target_system, "status": "no_runnable_actions", "total_actions": len(actions)}

    source = _target_source(db, target_system, his_source_code=his_source_code, jhemr_source_code=jhemr_source_code)
    if any(a.get("action_type") == ACTION_SYNC_INFECTIOUS for a in runnable):
        if not plan.approved_by or plan.approved_by == plan.created_by:
            raise HTTPException(status_code=403, detail="infectious sync requires independent plan approval")
        _require_infectious_executor(db, source)
    conn, dialect = _open_write_connection(source)
    row_counts: dict[str, int] = {}
    outcomes: dict[str, str] = {}
    readback_summary: dict[str, Any] | None = None
    run = DictMedicalPushRun(
        plan_id=plan.id,
        target_system=target_system,
        target_source_code=source.source_code,
        status="running",
        total_actions=len(runnable),
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()
    plan.execution_status = "running"
    try:
        try:
            # 1) same-target multi-action DML on one connection
            _run_target_transaction(conn, dialect, runnable, row_counts=row_counts, outcomes=outcomes)
            # 2) same-connection readback BEFORE commit (112 A3)
            applied_actions = _actions_requiring_readback(runnable, row_counts)
            readback_summary = readback_actions_on_conn(conn, dialect, applied_actions)
            # 3) only commit after readback confirms every key
            conn.commit()
        except HTTPException as exc:
            conn.rollback()
            run.status = "failed"
            run.failed_count = len(runnable)
            run.succeeded_count = 0
            run.error_masked = sanitize_text(str(exc.detail if hasattr(exc, "detail") else exc))[:500]
            run.reconcile_result = {
                "status": "reconcile_required",
                "reason": "write_or_readback_failed",
                "row_counts": row_counts,
            }
            run.finished_at = datetime.now(timezone.utc)
            _update_action_and_plan_status(
                db, plan, target_system, run_id=run.id, outcomes=outcomes,
                generated=runnable, failed_reason=run.error_masked,
            )
            db.commit()
            raise
        except Exception as exc:
            conn.rollback()
            run.status = "failed"
            run.failed_count = len(runnable)
            run.succeeded_count = 0
            run.error_masked = sanitize_text(f"{type(exc).__name__}")[:500]
            run.reconcile_result = {
                "status": "reconcile_required",
                "reason": "write_or_readback_failed",
                "row_counts": row_counts,
            }
            run.finished_at = datetime.now(timezone.utc)
            _update_action_and_plan_status(
                db, plan, target_system, run_id=run.id, outcomes=outcomes,
                generated=runnable, failed_reason=run.error_masked,
            )
            db.commit()
            raise HTTPException(status_code=500, detail=f"dict target dispatch failed: {type(exc).__name__}") from exc
    finally:
        conn.close()

    # 源端已 commit；平台侧结果落库失败 → unknown_commit + reconcile（D07），
    # 不得让事件被盲重放成重复新增。
    breakdown: dict[str, int] = {}
    for outcome in outcomes.values():
        breakdown[outcome] = breakdown.get(outcome, 0) + 1
    run.status = "succeeded"
    run.succeeded_count = sum(1 for v in outcomes.values() if v != "no_op")
    run.skipped_count = sum(1 for v in outcomes.values() if v == "no_op")
    run.failed_count = 0
    run.reconcile_result = {
        "status": "ok",
        "readback": readback_summary,
        "row_counts": row_counts,
        "outcomes": outcomes,
        "breakdown": breakdown,
    }
    run.finished_at = datetime.now(timezone.utc)
    _update_action_and_plan_status(
        db, plan, target_system, run_id=run.id, outcomes=outcomes, generated=runnable
    )
    try:
        db.commit()
    except Exception:
        # D07：源端已提交而平台落库失败。rollback 会回退 run 插入与计划
        # 状态改动，恢复必须在 rollback 之后重设并重新 add，尽最大努力
        # 留下 unknown_commit 对账标记（仍失败则只记日志，事件走 reconcile
        # 路径，禁止盲重放）。
        db.rollback()
        try:
            run.status = "unknown_commit"
            run.reconcile_result = {
                "status": "reconcile_required",
                "reason": "platform_result_commit_failed_after_source_commit",
                "row_counts": row_counts,
            }
            plan.execution_status = "unknown_commit"
            db.add(run)
            db.add(plan)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "dict dispatch unknown_commit marker persistence failed plan_id=%s target=%s",
                plan.id, target_system,
            )
        raise HTTPException(
            status_code=500,
            detail="source committed but platform result persistence failed; event must reconcile before retry",
        )

    return {
        "target_system": target_system,
        "total_actions": len(runnable),
        "succeeded": sum(1 for v in outcomes.values() if v != "no_op"),
        "no_op": run.skipped_count,
        "row_counts": row_counts,
        "outcomes": outcomes,
        "readback": readback_summary,
        "status": "succeeded",
        "source_code": source.source_code,
    }
