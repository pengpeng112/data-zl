import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

import hashlib
import uuid
from datetime import timedelta

from ...core.config import settings
from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.asset_system import AssetDataSource
from ...models.governance_base import GovernAuditLog
from ...models.ops_tool import OpsEventLog, OpsToolRun, OpsToolTemplate
from ...schemas.common import ApiResponse
from ...services.data_masking import mask_sensitive, sanitize_text
from ...services.ops_event_log import log_event
from ...services.ops_executor import execute_whitelist_dml, sql_template_hash
from ...services.ops_sql_safety import validate_dry_run_sql, validate_writable_sql
from ...services.quality_rule_engine import validate_sql_safety

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])


EXECUTOR_DISPATCH = {
    "readonly_sql": lambda tool, run, db: _exec_readonly(tool, run, db),
    "stored_procedure": lambda tool, run, db: _exec_stored_procedure(tool, run, db),
    "http_api": lambda tool, run, db: _exec_http_api(tool, run, db),
    "whitelist_dml": lambda tool, run, db: execute_whitelist_dml(tool, run, db),
}


OPS_WRITE_CONFIG_KEY = "__ops_write_config__"


def _write_config_from_schema(input_schema: dict | None) -> dict:
    if not isinstance(input_schema, dict):
        return {}
    config = input_schema.get(OPS_WRITE_CONFIG_KEY) or {}
    return dict(config) if isinstance(config, dict) else {}


def _merge_write_config(input_schema: dict | None, req: "ToolUpsert") -> dict:
    schema = dict(input_schema or {})
    schema[OPS_WRITE_CONFIG_KEY] = {
        "allowed_tables": req.allowed_tables or [],
        "allowed_operations": req.allowed_operations or [],
        "require_audit": bool(req.require_audit),
        "dry_run_sql": req.dry_run_sql,
        "max_affected_rows": req.max_affected_rows,
        "write_credential_ref": req.write_credential_ref,
    }
    return schema


def _exec_readonly(tool, run, db):
    if tool.source_code not in (None, "", "asset", "ASSET_PLATFORM"):
        raise ValueError("readonly_sql currently supports platform database only")
    sql = (tool.sql_or_endpoint_ref or "").strip()
    if not sql:
        raise ValueError("readonly_sql requires sql_or_endpoint_ref")
    validation = validate_sql_safety(sql, db_type="postgresql")
    if not validation.get("valid"):
        raise ValueError("; ".join(validation.get("errors") or []))

    params = dict(run.input_params_masked or {})
    max_rows = int(params.pop("max_rows", 100) or 100)
    max_rows = max(1, min(max_rows, 1000))
    result = db.execute(text(sql), params)
    rows = [dict(row._mapping) for row in result.fetchmany(max_rows)]
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run.id),
        action="execute_readonly_sql",
        operator=run.requested_by,
        after_data={
            "tool_code": tool.tool_code,
            "row_count": len(rows),
            "max_rows": max_rows,
            "warnings": validation.get("warnings") or [],
        },
    ))
    return {
        "result": "readonly_sql executed",
        "row_count": len(rows),
        "rows": rows,
        "risk_scan": validation,
    }


def _exec_stored_procedure(tool, run, db):
    raise ValueError("stored_procedure execution is disabled in phase 1")


def _exec_http_api(tool, run, db):
    raise ValueError("http_api execution is disabled in phase 1")


class ToolUpsert(BaseModel):
    tool_code: str
    tool_name_cn: str
    system_code: str
    source_code: str | None = None
    tool_type: str
    risk_level: str | None = "medium"
    input_schema: dict = Field(default_factory=dict, description="frontend form schema")
    execution_mode: str
    sql_or_endpoint_ref: str | None = None
    allowed_tables: list[str] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=list)
    require_audit: bool = True
    dry_run_sql: str | None = None
    max_affected_rows: int = 100
    write_credential_ref: str | None = None
    require_approval: bool = True
    require_second_confirm: bool = True
    enabled: bool = False
    description_cn: str | None = None
    rollback_note_cn: str | None = None


class ToolRunRequest(BaseModel):
    tool_code: str
    input_params: dict | None = None


class SubmitBody(BaseModel):
    note: str | None = None


class ApproveBody(BaseModel):
    note: str | None = None


class ExecuteBody(BaseModel):
    second_confirm: bool = False
    dry_run: bool = False


def _tool_payload(r: OpsToolTemplate) -> dict:
    write_config = _write_config_from_schema(r.input_schema)
    max_rows = getattr(r, "max_affected_rows", None)
    if max_rows is None:
        max_rows = int(write_config.get("max_affected_rows", 100) or 100)
    return {
        "id": r.id,
        "tool_code": r.tool_code,
        "tool_name_cn": r.tool_name_cn,
        "system_code": r.system_code,
        "source_code": r.source_code,
        "tool_type": r.tool_type,
        "risk_level": r.risk_level,
        "input_schema": r.input_schema or {},
        "execution_mode": r.execution_mode,
        "sql_or_endpoint_ref": r.sql_or_endpoint_ref,
        "allowed_tables": write_config.get("allowed_tables") or [],
        "allowed_operations": write_config.get("allowed_operations") or [],
        "require_audit": bool(write_config.get("require_audit", True)),
        "dry_run_sql": write_config.get("dry_run_sql"),
        "max_affected_rows": min(int(max_rows or 100), 100),
        "write_credential_ref": write_config.get("write_credential_ref"),
        "require_approval": bool(r.require_approval),
        "require_second_confirm": bool(r.require_second_confirm),
        "enabled": bool(r.enabled),
        "description_cn": r.description_cn,
        "rollback_note_cn": r.rollback_note_cn,
        "version": getattr(r, "version", 1) or 1,
        "status": getattr(r, "status", None) or ("approved" if r.enabled else "draft"),
        "sql_hash": getattr(r, "sql_hash", None),
        "created_by": getattr(r, "created_by", None),
        "updated_by": getattr(r, "updated_by", None),
        "reviewed_by": getattr(r, "reviewed_by", None),
        "reviewed_at": r.reviewed_at.isoformat() if getattr(r, "reviewed_at", None) else None,
        "target_scope": getattr(r, "target_scope", None) or "platform_asset",
        "immutable_after_approval": bool(getattr(r, "immutable_after_approval", True)),
        "ops_write_enabled": bool(getattr(settings, "ops_write_enabled", False)),
    }


@router.get("/tools", summary="Ops tool template list")
def list_tools(
    tool_type: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(OpsToolTemplate)
    if tool_type:
        stmt = stmt.where(OpsToolTemplate.tool_type == tool_type)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(OpsToolTemplate.tool_code.ilike(like) | OpsToolTemplate.tool_name_cn.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(OpsToolTemplate.tool_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": [_tool_payload(r) for r in rows]})


@router.put("/tools", summary="Create or update ops tool template", dependencies=[Depends(require_permission("ops.tool.manage"))])
def upsert_tool(req: ToolUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == req.tool_code))
    input_schema = _merge_write_config(req.input_schema, req)
    if existing:
        existing.tool_name_cn = req.tool_name_cn
        existing.system_code = req.system_code
        existing.source_code = req.source_code
        existing.tool_type = req.tool_type
        existing.risk_level = req.risk_level or "medium"
        existing.input_schema = input_schema
        existing.execution_mode = req.execution_mode
        existing.sql_or_endpoint_ref = req.sql_or_endpoint_ref
        existing.require_approval = req.require_approval
        existing.require_second_confirm = req.require_second_confirm
        existing.enabled = req.enabled
        existing.description_cn = req.description_cn
        existing.rollback_note_cn = req.rollback_note_cn
        existing.updated_at = datetime.now(timezone.utc)
        tool = existing
    else:
        tool = OpsToolTemplate(
            tool_code=req.tool_code,
            tool_name_cn=req.tool_name_cn,
            system_code=req.system_code,
            source_code=req.source_code,
            tool_type=req.tool_type,
            risk_level=req.risk_level or "medium",
            input_schema=input_schema,
            execution_mode=req.execution_mode,
            sql_or_endpoint_ref=req.sql_or_endpoint_ref,
            require_approval=req.require_approval,
            require_second_confirm=req.require_second_confirm,
            enabled=req.enabled,
            description_cn=req.description_cn,
            rollback_note_cn=req.rollback_note_cn,
        )
        db.add(tool)
    db.commit()
    db.refresh(tool)
    return ApiResponse(data={"id": tool.id, "tool_code": tool.tool_code})


@router.post("/runs", summary="Create ops run request")
def create_run(req: ToolRunRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == req.tool_code))
    if not tool or not tool.enabled:
        raise HTTPException(status_code=400, detail="tool does not exist or is disabled")
    run = OpsToolRun(
        tool_code=req.tool_code,
        requested_by=current_user,
        input_params_masked=mask_sensitive(req.input_params or {}),
    )
    db.add(run)
    db.flush()
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run.id),
        action="create",
        operator=current_user,
        after_data={"tool_code": req.tool_code, "input_params_masked": run.input_params_masked},
    ))
    db.commit()
    db.refresh(run)
    return ApiResponse(data={"id": run.id, "approval_status": run.approval_status})


@router.post("/runs/{run_id}/submit", summary="Submit ops run for approval")
def submit_run(run_id: int, request: Request, req: SubmitBody = SubmitBody(), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    if run.approval_status != "draft":
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot be submitted")
    run.approval_status = "submitted"
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run_id),
        action="submit",
        operator=current_user,
        reason=req.note,
    ))
    db.commit()
    return ApiResponse(data={"id": run.id, "approval_status": "submitted"})


@router.post("/runs/{run_id}/approve", summary="Approve ops run")
@router.patch("/runs/{run_id}/approve", summary="Approve ops run")
def approve_run(run_id: int, req: ApproveBody, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    if run.approval_status not in ("submitted", "pending"):
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot be approved")
    if current_user == run.requested_by:
        raise HTTPException(status_code=400, detail="approver and requester cannot be the same user")
    run.approval_status = "approved"
    run.approved_by = current_user
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run_id),
        action="approve",
        operator=current_user,
        reason=req.note,
    ))
    db.commit()
    return ApiResponse(data={"id": run.id, "approval_status": "approved"})


@router.get("/runs", summary="Ops run list")
def list_runs(
    status: str | None = Query(None),
    approval_status: str | None = Query(None),
    run_id: int | None = Query(None, description="定位指定 run 所在页（146 E7）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(OpsToolRun)
    status_filter = status or approval_status
    if status_filter:
        stmt = stmt.where(OpsToolRun.approval_status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if run_id:
        target = db.get(OpsToolRun, run_id)
        if target:
            newer = db.scalar(
                select(func.count()).select_from(stmt.where(OpsToolRun.created_at > target.created_at, OpsToolRun.id != run_id).subquery())
            ) or 0
            page = newer // page_size + 1
    rows = db.scalars(
        stmt.order_by(OpsToolRun.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "tool_code": r.tool_code,
            "requested_by": r.requested_by,
            "approved_by": r.approved_by,
            "approval_status": r.approval_status,
            "affected_count": r.affected_count,
            "risk_scan": r.risk_scan,
            "execution_summary": r.execution_summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.post("/runs/{run_id}/reject", summary="Reject ops run")
@router.patch("/runs/{run_id}/reject", summary="Reject ops run")
def reject_run(run_id: int, req: ApproveBody, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    if run.approval_status not in ("submitted", "pending"):
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot be rejected")
    if current_user == run.requested_by:
        raise HTTPException(status_code=400, detail="approver and requester cannot be the same user")
    run.approval_status = "rejected"
    run.approved_by = current_user
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run_id),
        action="reject",
        operator=current_user,
        reason=req.note,
    ))
    db.commit()
    return ApiResponse(data={"id": run.id, "approval_status": "rejected"})


@router.post("/runs/{run_id}/dry-run", summary="Dry-run approved ops run")
def dry_run(run_id: int, request: Request, body: ExecuteBody = ExecuteBody(dry_run=True), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == run.tool_code))
    if not tool or not tool.enabled:
        raise HTTPException(status_code=400, detail="tool template does not exist or is disabled")
    if tool.execution_mode != "whitelist_dml":
        raise HTTPException(status_code=400, detail="dry_run only supports whitelist_dml")
    if run.approval_status != "approved":
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot dry-run; approval is required")
    try:
        dry_result = execute_whitelist_dml(tool, run, db, dry_run=True, executed_by=current_user)
        db.add(GovernAuditLog(
            module="ops",
            entity_type="ops_tool_run",
            entity_ref=str(run_id),
            action="dry_run",
            operator=current_user,
            after_data=dry_result,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"dry_run failed: {sanitize_text(str(e))}")
    return ApiResponse(data={"id": run.id, "status": "dry_run", **dry_result})


@router.post("/runs/{run_id}/execute", summary="Execute approved ops run")
def execute_run(run_id: int, request: Request, body: ExecuteBody = ExecuteBody(), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    # row lock prevents double-click / concurrent execute of the same run
    run = db.scalar(select(OpsToolRun).where(OpsToolRun.id == run_id).with_for_update())
    if not run:
        raise HTTPException(status_code=404)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == run.tool_code))
    if not tool or not tool.enabled:
        raise HTTPException(status_code=400, detail="tool template does not exist or is disabled")
    if run.approval_status in ("executing", "executed", "succeeded", "failed"):
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot execute again")
    if (tool.require_approval or tool.execution_mode == "whitelist_dml") and run.approval_status != "approved":
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot execute; approval is required")
    if tool.require_second_confirm and not body.second_confirm:
        raise HTTPException(status_code=400, detail="second confirmation is required")
    if tool.execution_mode == "whitelist_dml" and not body.dry_run:
        if (
            not getattr(settings, "ops_write_enabled", False)
            or not getattr(settings, "ops_write_d1_d5_confirmed", False)
            or getattr(settings, "ops_write_confirmation_token", "") != "D1-D5-CONFIRMED"
        ):
            raise HTTPException(
                status_code=403,
                detail="ops write execution is disabled until D1-D5 are confirmed and APP_OPS_WRITE_ENABLED/APP_OPS_WRITE_D1_D5_CONFIRMED are true and APP_OPS_WRITE_CONFIRMATION_TOKEN is D1-D5-CONFIRMED",
            )
    executor = EXECUTOR_DISPATCH.get(tool.execution_mode)
    if not executor:
        raise HTTPException(status_code=400, detail=f"unsupported execution mode: {tool.execution_mode}")

    if body.dry_run:
        if tool.execution_mode != "whitelist_dml":
            raise HTTPException(status_code=400, detail="dry_run only supports whitelist_dml")
        try:
            dry_result = execute_whitelist_dml(tool, run, db, dry_run=True, executed_by=current_user)
            run.preview_count = dry_result.get("estimated_count")
            db.add(GovernAuditLog(
                module="ops",
                entity_type="ops_tool_run",
                entity_ref=str(run_id),
                action="dry_run",
                operator=current_user,
                after_data=dry_result,
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"dry_run failed: {sanitize_text(str(e))}")
        return ApiResponse(data={"id": run.id, "status": "dry_run", **dry_result})

    # conditional transition approved -> executing (second guard against races)
    if run.approval_status != "approved":
        raise HTTPException(status_code=400, detail=f"status {run.approval_status} cannot execute")
    start_time = datetime.now(timezone.utc)
    run.approval_status = "executing"
    run.started_at = start_time
    run.template_version = getattr(tool, "version", None)
    run.sql_hash = getattr(tool, "sql_hash", None) or sql_template_hash(tool.sql_or_endpoint_ref or "")
    import uuid
    run.transaction_id = str(uuid.uuid4())
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run_id),
        action="execute_start",
        operator=current_user,
        after_data={
            "execution_mode": tool.execution_mode,
            "transaction_id": run.transaction_id,
            "sql_hash": run.sql_hash,
        },
    ))
    db.commit()
    try:
        # re-lock after commit for execute phase
        run = db.scalar(select(OpsToolRun).where(OpsToolRun.id == run_id).with_for_update())
        if not run or run.approval_status != "executing":
            raise HTTPException(status_code=409, detail="run execution state changed concurrently")
        if tool.execution_mode == "whitelist_dml":
            exec_result = execute_whitelist_dml(tool, run, db, executed_by=current_user)
        else:
            exec_result = executor(tool, run, db)
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        run = db.get(OpsToolRun, run_id)
        if run:
            run.approval_status = "failed"
            run.execution_summary = f"execution rejected: {e}"
            run.error_code = "rejected"
            run.error_summary_masked = str(e)[:300]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=400, detail=f"execute rejected: {sanitize_text(str(e))}")
    except Exception as e:
        db.rollback()
        run = db.get(OpsToolRun, run_id)
        if run:
            run.approval_status = "failed"
            run.execution_summary = f"execution failed: {e}"
            run.error_code = "failed"
            run.error_summary_masked = str(e)[:300]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=500, detail=f"execute failed: {sanitize_text(str(e))}")

    finish_time = datetime.now(timezone.utc)
    elapsed_ms = int((finish_time - start_time).total_seconds() * 1000)
    affected_count = exec_result.get("affected_count", 0) if isinstance(exec_result, dict) else 0
    run.approval_status = "succeeded"
    run.execution_summary = json.dumps(exec_result, ensure_ascii=False)
    run.affected_count = affected_count
    run.started_at = start_time
    run.finished_at = finish_time
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run_id),
        action="execute_success",
        operator=current_user,
        after_data={"affected_count": affected_count, "execution_mode": tool.execution_mode},
    ))
    db.commit()
    return ApiResponse(data={
        "id": run.id,
        "status": "succeeded",
        "elapsed_ms": elapsed_ms,
        "affected_count": affected_count,
        "execution_summary": run.execution_summary,
    })

@router.get("/runs/{run_id}/audit", summary="Get ops run audit logs")
def get_run_audit(run_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    logs = db.scalars(
        select(GovernAuditLog)
        .where(GovernAuditLog.entity_type == "ops_tool_run")
        .where(GovernAuditLog.entity_ref == str(run_id))
        .order_by(GovernAuditLog.created_at.asc())
    ).all()
    return ApiResponse(data=[
        {
            "id": l.id,
            "module": l.module,
            "entity_type": l.entity_type,
            "entity_ref": l.entity_ref,
            "action": l.action,
            "operator": l.operator,
            "reason": l.reason,
            "before_data": l.before_data,
            "after_data": l.after_data,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ])


# ── SQL 工作台（受控 INSERT/UPDATE；仅 platform asset schema）──


class SqlValidateBody(BaseModel):
    sql: str
    dry_run_sql: str | None = None
    allowed_tables: list[str] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=lambda: ["INSERT", "UPDATE"])
    params: dict | None = None


class SqlTemplateCreate(BaseModel):
    tool_code: str
    tool_name_cn: str
    sql: str
    dry_run_sql: str | None = None
    allowed_tables: list[str] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=lambda: ["INSERT", "UPDATE"])
    input_schema: dict = Field(default_factory=dict)
    max_affected_rows: int = 100
    description_cn: str | None = None
    rollback_note_cn: str | None = None
    risk_level: str = "high"
    write_credential_ref: str | None = None
    # plan 76: target database selection (write only platform)
    target_source_code: str = "asset"
    target_connection_id: int | None = None
    target_database_key: str | None = None
    target_schema: str = "asset"
    admin_publish: bool = True


class SqlTemplateReview(BaseModel):
    note: str | None = None


class SqlRunCreate(BaseModel):
    tool_code: str
    input_params: dict | None = None


@router.post("/sql/validate", summary="校验受控 SQL（不执行）", dependencies=[Depends(require_permission("ops:sql:view"))])
def sql_validate(req: SqlValidateBody) -> ApiResponse[dict]:
    scan = validate_writable_sql(
        req.sql,
        allowed_tables=req.allowed_tables or None,
        allowed_ops=req.allowed_operations,
        params=req.params or {},
    )
    # when allowed_tables empty, still parse for guidance
    if not req.allowed_tables and scan.get("parsed_summary"):
        target = scan["parsed_summary"].get("target_table")
        if target:
            scan = validate_writable_sql(
                req.sql,
                allowed_tables=[target],
                allowed_ops=req.allowed_operations,
                params=req.params or {p: 1 for p in (scan["parsed_summary"].get("param_names") or [])},
            )
    dry = None
    if req.dry_run_sql:
        dry = validate_dry_run_sql(req.sql, req.dry_run_sql, allowed_tables=req.allowed_tables)
    return ApiResponse(data={
        "valid": bool(scan.get("valid")) and (dry is None or dry.get("valid")),
        "risk_scan": scan,
        "dry_run_scan": dry,
        "scope": "platform_asset_only",
        "allowed_ops": ["INSERT", "UPDATE"],
        "forbidden": ["DELETE", "DDL", "business_source_write", "free_text_execute"],
        "ops_write_enabled": bool(getattr(settings, "ops_write_enabled", False)),
    })


def _assert_platform_write_target(req: SqlTemplateCreate, db: Session) -> tuple[str, str | None, int | None]:
    """Only platform asset may be write target. Returns (source_code, database_key, connection_id)."""
    source_code = (req.target_source_code or "asset").strip()
    if source_code not in {"asset", "ASSET_PLATFORM", "platform"}:
        # explicit business source rejection
        ds = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
        if ds and (ds.write_policy or "readonly") != "platform_controlled":
            raise HTTPException(status_code=403, detail="业务源库只读，禁止作为 INSERT/UPDATE 目标")
        if source_code not in {"asset", "ASSET_PLATFORM"}:
            raise HTTPException(status_code=403, detail="write templates only allow platform asset target")
    if req.target_schema and req.target_schema.lower() not in {"asset", ""}:
        raise HTTPException(status_code=400, detail="target_schema must be asset")
    db_key = req.target_database_key or "postgresql://platform/database/data_asset"
    return "asset", db_key, req.target_connection_id


@router.post("/sql/templates", summary="保存 SQL 模板（管理员可直接发布）", dependencies=[Depends(require_permission("ops:sql:create"))])
def sql_create_template(req: SqlTemplateCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    if not req.target_source_code:
        raise HTTPException(status_code=400, detail="target database is required")
    target_source, target_db_key, target_conn_id = _assert_platform_write_target(req, db)
    max_rows = max(1, min(int(req.max_affected_rows or 100), 100))
    import re as _re
    param_guess = _re.findall(r"(?<!:):([A-Za-z_]\w*)", req.sql or "")
    preview = validate_writable_sql(
        req.sql,
        allowed_tables=req.allowed_tables or ["asset.__placeholder__"],
        allowed_ops=req.allowed_operations or ["INSERT", "UPDATE"],
        params={p: 1 for p in param_guess},
    )
    parsed = preview.get("parsed_summary") or {}
    tables = req.allowed_tables or ([parsed["target_table"]] if parsed.get("target_table") else [])
    scan = validate_writable_sql(
        req.sql,
        allowed_tables=tables,
        allowed_ops=req.allowed_operations or ["INSERT", "UPDATE"],
        params={p: 1 for p in (parsed.get("param_names") or [])},
    )
    if not scan["valid"]:
        raise HTTPException(status_code=400, detail="; ".join(scan["errors"]))
    dry_run_sql = req.dry_run_sql
    if not dry_run_sql and parsed.get("operation") == "UPDATE" and parsed.get("where_summary"):
        dry_run_sql = f"SELECT count(*) FROM {parsed['target_table']} WHERE {parsed['where_summary']}"
    if dry_run_sql:
        dry = validate_dry_run_sql(req.sql, dry_run_sql, allowed_tables=tables)
        if not dry["valid"]:
            raise HTTPException(status_code=400, detail="; ".join(dry["errors"]))

    existing = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == req.tool_code))
    sql_hash = sql_template_hash(req.sql)
    input_schema = dict(req.input_schema or {})
    input_schema[OPS_WRITE_CONFIG_KEY] = {
        "allowed_tables": tables,
        "allowed_operations": req.allowed_operations or ["INSERT", "UPDATE"],
        "require_audit": True,
        "dry_run_sql": dry_run_sql,
        "max_affected_rows": max_rows,
        "write_credential_ref": req.write_credential_ref,
    }
    admin_mode = (not getattr(settings, "ops_approval_ui_enabled", True)) and req.admin_publish
    publish = bool(admin_mode)

    if existing:
        status = getattr(existing, "status", None) or ("approved" if existing.enabled else "draft")
        if status == "approved" and bool(getattr(existing, "immutable_after_approval", True)) and not publish:
            raise HTTPException(
                status_code=400,
                detail="approved template is immutable; create a new tool_code version for changes",
            )
        if status == "approved" and publish:
            # admin republish: bump version
            existing.version = int(getattr(existing, "version", 1) or 1) + 1
        existing.tool_name_cn = req.tool_name_cn
        existing.sql_or_endpoint_ref = req.sql
        existing.input_schema = input_schema
        existing.max_affected_rows = max_rows
        existing.sql_hash = sql_hash
        existing.updated_by = operator
        existing.updated_at = datetime.now(timezone.utc)
        existing.description_cn = req.description_cn
        existing.rollback_note_cn = req.rollback_note_cn
        existing.risk_level = req.risk_level or "high"
        existing.target_source_code = target_source
        existing.target_database_key = target_db_key
        existing.target_connection_id = target_conn_id
        existing.target_schema = req.target_schema or "asset"
        existing.target_scope = "platform_asset"
        if publish:
            existing.status = "approved"
            existing.enabled = True
            existing.reviewed_by = operator
            existing.reviewed_at = datetime.now(timezone.utc)
        else:
            existing.status = "draft"
            existing.enabled = False
        tool = existing
    else:
        tool = OpsToolTemplate(
            tool_code=req.tool_code,
            tool_name_cn=req.tool_name_cn,
            system_code="ASSET_PLATFORM",
            source_code=target_source,
            tool_type="sql_workbench",
            risk_level=req.risk_level or "high",
            input_schema=input_schema,
            execution_mode="whitelist_dml",
            sql_or_endpoint_ref=req.sql,
            require_approval=not publish,
            require_second_confirm=True,
            enabled=publish,
            description_cn=req.description_cn,
            rollback_note_cn=req.rollback_note_cn,
            version=1,
            status="approved" if publish else "draft",
            sql_hash=sql_hash,
            created_by=operator,
            updated_by=operator,
            reviewed_by=operator if publish else None,
            reviewed_at=datetime.now(timezone.utc) if publish else None,
            max_affected_rows=max_rows,
            target_scope="platform_asset",
            immutable_after_approval=True,
            target_source_code=target_source,
            target_database_key=target_db_key,
            target_connection_id=target_conn_id,
            target_schema=req.target_schema or "asset",
        )
        db.add(tool)
    action = "admin_publish" if publish else "create_or_update_draft"
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_sql_template",
        entity_ref=req.tool_code,
        action=action,
        operator=operator,
        after_data={
            "sql_hash": sql_hash,
            "tables": tables,
            "max_affected_rows": max_rows,
            "target_source_code": target_source,
            "target_database_key": target_db_key,
            "status": tool.status,
        },
    ))
    log_event(
        db,
        module="ops",
        entity_type="ops_sql_template",
        entity_ref=req.tool_code,
        action=action,
        operator=operator,
        status=tool.status,
        target_source_code=target_source,
        target_database_key=target_db_key,
        summary_masked=f"{action} {req.tool_code}",
        detail={"sql_hash": sql_hash, "tables": tables},
    )
    db.commit()
    db.refresh(tool)
    payload = _tool_payload(tool)
    payload["approval_ui_enabled"] = bool(getattr(settings, "ops_approval_ui_enabled", False))
    return ApiResponse(data=payload)


@router.post("/sql/templates/{tool_code}/submit", summary="提交 SQL 模板审批", dependencies=[Depends(require_permission("ops:sql:create"))])
def sql_submit_template(tool_code: str, req: SqlTemplateReview, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == tool_code))
    if not tool:
        raise HTTPException(status_code=404)
    if (getattr(tool, "status", None) or "draft") not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail=f"status {tool.status} cannot submit")
    tool.status = "pending_review"
    tool.updated_by = operator
    tool.updated_at = datetime.now(timezone.utc)
    db.add(GovernAuditLog(
        module="ops", entity_type="ops_sql_template", entity_ref=tool_code,
        action="submit", operator=operator, reason=req.note,
    ))
    db.commit()
    return ApiResponse(data=_tool_payload(tool))


@router.post("/sql/templates/{tool_code}/approve", summary="审批通过 SQL 模板", dependencies=[Depends(require_permission("ops:sql:review"))])
def sql_approve_template(tool_code: str, req: SqlTemplateReview, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == tool_code))
    if not tool:
        raise HTTPException(status_code=404)
    if (getattr(tool, "status", None) or "") != "pending_review":
        raise HTTPException(status_code=400, detail=f"status {tool.status} cannot approve")
    if operator == getattr(tool, "created_by", None) or operator == getattr(tool, "updated_by", None):
        # self-review ban: creator cannot approve
        if operator == tool.created_by:
            raise HTTPException(status_code=400, detail="creator cannot approve own template")
    tool.status = "approved"
    tool.enabled = True
    tool.reviewed_by = operator
    tool.reviewed_at = datetime.now(timezone.utc)
    db.add(GovernAuditLog(
        module="ops", entity_type="ops_sql_template", entity_ref=tool_code,
        action="approve", operator=operator, reason=req.note,
    ))
    db.commit()
    return ApiResponse(data=_tool_payload(tool))


@router.post("/sql/templates/{tool_code}/reject", summary="驳回 SQL 模板", dependencies=[Depends(require_permission("ops:sql:review"))])
def sql_reject_template(tool_code: str, req: SqlTemplateReview, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == tool_code))
    if not tool:
        raise HTTPException(status_code=404)
    if operator == tool.created_by:
        raise HTTPException(status_code=400, detail="creator cannot reject own template")
    tool.status = "rejected"
    tool.enabled = False
    tool.reviewed_by = operator
    tool.reviewed_at = datetime.now(timezone.utc)
    db.add(GovernAuditLog(
        module="ops", entity_type="ops_sql_template", entity_ref=tool_code,
        action="reject", operator=operator, reason=req.note,
    ))
    db.commit()
    return ApiResponse(data=_tool_payload(tool))


@router.post("/sql/runs", summary="基于模板创建运维 run", dependencies=[Depends(require_permission("ops:sql:execute"))])
def sql_create_run(req: SqlRunCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == req.tool_code))
    if not tool or not tool.enabled:
        raise HTTPException(status_code=400, detail="tool does not exist or is disabled")
    if getattr(tool, "status", None) not in (None, "approved"):
        raise HTTPException(status_code=400, detail="tool template is not approved")
    # re-validate write target snapshot is still platform
    if (getattr(tool, "target_source_code", None) or tool.source_code or "asset") not in {
        "asset", "ASSET_PLATFORM", "platform", None, "",
    }:
        raise HTTPException(status_code=403, detail="template target is not platform asset")
    if (getattr(tool, "target_scope", None) or "platform_asset") != "platform_asset":
        raise HTTPException(status_code=403, detail="template target_scope must be platform_asset")

    admin_mode = not getattr(settings, "ops_approval_ui_enabled", True)
    correlation_id = str(uuid.uuid4())
    params_masked = mask_sensitive(req.input_params or {})
    params_hash = hashlib.sha256(
        json.dumps(params_masked, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    run = OpsToolRun(
        tool_code=req.tool_code,
        requested_by=current_user,
        input_params_masked=params_masked,
        template_version=getattr(tool, "version", 1),
        sql_hash=getattr(tool, "sql_hash", None) or sql_template_hash(tool.sql_or_endpoint_ref or ""),
        # admin simplified: ready for preview without run approval
        approval_status="ready_for_preview" if admin_mode else "draft",
        target_connection_id=getattr(tool, "target_connection_id", None),
        target_source_code=getattr(tool, "target_source_code", None) or tool.source_code or "asset",
        target_database_key=getattr(tool, "target_database_key", None),
        target_schema=getattr(tool, "target_schema", None) or "asset",
        correlation_id=correlation_id,
        preview_params_hash=params_hash,
    )
    db.add(run)
    db.flush()
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run.id),
        action="create",
        operator=current_user,
        after_data={
            "tool_code": req.tool_code,
            "template_version": run.template_version,
            "sql_hash": run.sql_hash,
            "input_params_masked": run.input_params_masked,
            "approval_status": run.approval_status,
            "correlation_id": correlation_id,
            "target_source_code": run.target_source_code,
        },
    ))
    log_event(
        db,
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run.id),
        action="create",
        operator=current_user,
        status=run.approval_status,
        target_source_code=run.target_source_code,
        target_database_key=run.target_database_key,
        correlation_id=correlation_id,
        summary_masked=f"run created for {req.tool_code}",
    )
    db.commit()
    db.refresh(run)
    return ApiResponse(data={
        "id": run.id,
        "approval_status": run.approval_status,
        "template_version": run.template_version,
        "sql_hash": run.sql_hash,
        "correlation_id": correlation_id,
        "target_source_code": run.target_source_code,
        "ops_write_enabled": bool(getattr(settings, "ops_write_enabled", False)),
        "approval_ui_enabled": bool(getattr(settings, "ops_approval_ui_enabled", False)),
        "task_path": f"/ops/runs?run_id={run.id}",
    })


@router.post("/sql/runs/{run_id}/preview", summary="dry-run 影响行预览", dependencies=[Depends(require_permission("ops:sql:execute"))])
def sql_preview_run(run_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == run.tool_code))
    if not tool:
        raise HTTPException(status_code=400, detail="tool missing")
    try:
        dry_result = execute_whitelist_dml(tool, run, db, dry_run=True, executed_by=current_user)
        run.preview_count = dry_result.get("estimated_count")
        # after successful preview, admin-mode runs become approved for second-confirm execute
        if run.approval_status in {"ready_for_preview", "draft"} and not getattr(settings, "ops_approval_ui_enabled", True):
            run.approval_status = "approved"
            run.approved_by = "system:admin_mode"
            run.confirmation_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.add(GovernAuditLog(
            module="ops", entity_type="ops_tool_run", entity_ref=str(run_id),
            action="preview", operator=current_user, after_data=dry_result,
        ))
        log_event(
            db,
            module="ops",
            entity_type="ops_tool_run",
            entity_ref=str(run_id),
            action="preview",
            operator=current_user,
            status="previewed",
            target_source_code=run.target_source_code,
            target_database_key=run.target_database_key,
            correlation_id=run.correlation_id,
            affected_count=dry_result.get("estimated_count"),
            summary_masked=f"preview estimated={dry_result.get('estimated_count')}",
            detail={"sql_template_hash": dry_result.get("sql_template_hash")},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"preview failed: {sanitize_text(str(e))}")
    return ApiResponse(data={
        "id": run.id,
        "status": "preview",
        "approval_status": run.approval_status,
        "confirmation_expires_at": run.confirmation_expires_at.isoformat() if run.confirmation_expires_at else None,
        "task_path": f"/ops/runs?run_id={run.id}",
        **dry_result,
    })


@router.get("/sql/runs", summary="SQL 工作台任务列表", dependencies=[Depends(require_permission("ops:sql:view"))])
def sql_list_runs(
    status: str | None = Query(None),
    tool_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(OpsToolRun)
    if status:
        stmt = stmt.where(OpsToolRun.approval_status == status)
    if tool_code:
        stmt = stmt.where(OpsToolRun.tool_code == tool_code)
    # prefer workbench tools but do not exclude others when filtering
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(OpsToolRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "tool_code": r.tool_code,
            "requested_by": r.requested_by,
            "approved_by": r.approved_by,
            "approval_status": r.approval_status,
            "affected_count": r.affected_count,
            "preview_count": r.preview_count,
            "target_source_code": r.target_source_code,
            "target_database_key": r.target_database_key,
            "sql_hash": r.sql_hash,
            "template_version": r.template_version,
            "correlation_id": r.correlation_id,
            "error_code": r.error_code,
            "error_summary_masked": r.error_summary_masked,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/sql/runs/{run_id}", summary="SQL run 详情", dependencies=[Depends(require_permission("ops:sql:view"))])
def sql_get_run(run_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    events = db.scalars(
        select(OpsEventLog)
        .where(OpsEventLog.entity_type == "ops_tool_run", OpsEventLog.entity_ref == str(run_id))
        .order_by(OpsEventLog.created_at.asc())
    ).all()
    return ApiResponse(data={
        "id": run.id,
        "tool_code": run.tool_code,
        "requested_by": run.requested_by,
        "approved_by": run.approved_by,
        "approval_status": run.approval_status,
        "input_params_masked": run.input_params_masked,
        "affected_count": run.affected_count,
        "preview_count": run.preview_count,
        "risk_scan": run.risk_scan,
        "execution_summary": run.execution_summary,
        "sql_hash": run.sql_hash,
        "template_version": run.template_version,
        "target_source_code": run.target_source_code,
        "target_database_key": run.target_database_key,
        "target_schema": run.target_schema,
        "correlation_id": run.correlation_id,
        "error_code": run.error_code,
        "error_summary_masked": run.error_summary_masked,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "timeline": [
            {
                "event_id": e.event_id,
                "action": e.action,
                "status": e.status,
                "operator": e.operator,
                "summary_masked": e.summary_masked,
                "affected_count": e.affected_count,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    })


@router.get("/events", summary="统一运维事件流", dependencies=[Depends(require_permission("ops:sql:audit"))])
def list_ops_events(
    module: str | None = Query(None),
    action: str | None = Query(None),
    correlation_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(OpsEventLog)
    if module:
        stmt = stmt.where(OpsEventLog.module == module)
    if action:
        stmt = stmt.where(OpsEventLog.action == action)
    if correlation_id:
        stmt = stmt.where(OpsEventLog.correlation_id == correlation_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(OpsEventLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApiResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "event_id": r.event_id,
                "module": r.module,
                "entity_type": r.entity_type,
                "entity_ref": r.entity_ref,
                "action": r.action,
                "status": r.status,
                "operator": r.operator,
                "target_source_code": r.target_source_code,
                "target_database_key": r.target_database_key,
                "correlation_id": r.correlation_id,
                "batch_code": r.batch_code,
                "affected_count": r.affected_count,
                "duration_ms": r.duration_ms,
                "error_code": r.error_code,
                "summary_masked": r.summary_masked,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    })


@router.get("/events/{event_id}", summary="事件详情", dependencies=[Depends(require_permission("ops:sql:audit"))])
def get_ops_event(event_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.scalar(select(OpsEventLog).where(OpsEventLog.event_id == event_id))
    if not row:
        raise HTTPException(status_code=404)
    return ApiResponse(data={
        "event_id": row.event_id,
        "module": row.module,
        "entity_type": row.entity_type,
        "entity_ref": row.entity_ref,
        "action": row.action,
        "status": row.status,
        "operator": row.operator,
        "target_source_code": row.target_source_code,
        "target_database_key": row.target_database_key,
        "correlation_id": row.correlation_id,
        "batch_code": row.batch_code,
        "affected_count": row.affected_count,
        "duration_ms": row.duration_ms,
        "error_code": row.error_code,
        "summary_masked": row.summary_masked,
        "detail": row.detail,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    })


@router.get("/config", summary="运维前端配置（审批 UI / 写开关状态）")
def ops_config() -> ApiResponse[dict]:
    return ApiResponse(data={
        "ops_write_enabled": bool(getattr(settings, "ops_write_enabled", False)),
        "ops_approval_ui_enabled": bool(getattr(settings, "ops_approval_ui_enabled", False)),
        "write_scope": "platform_asset_only",
    })
