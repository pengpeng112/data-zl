from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.governance_ops import ChangeRule, GovernEvent, SchedulerJob
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/govern", tags=["govern-ops"])


# ── 调度任务 ──

class JobCreate(BaseModel):
    job_type: str
    source_code: str | None = None
    trigger_mode: str | None = "manual"
    schedule_cron: str | None = None


@router.post("/scheduler/jobs", summary="创建调度任务记录")
def create_scheduler_job(req: JobCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    job = SchedulerJob(
        job_type=req.job_type,
        source_code=req.source_code,
        trigger_mode=req.trigger_mode or "manual",
        schedule_cron=req.schedule_cron,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return ApiResponse(data={"id": job.id, "job_type": job.job_type, "status": job.status})


@router.get("/scheduler/jobs", summary="调度任务列表")
def list_scheduler_jobs(
    job_type: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(SchedulerJob)
    if job_type:
        stmt = stmt.where(SchedulerJob.job_type == job_type)
    if status:
        stmt = stmt.where(SchedulerJob.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(SchedulerJob.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "job_type": r.job_type, "source_code": r.source_code,
            "trigger_mode": r.trigger_mode, "status": r.status,
            "total_processed": r.total_processed, "total_changes": r.total_changes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


# ── 事件/告警 ──

class EventCreate(BaseModel):
    event_type: str
    module: str
    entity_type: str | None = None
    entity_ref: str | None = None
    severity: str | None = "info"
    title: str | None = None
    detail: dict | None = None
    assigned_to: str | None = None


@router.get("/events", summary="事件/告警列表")
def list_events(
    module: str | None = Query(None),
    event_type: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernEvent)
    if module:
        stmt = stmt.where(GovernEvent.module == module)
    if event_type:
        stmt = stmt.where(GovernEvent.event_type == event_type)
    if status:
        stmt = stmt.where(GovernEvent.status == status)
    if severity:
        stmt = stmt.where(GovernEvent.severity == severity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernEvent.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "event_type": r.event_type, "module": r.module,
            "entity_type": r.entity_type, "entity_ref": r.entity_ref,
            "severity": r.severity, "title": r.title, "status": r.status,
            "assigned_to": r.assigned_to,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.post("/events", summary="创建事件")
def create_event(req: EventCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    evt = GovernEvent(
        event_type=req.event_type, module=req.module,
        entity_type=req.entity_type, entity_ref=req.entity_ref,
        severity=req.severity or "info", title=req.title,
        detail=req.detail, assigned_to=req.assigned_to,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return ApiResponse(data={"id": evt.id, "event_type": evt.event_type})


@router.patch("/events/{event_id}", summary="更新事件状态")
def update_event(event_id: int, status: str = Query(...), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    evt = db.get(GovernEvent, event_id)
    if not evt:
        raise HTTPException(status_code=404)
    evt.status = status
    if status == "acknowledged":
        evt.acknowledged_at = datetime.now(timezone.utc)
    elif status == "resolved":
        evt.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": evt.id, "status": evt.status})


# ── 变更规则 ──

class ChangeRuleUpsert(BaseModel):
    rule_code: str
    rule_name_cn: str
    system_code: str | None = None
    source_code: str | None = None
    db_type: str | None = None
    change_type: str = Field(..., description="table_added/table_removed/column_added/column_removed/column_type_changed/...")
    severity_override: str | None = None
    ignore_enabled: bool = False
    description: str | None = None
    enabled: bool = True


@router.get("/change-rules", summary="变更规则列表")
def list_change_rules(
    change_type: str | None = Query(None),
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(ChangeRule)
    if change_type:
        stmt = stmt.where(ChangeRule.change_type == change_type)
    if system_code:
        stmt = stmt.where(ChangeRule.system_code == system_code)
    rows = db.scalars(stmt.order_by(ChangeRule.change_type, ChangeRule.rule_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "rule_code": r.rule_code, "rule_name_cn": r.rule_name_cn,
            "system_code": r.system_code, "change_type": r.change_type,
            "severity_override": r.severity_override,
            "ignore_enabled": r.ignore_enabled, "enabled": r.enabled,
        }
        for r in rows
    ])


@router.put("/change-rules", summary="新增/更新变更规则")
def upsert_change_rule(req: ChangeRuleUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(ChangeRule).where(ChangeRule.rule_code == req.rule_code))
    if existing:
        existing.rule_name_cn = req.rule_name_cn
        existing.system_code = req.system_code
        existing.source_code = req.source_code
        existing.db_type = req.db_type
        existing.change_type = req.change_type
        existing.severity_override = req.severity_override
        existing.ignore_enabled = req.ignore_enabled
        existing.description = req.description
        existing.enabled = req.enabled
        existing.updated_at = datetime.now(timezone.utc)
        r = existing
    else:
        r = ChangeRule(
            rule_code=req.rule_code, rule_name_cn=req.rule_name_cn,
            system_code=req.system_code, source_code=req.source_code,
            db_type=req.db_type, change_type=req.change_type,
            severity_override=req.severity_override,
            ignore_enabled=req.ignore_enabled,
            description=req.description, enabled=req.enabled,
        )
        db.add(r)
    db.commit()
    db.refresh(r)
    return ApiResponse(data={"id": r.id, "rule_code": r.rule_code})
