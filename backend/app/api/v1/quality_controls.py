"""174 S5: 质控清单 API（/api/v1/quality-controls）。

清单是稳定编号 + 版本化口径；实质口径变化（threshold/metric/comparator/object_key）
在 PATCH 中递增 version；激活要求存在 active 检测器或手工清单。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import require_permission
from ...models.governance_base import GovernAuditLog
from ...models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityIssue,
    QualityObservation,
    QualityRun,
)
from ...services import quality_execution_service as qes
from ...services import quality_governance_service as qgs

router = APIRouter(prefix="/api/v1/quality-controls", tags=["quality-controls"])

LIFECYCLE = ("draft", "active", "blocked", "deprecated")


class DetectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    control_id: int
    detector_kind: str
    detector_ref: str
    detector_version: str
    status: str
    blocked_reason: str | None
    scope_mapping: dict | None
    result_mapping: dict | None
    last_bound_at: datetime | None


class ControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    control_code: str
    version: int
    title: str
    description: str | None
    lifecycle_status: str
    blocked_reason: str | None
    dimension: str | None
    category: str | None
    primary_system_code: str | None
    related_system_codes: list[str] | None
    object_key: str | None
    object_name_snapshot: str | None
    metric_name: str | None
    metric_unit: str | None
    comparator: str | None
    threshold_value: float | None
    no_data_policy: str
    default_severity: str | None
    default_priority: str | None
    default_dept_code: str | None
    default_person_code: str | None
    schedule_expr: str | None
    timezone: str | None
    verification_policy: str
    required_pass_count: int | None
    # 207 增量配置（F09：完整调度与复测配置可编辑）
    source_code: str | None = None
    schedule_enabled: bool = False
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    freshness_hours: int | None = None
    recheck_policy: str | None = None
    sla_hours: int | None = None
    execution_plan: dict | None = None
    lock_version: int
    created_by: str | None
    updated_by: str | None
    created_at: datetime | None
    updated_at: datetime | None
    detectors: list[DetectorOut] = []


class DetectorIn(BaseModel):
    detector_kind: str = Field(..., pattern="^(probe_template|quality_rule|value_domain|manual|external)$")
    detector_ref: str = Field(..., min_length=1, max_length=64)
    detector_version: str = "1"
    status: str = Field(default="draft", pattern="^(draft|active|blocked|disabled)$")
    blocked_reason: str | None = None
    scope_mapping: dict | None = None
    result_mapping: dict | None = None


class ControlCreateRequest(BaseModel):
    control_code: str = Field(..., min_length=3, max_length=64)
    title: str = Field(..., min_length=2, max_length=256)
    description: str | None = None
    lifecycle_status: str = "draft"
    blocked_reason: str | None = None
    dimension: str | None = None
    category: str | None = None
    primary_system_code: str | None = None
    related_system_codes: list[str] | None = None
    object_key: str | None = None
    object_name_snapshot: str | None = None
    metric_name: str | None = None
    metric_unit: str | None = None
    comparator: str | None = None
    threshold_value: float | None = None
    no_data_policy: str = "blocked"
    default_severity: str = "medium"
    default_priority: str = "P3"
    default_dept_code: str | None = None
    default_person_code: str | None = None
    schedule_expr: str | None = None
    timezone: str | None = None
    verification_policy: str = "manual"
    required_pass_count: int = 1
    source_code: str | None = None
    schedule_enabled: bool = False
    freshness_hours: int | None = None
    recheck_policy: str = "auto"
    sla_hours: int | None = None
    execution_plan: dict | None = None
    detectors: list[DetectorIn] = []


class ControlPatchRequest(BaseModel):
    expected_lock_version: int
    title: str | None = None
    description: str | None = None
    dimension: str | None = None
    category: str | None = None
    primary_system_code: str | None = None
    related_system_codes: list[str] | None = None
    object_key: str | None = None
    object_name_snapshot: str | None = None
    metric_name: str | None = None
    metric_unit: str | None = None
    comparator: str | None = None
    threshold_value: float | None = None
    no_data_policy: str | None = None
    default_severity: str | None = None
    default_priority: str | None = None
    default_dept_code: str | None = None
    default_person_code: str | None = None
    schedule_expr: str | None = None
    timezone: str | None = None
    blocked_reason: str | None = None
    # 207 F09：完整策略/调度/复测配置
    verification_policy: str | None = None
    required_pass_count: int | None = None
    source_code: str | None = None
    schedule_enabled: bool | None = None
    freshness_hours: int | None = None
    recheck_policy: str | None = None
    sla_hours: int | None = None
    execution_plan: dict | None = None
    detectors: list[DetectorIn] | None = None
    reason: str | None = None


def _validate_control_fields(payload: dict[str, Any], *, partial: bool) -> None:
    if not partial or "lifecycle_status" in payload:
        status = payload.get("lifecycle_status", "draft")
        if status not in LIFECYCLE:
            raise HTTPException(status_code=422, detail=f"非法 lifecycle_status: {status}")
        if status == "blocked" and not payload.get("blocked_reason"):
            raise HTTPException(status_code=422, detail="blocked 必须填写 blocked_reason")
    if payload.get("dimension") is not None and payload["dimension"] not in qgs.DIMENSIONS:
        raise HTTPException(status_code=422, detail=f"非法 dimension: {payload['dimension']}")
    if payload.get("category") is not None and payload["category"] not in qgs.CATEGORIES:
        raise HTTPException(status_code=422, detail=f"非法 category: {payload['category']}")
    if payload.get("comparator") is not None and payload["comparator"] not in qgs.COMPARATORS:
        raise HTTPException(status_code=422, detail=f"非法 comparator: {payload['comparator']}")
    if payload.get("no_data_policy") is not None and payload["no_data_policy"] not in qgs.NO_DATA_POLICIES:
        raise HTTPException(status_code=422, detail=f"非法 no_data_policy: {payload['no_data_policy']}")
    if payload.get("default_severity") is not None and payload["default_severity"] not in qgs.SEVERITIES:
        raise HTTPException(status_code=422, detail=f"非法 default_severity: {payload['default_severity']}")
    if payload.get("default_priority") is not None and payload["default_priority"] not in qgs.PRIORITIES:
        raise HTTPException(status_code=422, detail=f"非法 default_priority: {payload['default_priority']}")
    if not partial or "verification_policy" in payload:
        vp = payload.get("verification_policy", "manual")
        if vp not in qes.VERIFICATION_POLICIES:
            raise HTTPException(status_code=422, detail=f"非法 verification_policy: {vp}")
    if payload.get("recheck_policy") is not None and payload["recheck_policy"] not in qes.RECHECK_POLICIES:
        raise HTTPException(status_code=422, detail=f"非法 recheck_policy: {payload['recheck_policy']}")
    comparator = payload.get("comparator")
    threshold = payload.get("threshold_value")
    if (comparator is None) != (threshold is None) and not partial:
        raise HTTPException(status_code=422, detail="comparator 与 threshold_value 必须成对出现")


def _serialize(db: Session, control: QualityControl) -> ControlOut:
    out = ControlOut.model_validate(control)
    detectors = db.scalars(
        select(QualityControlDetector).where(QualityControlDetector.control_id == control.id)
    ).all()
    out.detectors = [DetectorOut.model_validate(d) for d in detectors]
    return out


def _sync_detectors(
    db: Session, control: QualityControl, detectors: list[DetectorIn], actor: str
) -> bool:
    """全量替换语义（F09）：提交的检测器 upsert；未提交的既有 active 检测器置 disabled。

    返回检测器绑定是否发生变化（用于版本递增判断）。
    """
    changed = False
    keep_keys: set[tuple[str, str, str]] = set()
    for det_in in detectors:
        key = (det_in.detector_kind, det_in.detector_ref, det_in.detector_version)
        keep_keys.add(key)
        existing = db.scalar(
            select(QualityControlDetector).where(
                QualityControlDetector.control_id == control.id,
                QualityControlDetector.detector_kind == det_in.detector_kind,
                QualityControlDetector.detector_ref == det_in.detector_ref,
                QualityControlDetector.detector_version == det_in.detector_version,
            )
        )
        if existing is None:
            db.add(
                QualityControlDetector(
                    control_id=control.id,
                    detector_kind=det_in.detector_kind,
                    detector_ref=det_in.detector_ref,
                    detector_version=det_in.detector_version,
                    status=det_in.status,
                    blocked_reason=det_in.blocked_reason,
                    scope_mapping=det_in.scope_mapping,
                    result_mapping=det_in.result_mapping,
                    last_bound_at=datetime.now(timezone.utc),
                    created_by=actor,
                    updated_by=actor,
                )
            )
            changed = True
        else:
            if (
                existing.status != det_in.status
                or existing.scope_mapping != det_in.scope_mapping
                or existing.result_mapping != det_in.result_mapping
            ):
                changed = True
            existing.status = det_in.status
            existing.blocked_reason = det_in.blocked_reason
            existing.scope_mapping = det_in.scope_mapping
            existing.result_mapping = det_in.result_mapping
            existing.updated_by = actor
            existing.updated_at = datetime.now(timezone.utc)
            existing.last_bound_at = datetime.now(timezone.utc)
    for existing in db.scalars(
        select(QualityControlDetector).where(QualityControlDetector.control_id == control.id)
    ).all():
        key = (existing.detector_kind, existing.detector_ref, existing.detector_version)
        if key not in keep_keys and existing.status not in ("disabled",):
            existing.status = "disabled"
            existing.updated_by = actor
            existing.updated_at = datetime.now(timezone.utc)
            changed = True
    return changed


@router.get("")
def list_controls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    lifecycle_status: str | None = None,
    primary_system_code: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("quality.control.read")),
):
    q = select(QualityControl)
    if lifecycle_status:
        q = q.where(QualityControl.lifecycle_status == lifecycle_status)
    if primary_system_code:
        q = q.where(QualityControl.primary_system_code == primary_system_code)
    if category:
        q = q.where(QualityControl.category == category)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(QualityControl.title.ilike(like), QualityControl.control_code.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityControl.control_code).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_serialize(db, r).model_dump() for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/coverage")
def control_coverage(
    system_code: str | None = None,
    source_code: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.read")),
):
    """207 B3 覆盖口径（§5.4）：分母快照=适用检查实例；零问题不等于健康。

    静态路由注册在 /{control_id} 之前，避免路由误匹配。
    """
    _ = user
    now = datetime.now(timezone.utc)
    controls = db.scalars(select(QualityControl)).all()
    detectors = db.scalars(select(QualityControlDetector)).all()
    by_control: dict[int, list] = {}
    for d in detectors:
        by_control.setdefault(d.control_id, []).append(d)
    issues = db.scalars(select(QualityIssue)).all()
    active_by_control: dict[int, int] = {}
    resolved_by_control: dict[int, int] = {}
    recurrence_count = 0
    for i in issues:
        if i.control_id is None:
            continue
        if i.status == "resolved":
            resolved_by_control[i.control_id] = resolved_by_control.get(i.control_id, 0) + 1
        elif i.status not in qgs.ISSUE_TERMINAL_STATUSES:
            active_by_control[i.control_id] = active_by_control.get(i.control_id, 0) + 1
        if (i.recurrence_no or 0) > 0:
            recurrence_count += 1

    denom_total = 0
    effective_total = 0
    status_counts = {"pass": 0, "fail": 0, "no_data": 0, "error": 0, "blocked": 0, "skipped": 0}
    uncovered: list[dict] = []
    for control in controls:
        if control.lifecycle_status != "active":
            continue
        if system_code and control.primary_system_code != system_code:
            continue
        dets = [d for d in by_control.get(control.id, []) if d.status == "active"]
        for det in dets:
            if source_code:
                mapping = det.scope_mapping if isinstance(det.scope_mapping, dict) else {}
                det_source = mapping.get("source_code") or control.source_code
                if det_source != source_code:
                    continue
            denom_total += 1
            latest = db.scalar(
                select(QualityObservation)
                .where(
                    QualityObservation.control_id == control.id,
                    QualityObservation.detector_id == det.id,
                )
                .order_by(QualityObservation.id.desc())
            )
            fresh = True
            if latest is not None and control.freshness_hours:
                observed = latest.observed_at
                if observed is not None:
                    observed = observed.replace(tzinfo=timezone.utc) if observed.tzinfo is None else observed
                    fresh = (now - observed).total_seconds() <= control.freshness_hours * 3600
            if latest is None:
                uncovered.append({
                    "control_id": control.id, "control_code": control.control_code,
                    "detector": f"{det.detector_kind}:{det.detector_ref}",
                    "reason": "never_run", "system_code": control.primary_system_code,
                })
            elif not fresh:
                uncovered.append({
                    "control_id": control.id, "control_code": control.control_code,
                    "detector": f"{det.detector_kind}:{det.detector_ref}",
                    "reason": "stale",
                    "last_observed_at": latest.observed_at.isoformat() if latest.observed_at else None,
                    "system_code": control.primary_system_code,
                })
                status_counts[latest.result_status] = status_counts.get(latest.result_status, 0)
            else:
                effective_total += 1
                if latest.result_status in status_counts:
                    status_counts[latest.result_status] += 1
    pass_cnt, fail_cnt = status_counts["pass"], status_counts["fail"]
    data_pass_rate = round(pass_cnt / (pass_cnt + fail_cnt) * 100, 2) if (pass_cnt + fail_cnt) else None
    resolved_total = sum(resolved_by_control.values())
    active_total = sum(active_by_control.values())
    remediation_rate = (
        round(resolved_total / (resolved_total + active_total) * 100, 2)
        if (resolved_total + active_total) else None
    )
    recurrence_rate = (
        round(recurrence_count / (resolved_total + recurrence_count) * 100, 2)
        if (resolved_total + recurrence_count) else None
    )
    return {
        "statistics_time": now.isoformat(),
        "filters": {"system_code": system_code, "source_code": source_code},
        "applicable_instances": denom_total,
        "effective_instances": effective_total,
        "executable_coverage_pct": round(effective_total / denom_total * 100, 2) if denom_total else None,
        "latest_status_counts": status_counts,
        "data_pass_rate_pct": data_pass_rate,
        "issues": {
            "active": active_total,
            "resolved": resolved_total,
            "recurrence": recurrence_count,
            "remediation_pass_rate_pct": remediation_rate,
            "recurrence_rate_pct": recurrence_rate,
        },
        "uncovered": uncovered[:200],
        "uncovered_total": len(uncovered),
        "note": (
            "覆盖分母=active 清单×active 检测器（同源/对象分别计实例）；有效=freshness 内最新观测；"
            "数据通过率=有效实测 PASS/(PASS+FAIL)；accepted_risk/false_positive/duplicate/cancelled 不计整改成功"
        ),
    }


@router.get("/{control_id}")
def get_control(
    control_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("quality.control.read")),
):
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    return _serialize(db, control).model_dump()


@router.get("/{control_id}/observations")
def list_control_observations(
    control_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    result_status: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.observation.read")),
):
    from .quality_observations import _has_issue_read_all

    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    q = select(QualityObservation).where(QualityObservation.control_id == control_id)
    if result_status:
        q = q.where(QualityObservation.result_status == result_status)
    if not _has_issue_read_all(db, user):
        from ...models.quality_governance import QualityIssue  # F05：app.api.models 不存在，必须三级相对导入

        scope = qgs.resolve_user_scope(db, user)
        q = q.join(QualityIssue, QualityIssue.id == QualityObservation.issue_id)
        q = qgs.apply_issue_scope_filter(q, scope, mode="department")
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityObservation.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": o.id,
                "control_id": o.control_id,
                "control_version": o.control_version,
                "issue_id": o.issue_id,
                "run_key": o.run_key,
                "scope_key": o.scope_key,
                "window_start": o.window_start,
                "window_end": o.window_end,
                "observed_at": o.observed_at.isoformat() if o.observed_at else None,
                "result_status": o.result_status,
                "metric_value": float(o.metric_value) if o.metric_value is not None else None,
                "metric_unit": o.metric_unit,
                "source_kind": o.source_kind,
                "source_record_ref": o.source_record_ref,
                "historical_precision": o.historical_precision,
            }
            for o in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
def create_control(
    req: ControlCreateRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.manage")),
):
    payload = req.model_dump(exclude={"detectors"})
    payload["schedule_enabled"] = "true" if payload.get("schedule_enabled") else "false"
    _validate_control_fields(payload, partial=False)
    exists = db.scalar(
        select(QualityControl).where(QualityControl.control_code == req.control_code)
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"control_code 已存在: {req.control_code}")
    control = QualityControl(
        **payload,
        lock_version=0,
        created_by=user,
        updated_by=user,
    )
    db.add(control)
    db.flush()
    _sync_detectors(db, control, req.detectors, user)
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_control",
            entity_ref=control.control_code,
            action="create",
            after_data={"title": control.title, "lifecycle_status": control.lifecycle_status},
            operator=user,
            reason=req.description,
        )
    )
    db.commit()
    db.refresh(control)
    return _serialize(db, control).model_dump()


_VERSION_BUMP_FIELDS = (
    "metric_name",
    "metric_unit",
    "comparator",
    "threshold_value",
    "object_key",
    "no_data_policy",
    "category",
    # 207 F09：复测/验证口径变化必须新版本（旧运行读冻结快照）
    "verification_policy",
    "required_pass_count",
)


@router.patch("/{control_id}")
def patch_control(
    control_id: int,
    req: ControlPatchRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.manage")),
):
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    if control.lock_version != req.expected_lock_version:
        raise HTTPException(
            status_code=409,
            detail=f"lock_version 冲突：期望 {req.expected_lock_version}，实际 {control.lock_version}",
        )
    payload = req.model_dump(exclude={"expected_lock_version", "detectors", "reason"}, exclude_none=True)
    _validate_control_fields(payload, partial=True)
    before_version = control.version
    bumped = any(
        key in payload and getattr(control, key) != value
        for key, value in payload.items()
        if key in _VERSION_BUMP_FIELDS
    )
    # 布尔列在库内以 'true'/'false' 字符串存储
    if "schedule_enabled" in payload:
        payload["schedule_enabled"] = "true" if payload["schedule_enabled"] else "false"
    for key, value in payload.items():
        setattr(control, key, value)
    detectors_changed = False
    if req.detectors is not None:
        detectors_changed = _sync_detectors(db, control, req.detectors, user)
    if detectors_changed:
        # F09：检测器增删/启停/映射变化属于口径变化 → 版本递增
        bumped = True
    if bumped:
        control.version = (control.version or 1) + 1
        # 口径变化即生成新版本快照（不可变；旧运行仍读旧快照）
        qes.ensure_revision(db, control, actor=user)
    control.lock_version += 1
    control.updated_by = user
    control.updated_at = datetime.now(timezone.utc)
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_control",
            entity_ref=control.control_code,
            action="patch",
            before_data={"version": before_version},
            after_data={"version": control.version, "fields": sorted(payload),
                        "detectors_changed": detectors_changed},
            operator=user,
            reason=req.reason,
        )
    )
    db.commit()
    db.refresh(control)
    return _serialize(db, control).model_dump()


@router.post("/{control_id}/activate")
def activate_control(
    control_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.manage")),
):
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    if control.lifecycle_status == "deprecated":
        raise HTTPException(status_code=409, detail="已废弃清单不能重新激活")
    detectors = db.scalars(
        select(QualityControlDetector).where(QualityControlDetector.control_id == control_id)
    ).all()
    has_active = any(d.status == "active" for d in detectors)
    if not has_active and (control.category or "") != "MANUAL":
        raise HTTPException(
            status_code=422, detail="激活自动规则至少需要一个 active 检测器（手工清单除外）"
        )
    control.lifecycle_status = "active"
    control.blocked_reason = None
    control.lock_version += 1
    qes.ensure_revision(db, control, actor=user)
    control.updated_by = user
    control.updated_at = datetime.now(timezone.utc)
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_control",
            entity_ref=control.control_code,
            action="activate",
            operator=user,
        )
    )
    db.commit()
    db.refresh(control)
    return _serialize(db, control).model_dump()


@router.post("/{control_id}/deprecate")
def deprecate_control(
    control_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.manage")),
):
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    control.lifecycle_status = "deprecated"
    control.lock_version += 1
    control.updated_by = user
    control.updated_at = datetime.now(timezone.utc)
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_control",
            entity_ref=control.control_code,
            action="deprecate",
            operator=user,
        )
    )
    db.commit()
    db.refresh(control)
    return _serialize(db, control).model_dump()


@router.post("/{control_id}/preflight")
def preflight_control(
    control_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.run")),
):
    """207 §5.0 预检：静态/平台元数据可执行性核验，不访问源库。"""
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    report = qes.preflight_control(db, control)
    return {
        "control_id": control.id,
        "control_code": control.control_code,
        "control_version": control.version,
        **report.as_dict(),
    }


class RunRequest(BaseModel):
    expected_control_version: int | None = None
    idempotency_key: str | None = Field(None, max_length=128)
    window_start: date | None = None
    window_end: date | None = None


@router.post("/{control_id}/run", status_code=202)
def run_control(
    control_id: int,
    req: RunRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.run")),
):
    """F01 修复：真实持久运行单（202 + run_id + 状态/下一窗口/受阻原因）。

    只在任务持久化后返回；版本冲突 409。隔离/本地演示（inline 模式）在持久化
    后同步走与 worker 相同的领取/执行/归并链路；生产默认由 worker 领取。
    """
    req = req or RunRequest()
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    if control.lifecycle_status != "active":
        raise HTTPException(status_code=409, detail=f"清单未激活（{control.lifecycle_status}）")
    if req.expected_control_version is not None and req.expected_control_version != control.version:
        raise HTTPException(
            status_code=409,
            detail=f"control version 冲突：期望 {req.expected_control_version}，当前 {control.version}",
        )
    try:
        result = qes.create_run(
            db, control, purpose="check", trigger_kind="manual", requested_by=user,
            idempotency_key=req.idempotency_key, window_start=req.window_start,
            window_end=req.window_end, actor=user,
        )
        db.commit()
    except qes.RunValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except qes.RunStateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if result["manual_required"]:
        return {
            "status": "manual_required",
            "control_code": control.control_code,
            "run_id": None,
            "blocked_reasons": result["blocked_reasons"],
            "note": "手工/外部清单无自动检测器，复测走人工验证路径",
        }

    run = result["run"]
    db.refresh(run)
    inline_executed: list[dict] = []
    if settings.quality_execution_inline and result["status"] in ("queued",):
        inline_executed = qes.process_inline(db)

    children = db.scalars(
        select(QualityRun).where(QualityRun.parent_run_id == run.id)
    ).all()
    db.refresh(run)
    return {
        "status": run.status,
        "control_code": control.control_code,
        "run_id": run.id,
        "run_code": run.run_code,
        "purpose": run.purpose,
        "next_window_at": run.next_window_at.isoformat() if run.next_window_at else None,
        "blocked_reasons": result["blocked_reasons"],
        "duplicate": result["duplicate"],
        "children": [
            {"run_id": c.id, "run_code": c.run_code, "detector_kind": c.detector_kind,
             "detector_ref": c.detector_ref, "status": c.status}
            for c in children
        ],
        "inline_executed": inline_executed,
        "note": "任务已持久化；由 worker（或隔离演示 inline 模式）受控执行",
    }


