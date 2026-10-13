from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...core.security import require_permission
from ...models.governance_ops import ChangeRule, GovernEvent, SchedulerJob
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/govern", tags=["govern-ops"])


# ── 调度任务 ──

class JobCreate(BaseModel):
    job_type: str
    source_code: str | None = None
    trigger_mode: str | None = "manual"
    schedule_cron: str | None = None


ALLOWED_JOB_TYPES = {"metadata_scan", "quality_check"}
ALLOWED_TRIGGER_MODES = {"manual", "scheduled", "oneshot"}


@router.post("/scheduler/jobs", summary="创建调度任务记录")
def create_scheduler_job(req: JobCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    # QA ST-009：scheduled 模式收紧（白名单 job_type + 合法 cron + platform_admin）；
    # manual/oneshot 保持既有自由记录行为（不进 APScheduler，无注册风险）。
    trigger_mode = req.trigger_mode or "manual"
    if trigger_mode not in ALLOWED_TRIGGER_MODES:
        raise HTTPException(status_code=400, detail=f"trigger_mode 仅允许 {sorted(ALLOWED_TRIGGER_MODES)}")
    roles = set(getattr(request.state, "roles", []) or [])
    if trigger_mode == "scheduled":
        if req.job_type not in ALLOWED_JOB_TYPES:
            raise HTTPException(status_code=400, detail=f"scheduled 模式 job_type 仅允许 {sorted(ALLOWED_JOB_TYPES)}")
        if not req.schedule_cron:
            raise HTTPException(status_code=400, detail="scheduled 模式必须提供 schedule_cron")
        if "platform_admin" not in roles:
            raise HTTPException(status_code=403, detail="创建常驻调度任务需要 platform_admin")
        if len(req.schedule_cron.split()) != 5:
            raise HTTPException(status_code=400, detail="schedule_cron 需为五段式 cron 表达式")
        try:
            from croniter import croniter  # type: ignore
            croniter(req.schedule_cron)
        except ImportError:
            pass  # 未安装 croniter 时五段式基础校验已兜底
        except Exception:
            raise HTTPException(status_code=400, detail="schedule_cron 不是合法的 cron 表达式")
    job = SchedulerJob(
        job_type=req.job_type,
        source_code=req.source_code,
        trigger_mode=trigger_mode,
        schedule_cron=req.schedule_cron,
    )
    db.add(job)
    db.flush()
    db.add(GovernAuditLog(
        module="governance_ops",
        entity_type="scheduler_job",
        entity_ref=str(job.id),
        action="create",
        after_data={"job_type": job.job_type, "trigger_mode": trigger_mode,
                    "schedule_cron": job.schedule_cron, "source_code": job.source_code},
        operator=getattr(request.state, "user_identifier", None) or "system",
        reason="QA ST-009：调度任务创建补审计",
    ))
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

@router.get(
    "/scheduler/ops-board",
    summary="215 E6：worker/调度心跳只读看板（零写操作）",
    dependencies=[Depends(require_permission("govern.executor.manage"))],
)
def scheduler_ops_board(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """聚合调度开关、表驱动 job、worker 心跳与启停审计——纯读，不写任何表。

    数据源均为现有字段：asset_scheduler_jobs、asset_quality_runs.heartbeat_at/
    lease_owner/lease_expires_at、asset_identity_scheduler_runs.provider_heartbeat_at、
    asset_govern_audit_logs（既有启停/创建端点落审计）。任务启停不在本端点——
    走既有端点（POST /scheduler/jobs 等，各自落审计）。
    """
    from ...core.config import settings
    from ...models.governance_base import GovernAuditLog
    from ...models.identity_sync import IdentitySchedulerRun
    from ...models.quality_governance import QualityRun

    now = datetime.now(timezone.utc)

    switches = {
        "identity_nightly_enabled": settings.identity_nightly_enabled,
        "dict_medical_push_enabled": settings.dict_medical_push_enabled,
        "query_schedule_enabled": settings.query_schedule_enabled,
        "quality_execution_scheduler_enabled": settings.quality_execution_scheduler_enabled,
        "ai_context_cache_cleanup_enabled": settings.ai_context_cache_cleanup_enabled,
        "scheduler_timezone": settings.scheduler_timezone,
    }

    job_rows = db.scalars(
        select(SchedulerJob).order_by(SchedulerJob.created_at.desc()).limit(500)
    ).all()
    by_status: dict[str, int] = {}
    by_trigger_mode: dict[str, int] = {}
    for r in job_rows:
        by_status[r.status or "unknown"] = by_status.get(r.status or "unknown", 0) + 1
        by_trigger_mode[r.trigger_mode or "unknown"] = by_trigger_mode.get(r.trigger_mode or "unknown", 0) + 1
    scheduled_jobs = [
        {
            "id": r.id, "job_type": r.job_type, "source_code": r.source_code,
            "schedule_cron": r.schedule_cron, "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "total_processed": r.total_processed, "total_changes": r.total_changes,
            "error_message": r.error_message,
        }
        for r in job_rows if r.trigger_mode == "scheduled"
    ][:50]

    def _age(ts) -> float | None:
        return (now - ts).total_seconds() if ts is not None else None

    quality_workers = [
        {
            "run_id": r.id, "run_code": r.run_code, "status": r.status,
            "detector_kind": r.detector_kind, "started_at": r.started_at.isoformat() if r.started_at else None,
            "heartbeat_at": r.heartbeat_at.isoformat() if r.heartbeat_at else None,
            "heartbeat_age_seconds": _age(r.heartbeat_at),
            "lease_owner": r.lease_owner,
            "lease_expires_at": r.lease_expires_at.isoformat() if r.lease_expires_at else None,
            "lease_active": bool(r.lease_expires_at and r.lease_expires_at > now),
        }
        for r in db.scalars(
            select(QualityRun)
            .where(QualityRun.status.in_(["running", "waiting_window", "queued"]))
            .order_by(QualityRun.id.desc())
            .limit(50)
        ).all()
    ]

    identity_runs = [
        {
            "run_id": r.run_id, "triggered_by": r.triggered_by, "status": r.status,
            "lock_holder": r.lock_holder,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "provider_code": r.provider_code,
            "provider_heartbeat_at": r.provider_heartbeat_at.isoformat() if r.provider_heartbeat_at else None,
            "provider_heartbeat_age_seconds": _age(r.provider_heartbeat_at),
        }
        for r in db.scalars(
            select(IdentitySchedulerRun).order_by(IdentitySchedulerRun.id.desc()).limit(5)
        ).all()
    ]

    audit_trail = [
        {
            "id": a.id, "action": a.action, "operator": a.operator,
            "entity_type": a.entity_type, "entity_ref": a.entity_ref,
            "reason": a.reason, "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in db.scalars(
            select(GovernAuditLog)
            .where(GovernAuditLog.entity_type == "scheduler_job")
            .order_by(GovernAuditLog.id.desc())
            .limit(20)
        ).all()
    ]

    return ApiResponse(data={
        "generated_at": now.isoformat(),
        "read_only": True,
        "scheduler_switches": switches,
        "jobs_summary": {
            "total": len(job_rows), "by_status": by_status, "by_trigger_mode": by_trigger_mode,
        },
        "scheduled_jobs": scheduled_jobs,
        "worker_heartbeats": {"quality_runs": quality_workers, "identity_nightly": identity_runs},
        "scheduler_job_audit_trail": audit_trail,
    })


@router.get("/scheduler/jobs/{job_id}", summary="Scheduler job detail")
def get_scheduler_job(job_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    job = db.get(SchedulerJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="scheduler job not found")
    return ApiResponse(data={
        "id": job.id,
        "job_type": job.job_type,
        "source_code": job.source_code,
        "trigger_mode": job.trigger_mode,
        "schedule_cron": job.schedule_cron,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "result_ref": job.result_ref,
        "total_processed": job.total_processed,
        "total_changes": job.total_changes,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    })


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


# ── 186 v1.10 P0-11/P0-19：执行器注册与批准范围治理 ──

from ...core.security import get_current_user, require_permission  # noqa: E402
from ...models.governance_base import AssetActionExecutor, GovernAuditLog  # noqa: E402
from fastapi import Depends, Request  # noqa: E402
from ...core.db import get_db as _get_db  # noqa: E402


class ExecutorPatch(BaseModel):
    enabled: bool | None = None
    require_approval: bool | None = None
    approval_ref: str | None = Field(default=None, max_length=128)
    reason: str = Field(min_length=2, max_length=255)


@router.get(
    "/action-executors",
    summary="执行器注册清单（含启用状态与目标/来源绑定）",
    dependencies=[Depends(require_permission("govern.executor.manage"))],
)
def list_action_executors(db: Session = Depends(_get_db)) -> ApiResponse[dict]:
    rows = db.scalars(select(AssetActionExecutor).order_by(AssetActionExecutor.executor_code)).all()
    return ApiResponse(data={"items": [
        {
            "executor_code": r.executor_code,
            "executor_name_cn": r.executor_name_cn,
            "execution_mode": r.execution_mode,
            "tool_code": r.tool_code,
            "sql_or_endpoint_ref": r.sql_or_endpoint_ref,
            "target_system_code": r.target_system_code,
            "target_source_code": r.target_source_code,
            "risk_level": r.risk_level,
            "require_approval": bool(r.require_approval),
            "enabled": bool(r.enabled),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]})


@router.patch(
    "/action-executors/{executor_code}",
    summary="受控变更执行器注册（enable/disable 等；写治理审计）",
    dependencies=[Depends(require_permission("govern.executor.manage"))],
)
def patch_action_executor(
    executor_code: str,
    req: ExecutorPatch,
    request: Request,
    db: Session = Depends(_get_db),
) -> ApiResponse[dict]:
    operator = get_current_user(request)
    row = db.scalar(
        select(AssetActionExecutor).where(AssetActionExecutor.executor_code == executor_code)
    )
    if not row:
        raise HTTPException(status_code=404, detail="executor not registered")
    identity_codes = {
        "JHEMR_ACCOUNT_DISABLE", "JHEMR_ACCOUNT_ENABLE",
        "CDMS_ACCOUNT_DISABLE", "CDMS_ACCOUNT_ENABLE",
    }
    if executor_code in identity_codes and req.enabled is True:
        if executor_code.endswith("_ENABLE"):
            raise HTTPException(
                status_code=403,
                detail="enable executors stay disabled: no approved enable scope exists (186 §12.8-E)",
            )
        if not (req.approval_ref or "").strip():
            raise HTTPException(status_code=400, detail="approval_ref required to enable a disable executor")
    before = {"enabled": bool(row.enabled), "require_approval": bool(row.require_approval)}
    if req.enabled is not None:
        row.enabled = req.enabled
    if req.require_approval is not None:
        row.require_approval = req.require_approval
    from datetime import datetime, timezone as _tz
    row.updated_at = datetime.now(_tz.utc)
    db.add(GovernAuditLog(
        module="governance",
        entity_type="asset_action_executor",
        entity_ref=executor_code,
        action="executor_patch",
        operator=operator,
        before_data=before,
        after_data={
            "enabled": bool(row.enabled),
            "require_approval": bool(row.require_approval),
            "approval_ref": req.approval_ref,
            "reason": req.reason,
        },
    ))
    db.commit()
    return ApiResponse(data={"executor_code": executor_code, "enabled": bool(row.enabled)})


class PilotScopeRegister(BaseModel):
    approval_ref: str = Field(min_length=3, max_length=128)
    person_codes: list[str] = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)


@router.post(
    "/identity-scopes/pilot",
    summary="登记显式试点人员批准范围（token 不是名单；成员此后不自动扩展）",
    dependencies=[Depends(require_permission("govern.executor.manage"))],
)
def register_pilot_scope_api(
    req: PilotScopeRegister,
    request: Request,
    db: Session = Depends(_get_db),
) -> ApiResponse[dict]:
    from ...services.identity_sync_action_gate import register_pilot_scope

    operator = get_current_user(request)
    try:
        scope = register_pilot_scope(
            db, approval_ref=req.approval_ref, person_codes=req.person_codes,
            created_by=operator, description=req.description,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(GovernAuditLog(
        module="governance",
        entity_type="identity_action_scope",
        entity_ref=f"pilot:{req.approval_ref}",
        action="scope_register",
        operator=operator,
        after_data={"members": len(req.person_codes), "approval_ref": req.approval_ref},
    ))
    db.commit()
    return ApiResponse(data={"scope_id": scope.id, "scope_type": "pilot", "members": len(req.person_codes)})


class BaselineFreeze(BaseModel):
    approval_ref: str = Field(min_length=3, max_length=128)
    max_members: int = Field(default=500, ge=1, le=1000)
    dry_run: bool = True
    description: str | None = Field(default=None, max_length=255)


@router.post(
    "/identity-scopes/baseline/freeze",
    summary="冻结停用基线范围（新鲜观测交集：人员有效+账号停用；冻结后不自动扩展）",
    dependencies=[Depends(require_permission("govern.executor.manage"))],
)
def freeze_baseline_scope_api(
    req: BaselineFreeze,
    request: Request,
    db: Session = Depends(_get_db),
) -> ApiResponse[dict]:
    from ...models.identity_sync import IdentityAccountStateDecision
    from ...models.identity import IdentityPerson
    from ...services.identity_sync_action_gate import freeze_baseline_scope, person_is_protected

    operator = get_current_user(request)
    decisions = db.execute(
        select(IdentityAccountStateDecision.person_code, IdentityAccountStateDecision.decision_reason)
        .where(
            IdentityAccountStateDecision.rule_version == "dual_source_v1",
            IdentityAccountStateDecision.desired_state == "disabled",
            IdentityAccountStateDecision.source_complete.is_(True),
            IdentityAccountStateDecision.execution_allowed.is_(True),
        )
        .order_by(IdentityAccountStateDecision.person_code.asc())
    ).all()
    candidates: list[tuple[str, str | None]] = []
    for person_code, reason in decisions:
        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
        if person is None or person.conflict_flag:
            continue
        protected, _hits = person_is_protected(db, person_code)
        if protected:
            continue
        candidates.append((person_code, reason))
        if len(candidates) >= req.max_members:
            break
    preview = {"candidate_members": len(candidates), "max_members": req.max_members}
    if req.dry_run:
        return ApiResponse(data={
            "dry_run": True, **preview,
            "sample_masked": [c[0][:2] + "***" for c in candidates[:5]],
        })
    try:
        scope = freeze_baseline_scope(
            db, approval_ref=req.approval_ref, members=candidates,
            created_by=operator, description=req.description,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(GovernAuditLog(
        module="governance",
        entity_type="identity_action_scope",
        entity_ref=f"baseline:{req.approval_ref}",
        action="scope_freeze",
        operator=operator,
        after_data={
            "members": len(candidates),
            "approval_ref": req.approval_ref,
            "scope_fingerprint": scope.scope_fingerprint,
        },
    ))
    db.commit()
    return ApiResponse(data={
        "scope_id": scope.id, "scope_type": "baseline",
        "members": len(candidates), "scope_fingerprint": scope.scope_fingerprint,
    })


@router.get(
    "/identity-scopes",
    summary="批准范围清单（人员计数与指纹，不含明细）",
    dependencies=[Depends(require_permission("govern.executor.manage"))],
)
def list_identity_scopes(db: Session = Depends(_get_db)) -> ApiResponse[dict]:
    from ...models.identity_sync import IdentityApprovedScope, IdentityApprovedScopeMember
    from sqlalchemy import func as _func

    rows = db.scalars(
        select(IdentityApprovedScope).order_by(IdentityApprovedScope.id.desc())
    ).all()
    items = []
    for scope in rows:
        count = db.scalar(
            select(_func.count()).select_from(IdentityApprovedScopeMember)
            .where(IdentityApprovedScopeMember.scope_id == scope.id)
        )
        items.append({
            "scope_id": scope.id,
            "scope_type": scope.scope_type,
            "approval_ref": scope.approval_ref,
            "action": scope.action,
            "status": scope.status,
            "scope_fingerprint": scope.scope_fingerprint,
            "members": count,
            "created_by": scope.created_by,
            "created_at": scope.created_at.isoformat() if scope.created_at else None,
        })
    return ApiResponse(data={"items": items})
