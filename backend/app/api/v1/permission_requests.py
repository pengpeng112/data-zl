"""Permission and data-scope requests backed by GovernChangeRequest."""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.auth import AuthUser
from ...models.governance_base import AssetRole, AssetUserDataScope, AssetUserRole, GovernAuditLog, GovernChangeRequest
from ...models.identity import IdentityPerson
from ...schemas.common import ApiResponse
from ...services.subject_policy import SubjectPolicyError, can_grant_role, operator_role_codes

router = APIRouter(prefix="/api/v1/permission-requests", tags=["permission-requests"])

# 200 R06：数据范围枚举与 filter_json 白名单（字段/形态/大小）。
ALLOWED_SCOPE_TYPES = ("system", "source", "schema", "domain")
_FILTER_KEY_RE = re.compile(r"^[a-z_][a-z0-9_]{0,39}$")


def _validate_filter_json(filter_json: dict | None) -> dict | None:
    """filter_json 只接受小写字段名的扁平标量映射，禁止任意可信 JSON。"""
    if filter_json is None:
        return None
    if not isinstance(filter_json, dict) or not filter_json:
        raise HTTPException(status_code=400, detail="filter_json must be a non-empty object")
    if len(filter_json) > 8:
        raise HTTPException(status_code=400, detail="filter_json supports at most 8 fields")
    for key, value in filter_json.items():
        if not isinstance(key, str) or not _FILTER_KEY_RE.fullmatch(key):
            raise HTTPException(status_code=400, detail=f"filter_json invalid field: {key}")
        if isinstance(value, (dict, list, tuple)):
            raise HTTPException(status_code=400, detail=f"filter_json field {key} must be a scalar (no nested operators)")
        if value is not None and len(str(value)) > 100:
            raise HTTPException(status_code=400, detail=f"filter_json field {key} exceeds 100 chars")
    return filter_json


def _ensure_target_registered(db: Session, target: str) -> None:
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == target))
    account = db.scalar(select(AuthUser).where(AuthUser.user_identifier == target))
    if person is None and account is None:
        raise HTTPException(status_code=400, detail="target_user_identifier not registered: 目标必须是已登记人员或本地账号身份")


class PermissionRequestCreate(BaseModel):
    request_kind: str = Field(..., pattern="^(role|data_scope)$")
    target_user_identifier: str = Field(..., min_length=1, max_length=200)
    role_code: str | None = None
    scope_type: str | None = None
    system_code: str | None = None
    source_code: str | None = None
    schema_name: str | None = None
    domain: str | None = None
    filter_json: dict | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    reason: str = Field(..., min_length=2, max_length=500)

    @field_validator("scope_type")
    @classmethod
    def _scope_type_enum(cls, value: str | None) -> str | None:
        if value is not None and value not in ALLOWED_SCOPE_TYPES:
            raise ValueError(f"scope_type must be one of {', '.join(ALLOWED_SCOPE_TYPES)}")
        return value


class RequestDecision(BaseModel):
    note: str | None = None


def _payload(row: GovernChangeRequest) -> dict:
    request_content = row.request_payload or {}
    return {
        "id": row.id,
        "module": row.module,
        "entity_type": row.entity_type,
        "entity_ref": row.entity_ref,
        "request_type": row.request_type,
        "request_content": request_content,
        "reason": row.note,
        "status": row.approval_status,
        "requested_by": row.requested_by,
        "approved_by": row.approved_by,
        "executed_by": row.executed_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        # Backward-compatible aliases for clients created before plan 146.
        "request_payload": request_content,
        "approval_status": row.approval_status,
    }


def _audit(db: Session, *, row: GovernChangeRequest, action: str, operator: str) -> None:
    db.add(GovernAuditLog(
        module="permission",
        entity_type="change_request",
        entity_ref=str(row.id),
        action=action,
        operator=operator,
        after_data={"status": row.approval_status},
    ))


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.post("", dependencies=[Depends(require_permission("identity.permission_request.create"))])
def create_request(req: PermissionRequestCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    if req.valid_from and req.valid_to and req.valid_to <= req.valid_from:
        raise HTTPException(status_code=400, detail="valid_to must be later than valid_from")
    if req.request_kind == "role":
        if not req.role_code or not db.scalar(select(AssetRole).where(AssetRole.role_code == req.role_code)):
            raise HTTPException(status_code=400, detail="role_code not found")
        entity_type = "user_role"
    else:
        if not req.scope_type:
            raise HTTPException(status_code=400, detail="scope_type required")
        entity_type = "user_data_scope"
    # 200 R04：目标必须是已登记主体（在角色/范围合法性之后，保持旧错误契约）。
    _ensure_target_registered(db, req.target_user_identifier)
    # 200 R06：filter_json 白名单校验（字段/形态/大小），不接受任意可信 JSON。
    _validate_filter_json(req.filter_json)
    row = GovernChangeRequest(module="permission", entity_type=entity_type, entity_ref=req.target_user_identifier, request_type="grant", request_payload=req.model_dump(mode="json"), approval_status="pending", requested_by=current_user, note=req.reason)
    db.add(row)
    db.flush()
    _audit(db, row=row, action="create", operator=current_user)
    _commit(db)
    db.refresh(row)
    return ApiResponse(data=_payload(row))


@router.get("/mine", dependencies=[Depends(require_permission("identity.permission_request.view"))])
def list_mine(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    stmt = select(GovernChangeRequest).where(
        GovernChangeRequest.module == "permission",
        GovernChangeRequest.requested_by == current_user,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernChangeRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApiResponse(data={"items": [_payload(row) for row in rows], "total": total, "page": page, "page_size": page_size})


@router.get("/pending", dependencies=[Depends(require_permission("identity.permission_request.approve"))])
def list_pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernChangeRequest).where(
        GovernChangeRequest.module == "permission",
        GovernChangeRequest.approval_status == "pending",
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernChangeRequest.created_at)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApiResponse(data={"items": [_payload(row) for row in rows], "total": total, "page": page, "page_size": page_size})


@router.get("/{request_id}", dependencies=[Depends(require_permission("identity.permission_request.view"))])
def get_request(request_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.get(GovernChangeRequest, request_id)
    if not row or row.module != "permission":
        raise HTTPException(status_code=404, detail="request not found")
    if row.requested_by != get_current_user(request):
        require_permission("identity.permission_request.approve")(request, db)
    return ApiResponse(data=_payload(row))


@router.patch("/{request_id}/approve", dependencies=[Depends(require_permission("identity.permission_request.approve"))])
def approve_request(request_id: int, request: Request, req: RequestDecision | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    row = db.get(GovernChangeRequest, request_id)
    if not row or row.module != "permission":
        raise HTTPException(status_code=404, detail="request not found")
    if row.approval_status != "pending":
        raise HTTPException(status_code=400, detail="request is not pending")
    if row.requested_by == current_user:
        raise HTTPException(status_code=400, detail="applicant cannot approve own request")
    payload = row.request_payload or {}
    # 200 R06：审批者当前权限复核——批准 platform_admin 授权的审批人自身
    # 必须已是 platform_admin（防低权限借审批链自提权）。
    if payload.get("role_code") == "platform_admin":
        op_roles = operator_role_codes(db, current_user)
        if "platform_admin" not in op_roles:
            raise HTTPException(status_code=403, detail="grant_role_forbidden: 仅平台管理员可以批准平台管理员授权")
    note = (req.note if req else None) or row.note
    row.approval_status, row.approved_by, row.note = "approved", current_user, note
    _audit(db, row=row, action="approve", operator=current_user)
    _commit(db)
    return ApiResponse(data=_payload(row))


@router.patch("/{request_id}/reject", dependencies=[Depends(require_permission("identity.permission_request.approve"))])
def reject_request(request_id: int, request: Request, req: RequestDecision | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    row = db.get(GovernChangeRequest, request_id)
    if not row or row.module != "permission" or row.approval_status != "pending":
        raise HTTPException(status_code=404, detail="pending request not found")
    if row.requested_by == current_user:
        raise HTTPException(status_code=400, detail="applicant cannot reject own request")
    note = (req.note if req else None) or row.note
    row.approval_status, row.approved_by, row.note = "rejected", current_user, note
    _audit(db, row=row, action="reject", operator=current_user)
    _commit(db)
    return ApiResponse(data=_payload(row))


@router.post("/{request_id}/execute", dependencies=[Depends(require_permission("identity.permission_request.execute"))])
def execute_request(request_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    row = db.get(GovernChangeRequest, request_id)
    if not row or row.module != "permission":
        raise HTTPException(status_code=404, detail="request not found")
    if row.approval_status != "approved":
        raise HTTPException(status_code=400, detail="request must be approved before execution")
    payload = row.request_payload or {}

    # 200 R06：条件状态转换（approved→executed）保证并发执行幂等——
    # 两个并发请求只有一个能拿到行，另一个 409。
    claimed = db.execute(
        update(GovernChangeRequest)
        .where(
            GovernChangeRequest.id == row.id,
            GovernChangeRequest.approval_status == "approved",
        )
        .values(approval_status="executed", executed_by=current_user, execution_result="applying")
    )
    if (claimed.rowcount or 0) != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="request already executed or concurrently claimed")
    db.expire(row)  # 条件 UPDATE 后刷新 ORM 属性，避免读回旧状态

    # 200 R06：执行前终态校验——目标存在、payload 快照仍合法、执行者当前
    # 权限仍覆盖该授予（审批与执行之间策略变更则拒绝）。
    _ensure_target_registered(db, payload["target_user_identifier"])
    _validate_filter_json(payload.get("filter_json"))

    def parse_time(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) and value else value

    if row.entity_type == "user_role":
        op_roles = operator_role_codes(db, current_user)
        try:
            can_grant_role(
                db,
                operator=current_user,
                operator_roles=op_roles,
                target_user=payload["target_user_identifier"],
                role_code=payload["role_code"],
            )
        except SubjectPolicyError as exc:
            db.rollback()
            raise HTTPException(status_code=exc.status_code, detail=f"{exc.reason_code}: {exc.message}") from exc
        active = db.scalar(select(AssetUserRole).where(AssetUserRole.user_identifier == payload["target_user_identifier"], AssetUserRole.role_code == payload["role_code"], AssetUserRole.status == "active"))
        if active:
            db.rollback()
            raise HTTPException(status_code=409, detail="active role grant already exists")
        db.add(AssetUserRole(user_identifier=payload["target_user_identifier"], role_code=payload["role_code"], source="request", request_id=row.id, status="active", granted_by=current_user, valid_from=parse_time(payload.get("valid_from")), expires_at=parse_time(payload.get("valid_to"))))
    elif row.entity_type == "user_data_scope":
        if payload.get("scope_type") not in ALLOWED_SCOPE_TYPES:
            db.rollback()
            raise HTTPException(status_code=400, detail="scope_type not in allowed enum; regenerate request")
        db.add(AssetUserDataScope(user_identifier=payload["target_user_identifier"], scope_type=payload["scope_type"], system_code=payload.get("system_code"), source_code=payload.get("source_code"), schema_name=payload.get("schema_name"), domain=payload.get("domain"), filter_json=payload.get("filter_json"), status="active", request_id=row.id, granted_by=current_user, valid_from=parse_time(payload.get("valid_from")), valid_to=parse_time(payload.get("valid_to"))))
    else:
        db.rollback()
        raise HTTPException(status_code=400, detail="unsupported request type")
    row.execution_result = "applied"
    _audit(db, row=row, action="execute", operator=current_user)
    _commit(db)
    return ApiResponse(data=_payload(row))


@router.post("/{request_id}/revoke", dependencies=[Depends(require_permission("identity.permission_request.execute"))])
def revoke_request(request_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    row = db.get(GovernChangeRequest, request_id)
    if not row or row.module != "permission" or row.approval_status != "executed":
        raise HTTPException(status_code=404, detail="executed request not found")
    if row.entity_type == "user_role":
        db.query(AssetUserRole).filter(AssetUserRole.request_id == row.id, AssetUserRole.status == "active").update({"status": "revoked"})
    else:
        db.query(AssetUserDataScope).filter(AssetUserDataScope.request_id == row.id, AssetUserDataScope.status == "active").update({"status": "revoked", "revoked_by": current_user})
    row.approval_status, row.executed_by = "revoked", current_user
    _audit(db, row=row, action="revoke", operator=current_user)
    _commit(db)
    return ApiResponse(data=_payload(row))
