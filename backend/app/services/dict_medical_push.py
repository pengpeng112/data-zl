"""诊断映射推送计划服务（101号 §4.3-4.5）。

服务端生成不可篡改计划，禁止客户端传入 SQL。
计划包含 content_hash，源数据变化则过期。
执行只接受 plan_id + 目标系统 + 确认。
"""
from __future__ import annotations

import hashlib
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
VALID_ACTION_TYPES = ("insert", "stop")
TARGET_ALIASES = {"HIS": "HIS_SOURCE", "JHEMR": "JHEMR_VASTBASE"}


def normalize_target_system(target: str) -> str:
    normalized = TARGET_ALIASES.get((target or "").strip().upper(), (target or "").strip().upper())
    if normalized not in VALID_TARGET_SYSTEMS:
        raise ValueError(f"无效目标系统: {target}")
    return normalized


def _local_code_set(category_code: str) -> str:
    return "operation_local_clinical" if category_code == CATEGORY_OPERATION else "diagnosis_local_clinical"


def _compute_plan_hash(items: list[dict[str, Any]]) -> str:
    parts = []
    for item in sorted(items, key=lambda x: x.get("item_code", "")):
        parts.append("|".join([
            item.get("item_code", ""),
            item.get("item_name_cn", ""),
            item.get("national_clinical_code", ""),
            item.get("insurance_code", ""),
            item.get("status", "active"),
        ]))
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:32]


def create_push_plan(
    db: Session,
    *,
    category_code: str,
    target_systems: list[str],
    item_codes: Optional[list[str]] = None,
    import_run_id: Optional[int] = None,
    created_by: str,
    action_type: str = "insert",
) -> DictMedicalPushPlan:
    """从平台正式字典生成推送计划。"""
    if category_code not in VALID_CATEGORIES:
        raise ValueError(f"仅支持 {', '.join(VALID_CATEGORIES)}，收到 {category_code}")
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError(f"无效动作类型: {action_type}")
    target_systems = list(dict.fromkeys(normalize_target_system(ts) for ts in target_systems))

    stmt = select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.category_code == category_code,
        DictMedicalCodeItem.code_set_code == _local_code_set(category_code),
        DictMedicalCodeItem.status == ("inactive" if action_type == "stop" else "active"),
    )
    if item_codes:
        stmt = stmt.where(DictMedicalCodeItem.item_code.in_(item_codes))
    items = list(db.scalars(stmt).all())
    if not items:
        raise ValueError("无符合条件的编码项")

    item_dicts = []
    for item in items:
        mappings = db.scalars(
            select(DictMedicalCodeMapping).where(
                DictMedicalCodeMapping.from_item_code == item.item_code,
                DictMedicalCodeMapping.category_code == category_code,
            )
        ).all()
        nc_code = ""
        ins_code = ""
        for m in mappings:
            if "clinical" in m.to_code_set:
                nc_code = m.to_item_code
            elif "insurance" in m.to_code_set:
                ins_code = m.to_item_code
        item_dicts.append({
            "item_code": item.item_code,
            "item_name_cn": item.item_name_cn,
            "national_clinical_code": nc_code,
            "insurance_code": ins_code,
            "status": item.status,
        })

    content_hash = _compute_plan_hash(item_dicts)
    plan_code = f"push-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    plan = DictMedicalPushPlan(
        plan_code=plan_code,
        category_code=category_code,
        target_systems=target_systems,
        status="draft",
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
                diff_type="stopped" if action_type == "stop" else "new",
            )
            db.add(action)

    db.commit()
    return plan


def approve_plan(db: Session, plan_id: int, approved_by: str, note: Optional[str] = None) -> DictMedicalPushPlan:
    """审批计划。审批人不能是创建人。"""
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise ValueError("计划不存在")
    if plan.status != "draft":
        raise ValueError(f"计划状态 {plan.status} 不允许审批")
    if plan.created_by == approved_by:
        raise ValueError("创建人不能自审")
    now = datetime.now(timezone.utc)
    if plan.expires_at and plan.expires_at < now:
        raise ValueError("计划已过期")
    plan.status = "approved"
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
    """Verify stored actions and current platform rows against the approved hash."""
    actions = db.scalars(
        select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan.id)
    ).all()
    item_dicts = []
    seen = set()
    for a in actions:
        key = a.item_code
        if key in seen:
            continue
        seen.add(key)
        payload = a.payload or {}
        item_dicts.append({
            "item_code": payload.get("item_code", a.item_code),
            "item_name_cn": payload.get("item_name_cn", a.item_name_cn or ""),
            "national_clinical_code": payload.get("national_clinical_code", ""),
            "insurance_code": payload.get("insurance_code", ""),
            "status": payload.get("status", "active"),
        })
    current_hash = _compute_plan_hash(item_dicts)
    if current_hash != plan.content_hash:
        return False
    current_items: list[dict[str, Any]] = []
    for snapshot in item_dicts:
        item = db.scalar(select(DictMedicalCodeItem).where(
            DictMedicalCodeItem.category_code == plan.category_code,
            DictMedicalCodeItem.code_set_code == _local_code_set(plan.category_code),
            DictMedicalCodeItem.item_code == snapshot["item_code"],
        ))
        if item is None:
            return False
        mappings = db.scalars(select(DictMedicalCodeMapping).where(
            DictMedicalCodeMapping.category_code == plan.category_code,
            DictMedicalCodeMapping.from_item_code == item.item_code,
        )).all()
        nc_code = next((m.to_item_code for m in mappings if "clinical" in m.to_code_set), "")
        ins_code = next((m.to_item_code for m in mappings if "insurance" in m.to_code_set), "")
        current_items.append({
            "item_code": item.item_code,
            "item_name_cn": item.item_name_cn,
            "national_clinical_code": nc_code,
            "insurance_code": ins_code,
            "status": item.status or "active",
        })
    return _compute_plan_hash(current_items) == plan.content_hash


def get_plan_summary(db: Session, plan_id: int) -> dict[str, Any]:
    """获取计划摘要（含分系统动作统计）。"""
    plan = db.get(DictMedicalPushPlan, plan_id)
    if not plan:
        raise ValueError("计划不存在")
    actions = db.scalars(
        select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan_id)
    ).all()
    by_system: dict[str, dict[str, int]] = {}
    for a in actions:
        sys_stats = by_system.setdefault(a.target_system, {"planned": 0, "succeeded": 0, "failed": 0, "conflict": 0})
        if a.status == "planned":
            sys_stats["planned"] += 1
        elif a.status == "succeeded":
            sys_stats["succeeded"] += 1
        elif a.status == "failed":
            sys_stats["failed"] += 1
        elif a.status == "conflict":
            sys_stats["conflict"] += 1
    now = datetime.now(timezone.utc)
    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "status": plan.status,
        "category_code": plan.category_code,
        "target_systems": plan.target_systems,
        "item_count": plan.item_count,
        "content_hash": plan.content_hash,
        "is_expired": plan.expires_at < now if plan.expires_at else False,
        "created_by": plan.created_by,
        "approved_by": plan.approved_by,
        "actions_by_system": by_system,
    }
