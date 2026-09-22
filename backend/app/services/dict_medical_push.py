"""诊断映射推送计划服务（101号 §4.3-4.5；200 号 D01/D02/D06 整改）。

服务端生成不可篡改计划，禁止客户端传入 SQL。
计划包含 content_hash，源数据变化则过期。
执行只接受 plan_id + 目标系统 + 确认。

200 号整改要点：
- D01：insert/stop/sync_infectious 一律要求明确选择 1—500 个编码
  （stop 单编码），缺失/空列表/空白编码不得解释为全选；选项不存在或
  状态不符时整包拒绝；import_run_id 在未实现"解析已审核批次明确编码"
  前显式拒绝。
- D02：共享规范化选择/映射解析器（精确 code_set + 歧义映射阻断），
  创建、核验、执行共用；快照 v3 覆盖执行器实际写入的全部字段并带
  版本；worker 按已审快照重建白名单 SQL，写入前经 verify 比对当前值。
- D06：摘要返回全部动作业务预览 + 授权/执行两条状态轴 + run/outbox 关联。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping
from ..models.dict_medical_push import (
    DictMedicalPushAction,
    DictMedicalPushPlan,
    DictMedicalPushRun,
)

PLAN_TTL_HOURS = 24
CATEGORY_DIAGNOSIS = "diagnosis"
CATEGORY_OPERATION = "operation"
VALID_CATEGORIES = (CATEGORY_DIAGNOSIS, CATEGORY_OPERATION)
VALID_TARGET_SYSTEMS = ("HIS_SOURCE", "JHEMR_VASTBASE")
VALID_ACTION_TYPES = ("insert", "stop", "sync_infectious")
TARGET_ALIASES = {"HIS": "HIS_SOURCE", "JHEMR": "JHEMR_VASTBASE"}

# 200 D01：单次计划编码上限。
MAX_ITEM_CODES = 500

# 200 D02：完整执行语义快照版本。v2 仅覆盖传染病字段；执行器对
# insert/stop 要求 v3（老计划可查看，待执行需重新生成）。
SNAPSHOT_VERSION = 3

# 精确 code_set（与 medical_code_push 常量一致；本层不反向依赖执行器模块）。
CODE_SETS = {
    "diagnosis": {
        "local": "diagnosis_local_clinical",
        "national": "diagnosis_national_clinical_v2",
        "insurance": "diagnosis_insurance_v2",
    },
    "operation": {
        "local": "operation_local_clinical",
        "national": "operation_national_clinical_v3",
        "insurance": "operation_insurance_v2",
    },
}


class PlanSelectionError(ValueError):
    """带稳定 reason_code 的计划选择/快照拒绝（API 层转 400 结构化错误）。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def normalize_target_system(target: str) -> str:
    normalized = TARGET_ALIASES.get((target or "").strip().upper(), (target or "").strip().upper())
    if normalized not in VALID_TARGET_SYSTEMS:
        raise PlanSelectionError("invalid_target_system", f"无效目标系统: {target}")
    return normalized


def _as_utc(value):
    """驱动/sqlite 可能返回 naive datetime；统一补 UTC 后再比较。"""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _local_code_set(category_code: str) -> str:
    return CODE_SETS[category_code]["local"]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_grey_insurance(insurance_code: str, insurance_name: str, mapping_status: str) -> bool:
    """灰码判定（与 medical_code_push._is_grey_insurance 保持同一口径）。"""
    if not insurance_code:
        return False
    if insurance_code == "灰码":
        return True
    if "灰码" in (insurance_name or ""):
        return True
    return (mapping_status or "").strip() == "grey"


# ---------------------------------------------------------------------------
# 200 D02：共享规范化选择/映射解析器
# ---------------------------------------------------------------------------

def _resolve_mappings_exact(
    db: Session, *, category_code: str, item_codes: list[str]
) -> dict[tuple[str, str], str]:
    """精确 code_set 的映射解析；同 (院内码, 目标体系) 出现多个不同目标码
    即歧义，直接阻断（D02：创建取最后一个、核验取第一个的不一致不复存在）。"""
    sets = CODE_SETS[category_code]
    mappings = db.scalars(
        select(DictMedicalCodeMapping).where(
            DictMedicalCodeMapping.category_code == category_code,
            DictMedicalCodeMapping.from_code_set == sets["local"],
            DictMedicalCodeMapping.from_item_code.in_(item_codes),
            DictMedicalCodeMapping.to_code_set.in_([sets["national"], sets["insurance"]]),
        )
    ).all()
    resolved: dict[tuple[str, str], str] = {}
    ambiguous: dict[tuple[str, str], set[str]] = {}
    for m in mappings:
        key = (m.from_item_code, m.to_code_set)
        code = _text(m.to_item_code)
        if key in resolved and resolved[key] != code:
            ambiguous.setdefault(key, {resolved[key]}).add(code)
            continue
        resolved[key] = code
    if ambiguous:
        detail = "; ".join(f"{k[0]}→{k[1]}: {sorted(v)}" for k, v in sorted(ambiguous.items()))
        raise PlanSelectionError("mapping_ambiguous", f"映射歧义，请先在维护页修正对照关系: {detail}")
    return resolved


def build_item_snapshot(
    db: Session,
    *,
    category_code: str,
    item: DictMedicalCodeItem,
    action_type: str,
    target_systems: list[str],
    hospital_no: str,
    map_by: dict[tuple[str, str], str],
    name_by: dict[tuple[str, str], str],
) -> dict[str, Any]:
    """单个编码项 → v3 完整快照（覆盖执行器写入的全部字段与派生标记）。"""
    sets = CODE_SETS[category_code]
    extra = item.extra or {}
    national_code = _text(map_by.get((item.item_code, sets["national"])) or extra.get("national_clinical_code"))
    national_name = _text(
        name_by.get((sets["national"], national_code)) or extra.get("national_clinical_name")
    )
    insurance_code = _text(map_by.get((item.item_code, sets["insurance"])) or extra.get("insurance_raw_code"))
    insurance_name = _text(
        name_by.get((sets["insurance"], insurance_code)) or extra.get("insurance_raw_name")
    )
    mapping_status = _text(extra.get("insurance_mapping_status"))
    requested_ybhm = _text(extra.get("jhemr_ybhm"))
    grey = requested_ybhm == "灰码" or _is_grey_insurance(insurance_code, insurance_name, mapping_status)
    write_contrast = (not grey) and bool(insurance_code) and insurance_code != "灰码"
    return {
        # 业务键与基础字段
        "item_code": item.item_code,
        "item_name_cn": item.item_name_cn,
        "status": item.status,
        # 国标/医保映射
        "national_clinical_code": national_code,
        "national_clinical_name": national_name,
        "insurance_code": insurance_code,
        "insurance_name": insurance_name,
        "insurance_mapping_status": mapping_status,
        "jhemr_ybhm": requested_ybhm or None,
        # extra 目标字段（执行器实际写入）
        "dict_attribute": _text(extra.get("dict_attribute")),
        "operation_level": _text(extra.get("operation_level")),
        "operation_category": _text(extra.get("operation_category")),
        "performance_level4_flag": _text(extra.get("performance_level4_flag")),
        "performance_minimally_invasive_flag": _text(extra.get("performance_minimally_invasive_flag")),
        "restricted_tech_flag": _text(extra.get("restricted_tech_flag")),
        "special_disease_code": _text(extra.get("special_disease_code")),
        "special_disease_name": _text(extra.get("special_disease_name")),
        "low_risk_category_code": _text(extra.get("low_risk_category_code")),
        "low_risk_disease_name": _text(extra.get("low_risk_disease_name")),
        "infectious_disease_name": _text(extra.get("infectious_disease_name")),
        "infectious_disease_code": _text(extra.get("infectious_disease_code")),
        # 派生标记（与 _load_platform_rows 同口径）
        "is_grey_insurance": grey,
        "write_contrast": write_contrast,
        # 执行语义绑定
        "action_type": action_type,
        "category_code": category_code,
        "target_systems": sorted(target_systems),
        "hospital_no": hospital_no,
        # 版本
        "snapshot_version": SNAPSHOT_VERSION,
        "hash_version": 2,
    }


def resolve_item_snapshots(
    db: Session,
    *,
    category_code: str,
    item_codes: list[str],
    expected_status: str,
    action_type: str,
    target_systems: list[str],
    hospital_no: str,
) -> list[dict[str, Any]]:
    """共享规范化选择/映射解析器：按明确编码集合加载并生成 v3 快照。

    - 精确 status 过滤（stop=inactive，其余=active）；
    - 选项缺失（不存在或状态不符）整包拒绝（D01）；
    - 映射歧义直接阻断（D02）。
    """
    sets = CODE_SETS[category_code]
    items = list(
        db.scalars(
            select(DictMedicalCodeItem).where(
                DictMedicalCodeItem.category_code == category_code,
                DictMedicalCodeItem.code_set_code == sets["local"],
                DictMedicalCodeItem.status == expected_status,
                DictMedicalCodeItem.item_code.in_(item_codes),
            )
        ).all()
    )
    found = {i.item_code for i in items}
    missing = sorted(set(item_codes) - found)
    if missing:
        raise PlanSelectionError(
            "invalid_item_state",
            f"所选编码不存在或状态不符合动作要求（需要 {expected_status}）: {', '.join(missing[:20])}"
            + ("…" if len(missing) > 20 else ""),
        )
    map_by = _resolve_mappings_exact(db, category_code=category_code, item_codes=item_codes)
    target_codes = [c for c in map_by.values() if c]
    name_by: dict[tuple[str, str], str] = {}
    if target_codes:
        targets = db.scalars(
            select(DictMedicalCodeItem).where(
                DictMedicalCodeItem.code_set_code.in_([sets["national"], sets["insurance"]]),
                DictMedicalCodeItem.item_code.in_(target_codes),
            )
        ).all()
        name_by = {(t.code_set_code, t.item_code): t.item_name_cn for t in targets}
    return [
        build_item_snapshot(
            db,
            category_code=category_code,
            item=item,
            action_type=action_type,
            target_systems=target_systems,
            hospital_no=hospital_no,
            map_by=map_by,
            name_by=name_by,
        )
        for item in sorted(items, key=lambda i: i.item_code)
    ]


def row_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """v3 快照 → 执行器 builder 的 row 形态（键名对齐 _load_platform_rows）。

    worker 按已审快照重建 SQL（D02）：值来自审批时冻结的快照，而非执行时
    的当前平台行；当前值变化由 verify_plan_integrity 在写入前拦截。
    """
    return {
        "category_code": snapshot.get("category_code"),
        "local_code": snapshot.get("item_code"),
        "local_name": snapshot.get("item_name_cn"),
        "dict_attribute": snapshot.get("dict_attribute") or "",
        "national_code": snapshot.get("national_clinical_code") or "",
        "national_name": snapshot.get("national_clinical_name") or "",
        "insurance_code": snapshot.get("insurance_code") or "",
        "insurance_name": snapshot.get("insurance_name") or "",
        "is_grey_insurance": bool(snapshot.get("is_grey_insurance")),
        "ybhm_to_write": "灰码" if snapshot.get("is_grey_insurance") else None,
        "write_contrast": bool(snapshot.get("write_contrast")),
        "mtb_code": snapshot.get("special_disease_code") or "",
        "mtb_name": snapshot.get("special_disease_name") or "",
        "icd_lr_code": snapshot.get("low_risk_category_code") or "",
        "icd_lr_name": snapshot.get("low_risk_disease_name") or "",
        "infectious_name": snapshot.get("infectious_disease_name") or "",
        "infectious_code": snapshot.get("infectious_disease_code") or "",
        "operation_level": snapshot.get("operation_level") or "",
        "operation_category": snapshot.get("operation_category") or "",
        "level4_flag": snapshot.get("performance_level4_flag") or "",
        "mini_flag": snapshot.get("performance_minimally_invasive_flag") or "",
        "limit_flag": snapshot.get("restricted_tech_flag") or "",
    }


def _compute_plan_hash(items: list[dict[str, Any]]) -> str:
    canonical_items = sorted(items, key=lambda item: item.get("item_code", ""))
    return hashlib.sha256(
        json.dumps(canonical_items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]


def _normalize_explicit_codes(item_codes: Optional[list[str]], *, action_type: str) -> list[str]:
    """D01：规范化去重后的明确编码；空选择一律拒绝，不解释为全选。"""
    if item_codes is None:
        raise PlanSelectionError("empty_selection", "必须明确选择编码：不允许空选择隐式扩大为整类字典")
    cleaned: list[str] = []
    for code in item_codes:
        text = (code or "").strip()
        if not text:
            raise PlanSelectionError("blank_item_code", "编码不能为空白值")
        cleaned.append(text)
    deduped = list(dict.fromkeys(cleaned))
    if not deduped:
        raise PlanSelectionError("empty_selection", "必须明确选择至少 1 个编码")
    if len(deduped) > MAX_ITEM_CODES:
        raise PlanSelectionError("too_many_codes", f"单次最多 {MAX_ITEM_CODES} 个编码，收到 {len(deduped)} 个")
    if action_type == "stop" and len(deduped) != 1:
        raise PlanSelectionError("stop_single_code_only", "停用一次只允许一个编码（单编码停用约束）")
    return deduped


def create_push_plan(
    db: Session,
    *,
    category_code: str,
    target_systems: list[str],
    item_codes: Optional[list[str]] = None,
    import_run_id: Optional[int] = None,
    created_by: str,
    action_type: str = "insert",
    hospital_no: str = "49557032X",
) -> DictMedicalPushPlan:
    """从平台正式字典生成推送计划（D01/D02：明确选择 + v3 完整快照）。"""
    if category_code not in VALID_CATEGORIES:
        raise PlanSelectionError("invalid_category", f"仅支持 {', '.join(VALID_CATEGORIES)}，收到 {category_code}")
    if action_type not in VALID_ACTION_TYPES:
        raise PlanSelectionError("invalid_action", f"无效动作类型: {action_type}")
    target_systems = list(dict.fromkeys(normalize_target_system(ts) for ts in target_systems))
    if import_run_id is not None:
        # D01：未实现"解析已审核批次的明确编码并与用户选项比对"前显式拒绝，
        # 不能继续静默忽略该参数。
        raise PlanSelectionError(
            "import_run_unsupported",
            "暂不支持按导入批次创建计划：请在维护页按明确编码选择后创建",
        )
    item_codes = _normalize_explicit_codes(item_codes, action_type=action_type)
    if action_type == "sync_infectious":
        if category_code != CATEGORY_DIAGNOSIS or target_systems != ["HIS_SOURCE"]:
            raise PlanSelectionError("invalid_infectious_scope", "传染病诊断同步仅支持 HIS 诊断字典")

    expected_status = "inactive" if action_type == "stop" else "active"
    item_dicts = resolve_item_snapshots(
        db,
        category_code=category_code,
        item_codes=item_codes,
        expected_status=expected_status,
        action_type=action_type,
        target_systems=target_systems,
        hospital_no=hospital_no,
    )

    content_hash = _compute_plan_hash(item_dicts)
    plan_code = f"push-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    plan = DictMedicalPushPlan(
        plan_code=plan_code,
        category_code=category_code,
        target_systems=target_systems,
        status="draft",
        execution_status="draft",
        platform_data_version=content_hash,
        content_hash=content_hash,
        expires_at=now + timedelta(hours=PLAN_TTL_HOURS),
        item_count=len(item_dicts),
        created_by=created_by,
    )
    db.add(plan)
    db.flush()

    for item_dict in item_dicts:
        for target in target_systems:
            action = DictMedicalPushAction(
                plan_id=plan.id,
                target_system=target,
                item_code=item_dict["item_code"],
                item_name_cn=item_dict["item_name_cn"],
                action_type=action_type,
                payload=item_dict,
                status="planned",
                diff_type="changed" if action_type == "sync_infectious" else ("stopped" if action_type == "stop" else "new"),
            )
            db.add(action)

    db.commit()
    return plan


def approve_plan(db: Session, plan_id: int, approved_by: str, note: Optional[str] = None) -> DictMedicalPushPlan:
    """审批计划。审批人不能是创建人；审批即入队（outbox 同事务）。"""
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise PlanSelectionError("plan_not_found", "计划不存在")
    if plan.status != "draft":
        raise PlanSelectionError("invalid_plan_status", f"计划状态 {plan.status} 不允许审批")
    if plan.created_by == approved_by:
        raise PlanSelectionError("self_approval_forbidden", "创建人不能自审")
    now = datetime.now(timezone.utc)
    if plan.expires_at and _as_utc(plan.expires_at) < now:
        raise PlanSelectionError("plan_expired", "计划已过期")
    plan.status = "approved"
    plan.execution_status = "queued"
    plan.approved_by = approved_by
    plan.approved_at = now
    plan.approval_note = note
    plan.updated_at = now
    # 112 A1/A5：审批即入队（outbox 与审批同事务，保证已审批计划不丢）
    from .dict_sync_worker import enqueue_plan_dispatch
    enqueue_plan_dispatch(db, plan.id, plan.content_hash or "", plan.target_systems or [])
    db.commit()
    return plan


def verify_plan_integrity(db: Session, plan: DictMedicalPushPlan) -> bool:
    """Verify stored actions and current platform rows against the approved hash.

    200 D02：当前值重算走共享解析器（与创建完全同口径），v3 快照哈希覆盖
    全部写入字段；v2（传染病专项）保持原可读语义。
    """
    actions = db.scalars(
        select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan.id)
    ).all()
    for action in actions:
        payload = action.payload or {}
        if action.action_type not in VALID_ACTION_TYPES:
            return False
        # 通用绑定：动作行目标必须属于计划目标集合（防止单行改 target 扩大范围）。
        if action.target_system not in (plan.target_systems or []):
            return False
        # 通用绑定：payload 声明的动作类型必须与动作行一致（防止单行改
        # action_type 换执行语义）。
        if payload.get("action_type") and payload.get("action_type") != action.action_type:
            return False
        if payload.get("snapshot_version") == SNAPSHOT_VERSION:
            if (payload.get("action_type") != action.action_type
                    or payload.get("category_code") != plan.category_code
                    or payload.get("item_code") != action.item_code
                    or payload.get("target_systems") != sorted(plan.target_systems or [])
                    or action.target_system not in payload.get("target_systems", [])):
                return False
            siblings = [a for a in actions if a.item_code == action.item_code]
            if (len(siblings) != len(plan.target_systems or [])
                    or {a.target_system for a in siblings} != set(plan.target_systems or [])
                    or any((a.payload or {}).get("snapshot_version") != SNAPSHOT_VERSION for a in siblings)):
                return False
        elif action.action_type == "sync_infectious" and payload.get("hash_version") == 2:
            if (payload.get("action_type") != action.action_type
                    or payload.get("category_code") != plan.category_code
                    or payload.get("item_code") != action.item_code
                    or payload.get("target_systems") != sorted(plan.target_systems or [])):
                return False
        # 兼容旧 v2/v1 insert/stop 快照：仅要求基础绑定一致（查看允许，
        # 执行侧会要求重新生成，见 dict_sync_executor._rebuild_actions）。

    item_payloads = []
    seen: set[str] = set()
    for a in actions:
        if a.item_code in seen:
            continue
        seen.add(a.item_code)
        item_payloads.append(dict(a.payload or {}))
    if not item_payloads:
        return False
    if _compute_plan_hash(item_payloads) != plan.content_hash:
        return False

    # 用同一解析器重算当前平台值：任何被快照覆盖的字段变化都使计划失效。
    stored_action_type = actions[0].action_type if actions else "insert"
    if all((a.payload or {}).get("snapshot_version") == SNAPSHOT_VERSION for a in actions):
        expected_status = "inactive" if stored_action_type == "stop" else "active"
        try:
            current = resolve_item_snapshots(
                db,
                category_code=plan.category_code,
                item_codes=sorted(seen),
                expected_status=expected_status,
                action_type=stored_action_type,
                target_systems=list(plan.target_systems or []),
                hospital_no=(actions[0].payload or {}).get("hospital_no") or "49557032X",
            )
        except PlanSelectionError:
            return False
        return _compute_plan_hash(current) == plan.content_hash

    # v2 传染病专项：按原口径核对（含 extra 字段）。
    current_items: list[dict[str, Any]] = []
    for snapshot in item_payloads:
        item = db.scalar(select(DictMedicalCodeItem).where(
            DictMedicalCodeItem.category_code == plan.category_code,
            DictMedicalCodeItem.code_set_code == _local_code_set(plan.category_code),
            DictMedicalCodeItem.item_code == snapshot.get("item_code"),
        ))
        if item is None:
            return False
        sets = CODE_SETS[plan.category_code]
        mappings = db.scalars(select(DictMedicalCodeMapping).where(
            DictMedicalCodeMapping.category_code == plan.category_code,
            DictMedicalCodeMapping.from_code_set == sets["local"],
            DictMedicalCodeMapping.from_item_code == item.item_code,
            DictMedicalCodeMapping.to_code_set.in_([sets["national"], sets["insurance"]]),
        )).all()
        map_exact = {(m.from_item_code, m.to_code_set): m.to_item_code for m in mappings}
        current = dict(snapshot)
        current.update({
            "item_code": item.item_code,
            "item_name_cn": item.item_name_cn,
            "national_clinical_code": _text(map_exact.get((item.item_code, sets["national"])) or (item.extra or {}).get("national_clinical_code")),
            "insurance_code": _text(map_exact.get((item.item_code, sets["insurance"])) or (item.extra or {}).get("insurance_raw_code")),
            "status": item.status or "active",
            "infectious_disease_name": _text((item.extra or {}).get("infectious_disease_name")),
            "infectious_disease_code": _text((item.extra or {}).get("infectious_disease_code")),
        })
        current_items.append(current)
    return _compute_plan_hash(current_items) == plan.content_hash


def get_plan_summary(db: Session, plan_id: int) -> dict[str, Any]:
    """计划摘要（200 D06：全部动作业务预览 + 授权/执行双轴 + run/outbox）。"""
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise PlanSelectionError("plan_not_found", "计划不存在")
    actions = db.scalars(
        select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan_id)
        .order_by(DictMedicalPushAction.target_system, DictMedicalPushAction.item_code)
    ).all()
    by_system: dict[str, dict[str, int]] = {}
    for a in actions:
        sys_stats = by_system.setdefault(
            a.target_system,
            {"planned": 0, "succeeded": 0, "failed": 0, "conflict": 0, "no_op": 0, "unknown": 0},
        )
        status = a.status if a.status in sys_stats else "unknown"
        sys_stats[status] += 1
    runs = db.scalars(
        select(DictMedicalPushRun).where(DictMedicalPushRun.plan_id == plan_id)
        .order_by(DictMedicalPushRun.id.desc())
    ).all()
    latest_run_by_target: dict[str, dict[str, Any]] = {}
    for run in runs:
        if run.target_system not in latest_run_by_target:
            latest_run_by_target[run.target_system] = {
                "run_id": run.id,
                "status": run.status,
                "total_actions": run.total_actions,
                "succeeded_count": run.succeeded_count,
                "failed_count": run.failed_count,
                "skipped_count": run.skipped_count,
                "error_masked": run.error_masked,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }
    outbox_by_target: dict[str, dict[str, Any]] = {}
    try:
        from ..models.dict_sync_outbox import DictSyncOutboxEvent
        from .dict_sync_worker import business_key_for_plan
        for target in plan.target_systems or []:
            event = db.scalar(
                select(DictSyncOutboxEvent).where(
                    DictSyncOutboxEvent.business_key == business_key_for_plan(plan.id, target)
                )
            )
            if event:
                outbox_by_target[target] = {
                    "status": event.status,
                    "attempt": event.attempt,
                    "last_error_masked": event.last_error_masked,
                }
    except Exception:
        outbox_by_target = {}
    now = datetime.now(timezone.utc)
    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        # 授权状态轴（draft/approved/...）与执行状态轴（queued/running/
        # succeeded/partial/failed/blocked/unknown_commit/reconcile_required）分离。
        "status": plan.status,
        "execution_status": plan.execution_status,
        "category_code": plan.category_code,
        "target_systems": plan.target_systems,
        "item_count": plan.item_count,
        "content_hash": plan.content_hash,
        "snapshot_version": SNAPSHOT_VERSION if all(
            (a.payload or {}).get("snapshot_version") == SNAPSHOT_VERSION for a in actions
        ) and actions else None,
        "is_expired": _as_utc(plan.expires_at) < now if plan.expires_at else False,
        "created_by": plan.created_by,
        "approved_by": plan.approved_by,
        "actions_by_system": by_system,
        "latest_runs": latest_run_by_target,
        "outbox": outbox_by_target,
        # D06：全部动作的业务预览（不只传染病专项）。
        "actions": [
            {
                "item_code": a.item_code,
                "item_name_cn": a.item_name_cn,
                "action_type": a.action_type,
                "target_system": a.target_system,
                "status": a.status,
                "run_id": a.run_id,
                "infectious_disease_name": (a.payload or {}).get("infectious_disease_name"),
                "national_clinical_code": (a.payload or {}).get("national_clinical_code"),
                "insurance_code": (a.payload or {}).get("insurance_code"),
            }
            for a in actions
        ],
    }
