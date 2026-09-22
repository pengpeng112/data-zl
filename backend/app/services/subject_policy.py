"""200 R04：对象级主体管理策略（can_manage_subject / can_grant_role）。

所有创建账号、替换角色、申请执行、密钥绑定、账号重置/换绑入口共享同一份
对象级判定，端点权限码之外补齐"操作者→目标主体"的边界：

- 非 platform_admin 不得操作 platform_admin 身份（改角色/换绑/停用/绑密钥）；
- 任何操作者不得授予自己没有资格授予的高风险角色（platform_admin）；
- 至少保护最后一个有效可登录管理员，拒绝并发删除/停用/撤权导致零管理员；
- 角色存在性与目标主体存在性由调用方先行校验，本模块专注边界判定。

判定基于"当前有效角色"（effective_permissions 口径）；目标保护采用保守
口径：目标名下存在任意未撤销（含未生效）的 platform_admin 授权即视为受
保护主体，防止用"先到期再操作"的窗口绕过。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.auth import AuthUser
from ..models.governance_base import AssetUserRole
from .effective_permissions import effective_role_codes

# 高风险角色：仅 platform_admin 可授予/操作（200 R04）。
PROTECTED_ROLES = frozenset({"platform_admin"})


class SubjectPolicyError(Exception):
    """对象级策略拒绝（端点转 403/409，附带稳定 reason_code）。"""

    def __init__(self, reason_code: str, message: str, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


def operator_role_codes(db: Session, operator: str | None) -> set[str]:
    if not operator:
        return set()
    return effective_role_codes(db, operator)


def target_granted_roles(db: Session, target_user: str) -> set[str]:
    """目标名下全部未撤销授权（保守口径，含未生效/已到期未撤销行）。"""
    rows = db.scalars(
        select(AssetUserRole).where(
            AssetUserRole.user_identifier == target_user,
            AssetUserRole.status != "revoked",
        )
    ).all()
    return {row.role_code for row in rows}


def can_manage_subject(
    db: Session, *, operator: str | None, operator_roles: set[str], target_user: str
) -> None:
    """操作者是否可以管理目标主体；不允许时抛 SubjectPolicyError。"""
    if not target_user:
        return
    if "platform_admin" in operator_roles:
        return
    target_roles = target_granted_roles(db, target_user)
    if PROTECTED_ROLES & target_roles:
        raise SubjectPolicyError(
            "protected_subject",
            "目标主体持有平台管理员授权，仅平台管理员可以操作",
        )


def can_grant_role(
    db: Session,
    *,
    operator: str | None,
    operator_roles: set[str],
    target_user: str,
    role_code: str,
) -> None:
    """单个角色授予边界；不允许时抛 SubjectPolicyError。

    规则（200 R04）：
    1. 高风险角色（platform_admin）仅 platform_admin 可授予；
    2. 非平台管理员不能操作受保护主体（先过 can_manage_subject）；
    3. 用户不能给自己增加超出批准范围的权限（自授高危角色一律拒绝；
       platform_admin 自身的高危自授权同样拒绝，避免单请求内自提权）。
    """
    if role_code in PROTECTED_ROLES and "platform_admin" not in operator_roles:
        raise SubjectPolicyError(
            "grant_role_forbidden",
            "仅平台管理员可以授予平台管理员角色",
        )
    can_manage_subject(db, operator=operator, operator_roles=operator_roles, target_user=target_user)
    if operator and target_user and operator == target_user and role_code in PROTECTED_ROLES:
        raise SubjectPolicyError(
            "self_grant_forbidden",
            "不能给自己授予平台管理员角色",
        )


def enabled_platform_admin_identifiers(db: Session) -> set[str]:
    """有效可登录（账号启用）且当前有效持有 platform_admin 的身份集合。"""
    effective_admins = {
        row.user_identifier
        for row in db.scalars(
            select(AssetUserRole).where(
                AssetUserRole.role_code == "platform_admin",
                AssetUserRole.status == "active",
            )
        ).all()
        if row.user_identifier
    }
    if not effective_admins:
        return set()
    accounts = db.scalars(
        select(AuthUser).where(
            AuthUser.enabled.is_(True),
            AuthUser.user_identifier.in_(effective_admins),
        )
    ).all()
    return {acc.user_identifier for acc in accounts if acc.user_identifier}


def ensure_not_losing_last_platform_admin(
    db: Session, *, losing_identifiers: set[str]
) -> None:
    """并发停用/撤权前的最后管理员保护（200 R04 / T36）。

    losing_identifiers：本操作将使其失去有效 platform_admin 的身份集合。
    若移除后有效可登录管理员归零则拒绝（409）。
    """
    remaining = enabled_platform_admin_identifiers(db) - set(losing_identifiers)
    if not remaining:
        raise SubjectPolicyError(
            "last_platform_admin",
            "操作将移除最后一个有效可登录的平台管理员，已拒绝",
            status_code=409,
        )
