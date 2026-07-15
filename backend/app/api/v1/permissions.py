from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.governance import ApiKey
from ...models.governance_base import (
    AssetPermissionResource,
    AssetRole,
    AssetRolePermission,
    AssetUserRole,
    GovernAuditLog,
)
from ...models.identity import IdentityPerson
from ...schemas.common import ApiResponse
from ...services.data_masking import mask_sensitive

router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])

RESOURCE_CATALOG: list[dict] = [
    {"code": "asset", "name_cn": "资产门户", "type": "menu", "parent_code": None},
    {"code": "asset.table.view", "name_cn": "资产表浏览", "type": "page", "parent_code": "asset"},
    {"code": "asset.graph.view", "name_cn": "关系图谱查看", "type": "page", "parent_code": "asset"},
    {"code": "asset.relation.review", "name_cn": "关系复核", "type": "page", "parent_code": "asset"},
    {"code": "quality", "name_cn": "质量规则", "type": "menu", "parent_code": None},
    {"code": "quality.rule.view", "name_cn": "规则查看", "type": "page", "parent_code": "quality"},
    {"code": "quality.rule.create", "name_cn": "规则创建", "type": "button", "parent_code": "quality.rule.view"},
    {"code": "quality.rule.execute", "name_cn": "规则执行", "type": "button", "parent_code": "quality.rule.view"},
    {"code": "metadata", "name_cn": "元数据变更", "type": "menu", "parent_code": None},
    {"code": "metadata.snapshot.collect", "name_cn": "采集快照", "type": "button", "parent_code": "metadata"},
    {"code": "identity", "name_cn": "身份与权限", "type": "menu", "parent_code": None},
    {"code": "identity.person.view", "name_cn": "人员查看", "type": "page", "parent_code": "identity"},
    {"code": "identity.sync.run", "name_cn": "人员同步", "type": "button", "parent_code": "identity"},
    {"code": "identity.role.manage", "name_cn": "角色管理", "type": "page", "parent_code": "identity"},
    {"code": "identity.role.grant", "name_cn": "人员授权", "type": "button", "parent_code": "identity.role.manage"},
    {"code": "identity.local_account.manage", "name_cn": "本地账号管理", "type": "page", "parent_code": "identity"},
    {"code": "dict", "name_cn": "字典中心", "type": "menu", "parent_code": None},
    {"code": "dict.medical.view", "name_cn": "诊断手术字典查看", "type": "page", "parent_code": "dict"},
    {"code": "dict.medical.edit", "name_cn": "诊断手术字典维护", "type": "button", "parent_code": "dict.medical.view"},
    {"code": "ops", "name_cn": "运维工具", "type": "menu", "parent_code": None},
    {"code": "ops.tool.manage", "name_cn": "工具模板管理", "type": "page", "parent_code": "ops"},
    {"code": "ops.run.submit", "name_cn": "提交运维申请", "type": "button", "parent_code": "ops"},
    {"code": "ops.run.approve", "name_cn": "审批运维申请", "type": "button", "parent_code": "ops"},
    {"code": "ops.run.execute", "name_cn": "执行运维申请", "type": "button", "parent_code": "ops"},
    {"code": "ops.sql.view", "name_cn": "SQL 工作台查看", "type": "page", "parent_code": "ops"},
    {"code": "ops.sql.create", "name_cn": "SQL 模板创建", "type": "button", "parent_code": "ops.sql.view"},
    {"code": "ops.sql.review", "name_cn": "SQL 模板审批", "type": "button", "parent_code": "ops.sql.view"},
    {"code": "ops.sql.execute", "name_cn": "SQL 执行申请", "type": "button", "parent_code": "ops.sql.view"},
    {"code": "ops.sql.audit", "name_cn": "SQL 执行审计", "type": "button", "parent_code": "ops.sql.view"},
    {"code": "source.manage", "name_cn": "业务系统与连接维护", "type": "page", "parent_code": "asset"},
    {"code": "source.credential_manage", "name_cn": "连接凭据维护", "type": "button", "parent_code": "source.manage"},
    {"code": "source.collect", "name_cn": "元数据采集", "type": "button", "parent_code": "source.manage"},
    {"code": "ai", "name_cn": "AI 协作", "type": "menu", "parent_code": None},
    {"code": "ai.draft.view", "name_cn": "AI 草稿查看", "type": "page", "parent_code": "ai"},
    {"code": "ai.draft.execute", "name_cn": "AI 草稿只读执行", "type": "button", "parent_code": "ai"},
]


def _resource_seed_rows() -> list[dict]:
    rows = []
    for index, item in enumerate(RESOURCE_CATALOG):
        # Persist the public dot-form contract used by the frontend and role
        # matrices.  The security matcher still accepts legacy colon codes.
        code = item["code"]
        parts = code.split(".")
        rows.append({
            "resource_code": code,
            "resource_name_cn": item["name_cn"],
            "module_code": parts[0],
            "action_code": parts[-1] if len(parts) > 1 else "access",
            "description": item.get("type"),
            "sort_order": index,
        })
    return rows

BUILTIN_ROLES: list[dict] = [
    {"role_code": "platform_admin", "role_name_cn": "平台管理员", "role_type": "builtin", "description": "平台最高权限角色"},
    {"role_code": "asset_viewer", "role_name_cn": "资产查看员", "role_type": "builtin", "description": "查看资产和图谱"},
    {"role_code": "asset_editor", "role_name_cn": "资产维护员", "role_type": "builtin", "description": "维护资产关系和元数据"},
    {"role_code": "quality_admin", "role_name_cn": "质量管理员", "role_type": "builtin", "description": "维护和执行质量规则"},
    {"role_code": "identity_admin", "role_name_cn": "身份权限管理员", "role_type": "builtin", "description": "维护人员、角色和权限"},
    {"role_code": "dict_admin", "role_name_cn": "字典管理员", "role_type": "builtin", "description": "维护诊断、手术、医保等字典"},
    {"role_code": "ops_admin", "role_name_cn": "运维工具管理员", "role_type": "builtin", "description": "维护运维工具并执行受控操作"},
    {"role_code": "approver", "role_name_cn": "审批人", "role_type": "builtin", "description": "审批治理和运维申请"},
    {"role_code": "ai_user", "role_name_cn": "AI 协作用户", "role_type": "builtin", "description": "使用 AI 草稿和只读协作能力"},
]

ROLE_DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    "platform_admin": [r["code"] for r in RESOURCE_CATALOG],
    "asset_viewer": ["asset", "asset.table.view", "asset.graph.view"],
    "asset_editor": [
        "asset",
        "asset.table.view",
        "asset.graph.view",
        "asset.relation.review",
        "metadata",
        "metadata.snapshot.collect",
        "source.manage",
        "source.collect",
    ],
    "quality_admin": ["quality", "quality.rule.view", "quality.rule.create", "quality.rule.execute"],
    "identity_admin": [
        "identity",
        "identity.person.view",
        "identity.sync.run",
        "identity.role.manage",
        "identity.role.grant",
        "identity.local_account.manage",
    ],
    "dict_admin": ["dict", "dict.medical.view", "dict.medical.edit"],
    "ops_admin": [
        "ops",
        "ops.tool.manage",
        "ops.run.submit",
        "ops.run.approve",
        "ops.run.execute",
        "ops.sql.view",
        "ops.sql.create",
        "ops.sql.review",
        "ops.sql.execute",
        "ops.sql.audit",
        "source.manage",
        "source.credential_manage",
        "source.collect",
    ],
    "approver": [
        "ops",
        "ops.run.approve",
        "ops.sql.view",
        "ops.sql.review",
        "identity",
        "identity.person.view",
    ],
    "ai_user": ["ai", "ai.draft.view", "ai.draft.execute", "asset", "asset.table.view", "asset.graph.view"],
}


class RoleUpsert(BaseModel):
    role_code: str = Field(..., min_length=2)
    role_name_cn: str
    role_type: str | None = "platform"
    description: str | None = None
    operator: str | None = None


class MatrixUpdate(BaseModel):
    permissions: list[str]
    operator: str | None = None
    reason: str | None = None


class UserRoleGrant(BaseModel):
    user_identifier: str
    role_codes: list[str]
    granted_by: str | None = None
    reason: str | None = None


class TokenBind(BaseModel):
    key_id: int
    user_identifier: str | None = None
    operator: str | None = None


def _audit_payload(row: GovernAuditLog) -> dict:
    return {
        "id": row.id,
        "module": row.module,
        "entity_type": row.entity_type,
        "entity_ref": row.entity_ref,
        "action": row.action,
        "before_data": row.before_data,
        "after_data": row.after_data,
        "operator": row.operator,
        "reason": row.reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _audit(db: Session, action: str, entity_type: str, entity_ref: str, operator: str | None, before=None, after=None, reason: str | None = None):
    db.add(GovernAuditLog(
        module="permission",
        entity_type=entity_type,
        entity_ref=entity_ref,
        action=action,
        before_data=mask_sensitive(before),
        after_data=mask_sensitive(after),
        operator=operator,
        reason=reason,
    ))


def _resource_map() -> dict[str, dict]:
    return {r["code"]: r for r in RESOURCE_CATALOG}


def _resource_payload(row: AssetPermissionResource) -> dict:
    return {
        "code": row.resource_code,
        "name_cn": row.resource_name_cn,
        "module_code": row.module_code,
        "action_code": row.action_code,
        "description": row.description,
        "enabled": row.enabled,
        "sort_order": row.sort_order,
        "source": "database",
    }


def _role_payload(role: AssetRole) -> dict:
    return {
        "id": role.id,
        "role_code": role.role_code,
        "role_name_cn": role.role_name_cn,
        "role_type": role.role_type,
        "description": role.description,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


def _permission_codes_for_roles(db: Session, role_codes: Iterable[str]) -> list[str]:
    codes = list(set(role_codes))
    if not codes:
        return []
    rows = db.scalars(select(AssetRolePermission).where(AssetRolePermission.role_code.in_(codes))).all()
    permissions = {r.resource if r.action in (None, "access", "*") else f"{r.resource}:{r.action}" for r in rows}
    return sorted(permissions)


@router.post("/seed", summary="Seed builtin roles and permission resources")
def seed_permissions(operator: str | None = Query("system"), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    created_roles = 0
    created_permissions = 0
    for item in BUILTIN_ROLES:
        role = db.scalar(select(AssetRole).where(AssetRole.role_code == item["role_code"]))
        if not role:
            role = AssetRole(**item)
            db.add(role)
            created_roles += 1
        else:
            role.role_name_cn = item["role_name_cn"]
            role.role_type = role.role_type or item["role_type"]
            role.description = role.description or item.get("description")
    db.flush()
    created_resources = 0
    for item in _resource_seed_rows():
        resource = db.scalar(select(AssetPermissionResource).where(
            AssetPermissionResource.resource_code == item["resource_code"]
        ))
        if not resource:
            db.add(AssetPermissionResource(**item))
            created_resources += 1
        else:
            resource.resource_name_cn = item["resource_name_cn"]
            resource.module_code = item["module_code"]
            resource.action_code = item["action_code"]
            resource.sort_order = item["sort_order"]
            resource.enabled = True
    db.flush()
    for role_code, resources in ROLE_DEFAULT_PERMISSIONS.items():
        for resource in resources:
            exists = db.scalar(select(AssetRolePermission).where(
                AssetRolePermission.role_code == role_code,
                AssetRolePermission.resource == resource,
                AssetRolePermission.action == "access",
            ))
            if not exists:
                db.add(AssetRolePermission(role_code=role_code, resource=resource, action="access"))
                created_permissions += 1
    _audit(db, "seed", "permission_seed", "builtin", operator, after={"roles": created_roles, "permissions": created_permissions, "resources": created_resources})
    db.commit()
    return ApiResponse(data={"created_roles": created_roles, "created_permissions": created_permissions, "created_resources": created_resources})


@router.get("/resources", summary="Permission resource catalog")
def list_resources(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetPermissionResource).order_by(AssetPermissionResource.sort_order, AssetPermissionResource.resource_code)).all()
    if rows:
        return ApiResponse(data=[_resource_payload(row) for row in rows])
    return ApiResponse(data=[{**item, "source": "fallback"} for item in RESOURCE_CATALOG])


@router.get("/roles", summary="Role list")
def list_roles(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(AssetRole).order_by(AssetRole.role_code)).all()
    return ApiResponse(data=[_role_payload(r) for r in rows])


@router.put("/roles", summary="Create or update role")
def upsert_role(req: RoleUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == req.role_code))
    before = _role_payload(role) if role else None
    if role:
        role.role_name_cn = req.role_name_cn
        role.role_type = req.role_type or role.role_type
        role.description = req.description
        role.updated_at = datetime.now(timezone.utc)
        action = "update_role"
    else:
        role = AssetRole(
            role_code=req.role_code,
            role_name_cn=req.role_name_cn,
            role_type=req.role_type or "platform",
            description=req.description,
        )
        db.add(role)
        action = "create_role"
    db.flush()
    after = _role_payload(role)
    _audit(db, action, "role", req.role_code, req.operator, before=before, after=after)
    db.commit()
    return ApiResponse(data=after)


@router.get("/roles/{role_code}/matrix", summary="Role permission matrix")
def get_role_matrix(role_code: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == role_code))
    if not role:
        raise HTTPException(status_code=404, detail="role not found")
    rows = db.scalars(select(AssetRolePermission).where(AssetRolePermission.role_code == role_code)).all()
    granted = sorted({r.resource for r in rows if r.action in (None, "access", "*")})
    return ApiResponse(data={"role": _role_payload(role), "resources": RESOURCE_CATALOG, "granted": granted})


@router.put("/roles/{role_code}/matrix", summary="Replace role permission matrix")
def update_role_matrix(role_code: str, req: MatrixUpdate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == role_code))
    if not role:
        raise HTTPException(status_code=404, detail="role not found")
    valid = _resource_map()
    invalid = [p for p in req.permissions if p not in valid]
    if invalid:
        raise HTTPException(status_code=400, detail=f"invalid permissions: {', '.join(invalid)}")
    before_rows = db.scalars(select(AssetRolePermission).where(AssetRolePermission.role_code == role_code)).all()
    before = sorted({r.resource for r in before_rows if r.action in (None, "access", "*")})
    db.execute(delete(AssetRolePermission).where(AssetRolePermission.role_code == role_code))
    for resource in sorted(set(req.permissions)):
        db.add(AssetRolePermission(role_code=role_code, resource=resource, action="access"))
    after = sorted(set(req.permissions))
    _audit(db, "update_role_matrix", "role", role_code, req.operator, before={"permissions": before}, after={"permissions": after}, reason=req.reason)
    db.commit()
    return ApiResponse(data={"role_code": role_code, "granted": after})


@router.get("/user-roles", summary="User role assignments")
def list_user_roles(user_identifier: str | None = Query(None), db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    stmt = select(AssetUserRole)
    if user_identifier:
        stmt = stmt.where(AssetUserRole.user_identifier == user_identifier)
    rows = db.scalars(stmt.order_by(AssetUserRole.user_identifier, AssetUserRole.role_code)).all()
    return ApiResponse(data=[{
        "id": r.id,
        "user_identifier": r.user_identifier,
        "role_code": r.role_code,
        "granted_by": r.granted_by,
        "granted_at": r.granted_at.isoformat() if r.granted_at else None,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
    } for r in rows])


@router.put("/users/{user_identifier}/roles", summary="Replace user roles")
def replace_user_roles(user_identifier: str, req: UserRoleGrant, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    if req.user_identifier != user_identifier:
        raise HTTPException(status_code=400, detail="path user_identifier does not match payload")
    role_codes = sorted(set(req.role_codes))
    if role_codes:
        existing_roles = set(db.scalars(select(AssetRole.role_code).where(AssetRole.role_code.in_(role_codes))).all())
        missing = [r for r in role_codes if r not in existing_roles]
        if missing:
            raise HTTPException(status_code=400, detail=f"roles not found: {', '.join(missing)}")
    before_rows = db.scalars(select(AssetUserRole).where(AssetUserRole.user_identifier == user_identifier)).all()
    before = sorted({r.role_code for r in before_rows})
    db.execute(delete(AssetUserRole).where(AssetUserRole.user_identifier == user_identifier))
    for role_code in role_codes:
        db.add(AssetUserRole(user_identifier=user_identifier, role_code=role_code, granted_by=req.granted_by))
    _audit(db, "replace_user_roles", "user", user_identifier, req.granted_by, before={"roles": before}, after={"roles": role_codes}, reason=req.reason)
    db.commit()
    return ApiResponse(data={"user_identifier": user_identifier, "roles": role_codes})


@router.get("/users/{user_identifier}/permissions", summary="Effective user permissions")
def get_user_permissions(user_identifier: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    role_codes = db.scalars(select(AssetUserRole.role_code).where(AssetUserRole.user_identifier == user_identifier)).all()
    permissions = _permission_codes_for_roles(db, role_codes)
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == user_identifier))
    return ApiResponse(data={
        "user_identifier": user_identifier,
        "person_name": person.person_name_cn if person else None,
        "roles": sorted(set(role_codes)),
        "permissions": permissions,
    })


@router.get("/me", summary="Current token roles and permissions")
def get_me_permissions(request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    import hashlib
    # Prefer identity established by middleware (JWT or ApiKey)
    user_identifier = getattr(request.state, "user_identifier", None)
    auth_via = getattr(request.state, "auth_via", None)
    if user_identifier:
        role_codes = list(getattr(request.state, "roles", None) or [])
        if not role_codes:
            role_codes = db.scalars(
                select(AssetUserRole.role_code).where(AssetUserRole.user_identifier == user_identifier)
            ).all()
        return ApiResponse(data={
            "key_id": None,
            "key_name": None,
            "user_identifier": user_identifier,
            "roles": sorted(set(role_codes)),
            "permissions": _permission_codes_for_roles(db, role_codes),
            "unbound_token": False,
            "auth_via": auth_via or "middleware",
        })

    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        from sqlalchemy import or_
        key = db.scalar(select(ApiKey).where(or_(ApiKey.token_hash == token_hash, ApiKey.token == token)))
    else:
        key = None
    if not key:
        raise HTTPException(status_code=401, detail="token not found")
    if not key.user_identifier:
        return ApiResponse(data={
            "key_id": key.id,
            "key_name": key.key_name,
            "user_identifier": None,
            "roles": [],
            "permissions": [],
            "unbound_token": True,
            "auth_via": "api_key",
        })
    role_codes = db.scalars(select(AssetUserRole.role_code).where(AssetUserRole.user_identifier == key.user_identifier)).all()
    return ApiResponse(data={
        "key_id": key.id,
        "key_name": key.key_name,
        "user_identifier": key.user_identifier,
        "roles": sorted(set(role_codes)),
        "permissions": _permission_codes_for_roles(db, role_codes),
        "unbound_token": False,
        "auth_via": "api_key",
    })


@router.get("/api-keys", summary="API keys for permission binding")
def list_api_keys(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())).all()
    return ApiResponse(data=[{
        "id": r.id,
        "key_name": r.key_name,
        "token_masked": (r.token[:8] + "...") if r.token else "",
        "enabled": bool(r.enabled),
        "user_identifier": r.user_identifier,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
    } for r in rows])


@router.get("/audit", summary="Permission audit logs")
def list_permission_audit(
    entity_type: str | None = Query(None),
    entity_ref: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(GovernAuditLog).where(GovernAuditLog.module == "permission")
    if entity_type:
        stmt = stmt.where(GovernAuditLog.entity_type == entity_type)
    if entity_ref:
        stmt = stmt.where(GovernAuditLog.entity_ref == entity_ref)
    if action:
        stmt = stmt.where(GovernAuditLog.action == action)
    rows = db.scalars(stmt.order_by(GovernAuditLog.created_at.desc(), GovernAuditLog.id.desc()).limit(limit)).all()
    return ApiResponse(data=[_audit_payload(r) for r in rows])


@router.patch("/api-keys/{key_id}/bind", summary="Bind API key to user identifier")
def bind_api_key(key_id: int, req: TokenBind, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    if req.key_id != key_id:
        raise HTTPException(status_code=400, detail="path key_id does not match payload")
    key = db.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="api key not found")
    before = {"user_identifier": key.user_identifier}
    key.user_identifier = req.user_identifier or None
    _audit(db, "bind_api_key", "api_key", str(key_id), req.operator, before=before, after={"user_identifier": key.user_identifier})
    db.commit()
    return ApiResponse(data={"id": key.id, "key_name": key.key_name, "user_identifier": key.user_identifier})
