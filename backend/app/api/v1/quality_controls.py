"""174 S5: 质控清单 API（/api/v1/quality-controls）。

清单是稳定编号 + 版本化口径；实质口径变化（threshold/metric/comparator/object_key）
在 PATCH 中递增 version；激活要求存在 active 检测器或手工清单。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...models.governance_base import GovernAuditLog
from ...models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityObservation,
)
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
    lock_version: int
    created_by: str | None
    updated_by: str | None
    created_at: datetime | None
    updated_at: datetime | None
    detectors: list[DetectorOut] = []


class DetectorIn(BaseModel):
    detector_kind: str = Field(..., pattern="^(probe_template|quality_rule|manual|external)$")
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
    blocked_reason: str | None = None
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
) -> None:
    for det_in in detectors:
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
        else:
            existing.status = det_in.status
            existing.blocked_reason = det_in.blocked_reason
            existing.scope_mapping = det_in.scope_mapping
            existing.result_mapping = det_in.result_mapping
            existing.updated_by = actor
            existing.updated_at = datetime.now(timezone.utc)
            existing.last_bound_at = datetime.now(timezone.utc)


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
        from ..models.quality_governance import QualityIssue

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
    for key, value in payload.items():
        setattr(control, key, value)
    if bumped:
        control.version = (control.version or 1) + 1
    control.lock_version += 1
    control.updated_by = user
    control.updated_at = datetime.now(timezone.utc)
    if req.detectors is not None:
        _sync_detectors(db, control, req.detectors, user)
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_control",
            entity_ref=control.control_code,
            action="patch",
            before_data={"version": before_version},
            after_data={"version": control.version, "fields": sorted(payload)},
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


@router.post("/{control_id}/run")
def run_control(
    control_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.run")),
):
    """触发受控检测器。

    探查模板的实际执行走既有夜间执行器（scripts/run_probe.py，源侧经 8.83
    受控连接器），本端点只做：检测器可用性校验 + 执行提示 + 审计，
    不伪造执行结果。
    """
    control = db.get(QualityControl, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="control not found")
    if control.lifecycle_status != "active":
        raise HTTPException(status_code=409, detail=f"清单未激活（{control.lifecycle_status}）")
    detectors = db.scalars(
        select(QualityControlDetector).where(
            QualityControlDetector.control_id == control_id,
            QualityControlDetector.status == "active",
        )
    ).all()
    runnable = [d for d in detectors if d.detector_kind == "probe_template"]
    blocked = [d for d in detectors if d.status == "blocked"]
    db.add(
        GovernAuditLog(
            module="quality_governance",
            entity_type="quality_control",
            entity_ref=control.control_code,
            action="run",
            after_data={"runnable": [d.detector_ref for d in runnable],
                        "blocked": [d.detector_ref for d in blocked]},
            operator=user,
        )
    )
    db.commit()
    return {
        "status": "accepted",
        "control_code": control.control_code,
        "runnable_detectors": [d.detector_ref for d in runnable],
        "blocked_detectors": [d.detector_ref for d in blocked],
        "executor_hint": (
            "python scripts/run_probe.py --only <code> --write-db <url> --out <dir>"
            if runnable
            else None
        ),
        "note": "探查模板由夜间执行器执行；本端点不伪造结果",
    }
