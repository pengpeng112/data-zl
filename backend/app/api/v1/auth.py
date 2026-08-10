"""Local account login / session / password management API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.rate_limit import limiter
from ...core.security import get_current_user
from ...models.auth import AuthLoginEvent, AuthUser
from ...models.governance_base import AssetUserRole, GovernAuditLog
from ...models.identity import IdentityPerson
from ...schemas.common import ApiResponse
from ...services import auth_service
from ...services.auth_service import AuthError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE = settings.auth_cookie_name


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    old_password: str | None = None
    new_password: str = Field(..., min_length=1, max_length=256)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=128)
    password: str | None = Field(default=None, max_length=256)
    user_identifier: str | None = None
    must_change_password: bool = True
    enabled: bool = True
    role_codes: list[str] = Field(default_factory=list)


class PatchUserRequest(BaseModel):
    enabled: bool | None = None
    unlock: bool | None = None
    must_change_password: bool | None = None
    reset_password: str | None = None
    user_identifier: str | None = None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _require_csrf(request: Request) -> None:
    """CSRF defense for cookie-authenticated auth endpoints."""
    if request.headers.get("X-Requested-With"):
        return
    origin = request.headers.get("Origin") or ""
    referer = request.headers.get("Referer") or ""
    allowed = settings.cors_origins or []
    if origin and any(origin.startswith(o.rstrip("/")) for o in allowed):
        return
    if referer and any(referer.startswith(o.rstrip("/")) for o in allowed):
        return
    # Same-origin absolute path requests without Origin (some tools)
    if not origin and not referer and settings.env in ("dev", "test", "development"):
        return
    raise HTTPException(status_code=403, detail="CSRF 校验失败")


def _cookie_secure() -> bool:
    # 显式配置优先；默认 false，避免 HTTP 内网部署时 Secure Cookie 被浏览器丢弃
    return bool(settings.auth_cookie_secure)


def _samesite_value() -> str:
    value = (settings.auth_cookie_samesite or "lax").lower()
    if value in {"lax", "strict", "none"}:
        return value
    return "lax"


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    max_age = int(settings.auth_refresh_token_ttl_hours * 3600)
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_samesite_value(),
        path=settings.auth_cookie_path,
        max_age=max_age,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=settings.auth_cookie_path,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )


def _login_payload(user: AuthUser, access_token: str, expires_at: datetime, roles: list[str], permissions: list[str]) -> dict:
    identifier = user.user_identifier or user.username
    return {
        "avatar": "",
        "username": user.username,
        "nickname": identifier,
        "roles": roles,
        "permissions": permissions,
        "accessToken": access_token,
        # Refresh 仅 HttpOnly Cookie；body 留空以兼容 pure-admin 模板字段
        "refreshToken": "",
        "expires": auth_service.format_expires(expires_at),
        "must_change_password": bool(user.must_change_password),
        "user_identifier": identifier,
    }


def _permissions_for_roles(db: Session, roles: list[str]) -> list[str]:
    from ...api.v1.permissions import _permission_codes_for_roles

    return _permission_codes_for_roles(db, roles)


def _require_admin_roles(request: Request) -> str:
    user = get_current_user(request)
    roles = getattr(request.state, "roles", None) or []
    if not any(r in roles for r in ("platform_admin", "identity_admin")):
        raise HTTPException(status_code=403, detail="权限不足")
    return user


def _audit(db: Session, action: str, entity_ref: str, operator: str, before=None, after=None, reason: str | None = None):
    db.add(
        GovernAuditLog(
            module="auth",
            entity_type="auth_user",
            entity_ref=entity_ref,
            action=action,
            before_data=before,
            after_data=after,
            operator=operator,
            reason=reason,
        )
    )


@router.post("/login", summary="本地账号登录")
@limiter.limit(settings.auth_login_rate_limit)
def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    _require_csrf(request)
    ip_masked = auth_service.mask_ip(_client_ip(request))
    try:
        user = auth_service.authenticate_user(
            db, body.username.strip(), body.password, client_ip_masked=ip_masked
        )
        roles = auth_service.lookup_roles(db, user.user_identifier or user.username)
        access_token, expires_at = auth_service.create_access_token(user, roles)
        raw_refresh, _ = auth_service.issue_refresh_session(
            db,
            user,
            client_ip_masked=ip_masked,
            user_agent=request.headers.get("User-Agent"),
        )
        db.commit()
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    _set_refresh_cookie(response, raw_refresh)
    permissions = _permissions_for_roles(db, roles)
    data = _login_payload(user, access_token, expires_at, roles, permissions)
    # pure-admin 模板检查 success；平台契约保留 code/message/data
    return {"code": 0, "message": "success", "success": True, "data": data}


@router.post("/refresh", summary="刷新 Access Token")
@limiter.limit(settings.auth_refresh_rate_limit)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _require_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="缺少刷新凭证")
    ip_masked = auth_service.mask_ip(_client_ip(request))
    try:
        user, raw_new, _, roles = auth_service.rotate_refresh_session(
            db,
            raw,
            client_ip_masked=ip_masked,
            user_agent=request.headers.get("User-Agent"),
        )
        access_token, expires_at = auth_service.create_access_token(user, roles)
        db.commit()
    except AuthError as e:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    _set_refresh_cookie(response, raw_new)
    permissions = _permissions_for_roles(db, roles)
    data = _login_payload(user, access_token, expires_at, roles, permissions)
    return {"code": 0, "message": "success", "success": True, "data": data}


@router.post("/logout", summary="登出并撤销会话")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    _require_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    auth_service.revoke_session(db, raw)
    db.commit()
    _clear_refresh_cookie(response)
    return ApiResponse(data={"logged_out": True})


@router.get("/me", summary="当前登录账号摘要")
def me(request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user_identifier = getattr(request.state, "user_identifier", None)
    if not user_identifier:
        raise HTTPException(status_code=401, detail="未登录")
    roles = list(getattr(request.state, "roles", None) or [])
    if not roles:
        roles = auth_service.lookup_roles(db, user_identifier)
    permissions = _permissions_for_roles(db, roles)
    auth_user = db.scalar(
        select(AuthUser).where(
            (AuthUser.user_identifier == user_identifier) | (AuthUser.username == user_identifier)
        )
    )
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == user_identifier))
    return ApiResponse(
        data={
            "username": auth_user.username if auth_user else user_identifier,
            "user_identifier": user_identifier,
            "person_name": person.person_name if person else None,
            "roles": roles,
            "permissions": permissions,
            "must_change_password": bool(auth_user.must_change_password) if auth_user else False,
            "enabled": bool(auth_user.enabled) if auth_user else True,
            "auth_user_id": auth_user.id if auth_user else None,
        }
    )


@router.post("/change-password", summary="修改密码")
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    user_identifier = get_current_user(request)
    auth_user = db.scalar(
        select(AuthUser).where(
            (AuthUser.user_identifier == user_identifier) | (AuthUser.username == user_identifier)
        )
    )
    if not auth_user:
        raise HTTPException(status_code=404, detail="本地账号不存在")
    # 首次强制改密允许不传旧密码；否则必须校验旧密码
    force = bool(auth_user.must_change_password) and not body.old_password
    try:
        auth_service.change_password(
            db,
            auth_user,
            old_password=body.old_password,
            new_password=body.new_password,
            force=force,
        )
        db.commit()
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return ApiResponse(data={"changed": True, "sessions_revoked": True})


@router.get("/users", summary="本地账号列表")
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    _require_admin_roles(request)
    stmt = select(AuthUser).order_by(AuthUser.id.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where((AuthUser.username.ilike(like)) | (AuthUser.user_identifier.ilike(like)))
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    identifiers = {r.user_identifier for r in rows if r.user_identifier}
    person_names = {
        person.person_code: person.person_name_cn
        for person in db.scalars(
            select(IdentityPerson).where(IdentityPerson.person_code.in_(identifiers))
        ).all()
    } if identifiers else {}
    items = [
        {
            "id": r.id,
            "username": r.username,
            "user_identifier": r.user_identifier,
            "person_name_cn": person_names.get(r.user_identifier),
            "enabled": r.enabled,
            "must_change_password": r.must_change_password,
            "failed_login_count": r.failed_login_count,
            "locked_until": r.locked_until.isoformat() if r.locked_until else None,
            "last_login_at": r.last_login_at.isoformat() if r.last_login_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"items": items, "page": page, "page_size": page_size})


@router.post("/users", summary="创建本地账号")
def create_user(
    request: Request,
    body: CreateUserRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    operator = _require_admin_roles(request)
    import secrets as _secrets

    person = None
    if body.user_identifier:
        person = db.scalar(
            select(IdentityPerson).where(
                IdentityPerson.person_code == body.user_identifier.strip()
            )
        )
        if not person:
            raise HTTPException(status_code=400, detail="所选人员不存在，请从人员管理中重新选择")
        bound = db.scalar(
            select(AuthUser).where(AuthUser.user_identifier == person.person_code)
        )
        if bound:
            raise HTTPException(status_code=409, detail="该人员已绑定本地账号")

    password = body.password or _secrets.token_urlsafe(16)
    try:
        user = auth_service.create_local_user(
            db,
            username=body.username.strip(),
            password=password,
            user_identifier=person.person_code if person else None,
            must_change_password=body.must_change_password,
            enabled=body.enabled,
        )
        for role in body.role_codes:
            db.add(
                AssetUserRole(
                    user_identifier=user.user_identifier or user.username,
                    role_code=role,
                    granted_by=operator,
                )
            )
        _audit(
            db,
            "create_user",
            user.username,
            operator,
            after={"username": user.username, "user_identifier": user.user_identifier, "roles": body.role_codes},
        )
        db.commit()
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return ApiResponse(
        data={
            "id": user.id,
            "username": user.username,
            "user_identifier": user.user_identifier,
            "person_name_cn": person.person_name_cn if person else None,
            "must_change_password": user.must_change_password,
            "initial_password": password if body.password is None else None,
            "warning": "初始密码仅返回一次，请通过安全渠道交付" if body.password is None else None,
        }
    )


@router.patch("/users/{user_id}", summary="启停/解锁/重置密码")
def patch_user(
    user_id: int,
    request: Request,
    body: PatchUserRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    operator = _require_admin_roles(request)
    user = db.get(AuthUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    before = {
        "enabled": user.enabled,
        "must_change_password": user.must_change_password,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "user_identifier": user.user_identifier,
    }
    if body.enabled is not None:
        user.enabled = body.enabled
        if not body.enabled:
            auth_service.revoke_all_user_sessions(db, user.id)
    if body.unlock:
        user.locked_until = None
        user.failed_login_count = 0
    if body.must_change_password is not None:
        user.must_change_password = body.must_change_password
    if body.user_identifier is not None:
        user.user_identifier = body.user_identifier or None
    initial_password = None
    if body.reset_password is not None:
        try:
            auth_service.change_password(
                db, user, old_password=None, new_password=body.reset_password, force=True
            )
            user.must_change_password = True
        except AuthError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message) from e
        initial_password = body.reset_password
    user.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        "patch_user",
        user.username,
        operator,
        before=before,
        after={
            "enabled": user.enabled,
            "must_change_password": user.must_change_password,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "user_identifier": user.user_identifier,
            "password_reset": body.reset_password is not None,
        },
    )
    db.commit()
    return ApiResponse(
        data={
            "id": user.id,
            "username": user.username,
            "enabled": user.enabled,
            "must_change_password": user.must_change_password,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "initial_password": initial_password,
        }
    )


@router.get("/login-events", summary="登录审计（脱敏）")
def login_events(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ApiResponse[dict]:
    _require_admin_roles(request)
    rows = db.scalars(
        select(AuthLoginEvent).order_by(AuthLoginEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "username": r.username,
            "user_identifier": r.user_identifier,
            "result": r.result,
            "reason_code": r.reason_code,
            "client_ip_masked": r.client_ip_masked,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"items": items, "page": page, "page_size": page_size})
