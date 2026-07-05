from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
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
from ...services.data_masking import mask_sensitive

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
    requested_by: str | None = None


@router.post("/change-requests", summary="创建变更请求")
def create_change_request(
    req: ChangeRequestCreate, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    cr = GovernChangeRequest(
        module=req.module,
        entity_type=req.entity_type,
        entity_ref=req.entity_ref,
        request_type=req.request_type,
        request_payload=req.request_payload,
        requested_by=req.requested_by,
        note=req.note,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    _write_audit(db, module=req.module, entity_type="change_request", entity_ref=str(cr.id),
                 action="create", operator=req.requested_by)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


class ChangeRequestApprove(BaseModel):
    approved_by: str
    note: str | None = None


@router.patch("/change-requests/{cr_id}/approve", summary="审批通过")
def approve_change_request(
    cr_id: int, req: ChangeRequestApprove, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if cr.approval_status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail=f"当前状态 {cr.approval_status} 不可审批")
    if req.approved_by == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    before = {"approval_status": cr.approval_status}
    cr.approval_status = "approved"
    cr.approved_by = req.approved_by
    cr.note = req.note
    cr.updated_at = datetime.now(timezone.utc)
    _write_audit(db, module=cr.module, entity_type="change_request", entity_ref=str(cr.id),
                 action="approve", operator=req.approved_by, before=before,
                 after={"approval_status": "approved"})
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.patch("/change-requests/{cr_id}/reject", summary="审批拒绝")
def reject_change_request(
    cr_id: int, req: ChangeRequestApprove, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if req.approved_by == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    before = {"approval_status": cr.approval_status}
    cr.approval_status = "rejected"
    cr.approved_by = req.approved_by
    cr.note = req.note
    cr.updated_at = datetime.now(timezone.utc)
    _write_audit(db, module=cr.module, entity_type="change_request", entity_ref=str(cr.id),
                 action="reject", operator=req.approved_by, before=before,
                 after={"approval_status": "rejected"})
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


# ──────────────────────────────────────────────
# 统一审计日志
# ──────────────────────────────────────────────

@router.get("/audit-logs", summary="审计日志列表")
def list_audit_logs(
    module: str | None = Query(None),
    operator: str | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernAuditLog)
    if module:
        stmt = stmt.where(GovernAuditLog.module == module)
    if operator:
        stmt = stmt.where(GovernAuditLog.operator == operator)
    if action:
        stmt = stmt.where(GovernAuditLog.action == action)
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
            "operator": r.operator,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


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
    req: UserRoleAssign, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == req.role_code))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    ur = AssetUserRole(user_identifier=req.user_identifier, role_code=req.role_code)
    db.add(ur)
    db.commit()
    db.refresh(ur)
    return ApiResponse(data={"id": ur.id, "user_identifier": ur.user_identifier, "role_code": ur.role_code})


@router.delete("/user-roles/{ur_id}", summary="移除用户角色")
def remove_user_role(ur_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    ur = db.get(AssetUserRole, ur_id)
    if not ur:
        raise HTTPException(status_code=404)
    db.delete(ur)
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
