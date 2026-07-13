import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import get_current_user
from ...models.governance_base import GovernAuditLog
from ...models.ops_tool import OpsToolRun, OpsToolTemplate
from ...schemas.common import ApiResponse
from ...services.data_masking import mask_sensitive
from ...services.ops_executor import execute_whitelist_dml
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
        "max_affected_rows": int(write_config.get("max_affected_rows", 100) or 100),
        "write_credential_ref": write_config.get("write_credential_ref"),
        "require_approval": bool(r.require_approval),
        "require_second_confirm": bool(r.require_second_confirm),
        "enabled": bool(r.enabled),
        "description_cn": r.description_cn,
        "rollback_note_cn": r.rollback_note_cn,
    }


@router.get("/tools", summary="Ops tool template list")
def list_tools(
    tool_type: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(OpsToolTemplate)
    if tool_type:
        stmt = stmt.where(OpsToolTemplate.tool_type == tool_type)
    rows = db.scalars(stmt.order_by(OpsToolTemplate.tool_code)).all()
    return ApiResponse(data=[_tool_payload(r) for r in rows])


@router.put("/tools", summary="Create or update ops tool template")
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(OpsToolRun)
    status_filter = status or approval_status
    if status_filter:
        stmt = stmt.where(OpsToolRun.approval_status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
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
        raise HTTPException(status_code=400, detail=f"dry_run failed: {e}")
    return ApiResponse(data={"id": run.id, "status": "dry_run", **dry_result})


@router.post("/runs/{run_id}/execute", summary="Execute approved ops run")
def execute_run(run_id: int, request: Request, body: ExecuteBody = ExecuteBody(), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    run = db.get(OpsToolRun, run_id)
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
            raise HTTPException(status_code=400, detail=f"dry_run failed: {e}")
        return ApiResponse(data={"id": run.id, "status": "dry_run", **dry_result})

    start_time = datetime.now(timezone.utc)
    run.approval_status = "executing"
    run.started_at = start_time
    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run_id),
        action="execute_start",
        operator=current_user,
        after_data={"execution_mode": tool.execution_mode},
    ))
    db.commit()
    try:
        if tool.execution_mode == "whitelist_dml":
            exec_result = execute_whitelist_dml(tool, run, db, executed_by=current_user)
        else:
            exec_result = executor(tool, run, db)
    except ValueError as e:
        db.rollback()
        run = db.get(OpsToolRun, run_id)
        if run:
            run.approval_status = "failed"
            run.execution_summary = f"execution rejected: {e}"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=400, detail=f"execute rejected: {e}")
    except Exception as e:
        db.rollback()
        run = db.get(OpsToolRun, run_id)
        if run:
            run.approval_status = "failed"
            run.execution_summary = f"execution failed: {e}"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=500, detail=f"execute failed: {e}")

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
