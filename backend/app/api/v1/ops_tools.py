import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.governance_base import GovernAuditLog
from ...models.ops_tool import OpsToolRun, OpsToolTemplate
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])


EXECUTOR_DISPATCH = {
    "readonly_sql": lambda tool, run, db: _exec_readonly(tool, run, db),
    "stored_procedure": lambda tool, run, db: _exec_stored_procedure(tool, run, db),
    "http_api": lambda tool, run, db: _exec_http_api(tool, run, db),
}


def _exec_readonly(tool, run, db):
    return {"result": "readonly query executed (placeholder)", "note": f"sql_ref={tool.sql_or_endpoint_ref}"}


def _exec_stored_procedure(tool, run, db):
    return {"result": "stored procedure called (placeholder)", "note": f"sp_ref={tool.sql_or_endpoint_ref}"}


def _exec_http_api(tool, run, db):
    return {"result": "http api called (placeholder)", "note": f"endpoint_ref={tool.sql_or_endpoint_ref}"}


class ToolUpsert(BaseModel):
    tool_code: str
    tool_name_cn: str
    system_code: str
    source_code: str | None = None
    tool_type: str
    risk_level: str | None = "medium"
    input_schema: dict = Field(default_factory=dict, description="前端表单字段定义")
    execution_mode: str
    sql_or_endpoint_ref: str | None = None
    require_approval: bool = True
    require_second_confirm: bool = True
    enabled: bool = False
    description_cn: str | None = None
    rollback_note_cn: str | None = None


class ToolRunRequest(BaseModel):
    tool_code: str
    requested_by: str
    input_params: dict | None = None


class ApproveBody(BaseModel):
    approved_by: str
    note: str | None = None


class ExecuteBody(BaseModel):
    second_confirm: bool = False


@router.get("/tools", summary="运维工具模板列表")
def list_tools(
    tool_type: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(OpsToolTemplate)
    if tool_type:
        stmt = stmt.where(OpsToolTemplate.tool_type == tool_type)
    rows = db.scalars(stmt.order_by(OpsToolTemplate.tool_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "tool_code": r.tool_code, "tool_name_cn": r.tool_name_cn,
            "tool_type": r.tool_type, "risk_level": r.risk_level,
            "execution_mode": r.execution_mode,
            "require_approval": r.require_approval, "enabled": r.enabled,
        }
        for r in rows
    ])


@router.put("/tools", summary="新增/更新运维工具模板")
def upsert_tool(req: ToolUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == req.tool_code))
    if existing:
        existing.tool_name_cn = req.tool_name_cn
        existing.tool_type = req.tool_type
        existing.risk_level = req.risk_level or "medium"
        existing.input_schema = req.input_schema
        existing.execution_mode = req.execution_mode
        existing.sql_or_endpoint_ref = req.sql_or_endpoint_ref
        existing.require_approval = req.require_approval
        existing.require_second_confirm = req.require_second_confirm
        existing.enabled = req.enabled
        existing.description_cn = req.description_cn
        existing.rollback_note_cn = req.rollback_note_cn
        existing.updated_at = datetime.now(timezone.utc)
        t = existing
    else:
        t = OpsToolTemplate(
            tool_code=req.tool_code, tool_name_cn=req.tool_name_cn,
            system_code=req.system_code, source_code=req.source_code,
            tool_type=req.tool_type, risk_level=req.risk_level or "medium",
            input_schema=req.input_schema, execution_mode=req.execution_mode,
            sql_or_endpoint_ref=req.sql_or_endpoint_ref,
            require_approval=req.require_approval,
            require_second_confirm=req.require_second_confirm,
            enabled=req.enabled, description_cn=req.description_cn,
            rollback_note_cn=req.rollback_note_cn,
        )
        db.add(t)
    db.commit()
    db.refresh(t)
    return ApiResponse(data={"id": t.id, "tool_code": t.tool_code})


@router.post("/runs", summary="创建运维操作申请")
def create_run(req: ToolRunRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == req.tool_code))
    if not tool or not tool.enabled:
        raise HTTPException(status_code=400, detail="工具不存在或未启用")
    run = OpsToolRun(
        tool_code=req.tool_code,
        requested_by=req.requested_by,
        input_params_masked=req.input_params,
    )
    db.add(run)
    db.flush()
    audit = GovernAuditLog(
        module="ops", entity_type="ops_tool_run", entity_ref=str(run.id),
        action="create", operator=req.requested_by,
    )
    db.add(audit)
    db.commit()
    db.refresh(run)
    return ApiResponse(data={"id": run.id, "approval_status": run.approval_status})


@router.patch("/runs/{run_id}/approve", summary="审批运维任务")

def approve_run(run_id: int, req: ApproveBody, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    if run.approval_status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail=f"状态 {run.approval_status} 不可审批")
    if req.approved_by == run.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    run.approval_status = "approved"
    run.approved_by = req.approved_by
    audit = GovernAuditLog(
        module="ops", entity_type="ops_tool_run", entity_ref=str(run_id),
        action="approve", operator=req.approved_by, reason=req.note,
    )
    db.add(audit)
    db.commit()
    return ApiResponse(data={"id": run.id, "approval_status": "approved"})


@router.get("/runs", summary="运维任务列表")
def list_runs(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(OpsToolRun)
    if status:
        stmt = stmt.where(OpsToolRun.approval_status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(OpsToolRun.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "tool_code": r.tool_code,
            "requested_by": r.requested_by, "approved_by": r.approved_by,
            "approval_status": r.approval_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.patch("/runs/{run_id}/reject", summary="拒绝运维任务")
def reject_run(run_id: int, req: ApproveBody, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    if run.approval_status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail=f"状态 {run.approval_status} 不可拒绝")
    if req.approved_by == run.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    run.approval_status = "rejected"
    run.approved_by = req.approved_by
    audit = GovernAuditLog(
        module="ops", entity_type="ops_tool_run", entity_ref=str(run_id),
        action="reject", operator=req.approved_by, reason=req.note,
    )
    db.add(audit)
    db.commit()
    return ApiResponse(data={"id": run.id, "approval_status": "rejected"})


@router.post("/runs/{run_id}/execute", summary="执行已审批的运维任务")

def execute_run(run_id: int, body: ExecuteBody = ExecuteBody(), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    run = db.get(OpsToolRun, run_id)
    if not run:
        raise HTTPException(status_code=404)
    tool = db.scalar(select(OpsToolTemplate).where(OpsToolTemplate.tool_code == run.tool_code))
    if not tool or not tool.enabled:
        raise HTTPException(status_code=400, detail="工具模板不存在或未启用")
    if tool.require_approval and run.approval_status != "approved":
        raise HTTPException(status_code=400, detail=f"当前状态 {run.approval_status} 不可执行，需已审批通过")
    if tool.require_second_confirm and not body.second_confirm:
        raise HTTPException(status_code=400, detail="该操作需要二次确认")
    executor = EXECUTOR_DISPATCH.get(tool.execution_mode)
    if not executor:
        raise HTTPException(status_code=400, detail=f"不支持的执行模式: {tool.execution_mode}")
    start_time = datetime.now(timezone.utc)
    try:
        exec_result = executor(tool, run, db)
    except Exception as e:
        run.approval_status = "failed"
        run.execution_summary = f"执行异常: {e}"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"执行失败: {e}")
    finish_time = datetime.now(timezone.utc)
    elapsed_ms = int((finish_time - start_time).total_seconds() * 1000)
    run.approval_status = "executed"
    run.execution_summary = json.dumps(exec_result, ensure_ascii=False)
    run.started_at = start_time
    run.finished_at = finish_time
    audit = GovernAuditLog(
        module="ops", entity_type="ops_tool_run", entity_ref=str(run_id),
        action="execute", operator="system",
    )
    db.add(audit)
    db.commit()
    affected_count = exec_result.get("affected_count", 0) if isinstance(exec_result, dict) else 0
    return ApiResponse(data={
        "id": run.id,
        "status": "executed",
        "elapsed_ms": elapsed_ms,
        "affected_count": affected_count,
        "execution_summary": run.execution_summary,
    })


@router.get("/runs/{run_id}/audit", summary="获取运维任务审计日志")
def get_run_audit(run_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    logs = db.scalars(
        select(GovernAuditLog)
        .where(GovernAuditLog.entity_type == "ops_tool_run")
        .where(GovernAuditLog.entity_ref == str(run_id))
        .order_by(GovernAuditLog.created_at.asc())
    ).all()
    return ApiResponse(data=[
        {
            "id": l.id, "module": l.module, "entity_type": l.entity_type,
            "entity_ref": l.entity_ref, "action": l.action,
            "operator": l.operator, "reason": l.reason,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ])
