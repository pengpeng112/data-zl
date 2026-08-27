from datetime import datetime, timezone
import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .db import get_db
from ..models.governance_base import AssetRolePermission, AssetUserRole

logger = logging.getLogger(__name__)


def get_current_user(request: Request) -> str:
    """Return the authenticated user set by the HTTP authentication middleware."""
    user_identifier = getattr(request.state, "user_identifier", None)
    if not user_identifier:
        raise HTTPException(status_code=403, detail="Token 未绑定可信操作人")
    return user_identifier


def _effective_role_codes(db: Session, user_identifier: str) -> set[str]:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(AssetUserRole).where(
            AssetUserRole.user_identifier == user_identifier,
            AssetUserRole.status == "active",
            or_(AssetUserRole.valid_from.is_(None), AssetUserRole.valid_from <= now),
            or_(AssetUserRole.expires_at.is_(None), AssetUserRole.expires_at > now),
        )
    ).all()
    return {row.role_code for row in rows}


def _permission_matches(resource: str, requested: str) -> bool:
    if resource in {requested, "*", "*:*", "*:*:*"}:
        return True
    # Legacy slash/dot catalog entries remain valid during migration.
    normalized = resource.replace(".", ":").replace("/", ":")
    target = requested.replace(".", ":").replace("/", ":")
    return normalized in {target, "*", "*:*", "*:*:*"}


def require_permission(resource_code: str):
    """FastAPI dependency for server-side fine-grained authorization.

    The authenticated identity is always taken from middleware state; request
    payload fields such as ``operator`` are never trusted for authorization.
    """

    def dependency(request: Request, db: Session = Depends(get_db)) -> str:
        user_identifier = get_current_user(request)
        role_codes = _effective_role_codes(db, user_identifier)
        if "platform_admin" in role_codes:
            return user_identifier
        rows = db.scalars(
            select(AssetRolePermission).where(AssetRolePermission.role_code.in_(role_codes))
        ).all() if role_codes else []
        granted = [
            f"{row.resource}:{row.action}" if row.action not in (None, "", "access", "*") else row.resource
            for row in rows
        ]
        if not any(_permission_matches(item, resource_code) for item in granted):
            raise HTTPException(status_code=403, detail=f"缺少权限: {resource_code}")
        return user_identifier

    return dependency


def require_query_view_on_get(request: Request, db: Session = Depends(get_db)) -> None:
    """GET-only query.view gate（153 D1 单份实现）。

    queries/metrics/data-products 三个路由共用：GET 请求要求 query.view 权限，
    写方法跳过（写端点各自挂端点级权限码）。语义与原先三份局部副本一致。
    """
    if request.method == "GET":
        require_permission("query.view")(request, db)


def get_request_operator(request: Request | None = None, db: Session | None = None, default: str = "system") -> str:
    """解析请求操作人（153 D2 单份实现，取代 15 处样板）。

    优先读中间件写入的 request.state.user_identifier；读不到再走
    get_current_user（未认证时回落 default，记 debug 日志，不落 identifier 值）。
    db 参数保留给需要回查的调用方，此处不查库。
    """
    identifier = None
    if request is not None:
        identifier = getattr(request.state, "user_identifier", None)
        if not identifier:
            try:
                identifier = get_current_user(request) or None
            except HTTPException:
                logger.debug("operator resolution fell back to default=%s", default)
    return identifier or default
