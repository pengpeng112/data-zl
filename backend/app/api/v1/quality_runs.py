"""207 A2: 质量运行单 API（/api/v1/quality-runs）。

运行单可见范围与源可执行范围分别判定：查看需 quality.run.read；
取消/重试需 quality.run.manage 或授权发起者。错误信息一律脱敏。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import _effective_role_codes, require_permission
from ...models.governance_base import AssetRolePermission, GovernAuditLog
from ...models.quality_governance import QualityObservation, QualityRun
from ...services import quality_execution_service as qes

router = APIRouter(prefix="/api/v1/quality-runs", tags=["quality-runs"])


def _serialize_run(run: QualityRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_code": run.run_code,
        "control_id": run.control_id,
        "revision_id": run.revision_id,
        "parent_run_id": run.parent_run_id,
        "issue_id": run.issue_id,
        "purpose": run.purpose,
        "trigger_kind": run.trigger_kind,
        "requested_by": run.requested_by,
        "status": run.status,
        "detector_id": run.detector_id,
        "detector_kind": run.detector_kind,
        "detector_ref": run.detector_ref,
        "scope_key": run.scope_key,
        "system_code": run.system_code,
        "source_code": run.source_code,
        "object_key": run.object_key,
        "window_start": run.window_start.isoformat() if run.window_start else None,
        "window_end": run.window_end.isoformat() if run.window_end else None,
        "scheduled_for": run.scheduled_for.isoformat() if run.scheduled_for else None,
        "next_window_at": run.next_window_at.isoformat() if run.next_window_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "heartbeat_at": run.heartbeat_at.isoformat() if run.heartbeat_at else None,
        "attempt": run.attempt,
        "max_attempts": run.max_attempts,
        "result_summary": run.result_summary,
        "error_code": run.error_code,
        "error_message_sanitized": run.error_message_sanitized,
        "cancel_requested": (run.cancel_requested or "false") == "true",
        "cancelled_reason": run.cancelled_reason,
        "budget": run.budget_json,
        "lock_version": run.lock_version,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def _has_run_manage(db: Session, user: str) -> bool:
    roles = _effective_role_codes(db, user)
    if "platform_admin" in roles:
        return True
    if not roles:
        return False
    rows = db.scalars(
        select(AssetRolePermission).where(AssetRolePermission.role_code.in_(roles))
    ).all()
    granted = {row.resource for row in rows if row.action in (None, "", "access", "*")}
    return "quality.run.manage" in granted


@router.get("")
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    control_id: int | None = None,
    issue_id: int | None = None,
    status: str | None = None,
    purpose: str | None = None,
    parent_only: bool = True,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("quality.run.read")),
):
    q = select(QualityRun)
    if parent_only:
        q = q.where(QualityRun.parent_run_id.is_(None))
    if control_id:
        q = q.where(QualityRun.control_id == control_id)
    if issue_id:
        q = q.where(QualityRun.issue_id == issue_id)
    if status:
        q = q.where(QualityRun.status == status)
    if purpose:
        q = q.where(QualityRun.purpose == purpose)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(QualityRun.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_serialize_run(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/{run_id}")
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("quality.run.read")),
):
    run = db.get(QualityRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    out = _serialize_run(run)
    children = db.scalars(
        select(QualityRun).where(QualityRun.parent_run_id == run.id).order_by(QualityRun.id)
    ).all()
    out["children"] = [_serialize_run(c) for c in children]
    obs_refs = db.scalars(
        select(QualityObservation).where(
            QualityObservation.source_record_ref == f"asset_quality_runs:{run.id}"
        )
    ).all() if run.detector_id is not None else []
    child_obs: list[QualityObservation] = list(obs_refs)
    for c in children:
        child_obs.extend(
            db.scalars(
                select(QualityObservation).where(
                    QualityObservation.source_record_ref == f"asset_quality_runs:{c.id}"
                )
            ).all()
        )
    out["observations"] = [
        {
            "id": o.id, "result_status": o.result_status, "metric_value": float(o.metric_value)
            if o.metric_value is not None else None,
            "numerator": float(o.numerator) if o.numerator is not None else None,
            "denominator": float(o.denominator) if o.denominator is not None else None,
            "observed_at": o.observed_at.isoformat() if o.observed_at else None,
            "run_key": o.run_key, "scope_key": o.scope_key,
            "evidence_ref": o.evidence_ref,
        }
        for o in sorted(child_obs, key=lambda x: x.id)
    ]
    return out


class CancelRequest(BaseModel):
    expected_lock_version: int
    reason: str


@router.post("/{run_id}/cancel")
def cancel_run(
    run_id: int,
    req: CancelRequest,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.run.read")),
):
    """取消：queued/waiting_window 立即取消；running 标记协作取消（worker 检查点生效）。"""
    run = db.get(QualityRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if not _has_run_manage(db, user) and run.requested_by != user:
        raise HTTPException(status_code=403, detail="仅运行管理员或发起者可取消")
    try:
        qes.cancel_run(db, run, expected_lock_version=req.expected_lock_version,
                       reason=req.reason, actor=user)
        db.add(GovernAuditLog(
            module="quality_governance", entity_type="quality_run",
            entity_ref=run.run_code, action="cancel",
            after_data={"status": run.status, "reason": req.reason}, operator=user,
        ))
        db.commit()
    except qes.RunStateError as exc:
        db.rollback()
        code = 409 if "lock_version" in str(exc) else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    db.refresh(run)
    return _serialize_run(run)


class RetryRequest(BaseModel):
    reason: str | None = None


@router.post("/{run_id}/retry", status_code=202)
def retry_run(
    run_id: int,
    req: RetryRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_permission("quality.run.manage")),
):
    """重试：创建关联重试运行（重新过窗口/预算/预检核验）。"""
    req = req or RetryRequest()
    run = db.get(QualityRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        new_run = qes.retry_run(db, run, actor=user, reason=req.reason)
        db.add(GovernAuditLog(
            module="quality_governance", entity_type="quality_run",
            entity_ref=run.run_code, action="retry",
            after_data={"new_run_id": new_run.id if new_run else None,
                        "new_run_code": new_run.run_code if new_run else None},
            operator=user, reason=req.reason,
        ))
        db.commit()
    except qes.RunStateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except qes.RunValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if new_run is None:
        return {"status": "manual_required", "run_id": None}
    db.refresh(new_run)
    return _serialize_run(new_run)
