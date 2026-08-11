from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.governance_base import GovernAuditLog, GovernChangeRequest
from ...models.governance_ops import SchedulerJob
from ...models.identity import (
    IdentityAccount,
    IdentityDepartment,
    IdentityPerson,
    IdentityPersonDepartment,
    IdentityPersonSource,
    IdentitySyncDiff,
)
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


@router.get("/departments", summary="科室基线列表（HIS dept_dict 为核心）")
def list_departments(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(IdentityDepartment).order_by(IdentityDepartment.dept_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "dept_code": r.dept_code, "dept_name_cn": r.dept_name_cn,
            "dept_type": r.dept_type, "source_system": r.source_system,
            "status": r.status,
        }
        for r in rows
    ])


@router.get("/persons", summary="人员主数据列表")
def list_persons(
    person_type: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(IdentityPerson)
    if person_type:
        stmt = stmt.where(IdentityPerson.person_type == person_type)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            IdentityPerson.person_name_cn.ilike(like)
            | IdentityPerson.person_code.ilike(like)
            | IdentityPerson.dept_name_cn.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(IdentityPerson.person_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "person_code": r.person_code, "person_name_cn": r.person_name_cn,
         "dept_code": r.dept_code, "dept_name_cn": r.dept_name_cn,
         "person_type": r.person_type, "employment_status": r.employment_status,
         "primary_source_system": r.primary_source_system}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/accounts", summary="多系统账号列表")
def list_accounts(
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(IdentityAccount)
    if system_code:
        stmt = stmt.where(IdentityAccount.system_code == system_code)
    rows = db.scalars(stmt.order_by(IdentityAccount.system_code, IdentityAccount.account_id)).all()
    return ApiResponse(data=[
        {"id": r.id, "person_code": r.person_code, "system_code": r.system_code,
         "account_id": r.account_id, "account_name": r.account_name,
         "account_status": r.account_status}
        for r in rows
    ])


def _diff_item(r: IdentitySyncDiff) -> dict:
    after = r.after_data if isinstance(r.after_data, dict) else {}
    suggestion = after.get("merge_suggestion") if isinstance(after, dict) else None
    return {
        "id": r.id,
        "diff_type": r.diff_type,
        "source_system": r.source_system,
        "target_system": r.target_system,
        "entity_type": r.entity_type,
        "entity_code": r.entity_code,
        "status": r.status,
        "severity": r.severity,
        "before_data": r.before_data,
        "after_data": r.after_data,
        "merge_suggestion": suggestion,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/sync-diffs", summary="人员/科室/账号同步差异")
def list_sync_diffs(
    status: str | None = Query(None),
    diff_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(IdentitySyncDiff)
    if status:
        stmt = stmt.where(IdentitySyncDiff.status == status)
    if diff_type:
        stmt = stmt.where(IdentitySyncDiff.diff_type == diff_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(IdentitySyncDiff.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [_diff_item(r) for r in rows]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/sync-diffs/{diff_id}", summary="差异详情（含合并建议，不自动覆盖）")
def get_sync_diff(diff_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    r = db.get(IdentitySyncDiff, diff_id)
    if not r:
        raise HTTPException(status_code=404, detail="sync diff not found")
    return ApiResponse(data=_diff_item(r))


@router.post(
    "/review/generate",
    summary="L13 生成主数据复核差异（仅 diff，不自动写主档）",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def generate_identity_review(
    request: Request,
    source_system: str = Query("HIS"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    get_current_user(request)
    from ...services.identity_review import build_his_master_review

    result = build_his_master_review(db, source_system=source_system, target_system="asset")
    db.commit()
    job = SchedulerJob(
        job_type="identity_review",
        source_code=source_system,
        trigger_mode="manual",
        status="success",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        result_ref=json.dumps(result, ensure_ascii=False),
        total_processed=result.get("scanned_person_codes"),
        total_changes=result.get("diffs_created"),
    )
    db.add(job)
    db.commit()
    result["job_id"] = job.id
    return ApiResponse(data=result)


@router.get("/persons/{person_code}", summary="人员统一画像")
def person_profile(person_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    p = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
    if not p:
        raise HTTPException(status_code=404)
    accounts = db.scalars(
        select(IdentityAccount).where(IdentityAccount.person_code == person_code)
    ).all()
    sources = db.scalars(
        select(IdentityPersonSource).where(IdentityPersonSource.person_code == person_code)
    ).all()
    departments = db.scalars(
        select(IdentityPersonDepartment).where(IdentityPersonDepartment.person_code == person_code)
    ).all()
    return ApiResponse(data={
        "person_code": p.person_code, "person_name_cn": p.person_name_cn,
        "dept_code": p.dept_code, "person_type": p.person_type,
        "primary_source_system": p.primary_source_system,
        "profile": {
            "summary": p.profile_summary,
            "tags": p.profile_tags or [],
            "review_status": p.review_status or "unreviewed",
            "updated_at": p.profile_updated_at.isoformat() if p.profile_updated_at else None,
        },
        "accounts": [
            {"system_code": a.system_code, "account_id": a.account_id, "account_status": a.account_status}
            for a in accounts
        ],
        "sources": [
            {"source_system": s.source_system, "source_person_id": s.source_person_id, "is_temporary": s.is_temporary}
            for s in sources
        ],
        "departments": [
            {
                "dept_code": d.dept_code,
                "is_primary": bool(d.is_primary),
                "source_table": d.source_table,
                "source_dept_code": d.source_dept_code,
            }
            for d in departments
        ],
    })


class ProfileChangeRequest(BaseModel):
    profile_summary: str | None = Field(default=None, max_length=2000)
    profile_tags: list[str] = Field(default_factory=list, max_length=30)
    reason: str = Field(..., min_length=2, max_length=500)


@router.post(
    "/persons/{person_code}/profile-change-requests",
    summary="提交人员画像变更审批",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def create_profile_change_request(
    person_code: str,
    req: ProfileChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
    if not person:
        raise HTTPException(status_code=404, detail="person not found")
    payload = {"person_code": person_code, "profile_summary": req.profile_summary, "profile_tags": req.profile_tags, "reason": req.reason}
    cr = GovernChangeRequest(
        module="identity",
        entity_type="person_profile",
        entity_ref=person_code,
        request_type="update_profile",
        request_payload=payload,
        before_data={"profile_summary": person.profile_summary, "profile_tags": person.profile_tags or []},
        requested_by=current_user,
        approval_status="pending",
        note=req.reason,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status, "requested_by": current_user})


@router.get("/persons/{person_code}/profile-change-requests", summary="人员画像变更审批记录")
def list_profile_change_requests(person_code: str, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(GovernChangeRequest)
        .where(GovernChangeRequest.module == "identity", GovernChangeRequest.entity_type == "person_profile", GovernChangeRequest.entity_ref == person_code)
        .order_by(GovernChangeRequest.created_at.desc())
    ).all()
    return ApiResponse(data=[{
        "id": row.id,
        "approval_status": row.approval_status,
        "request_type": row.request_type,
        "requested_by": row.requested_by,
        "approved_by": row.approved_by,
        "executed_by": row.executed_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "request_payload": row.request_payload,
    } for row in rows])


class AccountBind(BaseModel):
    person_code: str
    system_code: str
    account_id: str


class IdentityCRCreate(BaseModel):
    entity_type: str
    entity_ref: str | None = None
    request_type: str
    request_payload: dict | None = None


class IdentitySyncRunRequest(BaseModel):
    source_system: str
    target_system: str = "asset"
    entity_type: str


class IdentityCollectSourcesRequest(BaseModel):
    source_code: str | None = None
    source_system: str = "HIS"
    entity_type: str = "identity_department"
    max_rows: int = 10000


class IdentitySyncDiffUpdate(BaseModel):
    status: str
    note: str | None = None


class ApproveBody(BaseModel):
    note: str | None = None


@router.get("/departments/{dept_code}", summary="科室统一画像")
def department_profile(dept_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    d = db.scalar(select(IdentityDepartment).where(IdentityDepartment.dept_code == dept_code))
    if not d:
        raise HTTPException(status_code=404)
    persons = db.scalars(
        select(IdentityPerson).where(IdentityPerson.dept_code == dept_code)
    ).all()
    accounts = db.scalars(
        select(IdentityAccount).where(IdentityAccount.dept_code == dept_code)
    ).all()
    return ApiResponse(data={
        "dept_code": d.dept_code, "dept_name_cn": d.dept_name_cn,
        "dept_type": d.dept_type, "parent_dept_code": d.parent_dept_code,
        "source_system": d.source_system, "status": d.status,
        "persons": [
            {"person_code": p.person_code, "person_name_cn": p.person_name_cn, "person_type": p.person_type}
            for p in persons
        ],
        "accounts": [
            {"system_code": a.system_code, "account_id": a.account_id, "account_status": a.account_status}
            for a in accounts
        ],
    })


@router.post(
    "/collect-sources",
    summary="Collect identity source data",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def trigger_collection(
    request: Request,
    req: IdentityCollectSourcesRequest | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    get_current_user(request)
    if req is None or not req.source_code:
        return ApiResponse(data={"status": "scheduled", "note": "manual collection registered"})
    if req.entity_type not in {"identity_department", "identity_person", "identity_all"}:
        raise HTTPException(status_code=400, detail="unsupported identity source collection entity_type")

    from ...services.identity_source_collector import collect_his_identity_sources

    result = collect_his_identity_sources(
        db,
        source_code=req.source_code,
        source_system=req.source_system,
        entity_type=req.entity_type,
        max_rows=req.max_rows,
    )
    job = SchedulerJob(
        job_type="identity_source_collect",
        source_code=req.source_code,
        trigger_mode="manual",
        status="success",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        result_ref=json.dumps(result, ensure_ascii=False),
        total_processed=result.get("scanned"),
        total_changes=(result.get("inserted") or 0) + (result.get("updated") or 0),
    )
    db.add(job)
    db.commit()
    result["job_id"] = job.id
    return ApiResponse(data=result)


def _sync_job_status(sync_status: str | None) -> str:
    if sync_status == "success":
        return "success"
    if sync_status in {"failed", "skipped"}:
        return "failed"
    return "blocked"


def _store_sync_job(
    db: Session,
    *,
    req: IdentitySyncRunRequest,
    result: dict,
) -> SchedulerJob:
    now = datetime.now(timezone.utc)
    job = SchedulerJob(
        job_type="identity_sync",
        source_code=req.source_system,
        trigger_mode="manual",
        status=_sync_job_status(result.get("status")),
        started_at=now,
        finished_at=now,
        result_ref=json.dumps({
            "source_system": req.source_system,
            "target_system": req.target_system,
            "entity_type": req.entity_type,
            "result": result,
        }, ensure_ascii=False),
        total_processed=result.get("scanned"),
        total_changes=result.get("diffs_created"),
        error_message=result.get("error") or result.get("note") if result.get("status") != "success" else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post(
    "/sync/his",
    summary="Sync HIS identity departments/persons",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def sync_his_identity_endpoint(
    request: Request,
    dry_run: bool = Query(True),
    max_rows: int | None = Query(None, ge=1, le=50000),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...services.his_identity_sync import sync_his_identity

    result = sync_his_identity(db, operator=get_current_user(request), dry_run=dry_run, max_rows=max_rows)
    return ApiResponse(data=result)
@router.post(
    "/sync/run",
    summary="Run identity sync diff generation",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def run_identity_sync(req: IdentitySyncRunRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    if not req.entity_type.startswith("identity_"):
        raise HTTPException(status_code=400, detail="identity sync only accepts identity_* entity types")
    from ...services.sync_executor import run_sync

    result = run_sync(
        source_system=req.source_system,
        target_system=req.target_system,
        entity_type=req.entity_type,
        operator=current_user,
    )
    job = _store_sync_job(db, req=req, result=result)
    return ApiResponse(data={**result, "job_id": job.id, "job_status": job.status})


@router.post(
    "/sync/jobs/{job_id}/retry",
    summary="Retry identity sync job",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def retry_identity_sync_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    job = db.get(SchedulerJob, job_id)
    if not job or job.job_type != "identity_sync":
        raise HTTPException(status_code=404, detail="identity sync job not found")
    try:
        payload = json.loads(job.result_ref or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="sync job result_ref is not valid JSON")

    req = IdentitySyncRunRequest(
        source_system=payload.get("source_system") or job.source_code or "",
        target_system=payload.get("target_system") or "asset",
        entity_type=payload.get("entity_type") or "",
    )
    if not req.source_system or not req.entity_type.startswith("identity_"):
        raise HTTPException(status_code=400, detail="sync job is missing source_system or identity entity_type")

    from ...services.sync_executor import run_sync

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    result = run_sync(
        source_system=req.source_system,
        target_system=req.target_system,
        entity_type=req.entity_type,
        operator=current_user,
    )
    job.status = _sync_job_status(result.get("status"))
    job.finished_at = datetime.now(timezone.utc)
    job.result_ref = json.dumps({
        "source_system": req.source_system,
        "target_system": req.target_system,
        "entity_type": req.entity_type,
        "result": result,
    }, ensure_ascii=False)
    job.total_processed = result.get("scanned")
    job.total_changes = result.get("diffs_created")
    job.error_message = result.get("error") or result.get("note") if result.get("status") != "success" else None
    db.add(GovernAuditLog(
        module="identity",
        entity_type="sync_job",
        entity_ref=str(job.id),
        action="retry",
        after_data={"status": job.status, "result": result},
        operator=current_user,
    ))
    db.commit()
    return ApiResponse(data={**result, "job_id": job.id, "job_status": job.status})

@router.put(
    "/accounts/bind",
    summary="绑定人员到系统账号",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def bind_account(req: AccountBind, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    acct = db.scalar(
        select(IdentityAccount).where(
            IdentityAccount.system_code == req.system_code,
            IdentityAccount.account_id == req.account_id,
        )
    )
    if not acct:
        raise HTTPException(status_code=404, detail="账号不存在")
    acct.person_code = req.person_code
    db.commit()
    return ApiResponse(data={"system_code": req.system_code, "account_id": req.account_id, "person_code": req.person_code})


@router.post(
    "/change-requests",
    summary="创建身份变更请求",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def create_identity_cr(req: IdentityCRCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = GovernChangeRequest(
        module="identity",
        entity_type=req.entity_type,
        entity_ref=req.entity_ref,
        request_type=req.request_type,
        request_payload=req.request_payload,
        requested_by=current_user,
    )
    db.add(cr)
    db.flush()
    audit = GovernAuditLog(
        module="identity", entity_type="change_request", entity_ref=str(cr.id),
        action="create", operator=current_user,
    )
    db.add(audit)
    db.commit()
    db.refresh(cr)
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.get("/change-requests", summary="身份变更请求列表")
def list_identity_crs(
    approval_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernChangeRequest).where(GovernChangeRequest.module == "identity")
    if approval_status:
        stmt = stmt.where(GovernChangeRequest.approval_status == approval_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernChangeRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_ref": r.entity_ref,
            "request_type": r.request_type, "approval_status": r.approval_status,
            "requested_by": r.requested_by, "approved_by": r.approved_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.patch(
    "/change-requests/{cr_id}/approve",
    summary="审批身份变更请求",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def approve_identity_cr(cr_id: int, req: ApproveBody, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr or cr.module != "identity":
        raise HTTPException(status_code=404)
    if cr.approval_status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail=f"当前状态 {cr.approval_status} 不可审批")
    if current_user == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    cr.approval_status = "approved"
    cr.approved_by = current_user
    audit = GovernAuditLog(
        module="identity", entity_type="change_request", entity_ref=str(cr.id),
        action="approve", operator=current_user, reason=req.note,
    )
    db.add(audit)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.post(
    "/change-requests/{cr_id}/execute",
    summary="执行身份变更请求",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def execute_identity_cr(cr_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr or cr.module != "identity":
        raise HTTPException(status_code=404)
    if cr.approval_status != "approved":
        raise HTTPException(status_code=400, detail=f"当前状态 {cr.approval_status} 不可执行，需已审批通过")

    result = _execute_identity_payload(db, cr.request_type, cr.request_payload or {})
    cr.approval_status = "executed"
    cr.executed_by = current_user
    cr.execution_result = json.dumps(result, ensure_ascii=False)[:2000]
    audit = GovernAuditLog(
        module="identity",
        entity_type="change_request",
        entity_ref=str(cr.id),
        action="execute",
        operator=current_user,
        after_data=result,
    )
    db.add(audit)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": "executed", "result": result})


def _resolve_diff_after(diff: IdentitySyncDiff) -> tuple[dict, dict, dict]:
    after = diff.after_data if isinstance(diff.after_data, dict) else {}
    suggestion = after.get("merge_suggestion") if isinstance(after, dict) else {}
    if not isinstance(suggestion, dict):
        suggestion = {}
    changed = after.get("changed_fields") if isinstance(after, dict) else {}
    if not isinstance(changed, dict):
        changed = {}
    return after, suggestion, changed


def _mark_diff_resolved(db: Session, diff_id) -> None:
    if not diff_id:
        return
    diff = db.get(IdentitySyncDiff, int(diff_id))
    if diff:
        diff.status = "resolved"
        diff.handled_at = datetime.now(timezone.utc)


def _execute_identity_payload(db: Session, request_type: str, payload: dict) -> dict:
    """Apply approved identity master changes (platform PG only)."""
    if request_type in {"apply_person_master", "update_person_master"}:
        person_code = (payload.get("person_code") or "").strip()
        if not person_code:
            raise HTTPException(status_code=400, detail="person_code required")
        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
        if not person:
            raise HTTPException(status_code=404, detail=f"person {person_code} not found")
        before = {
            "person_name_cn": person.person_name_cn,
            "dept_code": person.dept_code,
            "employment_status": person.employment_status,
        }
        if "person_name_cn" in payload and payload["person_name_cn"]:
            person.person_name_cn = str(payload["person_name_cn"]).strip()
        if "dept_code" in payload and payload["dept_code"]:
            person.dept_code = str(payload["dept_code"]).strip()
        if "employment_status" in payload and payload["employment_status"]:
            person.employment_status = str(payload["employment_status"]).strip()
        person.updated_at = datetime.now(timezone.utc)
        diff_id = payload.get("diff_id")
        _mark_diff_resolved(db, diff_id)
        return {
            "person_code": person_code,
            "before": before,
            "after": {
                "person_name_cn": person.person_name_cn,
                "dept_code": person.dept_code,
                "employment_status": person.employment_status,
            },
            "diff_id": diff_id,
        }
    if request_type == "update_profile":
        person_code = (payload.get("person_code") or payload.get("entity_ref") or "").strip()
        if not person_code:
            raise HTTPException(status_code=400, detail="person_code required")
        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
        if not person:
            raise HTTPException(status_code=404, detail=f"person {person_code} not found")
        before = {"profile_summary": person.profile_summary, "profile_tags": person.profile_tags or []}
        if "profile_summary" in payload:
            person.profile_summary = payload.get("profile_summary")
        if "profile_tags" in payload:
            tags = payload.get("profile_tags") or []
            if not isinstance(tags, list) or len(tags) > 30:
                raise HTTPException(status_code=400, detail="profile_tags invalid")
            person.profile_tags = [str(tag)[:80] for tag in tags]
        person.review_status = "approved"
        person.profile_updated_at = datetime.now(timezone.utc)
        person.updated_at = datetime.now(timezone.utc)
        return {"person_code": person_code, "before": before, "after": {"profile_summary": person.profile_summary, "profile_tags": person.profile_tags or []}}
    if request_type in {"apply_department_master", "update_department_master"}:
        dept_code = (payload.get("dept_code") or "").strip()
        if not dept_code:
            raise HTTPException(status_code=400, detail="dept_code required")
        dept = db.scalar(select(IdentityDepartment).where(IdentityDepartment.dept_code == dept_code))
        if not dept:
            raise HTTPException(status_code=404, detail=f"department {dept_code} not found")
        before = {
            "dept_name_cn": dept.dept_name_cn,
            "dept_type": dept.dept_type,
            "parent_dept_code": dept.parent_dept_code,
            "status": dept.status,
        }
        if "dept_name_cn" in payload and payload["dept_name_cn"]:
            dept.dept_name_cn = str(payload["dept_name_cn"]).strip()
        if "dept_type" in payload and payload["dept_type"]:
            dept.dept_type = str(payload["dept_type"]).strip()
        if "parent_dept_code" in payload and payload["parent_dept_code"] is not None:
            dept.parent_dept_code = str(payload["parent_dept_code"]).strip() or None
        if "status" in payload and payload["status"]:
            dept.status = str(payload["status"]).strip()
        dept.updated_at = datetime.now(timezone.utc)
        diff_id = payload.get("diff_id")
        _mark_diff_resolved(db, diff_id)
        return {
            "dept_code": dept_code,
            "before": before,
            "after": {
                "dept_name_cn": dept.dept_name_cn,
                "dept_type": dept.dept_type,
                "parent_dept_code": dept.parent_dept_code,
                "status": dept.status,
            },
            "diff_id": diff_id,
        }
    if request_type in {"noop", "mark_only"}:
        return {"status": "noop"}
    raise HTTPException(status_code=400, detail=f"unsupported request_type: {request_type}")


class ApplyDiffMasterRequest(BaseModel):
    """L16：从差异提出主档修改；默认仅创建变更请求，需审批后执行。"""

    person_name_cn: str | None = None
    dept_code: str | None = None
    dept_name_cn: str | None = None
    dept_type: str | None = None
    parent_dept_code: str | None = None
    employment_status: str | None = None
    status: str | None = None
    use_prefer_source: bool = True
    auto_approve_execute: bool = False  # 仅运维调试；生产应 false


class BatchDiffIdsRequest(BaseModel):
    """批量差异操作，默认上限 50。"""

    diff_ids: list[int] = Field(default_factory=list)
    use_prefer_source: bool = True
    status: str | None = None  # for batch status update: resolved/ignored/open
    note: str | None = None


class BatchChangeRequestIds(BaseModel):
    ids: list[int] = Field(default_factory=list)
    note: str | None = None


def _build_master_payload_from_diff(
    diff: IdentitySyncDiff,
    req: ApplyDiffMasterRequest,
) -> tuple[dict, str, str, dict]:
    """Return (payload, entity_type, request_type, suggestion). Raises ValueError on validation."""
    if not diff.entity_code:
        raise ValueError("diff missing entity_code")
    if diff.entity_type not in {"identity_person", "identity_department"}:
        raise ValueError("only identity_person / identity_department diffs supported")

    after, suggestion, changed = _resolve_diff_after(diff)

    if diff.entity_type == "identity_person":
        payload: dict = {"person_code": diff.entity_code, "diff_id": diff.id}
        if req.person_name_cn:
            payload["person_name_cn"] = req.person_name_cn
        elif req.use_prefer_source and "person_name_cn" in changed:
            payload["person_name_cn"] = changed["person_name_cn"].get("source")
        elif req.use_prefer_source and after.get("source_person_name"):
            payload["person_name_cn"] = after.get("source_person_name")

        if req.dept_code:
            payload["dept_code"] = req.dept_code
        elif req.use_prefer_source and "dept_code" in changed:
            payload["dept_code"] = changed["dept_code"].get("source")
        elif req.use_prefer_source and after.get("source_dept_code"):
            payload["dept_code"] = after.get("source_dept_code")

        if req.employment_status:
            payload["employment_status"] = req.employment_status
        elif req.use_prefer_source and "employment_status" in changed:
            payload["employment_status"] = changed["employment_status"].get("source")

        if not any(k in payload for k in ("person_name_cn", "dept_code", "employment_status")):
            raise ValueError("no master fields to apply; provide values or use_prefer_source with mismatch data")
        return payload, "identity_person", "apply_person_master", suggestion

    payload = {"dept_code": diff.entity_code, "diff_id": diff.id}
    if req.dept_name_cn:
        payload["dept_name_cn"] = req.dept_name_cn
    elif req.use_prefer_source and "dept_name_cn" in changed:
        payload["dept_name_cn"] = changed["dept_name_cn"].get("source")
    elif req.use_prefer_source and after.get("source_dept_name"):
        payload["dept_name_cn"] = after.get("source_dept_name")

    if req.dept_type:
        payload["dept_type"] = req.dept_type
    elif req.use_prefer_source and "dept_type" in changed:
        payload["dept_type"] = changed["dept_type"].get("source")

    if req.parent_dept_code is not None:
        payload["parent_dept_code"] = req.parent_dept_code
    elif req.use_prefer_source and "parent_dept_code" in changed:
        payload["parent_dept_code"] = changed["parent_dept_code"].get("source")

    if req.status:
        payload["status"] = req.status
    elif req.use_prefer_source and "status" in changed:
        payload["status"] = changed["status"].get("source")

    if not any(k in payload for k in ("dept_name_cn", "dept_type", "parent_dept_code", "status")):
        raise ValueError("no department master fields to apply; provide values or use_prefer_source with mismatch data")
    return payload, "identity_department", "apply_department_master", suggestion


def _create_cr_from_diff(
    db: Session,
    diff: IdentitySyncDiff,
    req: ApplyDiffMasterRequest,
    current_user: str,
) -> dict:
    payload, entity_type, request_type, suggestion = _build_master_payload_from_diff(diff, req)
    cr = GovernChangeRequest(
        module="identity",
        entity_type=entity_type,
        entity_ref=diff.entity_code,
        request_type=request_type,
        request_payload=payload,
        before_data=diff.before_data if isinstance(diff.before_data, dict) else None,
        after_data=payload,
        approval_status="pending",
        requested_by=current_user,
        note=(
            f"from sync_diff #{diff.id} type={diff.diff_type}; "
            f"prefer={suggestion.get('prefer_source_table')}"
        ),
    )
    db.add(cr)
    db.flush()
    db.add(
        GovernAuditLog(
            module="identity",
            entity_type="change_request",
            entity_ref=str(cr.id),
            action="propose_from_diff",
            operator=current_user,
            after_data=payload,
        )
    )
    out = {
        "diff_id": diff.id,
        "change_request_id": cr.id,
        "approval_status": cr.approval_status,
        "payload": payload,
        "entity_type": entity_type,
        "request_type": request_type,
        "auto_applied": False,
        "note": "已创建变更请求；需另一人审批后 execute，才会写主档",
    }
    if req.auto_approve_execute:
        out["note"] = "auto_approve_execute 已忽略：请走审批/execute 双人流程"
    return out


@router.post(
    "/sync-diffs/{diff_id}/propose-master",
    summary="L16 从差异提出主档变更（默认不直接写）",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def propose_master_from_diff(
    diff_id: int,
    req: ApplyDiffMasterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    diff = db.get(IdentitySyncDiff, diff_id)
    if not diff:
        raise HTTPException(status_code=404, detail="sync diff not found")
    try:
        out = _create_cr_from_diff(db, diff, req, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="变更请求参数无效，请检查后重试") from e
    db.commit()
    return ApiResponse(data=out)


@router.post(
    "/sync-diffs/batch-propose-master",
    summary="L16 批量提出主档变更（默认上限 50）",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def batch_propose_master_from_diffs(
    req: BatchDiffIdsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    ids = list(dict.fromkeys(int(i) for i in (req.diff_ids or []) if i is not None))
    if not ids:
        raise HTTPException(status_code=400, detail="diff_ids required")
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="batch size max 50")
    apply_req = ApplyDiffMasterRequest(use_prefer_source=req.use_prefer_source)
    ok: list[dict] = []
    failed: list[dict] = []
    for diff_id in ids:
        diff = db.get(IdentitySyncDiff, diff_id)
        if not diff:
            failed.append({"diff_id": diff_id, "error": "not found"})
            continue
        try:
            out = _create_cr_from_diff(db, diff, apply_req, current_user)
            ok.append(out)
        except ValueError as e:
            failed.append({"diff_id": diff_id, "error": str(e)})
    db.commit()
    return ApiResponse(
        data={
            "requested": len(ids),
            "created": len(ok),
            "failed": len(failed),
            "items": ok,
            "errors": failed,
            "note": "仅创建 change_request，不写主档；需另一人审批后 execute",
        }
    )


@router.post(
    "/sync-diffs/batch-status",
    summary="批量更新差异状态 open/resolved/ignored",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def batch_update_sync_diff_status(
    req: BatchDiffIdsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    if req.status not in {"open", "resolved", "ignored"}:
        raise HTTPException(status_code=400, detail="status must be open/resolved/ignored")
    ids = list(dict.fromkeys(int(i) for i in (req.diff_ids or []) if i is not None))
    if not ids:
        raise HTTPException(status_code=400, detail="diff_ids required")
    if len(ids) > 100:
        raise HTTPException(status_code=400, detail="batch size max 100")
    updated = 0
    missing = 0
    for diff_id in ids:
        diff = db.get(IdentitySyncDiff, diff_id)
        if not diff:
            missing += 1
            continue
        before = {"status": diff.status}
        diff.status = req.status
        diff.handled_at = None if req.status == "open" else datetime.now(timezone.utc)
        db.add(
            GovernAuditLog(
                module="identity",
                entity_type="sync_diff",
                entity_ref=str(diff.id),
                action="batch_update_status",
                before_data=before,
                after_data={"status": diff.status},
                operator=current_user,
                reason=req.note,
            )
        )
        updated += 1
    db.commit()
    return ApiResponse(data={"requested": len(ids), "updated": updated, "missing": missing, "status": req.status})


@router.post(
    "/change-requests/batch-approve",
    summary="批量审批身份变更请求",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def batch_approve_identity_cr(
    req: BatchChangeRequestIds,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    ids = list(dict.fromkeys(int(i) for i in (req.ids or []) if i is not None))
    if not ids:
        raise HTTPException(status_code=400, detail="ids required")
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="batch size max 50")
    ok, failed = [], []
    for cr_id in ids:
        cr = db.get(GovernChangeRequest, cr_id)
        if not cr or cr.module != "identity":
            failed.append({"id": cr_id, "error": "not found"})
            continue
        if cr.approval_status not in ("draft", "pending"):
            failed.append({"id": cr_id, "error": f"status {cr.approval_status}"})
            continue
        if current_user == cr.requested_by:
            failed.append({"id": cr_id, "error": "same requester cannot approve"})
            continue
        cr.approval_status = "approved"
        cr.approved_by = current_user
        db.add(
            GovernAuditLog(
                module="identity",
                entity_type="change_request",
                entity_ref=str(cr.id),
                action="batch_approve",
                operator=current_user,
                reason=req.note,
            )
        )
        ok.append({"id": cr.id, "approval_status": "approved"})
    db.commit()
    return ApiResponse(data={"requested": len(ids), "approved": len(ok), "failed": len(failed), "items": ok, "errors": failed})


@router.post(
    "/change-requests/batch-execute",
    summary="批量执行已审批身份变更（写平台主档）",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def batch_execute_identity_cr(
    req: BatchChangeRequestIds,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    ids = list(dict.fromkeys(int(i) for i in (req.ids or []) if i is not None))
    if not ids:
        raise HTTPException(status_code=400, detail="ids required")
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="batch size max 50")
    ok, failed = [], []
    for cr_id in ids:
        cr = db.get(GovernChangeRequest, cr_id)
        if not cr or cr.module != "identity":
            failed.append({"id": cr_id, "error": "not found"})
            continue
        if cr.approval_status != "approved":
            failed.append({"id": cr_id, "error": f"status {cr.approval_status}"})
            continue
        try:
            result = _execute_identity_payload(db, cr.request_type, cr.request_payload or {})
            cr.approval_status = "executed"
            cr.executed_by = current_user
            cr.execution_result = json.dumps(result, ensure_ascii=False)[:2000]
            db.add(
                GovernAuditLog(
                    module="identity",
                    entity_type="change_request",
                    entity_ref=str(cr.id),
                    action="batch_execute",
                    operator=current_user,
                    after_data=result,
                )
            )
            ok.append({"id": cr.id, "approval_status": "executed", "result": result})
        except HTTPException as e:
            failed.append({"id": cr_id, "error": e.detail})
        except Exception as e:
            failed.append({"id": cr_id, "error": str(e)[:200]})
    db.commit()
    return ApiResponse(
        data={
            "requested": len(ids),
            "executed": len(ok),
            "failed": len(failed),
            "items": ok,
            "errors": failed,
            "note": "仅写平台 identity 主档，不写 HIS/ODS/HRP",
        }
    )


@router.patch(
    "/sync-diffs/{diff_id}",
    summary="Update identity sync diff status",
    dependencies=[Depends(require_permission("identity.sync.run"))],
)
def update_sync_diff(
    diff_id: int,
    req: IdentitySyncDiffUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    if req.status not in {"open", "resolved", "ignored"}:
        raise HTTPException(status_code=400, detail="status must be open/resolved/ignored")
    diff = db.get(IdentitySyncDiff, diff_id)
    if not diff:
        raise HTTPException(status_code=404, detail="sync diff not found")

    before = {"status": diff.status, "handled_at": diff.handled_at.isoformat() if diff.handled_at else None}
    diff.status = req.status
    diff.handled_at = None if req.status == "open" else datetime.now(timezone.utc)
    db.add(GovernAuditLog(
        module="identity",
        entity_type="sync_diff",
        entity_ref=str(diff.id),
        action="update_status",
        before_data=before,
        after_data={"status": diff.status, "handled_at": diff.handled_at.isoformat() if diff.handled_at else None},
        operator=current_user,
        reason=req.note,
    ))
    db.commit()
    return ApiResponse(data={
        "id": diff.id,
        "status": diff.status,
        "handled_at": diff.handled_at.isoformat() if diff.handled_at else None,
    })

@router.get("/inconsistencies", summary="身份数据不一致列表")
def list_inconsistencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(IdentitySyncDiff).where(IdentitySyncDiff.status == "open")
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(IdentitySyncDiff.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "diff_type": r.diff_type, "source_system": r.source_system,
            "target_system": r.target_system, "entity_type": r.entity_type,
            "entity_code": r.entity_code, "severity": r.severity, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


