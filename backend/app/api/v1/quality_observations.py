"""174 S5: 质量观测 API（/api/v1/quality-observations）。

观测不可变：只提供 list/get/ingest，无业务 UPDATE/DELETE；
ingest 仅内部服务/受控来源（quality.control.run 权限门禁）。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import _effective_role_codes, require_permission
from ...models.governance_base import AssetRolePermission, GovernAuditLog
from ...models.quality_governance import QualityIssue, QualityObservation
from ...services import quality_governance_service as qgs

router = APIRouter(prefix="/api/v1/quality-observations", tags=["quality-observations"])


class IngestRequest(BaseModel):
    control_id: int
    run_key: str = Field(..., min_length=1, max_length=128)
    scope_key: str = Field(..., min_length=1, max_length=256)
    result_status: str
    control_version: int | None = None
    detector_id: int | None = None
    window_start: date | None = None
    window_end: date | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    threshold_snapshot: dict | None = None
    control_definition_snapshot: dict | None = None
    numerator: float | None = None
    denominator: float | None = None
    source_kind: str = "external"
    source_record_ref: str | None = None
    evidence_digest: str | None = None
    evidence_ref: str | None = None
    historical_precision: str = "exact"
    error_code: str | None = None
    error_message_sanitized: str | None = None
    correlation_id: str | None = None


def _serialize(o: QualityObservation) -> dict:
    return {
        "id": o.id,
        "control_id": o.control_id,
        "detector_id": o.detector_id,
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
        "threshold_snapshot": o.threshold_snapshot,
        "control_definition_snapshot": o.control_definition_snapshot,
        "numerator": float(o.numerator) if o.numerator is not None else None,
        "denominator": float(o.denominator) if o.denominator is not None else None,
        "source_kind": o.source_kind,
        "source_record_ref": o.source_record_ref,
        "evidence_digest": o.evidence_digest,
        "evidence_ref": o.evidence_ref,
        "historical_precision": o.historical_precision,
        "error_code": o.error_code,
        "error_message_sanitized": o.error_message_sanitized,
        "created_by": o.created_by,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _has_issue_read_all(db: Session, user: str) -> bool:
    roles = _effective_role_codes(db, user)
    if "platform_admin" in roles:
        return True
    if not roles:
        return False
    rows = db.scalars(
        select(AssetRolePermission).where(AssetRolePermission.role_code.in_(roles))
    ).all()
    granted = {row.resource for row in rows if row.action in (None, "", "access", "*")}
    return "quality.issue.read_all" in granted


def _ensure_observation_read_access(db: Session, o: QualityObservation, user: str) -> None:
    if _has_issue_read_all(db, user):
        return
    if o.issue_id is None:
        raise HTTPException(status_code=403, detail="无权查看无关联问题的观测（需 quality.issue.read_all）")
    issue = db.get(QualityIssue, o.issue_id)
    if issue is None:
        raise HTTPException(status_code=403, detail="无权查看该观测（关联问题不存在）")
    scope = qgs.resolve_user_scope(db, user)
    if not qgs.user_can_touch_issue(issue, scope):
        raise HTTPException(status_code=403, detail="无权查看该观测（超出本人/本科室范围）")


@router.get("")
def list_observations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    control_id: int | None = None,
    issue_id: int | None = None,
    result_status: str | None = None,
    source_kind: str | None = None,
    window_from: date | None = None,
    window_to: date | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.observation.read")),
):
    q = select(QualityObservation)
    if control_id:
        q = q.where(QualityObservation.control_id == control_id)
    if issue_id:
        q = q.where(QualityObservation.issue_id == issue_id)
    if result_status:
        q = q.where(QualityObservation.result_status == result_status)
    if source_kind:
        q = q.where(QualityObservation.source_kind == source_kind)
    if window_from:
        q = q.where(QualityObservation.window_start >= window_from)
    if window_to:
        q = q.where(QualityObservation.window_start <= window_to)
    if not _has_issue_read_all(db, user):
        scope = qgs.resolve_user_scope(db, user)
        q = q.join(QualityIssue, QualityIssue.id == QualityObservation.issue_id)
        q = qgs.apply_issue_scope_filter(q, scope, mode="department")
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityObservation.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_serialize(o) for o in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{observation_id}")
def get_observation(
    observation_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.observation.read")),
):
    o = db.get(QualityObservation, observation_id)
    if o is None:
        raise HTTPException(status_code=404, detail="observation not found")
    _ensure_observation_read_access(db, o, user)
    return _serialize(o)


@router.post("/ingest")
def ingest_observation(
    req: IngestRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.control.run")),
):
    """受控来源观测摄取（幂等；重复 run_key 返回 duplicate）。"""
    try:
        result = qgs.apply_observation(
            db,
            control_id=req.control_id,
            detector_id=req.detector_id,
            control_version=req.control_version,
            run_key=req.run_key,
            scope_key=req.scope_key,
            result_status=req.result_status,
            window_start=req.window_start,
            window_end=req.window_end,
            metric_value=req.metric_value,
            metric_unit=req.metric_unit,
            threshold_snapshot=req.threshold_snapshot,
            control_definition_snapshot=req.control_definition_snapshot,
            numerator=req.numerator,
            denominator=req.denominator,
            source_kind=req.source_kind,
            source_record_ref=req.source_record_ref,
            evidence_digest=req.evidence_digest,
            evidence_ref=req.evidence_ref,
            historical_precision=req.historical_precision,
            error_code=req.error_code,
            error_message_sanitized=req.error_message_sanitized,
            actor=user,
            correlation_id=req.correlation_id,
        )
        if result["outcome"] != "duplicate":
            db.add(
                GovernAuditLog(
                    module="quality_governance",
                    entity_type="quality_observation",
                    entity_ref=str(result["observation_id"]),
                    action="ingest",
                    after_data={"run_key": req.run_key, "result_status": req.result_status,
                                "outcome": result["outcome"]},
                    operator=user,
                )
            )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result
