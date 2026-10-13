import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from ..models.governance_base import AssetRolePermission, AssetUserRole
from ..services.effective_permissions import (
    effective_role_codes as _service_effective_role_codes,
    normalize_permission_code,
)

logger = logging.getLogger(__name__)


class PermissionDenied(HTTPException):
    """端点级权限拒绝（DEF-01 / 214 E-A2 统一 403 信封）。

    message 固定「权限不足」；resource_code 进 data；旧文案「缺少权限: <码>」
    由 main.py 的 403 处理器镜像进 detail 兼容字段，老读取方无感。
    """

    def __init__(self, resource_code: str):
        super().__init__(status_code=403, detail="权限不足")
        self.resource_code = resource_code
        self.legacy_detail = f"缺少权限: {resource_code}"


def get_current_user(request: Request) -> str:
    """Return the authenticated user set by the HTTP authentication middleware."""
    user_identifier = getattr(request.state, "user_identifier", None)
    if not user_identifier:
        raise HTTPException(status_code=403, detail="Token 未绑定可信操作人")
    return user_identifier


def _effective_role_codes(db: Session, user_identifier: str) -> set[str]:
    # 200 R01：有效角色计算统一委托 effective_permissions 服务，
    # 展示（/me、预览）与执行（中间件、端点依赖）共用同一口径。
    return _service_effective_role_codes(db, user_identifier)


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
        # 200 R02：与展示侧共用 normalize_permission_code；历史 allow 行
        # 按"裸资源权限"编码，不再拼成 resource:allow 导致界面勾选而后端拒绝。
        granted = [normalize_permission_code(row.resource, row.action) for row in rows]
        if not any(_permission_matches(item, resource_code) for item in granted):
            raise PermissionDenied(resource_code)
        return user_identifier

    return dependency


def effective_permission_scope(request: Request, db: Session) -> list[str]:
    """215 E5：调用方有效权限码清单（与 require_permission 同口径）。

    用途：AI 上下文缓存键的权限过滤分量。platform_admin 以通配符入键，
    保证未来若按权限裁剪快照内容，不同权限域不会共享缓存条目。
    """
    user_identifier = getattr(request.state, "user_identifier", None)
    if not user_identifier:
        return []
    role_codes = _effective_role_codes(db, user_identifier)
    if "platform_admin" in role_codes:
        return ["platform_admin:*"]
    rows = db.scalars(
        select(AssetRolePermission).where(AssetRolePermission.role_code.in_(role_codes))
    ).all() if role_codes else []
    return sorted(
        {normalize_permission_code(row.resource, row.action) for row in rows}
    )


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
