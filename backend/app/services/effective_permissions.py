"""200 R01/R02：唯一有效授权计算与权限码归一服务。

展示（/me、权限预览、用户权限查询）与执行（中间件、端点依赖）必须共用
同一份有效角色计算与权限码编码，消除"页面显示的授权不是当前有效授权"
（R01）与"历史 allow 界面已勾选、后端拒绝"（R02）两类不一致。

有效角色定义（与 core.security._effective_role_codes 同一口径，此后该函数
委托到本服务）：status == "active" 且 valid_from <= now 且 expires_at > now。
有效角色为空就是空，禁止回退到全部历史角色。

R02 归一规则：action ∈ {None, "", "access", "allow", "*"} 一律视为"裸资源
权限"（等值 resource 本身）；其余编码为 "resource:action"。历史 allow 行与
新 access 行由此在展示与执行两侧同义，配合 repair_legacy_allow_rows 的
allow→access 幂等修复（旧值到新值，不动用户定制矩阵）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.governance_base import AssetRolePermission, AssetUserRole

# 与裸资源等价的 action 取值（含历史 allow，200 R02 统一口径）。
BARE_RESOURCE_ACTIONS = (None, "", "access", "allow", "*")


def normalize_permission_code(resource: str, action: str | None) -> str:
    """统一权限编码：裸资源 action → resource；否则 resource:action。"""
    if action in BARE_RESOURCE_ACTIONS:
        return resource
    return f"{resource}:{action}"


def is_bare_resource_action(action: str | None) -> bool:
    return action in BARE_RESOURCE_ACTIONS


def effective_role_grants(
    db: Session, user_identifier: str, *, now: datetime | None = None
) -> list[AssetUserRole]:
    """当前时刻有效（active 且在有效期窗口内）的角色授权行。"""
    now = now or datetime.now(timezone.utc)
    return list(
        db.scalars(
            select(AssetUserRole).where(
                AssetUserRole.user_identifier == user_identifier,
                AssetUserRole.status == "active",
                or_(
                    AssetUserRole.valid_from.is_(None),
                    AssetUserRole.valid_from <= now,
                ),
                or_(
                    AssetUserRole.expires_at.is_(None),
                    AssetUserRole.expires_at > now,
                ),
            )
        ).all()
    )


def effective_role_codes(
    db: Session, user_identifier: str, *, now: datetime | None = None
) -> set[str]:
    return {row.role_code for row in effective_role_grants(db, user_identifier, now=now)}


def grant_state(row: AssetUserRole, *, now: datetime | None = None) -> str:
    """单条授权相对当前时刻的状态（展示历史区用，与有效口径一致）。"""
    now = now or datetime.now(timezone.utc)
    if row.status != "active":
        return row.status or "unknown"
    valid_from = row.valid_from
    expires_at = row.expires_at
    if valid_from is not None:
        vf = valid_from if valid_from.tzinfo else valid_from.replace(tzinfo=timezone.utc)
        if vf > now:
            return "pending"
    if expires_at is not None:
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if exp <= now:
            return "expired"
    return "effective"


def grant_payload(row: AssetUserRole, *, state: str | None = None) -> dict:
    return {
        "role_code": row.role_code,
        "state": state or grant_state(row),
        "status": row.status,
        "source": row.source or "direct",
        "request_id": row.request_id,
        "granted_by": row.granted_by,
        "granted_at": row.granted_at.isoformat() if row.granted_at else None,
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def all_role_grants(db: Session, user_identifier: str) -> list[AssetUserRole]:
    return list(
        db.scalars(
            select(AssetUserRole).where(AssetUserRole.user_identifier == user_identifier)
        ).all()
    )


def historical_role_grants(
    db: Session, user_identifier: str, *, now: datetime | None = None
) -> list[dict]:
    """非有效授权（到期/未生效/已撤销）的展示负载，单列历史区，不混入生效区。"""
    now = now or datetime.now(timezone.utc)
    rows = all_role_grants(db, user_identifier)
    payload = [grant_payload(row, state=grant_state(row, now=now)) for row in rows]
    return [item for item in payload if item["state"] != "effective"]


def permission_codes_for_roles(db: Session, role_codes) -> list[str]:
    """角色 → 归一化权限码列表（展示与执行共用编码）。"""
    codes = sorted({c for c in role_codes if c})
    if not codes:
        return []
    rows = db.scalars(
        select(AssetRolePermission).where(AssetRolePermission.role_code.in_(codes))
    ).all()
    permissions = {normalize_permission_code(r.resource, r.action) for r in rows}
    return sorted(permissions)


def legacy_allow_permission_rows(db: Session) -> list[AssetRolePermission]:
    """仍为历史 allow 编码的行（只读差异清单）。"""
    return list(
        db.scalars(
            select(AssetRolePermission).where(AssetRolePermission.action == "allow")
        ).all()
    )


def repair_legacy_allow_rows(db: Session, *, apply: bool = False) -> dict:
    """R02 幂等修复：action=allow → action=access（限定旧值到新值）。

    - 只改 action 值，不增删行、不覆盖角色矩阵的其他定制；
    - apply=False 时只读返回差异清单；apply=True 时执行 UPDATE 并提交；
    - 重复执行零变更（没有 allow 行时 changed=0）。
    生产平台正式 apply 属独立授权事项，本函数不自动调用。
    """
    rows = legacy_allow_permission_rows(db)
    diff = [
        {
            "role_code": row.role_code,
            "resource": row.resource,
            "action_before": row.action,
            "action_after": "access",
        }
        for row in rows
    ]
    if not apply:
        return {"apply": False, "found": len(rows), "changed": 0, "diff": diff}
    for row in rows:
        row.action = "access"
    db.commit()
    return {"apply": True, "found": len(rows), "changed": len(rows), "diff": diff}
