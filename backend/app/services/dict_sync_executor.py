"""Per-target transactional executor for dictionary sync (112 A2/A3).

Single-action apply_one_action commits per action; that is unsafe for JHEMR
multi-table packages. This module adds a same-target shared-connection /
shared-transaction abstraction: ALL actions for one target run on ONE
connection and are committed together (or rolled back together).

Server-side only:
- It never accepts client-supplied SQL / target / connection string / action.
- It reads an approved plan + its actions from the platform DB, verifies the
  content hash, rebuilds SQL from the platform rows using the same builders
  as plan_push_actions, then dispatches per target.

Fail-closed gates mirror apply_one_action: nothing touches the business DB
unless dict_medical_push_enabled AND confirmation_token are satisfied.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dict_medical_push import (
    DictMedicalPushAction,
    DictMedicalPushPlan,
    DictMedicalPushRun,
)
from ..models.asset_system import AssetDataSource
from ..core.config import settings
from .dict_medical_push import verify_plan_integrity
from .medical_code_push import (
    _load_platform_rows,
    _open_write_connection,
    _resolve_serial_from_whitelisted_sequence,
    _resolve_serial_from_locked_max,
    _run_write_on_conn,
    _whitelisted_serial_sequence,
    build_his_diagnosis_insert,
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


def _rebuild_actions(
    db: Session,
    plan: DictMedicalPushPlan,
    target_system: str,
    *,
    hospital_no: str,
    include_jhdict: bool = True,
) -> list[dict[str, Any]]:
    """Rebuild validated SQL actions for one target from platform rows.

    Mirrors plan_push_actions so the executed SQL is exactly what would be
    planned today; a hash mismatch between plan and current platform rows is
    detected earlier by verify_plan_integrity.
    """
    stored = list(
        db.scalars(
            select(DictMedicalPushAction).where(
                DictMedicalPushAction.plan_id == plan.id,
                DictMedicalPushAction.target_system == target_system,
            )
        ).all()
    )
    item_codes = sorted({a.item_code for a in stored if a.item_code})
    rows = _load_platform_rows(
        db,
        category_code=plan.category_code,
        item_codes=item_codes,
        max_items=len(item_codes) or 50,
    )
    actions: list[dict[str, Any]] = []
    for row in rows:
        if not row["local_code"] or not row["local_name"]:
            continue
        stored_action_type = next((a.action_type for a in stored if a.item_code == row["local_code"]), "insert")
        if stored_action_type == "stop":
            stop = build_stop_action(
                category_code=plan.category_code,
                target_system=target_system,
                item_code=row["local_code"],
                item_name=row["local_name"],
                hospital_no=hospital_no,
            )
            actions.append(_push_to_dict(stop))
            # JHEMR keeps operation clinical and national-code dictionaries
            # separately; stop both rows in the same target transaction.
            if target_system == TARGET_JHEMR and plan.category_code == "operation" and row.get("national_code"):
                code_stop = build_stop_action(
                    category_code=plan.category_code,
                    target_system=target_system,
                    item_code=row["national_code"],
                    item_name=row.get("national_name") or row["local_name"],
                    hospital_no=hospital_no,
                    target_table="jhemr.operation_dict_code",
                )
                actions.append(_push_to_dict(code_stop))
            continue
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
                actions.append(_push_to_dict(build_jhemr_diagnosis_dict_insert(row, hospital_no)))
                if include_jhdict:
                    actions.append(_push_to_dict(build_jhemr_jhdict_icd_insert(row, hospital_no, serial_no=None)))
                contrast = build_jhemr_diagnosis_contrast_insert(row)
                if contrast:
                    actions.append(_push_to_dict(contrast))
            else:
                actions.append(_push_to_dict(build_jhemr_operation_dict_insert(row, hospital_no)))
                code_act = build_jhemr_operation_dict_code_insert(row, hospital_no)
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


def _run_target_transaction(
    conn: Any,
    dialect: str,
    actions: list[dict[str, Any]],
    *,
    row_counts: dict[str, int],
) -> None:
    """Execute all validated actions for one target on a shared connection.

    Sets serial_no from the DBA-whitelisted sequence when needed. No commit
    here; caller decides commit vs rollback after ALL actions succeed.
    """
    for act in actions:
        action_type = act.get("action_type")
        target_table = act.get("target_table") or ""
        sql = act.get("sql") or ""
        params = dict(act.get("params") or {})
        if target_table in {"COMM.DIAGNOSIS_DICT", "COMM.OPERATION_DICT"}:
            cur = conn.cursor()
            try:
                if target_table == "COMM.DIAGNOSIS_DICT":
                    cur.execute(
                        "SELECT 1 FROM COMM.DIAGNOSIS_DICT "
                        "WHERE DIAGNOSIS_CODE = :code AND ROWNUM <= 1",
                        {"code": params.get("diagnosis_code")},
                    )
                else:
                    cur.execute(
                        "SELECT 1 FROM COMM.OPERATION_DICT "
                        "WHERE OPERATION_CODE = :code AND ROWNUM <= 1",
                        {"code": params.get("operation_code")},
                    )
                if cur.fetchone() is not None:
                    row_counts[act.get("action_id") or act.get("item_code")] = 0
                    continue
            finally:
                cur.close()
        if target_table == "jhemr.diagnosis_dict":
            # Standard-code rows are shared with the existing dictionary;
            # an existing row is idempotent and must not be inserted again.
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM jhemr.diagnosis_dict "
                    "WHERE diagnosis_code = %s AND hospital_no = %s LIMIT 1",
                    (params.get("diagnosis_code"), params.get("hospital_no")),
                )
                if cur.fetchone() is not None:
                    row_counts[act.get("action_id") or act.get("item_code")] = 0
                    continue
        if target_table in {"jhemr.operation_dict", "jhemr.operation_dict_code"}:
            with conn.cursor() as cur:
                if target_table == "jhemr.operation_dict":
                    cur.execute(
                        "SELECT 1 FROM jhemr.operation_dict "
                        "WHERE operation_code = %s AND hospital_no = %s LIMIT 1",
                        (params.get("operation_code"), params.get("hospital_no")),
                    )
                else:
                    # The standard-code catalog contains legacy source
                    # hospital identifiers; the national code is the stable
                    # idempotency key across those records.
                    cur.execute(
                        "SELECT 1 FROM jhemr.operation_dict_code "
                        "WHERE operation_code = %s LIMIT 1",
                        (params.get("operation_code"),),
                    )
                if cur.fetchone() is not None:
                    row_counts[act.get("action_id") or act.get("item_code")] = 0
                    continue
        if target_table == "jhemr.operation_contrast_dict":
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM jhemr.operation_contrast_dict "
                    "WHERE operation_code = %s AND classify = %s LIMIT 1",
                    (params.get("operation_code"), params.get("classify")),
                )
                if cur.fetchone() is not None:
                    row_counts[act.get("action_id") or act.get("item_code")] = 0
                    continue
        if target_table == "jhemr.diagnosis_contrast_dict":
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM jhemr.diagnosis_contrast_dict "
                    "WHERE diagnosis_code = %s AND classify = %s LIMIT 1",
                    (params.get("diagnosis_code"), params.get("classify")),
                )
                if cur.fetchone() is not None:
                    row_counts[act.get("action_id") or act.get("item_code")] = 0
                    continue
        if target_table == "jhemr.jhdict_icd_vs_clinic":
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM jhemr.jhdict_icd_vs_clinic "
                    "WHERE diagnosis_code = %s AND hospital_no = %s LIMIT 1",
                    (params.get("diagnosis_code"), params.get("hospital_no")),
                )
                if cur.fetchone() is not None:
                    row_counts[act.get("action_id") or act.get("item_code")] = 0
                    continue
        needs_serial = target_table == "jhemr.jhdict_icd_vs_clinic" and params.get("serial_no") is None
        if act.get("plan_status") == "blocked" and not needs_serial:
            raise HTTPException(status_code=409, detail="target package contains blocked action")
        sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
        if target_table == "jhemr.jhdict_icd_vs_clinic" and params.get("serial_no") is None:
            seq = _whitelisted_serial_sequence()
            strategy = (settings.jhemr_serial_strategy or "disabled").strip().lower()
            if seq:
                params["serial_no"] = _resolve_serial_from_whitelisted_sequence(conn, dialect, seq)
            elif strategy == "max_plus_one_locked":
                params["serial_no"] = _resolve_serial_from_locked_max(conn, dialect)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="jhemr.jhdict_icd_vs_clinic needs serial_no; no approved allocator configured",
                )
            sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
        row_counts[act.get("action_id") or act.get("item_code")] = _run_write_on_conn(conn, dialect, sql, params)


def _actions_requiring_readback(
    actions: list[dict[str, Any]], row_counts: dict[str, int]
) -> list[dict[str, Any]]:
    """Return only actions that changed a row in the current transaction."""
    return [
        action for action in actions
        if row_counts.get(action.get("action_id") or action.get("item_code"), 0) != 0
    ]


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
    # 112 A2 / 114: fail-closed at the executor boundary too. Even when driven
    # by the outbox worker (not the approval HTTP path), never write unless the
    # global push enable flag is on.
    if not settings.dict_medical_push_enabled:
        return {"target_system": target_system, "status": "disabled", "reason": "APP_DICT_MEDICAL_PUSH_ENABLED=false"}
    if not (settings.dict_medical_push_confirmation_token or "").strip():
        return {"target_system": target_system, "status": "disabled", "reason": "medical push confirmation gate is not configured"}
    if plan.status != "approved":
        raise HTTPException(status_code=409, detail="only approved plans may be dispatched")
    if plan.expires_at and plan.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="approved plan has expired")
    if target_system not in (plan.target_systems or []):
        raise HTTPException(status_code=409, detail="target is not part of approved plan")
    if target_system not in {TARGET_HIS, TARGET_JHEMR}:
        raise HTTPException(status_code=400, detail="unsupported target_system")
    if not verify_plan_integrity(db, plan):
        raise HTTPException(status_code=409, detail="plan content hash mismatch")
    actions = _rebuild_actions(db, plan, target_system, hospital_no=hospital_no)
    hard_blocked = [
        a for a in actions
        if a.get("plan_status") == "blocked"
        and not (a.get("target_table") == "jhemr.jhdict_icd_vs_clinic" and (a.get("params") or {}).get("serial_no") is None)
    ]
    if hard_blocked:
        return {"target_system": target_system, "status": "blocked", "blocked_actions": len(hard_blocked)}
    runnable = actions
    if not runnable:
        return {"target_system": target_system, "status": "no_runnable_actions", "total_actions": len(actions)}

    source = _target_source(db, target_system, his_source_code=his_source_code, jhemr_source_code=jhemr_source_code)
    conn, dialect = _open_write_connection(source)
    row_counts: dict[str, int] = {}
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
    try:
        try:
            # 1) same-target multi-action DML on one connection
            _run_target_transaction(conn, dialect, runnable, row_counts=row_counts)
            # 2) same-connection readback BEFORE commit (112 A3):
            #    missing/multi-row/wrong stop state => fail-closed + full rollback.
            #    Existing rows are deliberately skipped by the idempotency probes
            #    above, so they must not be treated as newly inserted rows here
            #    (including rows that are currently stopped).
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
            db.commit()
            raise HTTPException(status_code=500, detail=f"dict target dispatch failed: {type(exc).__name__}") from exc
    finally:
        conn.close()

    run.status = "succeeded"
    run.succeeded_count = len(runnable)
    run.failed_count = 0
    run.reconcile_result = {
        "status": "ok",
        "readback": readback_summary,
        "row_counts": row_counts,
    }
    run.finished_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "target_system": target_system,
        "total_actions": len(runnable),
        "succeeded": len(runnable),
        "row_counts": row_counts,
        "readback": readback_summary,
        "status": "succeeded",
        "source_code": source.source_code,
    }
