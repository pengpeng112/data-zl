import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...core.security import get_current_user, get_request_operator
from ...models.governance_base import (
    AssetActionExecutor,
    AssetRole,
    AssetRolePermission,
    AssetUserRole,
    GovernAuditLog,
    GovernChangeRequest,
    GovernEnumValue,
)
from ...schemas.common import ApiResponse
from ...services.data_masking import mask_sensitive, sanitize_text

router = APIRouter(prefix="/api/v1/govern", tags=["govern"])


def _write_audit(
    db: Session,
    module: str,
    entity_type: str,
    entity_ref: str,
    action: str,
    operator: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
):
    log = GovernAuditLog(
        module=module,
        entity_type=entity_type,
        entity_ref=entity_ref,
        action=action,
        before_data=mask_sensitive(before),
        after_data=mask_sensitive(after),
        operator=operator,
        reason=reason,
    )
    db.add(log)


# ──────────────────────────────────────────────
# RBAC 角色
# ──────────────────────────────────────────────

class RoleUpsert(BaseModel):
    role_code: str
    role_name_cn: str
    role_type: str | None = "platform"
    description: str | None = None


@router.get("/roles", summary="角色列表")
def list_roles(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetRole).order_by(AssetRole.created_at)).all()
    return ApiResponse(data=[
        {
            "id": r.id,
            "role_code": r.role_code,
            "role_name_cn": r.role_name_cn,
            "role_type": r.role_type,
            "description": r.description,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ])


@router.put("/roles", summary="新增/更新角色")
def upsert_role(req: RoleUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(AssetRole).where(AssetRole.role_code == req.role_code))
    if existing:
        existing.role_name_cn = req.role_name_cn
        existing.role_type = req.role_type
        existing.description = req.description
        existing.updated_at = datetime.now(timezone.utc)
        role = existing
    else:
        role = AssetRole(
            role_code=req.role_code,
            role_name_cn=req.role_name_cn,
            role_type=req.role_type or "platform",
            description=req.description,
        )
        db.add(role)
    db.commit()
    db.refresh(role)
    return ApiResponse(data={"id": role.id, "role_code": role.role_code})


@router.delete("/roles/{role_code}", summary="删除角色")
def delete_role(role_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == role_code))
    if not role:
        raise HTTPException(status_code=404)
    db.delete(role)
    db.commit()
    return ApiResponse(data={"deleted": role_code})


# ──────────────────────────────────────────────
# RBAC 角色权限
# ──────────────────────────────────────────────

class PermissionAssign(BaseModel):
    role_code: str
    resource: str
    action: str


@router.get("/roles/{role_code}/permissions", summary="角色权限列表")
def list_permissions(role_code: str, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(AssetRolePermission).where(AssetRolePermission.role_code == role_code)
    ).all()
    return ApiResponse(data=[
        {"id": r.id, "role_code": r.role_code, "resource": r.resource, "action": r.action}
        for r in rows
    ])


@router.post("/roles/{role_code}/permissions", summary="给角色添加权限")
def add_permission(
    role_code: str, req: PermissionAssign, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == role_code))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    perm = AssetRolePermission(role_code=role_code, resource=req.resource, action=req.action)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return ApiResponse(data={"id": perm.id})


@router.delete("/roles/{role_code}/permissions/{perm_id}", summary="删除角色权限")
def remove_permission(
    role_code: str, perm_id: int, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    perm = db.get(AssetRolePermission, perm_id)
    if not perm or perm.role_code != role_code:
        raise HTTPException(status_code=404)
    db.delete(perm)
    db.commit()
    return ApiResponse(data={"deleted": perm_id})


# ──────────────────────────────────────────────
# 统一审批 / 变更请求
# ──────────────────────────────────────────────

@router.get("/change-requests", summary="变更请求列表")
def list_change_requests(
    module: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernChangeRequest)
    if module:
        stmt = stmt.where(GovernChangeRequest.module == module)
    if status:
        stmt = stmt.where(GovernChangeRequest.approval_status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernChangeRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "module": r.module, "entity_type": r.entity_type,
            "entity_ref": r.entity_ref, "request_type": r.request_type,
            "approval_status": r.approval_status,
            "requested_by": r.requested_by, "approved_by": r.approved_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class ChangeRequestCreate(BaseModel):
    module: str
    entity_type: str
    entity_ref: str | None = None
    request_type: str
    request_payload: dict | None = None
    note: str | None = None


@router.post("/change-requests", summary="创建变更请求")
def create_change_request(
    req: ChangeRequestCreate, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = GovernChangeRequest(
        module=req.module,
        entity_type=req.entity_type,
        entity_ref=req.entity_ref,
        request_type=req.request_type,
        request_payload=req.request_payload,
        requested_by=current_user,
        note=req.note,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    _write_audit(db, module=req.module, entity_type="change_request", entity_ref=str(cr.id),
                  action="create", operator=current_user)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


class ChangeRequestApprove(BaseModel):
    note: str | None = None


@router.patch("/change-requests/{cr_id}/approve", summary="审批通过")
def approve_change_request(
    cr_id: int, req: ChangeRequestApprove, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if cr.approval_status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail=f"当前状态 {cr.approval_status} 不可审批")
    if current_user == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    before = {"approval_status": cr.approval_status}
    cr.approval_status = "approved"
    cr.approved_by = current_user
    cr.note = req.note
    cr.updated_at = datetime.now(timezone.utc)
    _write_audit(db, module=cr.module, entity_type="change_request", entity_ref=str(cr.id),
                  action="approve", operator=current_user, before=before,
                 after={"approval_status": "approved"})
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.patch("/change-requests/{cr_id}/reject", summary="审批拒绝")
def reject_change_request(
    cr_id: int, req: ChangeRequestApprove, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if current_user == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    before = {"approval_status": cr.approval_status}
    cr.approval_status = "rejected"
    cr.approved_by = current_user
    cr.note = req.note
    cr.updated_at = datetime.now(timezone.utc)
    _write_audit(db, module=cr.module, entity_type="change_request", entity_ref=str(cr.id),
                  action="reject", operator=current_user, before=before,
                 after={"approval_status": "rejected"})
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


# ──────────────────────────────────────────────
# 统一审计日志
# ──────────────────────────────────────────────

def _audit_filters(
    module: str | None,
    operator: str | None,
    action: str | None,
    entity_type: str | None,
    entity_ref: str | None,
    created_from: str | None,
    created_to: str | None,
):
    from datetime import datetime as _dt
    filters = []
    if module:
        filters.append(GovernAuditLog.module == module)
    if operator:
        filters.append(GovernAuditLog.operator == operator)
    if action:
        filters.append(GovernAuditLog.action == action)
    if entity_type:
        filters.append(GovernAuditLog.entity_type == entity_type)
    if entity_ref:
        filters.append(GovernAuditLog.entity_ref.ilike(f"%{entity_ref}%"))
    if created_from:
        try:
            filters.append(GovernAuditLog.created_at >= _dt.fromisoformat(created_from.replace("Z", "+00:00")))
        except ValueError:
            raise HTTPException(status_code=400, detail="created_from 需为 ISO 时间")
    if created_to:
        try:
            filters.append(GovernAuditLog.created_at <= _dt.fromisoformat(created_to.replace("Z", "+00:00")))
        except ValueError:
            raise HTTPException(status_code=400, detail="created_to 需为 ISO 时间")
    return filters


def _audit_limited(value) -> str | None:
    if value is None:
        return None
    rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return sanitize_text(rendered, limit=300)


@router.get("/audit-logs", summary="审计日志列表（146 E7：时间/操作人/动作/实体筛选 + 详情字段）")
def list_audit_logs(
    module: str | None = Query(None),
    operator: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_ref: str | None = Query(None),
    created_from: str | None = Query(None),
    created_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernAuditLog).where(*_audit_filters(module, operator, action, entity_type, entity_ref, created_from, created_to))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "module": r.module, "entity_type": r.entity_type,
            "entity_ref": r.entity_ref, "action": r.action,
            "operator": r.operator, "reason": r.reason,
            "before_data": _audit_limited(r.before_data),
            "after_data": _audit_limited(r.after_data),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/audit-logs/summary", summary="审计日志全量统计（与列表同口径筛选；146 E7）")
def audit_logs_summary(
    module: str | None = Query(None),
    operator: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_ref: str | None = Query(None),
    created_from: str | None = Query(None),
    created_to: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    filters = _audit_filters(module, operator, action, entity_type, entity_ref, created_from, created_to)
    rows = db.scalars(select(GovernAuditLog).where(*filters)).all()
    by_module: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_operator: dict[str, int] = {}
    for r in rows:
        by_module[r.module] = by_module.get(r.module, 0) + 1
        by_action[r.action] = by_action.get(r.action, 0) + 1
        if r.operator:
            by_operator[r.operator] = by_operator.get(r.operator, 0) + 1
    return ApiResponse(data={
        "total": len(rows),
        "by_module": by_module,
        "by_action": by_action,
        "by_operator": by_operator,
    })


AUDIT_EXPORT_LIMIT = 5000


@router.get("/audit-logs/export", summary="审计日志 CSV 导出（与列表同口径筛选；146 E7）")
def audit_logs_export(
    module: str | None = Query(None),
    operator: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_ref: str | None = Query(None),
    created_from: str | None = Query(None),
    created_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    import csv
    import io as _io
    from fastapi.responses import StreamingResponse
    filters = _audit_filters(module, operator, action, entity_type, entity_ref, created_from, created_to)
    rows = db.scalars(
        select(GovernAuditLog).where(*filters)
        .order_by(GovernAuditLog.created_at.desc())
        .limit(AUDIT_EXPORT_LIMIT)
    ).all()
    buffer = _io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "module", "entity_type", "entity_ref", "action", "operator", "reason"])
    for r in rows:
        writer.writerow([
            r.id,
            r.created_at.isoformat() if r.created_at else "",
            r.module, r.entity_type, r.entity_ref, r.action,
            r.operator or "", (r.reason or "").replace(chr(10), " "),
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )


# ──────────────────────────────────────────────
# 统一执行器注册
# ──────────────────────────────────────────────

class ExecutorUpsert(BaseModel):
    executor_code: str
    executor_name_cn: str
    execution_mode: str = Field(..., description="whitelist_dml/stored_procedure/http_api/sync_executor/readonly_sql")
    tool_code: str | None = None
    sql_or_endpoint_ref: str | None = None
    target_system_code: str | None = None
    target_source_code: str | None = None
    risk_level: str | None = "medium"
    require_approval: bool = True
    require_second_confirm: bool = False
    enabled: bool = False
    description: str | None = None


@router.get("/executors", summary="执行器列表")
def list_executors(
    execution_mode: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetActionExecutor)
    if execution_mode:
        stmt = stmt.where(AssetActionExecutor.execution_mode == execution_mode)
    rows = db.scalars(stmt.order_by(AssetActionExecutor.created_at)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "executor_code": r.executor_code,
            "executor_name_cn": r.executor_name_cn,
            "execution_mode": r.execution_mode,
            "risk_level": r.risk_level,
            "require_approval": r.require_approval,
            "enabled": r.enabled,
        }
        for r in rows
    ])


@router.put("/executors", summary="新增/更新执行器注册")
def upsert_executor(
    req: ExecutorUpsert, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    existing = db.scalar(
        select(AssetActionExecutor).where(AssetActionExecutor.executor_code == req.executor_code)
    )
    if existing:
        existing.executor_name_cn = req.executor_name_cn
        existing.execution_mode = req.execution_mode
        existing.tool_code = req.tool_code
        existing.sql_or_endpoint_ref = req.sql_or_endpoint_ref
        existing.target_system_code = req.target_system_code
        existing.target_source_code = req.target_source_code
        existing.risk_level = req.risk_level or "medium"
        existing.require_approval = req.require_approval
        existing.require_second_confirm = req.require_second_confirm
        existing.enabled = req.enabled
        existing.description = req.description
        existing.updated_at = datetime.now(timezone.utc)
        exe = existing
    else:
        exe = AssetActionExecutor(
            executor_code=req.executor_code,
            executor_name_cn=req.executor_name_cn,
            execution_mode=req.execution_mode,
            tool_code=req.tool_code,
            sql_or_endpoint_ref=req.sql_or_endpoint_ref,
            target_system_code=req.target_system_code,
            target_source_code=req.target_source_code,
            risk_level=req.risk_level or "medium",
            require_approval=req.require_approval,
            require_second_confirm=req.require_second_confirm,
            enabled=req.enabled,
            description=req.description,
        )
        db.add(exe)
    db.commit()
    db.refresh(exe)
    return ApiResponse(data={"id": exe.id, "executor_code": exe.executor_code})


@router.patch("/executors/{executor_code}", summary="启用/禁用执行器")
def toggle_executor(
    executor_code: str,
    enabled: bool = Query(True),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    exe = db.scalar(
        select(AssetActionExecutor).where(AssetActionExecutor.executor_code == executor_code)
    )
    if not exe:
        raise HTTPException(status_code=404)
    exe.enabled = enabled
    exe.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"executor_code": exe.executor_code, "enabled": exe.enabled})


# ──────────────────────────────────────────────
# 用户角色分配
# ──────────────────────────────────────────────

class UserRoleAssign(BaseModel):
    user_identifier: str
    role_code: str


@router.get("/user-roles", summary="用户角色列表")
def list_user_roles(
    user_identifier: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetUserRole)
    if user_identifier:
        stmt = stmt.where(AssetUserRole.user_identifier == user_identifier)
    rows = db.scalars(stmt.order_by(AssetUserRole.granted_at.desc())).all()
    return ApiResponse(data=[
        {
            "id": r.id, "user_identifier": r.user_identifier,
            "role_code": r.role_code,
            "granted_at": r.granted_at.isoformat() if r.granted_at else None,
        }
        for r in rows
    ])


@router.post("/user-roles", summary="分配用户角色")
def assign_user_role(
    req: UserRoleAssign, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == req.role_code))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    ur = AssetUserRole(user_identifier=req.user_identifier, role_code=req.role_code)
    db.add(ur)
    db.flush()
    # B4：角色分配此前零审计，补 GovernAuditLog（不含任何凭据类字段）。
    operator = get_request_operator(request, default="system")
    db.add(GovernAuditLog(
        module="governance",
        entity_type="user_role",
        entity_ref=f"{req.user_identifier}:{req.role_code}",
        action="assign",
        after_data={"user_identifier": req.user_identifier, "role_code": req.role_code},
        operator=operator,
    ))
    db.commit()
    db.refresh(ur)
    return ApiResponse(data={"id": ur.id, "user_identifier": ur.user_identifier, "role_code": ur.role_code})


@router.delete("/user-roles/{ur_id}", summary="移除用户角色")
def remove_user_role(ur_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ur = db.get(AssetUserRole, ur_id)
    if not ur:
        raise HTTPException(status_code=404)
    before = {"user_identifier": ur.user_identifier, "role_code": ur.role_code}
    db.delete(ur)
    # B4：移除角色同补审计。
    operator = get_request_operator(request, default="system")
    db.add(GovernAuditLog(
        module="governance",
        entity_type="user_role",
        entity_ref=f"{before['user_identifier']}:{before['role_code']}",
        action="remove",
        before_data=before,
        operator=operator,
    ))
    db.commit()
    return ApiResponse(data={"deleted": ur_id})


# ──────────────────────────────────────────────
# 枚举值管理
# ──────────────────────────────────────────────

class EnumValueUpsert(BaseModel):
    enum_code: str
    value_code: str
    value_name_cn: str
    sort_order: int | None = 0
    enabled: bool = True


@router.get("/enum-values", summary="枚举值列表")
def list_enum_values(
    enum_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(GovernEnumValue)
    if enum_code:
        stmt = stmt.where(GovernEnumValue.enum_code == enum_code)
    rows = db.scalars(stmt.order_by(GovernEnumValue.enum_code, GovernEnumValue.sort_order)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "enum_code": r.enum_code,
            "value_code": r.value_code, "value_name_cn": r.value_name_cn,
            "sort_order": r.sort_order, "enabled": r.enabled,
        }
        for r in rows
    ])


@router.put("/enum-values", summary="新增/更新枚举值")
def upsert_enum_value(req: EnumValueUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(GovernEnumValue).where(
        GovernEnumValue.enum_code == req.enum_code,
        GovernEnumValue.value_code == req.value_code,
    ))
    if existing:
        existing.value_name_cn = req.value_name_cn
        existing.sort_order = req.sort_order
        existing.enabled = req.enabled
        ev = existing
    else:
        ev = GovernEnumValue(
            enum_code=req.enum_code,
            value_code=req.value_code,
            value_name_cn=req.value_name_cn,
            sort_order=req.sort_order or 0,
            enabled=req.enabled,
        )
        db.add(ev)
    db.commit()
    db.refresh(ev)
    return ApiResponse(data={"id": ev.id, "enum_code": ev.enum_code, "value_code": ev.value_code})
