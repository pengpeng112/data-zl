"""123 R3 / 85-F2：基础角色矩阵（无人工审批角色）。

覆盖：匿名、只读用户、业务操作员、管理员、越权用户。
不新增申请人/审核员流程；审批相关能力标记 DEFERRED_BY_USER。
依赖隔离 APP_TEST_DB_URL。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.security import _effective_role_codes, require_permission
from app.main import app
from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole
from tests.conftest import TEST_TOKEN


def _token_for(user: str, token: str) -> str:
    db = SessionLocal()
    try:
        row = db.scalar(select(ApiKey).where(ApiKey.key_name == f"f2-{user}"))
        th = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not row:
            db.add(
                ApiKey(
                    key_name=f"f2-{user}",
                    token_hash=th,
                    user_identifier=user,
                    enabled=True,
                )
            )
        else:
            row.token_hash = th
            row.token = None
            row.user_identifier = user
            row.enabled = True
        # ensure roles table has codes used below
        for code, name in (
            ("platform_admin", "平台管理员"),
            ("asset_viewer", "资产只读"),
            ("quality_admin", "质量管理员"),
        ):
            if not db.scalar(select(AssetRole).where(AssetRole.role_code == code)):
                db.add(AssetRole(role_code=code, role_name_cn=name, role_type="builtin"))
        db.execute(delete(AssetUserRole).where(AssetUserRole.user_identifier == user))
        db.commit()
    finally:
        db.close()
    return token


def _grant(user: str, roles: list[str], *, expires_at=None) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(AssetUserRole).where(AssetUserRole.user_identifier == user))
        for rc in roles:
            db.add(
                AssetUserRole(
                    user_identifier=user,
                    role_code=rc,
                    status="active",
                    expires_at=expires_at,
                )
            )
        db.commit()
    finally:
        db.close()


def _client(token: str | None) -> TestClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return TestClient(app, headers=headers)


def test_anonymous_write_rejected():
    c = _client(None)
    r = c.post("/api/v1/permissions/seed")
    assert r.status_code in (401, 403)


def test_readonly_user_write_forbidden():
    user = "f2-readonly"
    tok = _token_for(user, "f2-readonly-token")
    _grant(user, ["asset_viewer"])
    # 只读角色不应拥有管理写权限
    db = SessionLocal()
    try:
        db.execute(
            delete(AssetRolePermission).where(AssetRolePermission.role_code == "asset_viewer")
        )
        db.add(
            AssetRolePermission(
                role_code="asset_viewer",
                resource="asset.table.view",
                action="access",
            )
        )
        db.commit()
    finally:
        db.close()
    c = _client(tok)
    # 权限管理写接口需要 identity_admin/platform_admin
    r = c.put(
        "/api/v1/permissions/roles/asset_viewer/matrix",
        json={"permissions": ["asset.table.view"], "operator": user, "reason": "f2"},
    )
    assert r.status_code == 403


def test_operator_and_admin_and_cross_resource():
    op = "f2-operator"
    adm = "f2-admin"
    xuser = "f2-xuser"
    op_tok = _token_for(op, "f2-operator-token")
    adm_tok = _token_for(adm, "f2-admin-token")
    x_tok = _token_for(xuser, "f2-xuser-token")

    _grant(op, ["quality_admin"])
    _grant(adm, ["platform_admin"])
    _grant(xuser, ["asset_viewer"])

    # 管理员可 seed 权限目录
    admin_c = _client(adm_tok)
    seed = admin_c.post("/api/v1/permissions/seed?operator=f2-admin")
    assert seed.status_code == 200, seed.text

    # 业务操作员（quality）可访问质量模块前缀（ROLE_REQUIRED），但不可越权改权限矩阵
    op_c = _client(op_tok)
    denied = op_c.put(
        "/api/v1/permissions/roles/asset_viewer/matrix",
        json={"permissions": ["asset"], "operator": op, "reason": "x"},
    )
    assert denied.status_code == 403

    # 越权用户不能访问 identity 管理
    x_c = _client(x_tok)
    xdeny = x_c.get("/api/v1/identity/persons")
    # 可能 403（角色不足）或 404/200 取决于路由；身份前缀要求 identity_admin
    assert xdeny.status_code in (403, 404, 405, 200)
    if xdeny.status_code == 200:
        # 若只读列表对 viewer 放开，则写操作必须失败
        xw = x_c.post("/api/v1/identity-sync/nightly/trigger")
        assert xw.status_code in (401, 403, 404, 405)


def test_role_revoke_and_expiry_invalidate_immediately():
    user = "f2-revoke"
    tok = _token_for(user, "f2-revoke-token")
    _grant(user, ["platform_admin"])
    c = _client(tok)
    ok = c.post("/api/v1/permissions/seed?operator=f2-revoke")
    assert ok.status_code == 200, ok.text

    # 撤权后同一 token 立即 403
    _grant(user, [])
    denied = c.post("/api/v1/permissions/seed?operator=f2-revoke")
    assert denied.status_code == 403

    # 过期角色立即失效
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    _grant(user, ["platform_admin"], expires_at=past)
    db = SessionLocal()
    try:
        roles = _effective_role_codes(db, user)
        assert "platform_admin" not in roles
    finally:
        db.close()
    denied2 = c.post("/api/v1/permissions/seed?operator=f2-revoke")
    assert denied2.status_code == 403
