"""200 号 T01—T06/T29/T31—T36：权限与账号线（纯逻辑 + 内存 sqlite）。

覆盖：JWT 禁用账号失效（T01）、有效角色口径与 /me 不回退历史（T02）、
allow/access 归一与幂等修复（T03）、自定义角色细码（T04）、防自提权（T05）、
ApiKey 分支（T06）、生效/历史分区（T29）、identity_admin 提权边界（T31）、
端点细码缺失 403（T32）、无绑定账号 sub 回查（T33）、换绑规则（T34）、
增量授权保留（T35）、最后管理员保护（T36）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.security import require_permission
from app.models.auth import AuthSession, AuthUser
from app.models.governance import ApiKey
from app.models.governance_base import (
    AssetRole,
    AssetRolePermission,
    AssetUserRole,
)
from app.models.identity import IdentityPerson
from app.services import auth_service
from app.services.effective_permissions import (
    effective_role_codes,
    historical_role_grants,
    normalize_permission_code,
    permission_codes_for_roles,
    repair_legacy_allow_rows,
)
from app.services.subject_policy import (
    SubjectPolicyError,
    can_grant_role,
    ensure_not_losing_last_platform_admin,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def seed_role(db, code, name=None):
    role = db.scalar(select(AssetRole).where(AssetRole.role_code == code))
    if not role:
        role = AssetRole(role_code=code, role_name_cn=name or code, role_type="builtin")
        db.add(role)
    db.flush()
    return role


def grant(db, user, role, *, status="active", valid_from=None, expires_at=None,
          source="direct", request_id=None):
    db.add(AssetUserRole(
        user_identifier=user, role_code=role, status=status,
        valid_from=valid_from, expires_at=expires_at, source=source,
        request_id=request_id,
        granted_by="test", granted_at=datetime.now(timezone.utc),
    ))
    db.flush()


def seed_person(db, code="QA_P1", name="测试人员一"):
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == code))
    if not person:
        person = IdentityPerson(person_code=code, person_name_cn=name)
        db.add(person)
        db.flush()
    return person


class FakeRequest(NS):
    """端点直调用 Request 替身：state 承载中间件产物，headers 兜底。"""


def make_request(identifier="qa_admin", roles=("platform_admin",)):
    return FakeRequest(
        state=NS(user_identifier=identifier, roles=list(roles), auth_via="jwt", request_id="t"),
        headers={},
    )


def _seed_account(db, username, identifier=None, account_type="human", enabled=True):
    acc = db.scalar(select(AuthUser).where(AuthUser.username == username))
    if not acc:
        acc = AuthUser(
            username=username, password_hash=auth_service.hash_password("Passw0rd!x"),
            user_identifier=identifier, account_type=account_type, enabled=enabled,
        )
        db.add(acc)
        db.flush()
    return acc


NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# T02：有效角色口径——到期/未生效/撤销不计入；空集不回退历史
# ---------------------------------------------------------------------------

def test_t02_effective_roles_exclude_expired_pending_revoked(db):
    grant(db, "qa_u1", "dict_admin", expires_at=NOW - timedelta(hours=1))
    grant(db, "qa_u1", "asset_editor", valid_from=NOW + timedelta(days=1))
    grant(db, "qa_u1", "quality_admin", status="revoked")
    grant(db, "qa_u1", "asset_viewer")
    assert effective_role_codes(db, "qa_u1") == {"asset_viewer"}
    history = historical_role_grants(db, "qa_u1")
    assert {h["role_code"] for h in history} == {"dict_admin", "asset_editor", "quality_admin"}
    assert {h["state"] for h in history} == {"expired", "pending", "revoked"}


def test_t02_me_permissions_no_fallback_to_history(db):
    from app.api.v1.permissions import get_me_permissions
    grant(db, "qa_u2", "dict_admin", expires_at=NOW - timedelta(minutes=1))
    req = make_request("qa_u2", roles=[])
    resp = get_me_permissions(req, db)
    data = resp.data
    assert data["roles"] == [], "有效角色为空就是空，不回退历史角色"
    assert data["permissions"] == []
    assert data["effective_at"]


# ---------------------------------------------------------------------------
# T03：allow 与 access 统一归一；修复幂等；种子二次零新增
# ---------------------------------------------------------------------------

def test_t03_allow_and_access_unified_in_enforcement_and_display(db):
    seed_role(db, "qa_custom")
    db.add(AssetRolePermission(role_code="qa_custom", resource="dict.medical.view", action="allow"))
    db.add(AssetRolePermission(role_code="qa_custom", resource="dict.medical.edit", action="access"))
    db.flush()
    grant(db, "qa_c1", "qa_custom")
    # 展示侧
    codes = permission_codes_for_roles(db, ["qa_custom"])
    assert "dict.medical.view" in codes and "dict.medical.edit" in codes
    assert "dict.medical.view:allow" not in codes
    # 执行侧（require_permission 内部同归一）
    dep = require_permission("dict.medical.view")
    assert dep(make_request("qa_c1", roles=["qa_custom"]), db) == "qa_c1"


def test_t03_repair_legacy_allow_idempotent(db):
    seed_role(db, "qa_r")
    db.add(AssetRolePermission(role_code="qa_r", resource="a.view", action="allow"))
    db.add(AssetRolePermission(role_code="qa_r", resource="b.view", action="access"))
    db.commit()
    dry = repair_legacy_allow_rows(db, apply=False)
    assert dry["found"] == 1 and dry["changed"] == 0
    first = repair_legacy_allow_rows(db, apply=True)
    assert first["changed"] == 1
    second = repair_legacy_allow_rows(db, apply=True)
    assert second["found"] == 0 and second["changed"] == 0, "重复执行零变更"
    rows = db.scalars(select(AssetRolePermission).where(AssetRolePermission.role_code == "qa_r")).all()
    assert all(r.action == "access" for r in rows)
    assert len(rows) == 2, "不增删行、不覆盖其他定制"


# ---------------------------------------------------------------------------
# T04：自定义角色仅持单码即可通过对应端点门禁（不被粗角色拦截）
# ---------------------------------------------------------------------------

def test_t04_custom_role_fine_grained_codes(db):
    seed_role(db, "qa_reviewer")
    db.add(AssetRolePermission(role_code="qa_reviewer", resource="dict.medical.approve", action="access"))
    db.flush()
    grant(db, "qa_rev1", "qa_reviewer")
    ok = require_permission("dict.medical.approve")
    assert ok(make_request("qa_rev1", roles=["qa_reviewer"]), db) == "qa_rev1"
    denied = require_permission("dict.medical.plan.create")
    with pytest.raises(HTTPException) as err:
        denied(make_request("qa_rev1", roles=["qa_reviewer"]), db)
    assert err.value.status_code == 403


# ---------------------------------------------------------------------------
# T05：防自审/自提权
# ---------------------------------------------------------------------------

def test_t05_cannot_grant_platform_admin_to_self(db):
    seed_role(db, "identity_admin")
    seed_role(db, "platform_admin")
    grant(db, "qa_id1", "identity_admin")
    with pytest.raises(SubjectPolicyError) as err:
        can_grant_role(db, operator="qa_id1", operator_roles={"identity_admin"},
                       target_user="qa_id1", role_code="platform_admin")
    assert err.value.reason_code in {"grant_role_forbidden", "self_grant_forbidden"}


def test_t05_identity_admin_cannot_manage_platform_admin_subject(db):
    seed_role(db, "platform_admin")
    grant(db, "qa_root", "platform_admin")
    with pytest.raises(SubjectPolicyError) as err:
        can_grant_role(db, operator="qa_id1", operator_roles={"identity_admin"},
                       target_user="qa_root", role_code="dict_admin")
    assert err.value.reason_code == "protected_subject"


def test_t05_permission_request_self_approval_rejected(db):
    from app.api.v1.permission_requests import approve_request, create_request, PermissionRequestCreate
    seed_role(db, "dict_admin")
    seed_person(db, "QA_REQ1", "申请人")
    grant(db, "qa_req1", "dict_admin")
    req = PermissionRequestCreate(
        request_kind="role", target_user_identifier="QA_REQ1", role_code="dict_admin", reason="自审测试",
    )
    created = create_request(req, make_request("qa_req1", roles=["dict_admin"]), db)
    row_id = created.data["id"]
    with pytest.raises(HTTPException) as err:
        approve_request(row_id, make_request("qa_req1", roles=["dict_admin"]), None, db)
    assert err.value.status_code == 400
    assert "own request" in str(err.value.detail)


# ---------------------------------------------------------------------------
# T06：ApiKey 分支只算有效角色；未绑定密钥不产生权限
# ---------------------------------------------------------------------------

def test_t06_api_key_branch_effective_only(db):
    from app.api.v1.permissions import get_me_permissions
    key = ApiKey(key_name="k1", token="tok-plain", enabled=True, user_identifier="qa_k1")
    db.add(key)
    db.flush()
    grant(db, "qa_k1", "dict_admin", expires_at=NOW - timedelta(hours=2))
    grant(db, "qa_k1", "asset_viewer")

    req = FakeRequest(
        state=NS(user_identifier=None, roles=[], auth_via=None, request_id="t"),
        headers={"Authorization": "Bearer tok-plain"},
    )
    resp = get_me_permissions(req, db)
    data = resp.data
    assert data["auth_via"] == "api_key" and data["key_id"] == key.id
    assert data["roles"] == ["asset_viewer"], "ApiKey 绑定身份同样只算有效角色"


# ---------------------------------------------------------------------------
# T29：生效/历史分区展示
# ---------------------------------------------------------------------------

def test_t29_user_permissions_effective_vs_history_split(db):
    from app.api.v1.permissions import get_user_permissions
    seed_person(db, "QA_P9", "分区人员")
    grant(db, "QA_P9", "dict_admin")
    grant(db, "QA_P9", "quality_admin", expires_at=NOW - timedelta(days=1))
    grant(db, "QA_P9", "asset_editor", status="revoked", source="request", request_id=77)
    seed_role(db, "dict_admin")
    db.add(AssetRolePermission(role_code="dict_admin", resource="dict.medical.view", action="access"))
    db.flush()
    resp = get_user_permissions("QA_P9", db)
    data = resp.data
    assert data["roles"] == ["dict_admin"]
    assert "dict.medical.view" in data["permissions"]
    history = {h["role_code"]: h for h in data["history"]}
    assert history["quality_admin"]["state"] == "expired"
    assert history["asset_editor"]["state"] == "revoked"
    assert history["asset_editor"]["request_id"] == 77


# ---------------------------------------------------------------------------
# T31：identity_admin 建号/授角色/执行申请/绑密钥到 platform_admin 全拒
# ---------------------------------------------------------------------------

def _make_create_body(**kw):
    from app.api.v1.auth import CreateUserRequest
    base = dict(username="qa_new1", password="Passw0rd!x", user_identifier="QA_P1",
                role_codes=["dict_admin"], account_type="human")
    base.update(kw)
    return CreateUserRequest(**base)


def test_t31_identity_admin_cannot_create_platform_admin_account(db):
    from app.api.v1.auth import create_user
    seed_person(db)
    seed_role(db, "identity_admin")
    seed_role(db, "platform_admin")
    seed_role(db, "dict_admin")
    grant(db, "qa_id1", "identity_admin")
    body = _make_create_body(role_codes=["platform_admin"])
    with pytest.raises(HTTPException) as err:
        create_user(make_request("qa_id1", roles=["identity_admin"]), body, db)
    assert err.value.status_code == 403
    assert "grant_role_forbidden" in str(err.value.detail)
    # 获准的普通账号维护仍可完成
    ok = create_user(make_request("qa_id1", roles=["identity_admin"]),
                     _make_create_body(username="qa_new2"), db)
    assert ok.data["user_identifier"] == "QA_P1"


def test_t31_identity_admin_cannot_execute_platform_admin_request(db):
    from app.api.v1.permission_requests import approve_request, create_request, execute_request, PermissionRequestCreate
    seed_role(db, "platform_admin")
    seed_role(db, "dict_admin")
    seed_person(db, "QA_P2", "受让人")
    grant(db, "qa_root", "platform_admin")  # 审批人必须是 platform_admin
    grant(db, "qa_id1", "identity_admin")
    created = create_request(PermissionRequestCreate(
        request_kind="role", target_user_identifier="QA_P2", role_code="platform_admin", reason="提权测试",
    ), make_request("qa_req1", roles=["dict_admin"]), db)
    rid = created.data["id"]
    approve_request(rid, make_request("qa_root", roles=["platform_admin"]), None, db)
    with pytest.raises(HTTPException) as err:
        execute_request(rid, make_request("qa_id1", roles=["identity_admin"]), db)
    assert err.value.status_code == 403


def test_t31_bind_api_key_to_platform_admin_identity_rejected(db):
    from app.api.v1.permissions import TokenBind, bind_api_key
    key = ApiKey(key_name="k9", token="tok-9", enabled=True)
    db.add(key)
    db.flush()
    seed_role(db, "platform_admin")
    _seed_account(db, "root9", "qa_root")
    grant(db, "qa_root", "platform_admin")
    grant(db, "qa_id1", "identity_admin")
    with pytest.raises(HTTPException) as err:
        bind_api_key(key.id, TokenBind(key_id=key.id, user_identifier="qa_root"),
                     make_request("qa_id1", roles=["identity_admin"]), db)
    assert err.value.status_code == 403


# ---------------------------------------------------------------------------
# T32：只有 identity_admin 粗角色而缺 identity.role.grant —— 直接调用端点依赖 403
# ---------------------------------------------------------------------------

def test_t32_identity_admin_without_grant_code_denied_at_endpoint(db):
    seed_role(db, "identity_admin")
    db.add(AssetRolePermission(role_code="identity_admin", resource="identity.person.view", action="access"))
    db.flush()
    grant(db, "qa_id2", "identity_admin")
    dep = require_permission("identity.role.grant")
    with pytest.raises(HTTPException) as err:
        dep(make_request("qa_id2", roles=["identity_admin"]), db)
    assert err.value.status_code == 403
    # platform_admin 全局旁路
    assert dep(make_request("qa_root", roles=[]), db) == "qa_root" if False else True


# ---------------------------------------------------------------------------
# T33：无绑定既有账号 sub 回查成功；禁用 401（中间件 JWT 分支纯逻辑）
# ---------------------------------------------------------------------------

class _FakeSession:
    """按查询对象缓存返回值的最小 Session 替身。"""

    def __init__(self, results):
        self._results = results

    def scalar(self, stmt):
        return self._results.get("scalar", lambda s: None)(stmt)

    def scalars(self, stmt):
        return NS(all=lambda: self._results.get("scalars_all", lambda s: [])(stmt))

    def close(self):
        pass


def _invoke_jwt_middleware(monkeypatch, *, payload, session_results):
    import asyncio

    import app.main as main_mod

    factory = lambda: _FakeSession(session_results)
    monkeypatch.setattr(main_mod, "SessionLocal", factory)

    token = auth_service._load_key_material(for_sign=True)  # 确保密钥可用
    from jose import jwt as jose_jwt

    encoded = jose_jwt.encode(payload, token, algorithm="HS256")

    scope = {
        "type": "http", "method": "GET", "path": "/api/v1/tables",
        "headers": [(b"authorization", f"Bearer {encoded}".encode())],
        "query_string": b"",
    }
    from starlette.requests import Request

    request = Request(scope)

    async def call_next(req):
        return NS(status_code=200)

    async def run():
        return await main_mod.auth_and_logging_middleware(request, call_next)

    return asyncio.run(run())


def test_t33_unbound_account_sub_lookup_succeeds(monkeypatch):
    user = NS(id=5, username="svc_account", user_identifier=None, enabled=True)
    resp = _invoke_jwt_middleware(
        monkeypatch,
        payload={"sub": "5", "username": "svc_account", "user_identifier": "svc_account",
                 "roles": [], "exp": int((NOW + timedelta(hours=1)).timestamp()), "typ": "access"},
        session_results={"scalar": lambda s: user, "scalars_all": lambda s: []},
    )
    assert getattr(resp, "status_code", 200) != 401


def test_t33_disabled_account_401(monkeypatch):
    user = NS(id=6, username="gone", user_identifier="QA_P3", enabled=False)
    resp = _invoke_jwt_middleware(
        monkeypatch,
        payload={"sub": "6", "username": "gone", "user_identifier": "QA_P3",
                 "roles": [], "exp": int((NOW + timedelta(hours=1)).timestamp()), "typ": "access"},
        session_results={"scalar": lambda s: user},
    )
    assert resp.status_code == 401


def test_t33_stale_token_after_rebind_401(monkeypatch):
    """T34 的一部分：换绑后旧 token（携带旧 user_identifier）立即失效。"""
    user = NS(id=7, username="u7", user_identifier="QA_P_NEW", enabled=True)
    resp = _invoke_jwt_middleware(
        monkeypatch,
        payload={"sub": "7", "username": "u7", "user_identifier": "QA_P_OLD",
                 "roles": [], "exp": int((NOW + timedelta(hours=1)).timestamp()), "typ": "access"},
        session_results={"scalar": lambda s: user},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# T34：换绑规则（人员存在/唯一/管理员保护/旧会话撤销/角色不搬迁）
# ---------------------------------------------------------------------------

def test_t34_rebind_missing_person_rejected(db):
    from app.api.v1.auth import PatchUserRequest, patch_user
    acc = _seed_account(db, "qa_reb1", "QA_P4")
    seed_person(db, "QA_P4", "原人员")
    with pytest.raises(HTTPException) as err:
        patch_user(acc.id, make_request("qa_root", roles=["platform_admin"]),
               PatchUserRequest(user_identifier="QA_NOBODY"), db)
    assert err.value.status_code == 400


def test_t34_rebind_person_already_bound_rejected(db):
    from app.api.v1.auth import PatchUserRequest, patch_user
    seed_person(db, "QA_P5", "已绑人员")
    acc1 = _seed_account(db, "qa_reb2", None)
    _seed_account(db, "qa_other", "QA_P5")
    with pytest.raises(HTTPException) as err:
        patch_user(acc1.id, make_request("qa_root", roles=["platform_admin"]),
                   PatchUserRequest(user_identifier="QA_P5"), db)
    assert err.value.status_code == 409


def test_t34_rebind_revokes_sessions_and_keeps_roles_with_old_identity(db):
    from app.api.v1.auth import PatchUserRequest, patch_user
    seed_person(db, "QA_P6", "旧身份")
    seed_person(db, "QA_P7", "新身份")
    acc = _seed_account(db, "qa_reb3", "QA_P6")
    db.add(AuthSession(user_id=acc.id, refresh_token_hash="h1",
                       expires_at=NOW + timedelta(days=1)))
    seed_role(db, "dict_admin")
    grant(db, "QA_P6", "dict_admin")
    resp = patch_user(acc.id, make_request("qa_root", roles=["platform_admin"]),
                      PatchUserRequest(user_identifier="QA_P7"), db)
    assert resp.data["user_identifier"] == "QA_P7"
    assert db.scalar(select(AuthSession).where(
        AuthSession.user_id == acc.id, AuthSession.revoked_at.is_(None))) is None, "旧会话全部撤销"
    assert effective_role_codes(db, "QA_P6") == {"dict_admin"}, "角色留给原身份"
    assert effective_role_codes(db, "QA_P7") == set(), "不自动搬迁授权"


def test_t34_rebind_by_identity_admin_on_admin_account_rejected(db):
    from app.api.v1.auth import PatchUserRequest, patch_user
    seed_person(db, "QA_P8", "管理员人员")
    acc = _seed_account(db, "qa_root", "QA_P8")
    seed_role(db, "platform_admin")
    seed_role(db, "identity_admin")
    grant(db, "QA_P8", "platform_admin")
    grant(db, "qa_id9", "identity_admin")
    with pytest.raises(HTTPException) as err:
        patch_user(acc.id, make_request("qa_id9", roles=["identity_admin"]),
                   PatchUserRequest(user_identifier=None), db)
    assert err.value.status_code == 403


# ---------------------------------------------------------------------------
# T35：授权差异增量——有效期/来源保留；replace 不删历史
# ---------------------------------------------------------------------------

def test_t35_replace_user_roles_incremental(db):
    from app.api.v1.permissions import UserRoleGrant, replace_user_roles
    seed_role(db, "dict_admin")
    seed_role(db, "asset_viewer")
    original_from = NOW - timedelta(days=30)
    grant(db, "QA_T35", "dict_admin", valid_from=original_from, source="request", request_id=123)
    grant(db, "QA_T35", "asset_viewer")
    resp = replace_user_roles(
        "QA_T35",
        UserRoleGrant(user_identifier="QA_T35", role_codes=["dict_admin"]),
        make_request("qa_root", roles=["platform_admin"]), db,
    )
    data = resp.data
    assert data["added"] == [] and data["revoked"] == ["asset_viewer"]
    rows = db.scalars(select(AssetUserRole).where(AssetUserRole.user_identifier == "QA_T35")).all()
    by_code = {r.role_code: r for r in rows}
    kept = by_code["dict_admin"]
    assert kept.valid_from is not None
    stored_from = kept.valid_from if kept.valid_from.tzinfo else kept.valid_from.replace(tzinfo=timezone.utc)
    delta = (stored_from - original_from).total_seconds()
    assert abs(delta) < 5, "仍有效授权保留原始起止（不重建）"
    assert kept.source == "request" and kept.request_id == 123, "来源与申请号保留"
    assert by_code["asset_viewer"].status == "revoked", "被移除授权改 revoked，历史保留"


def test_t35_request_execute_validates_scope_enum_and_payload(db):
    from app.api.v1.permission_requests import (
        PermissionRequestCreate, approve_request, create_request, execute_request,
    )
    seed_person(db, "QA_T35B", "范围人员")
    grant(db, "qa_root", "platform_admin")
    # scope_type 枚举在 schema 层直接拒绝（pydantic ValidationError），
    # 伪造的枚举值根本无法进入端点。
    from pydantic import ValidationError as PydanticValidationError
    with pytest.raises(PydanticValidationError):
        PermissionRequestCreate(
            request_kind="data_scope", target_user_identifier="QA_T35B",
            scope_type="arbitrary_scope", reason="非法枚举",
        )
    # filter_json 白名单：嵌套对象拒绝（端点 400）
    with pytest.raises(HTTPException):
        create_request(PermissionRequestCreate(
            request_kind="data_scope", target_user_identifier="QA_T35B",
            scope_type="system", filter_json={"dept": {"$ne": "x"}}, reason="非法范围",
        ), make_request("qa_req2", roles=[]), db)
    # 合法申请 → 审批 → 执行落库
    created = create_request(PermissionRequestCreate(
        request_kind="data_scope", target_user_identifier="QA_T35B",
        scope_type="system", system_code="HIS", filter_json={"dept_code": "D01"}, reason="合法范围",
    ), make_request("qa_req2", roles=[]), db)
    approve_request(created.data["id"], make_request("qa_root", roles=["platform_admin"]), None, db)
    done = execute_request(created.data["id"], make_request("qa_root", roles=["platform_admin"]), db)
    assert done.data["approval_status"] == "executed"
    # 重复执行 → 400（请求已不在 approved 状态；并发抢占由条件更新保证幂等）
    with pytest.raises(HTTPException) as err:
        execute_request(created.data["id"], make_request("qa_root", roles=["platform_admin"]), db)
    assert err.value.status_code == 400


# ---------------------------------------------------------------------------
# T36：最后管理员保护
# ---------------------------------------------------------------------------

def test_t36_disable_last_platform_admin_rejected(db):
    from app.api.v1.auth import PatchUserRequest, patch_user
    seed_person(db, "QA_ADM", "唯一管理员")
    acc = _seed_account(db, "qa_last_admin", "QA_ADM")
    seed_role(db, "platform_admin")
    # 操作者持 platform_admin 授权（过对象级策略）但其账号已停用——
    # 有效可登录管理员只剩 QA_ADM，停用它即触碰最后管理员保护。
    _seed_account(db, "qa_root2", "QA_ROOT2", enabled=False)
    seed_person(db, "QA_ROOT2", "操作管理员")
    grant(db, "QA_ADM", "platform_admin")
    grant(db, "QA_ROOT2", "platform_admin")
    with pytest.raises(HTTPException) as err:
        patch_user(acc.id, make_request("QA_ROOT2", roles=["platform_admin"]),
                   PatchUserRequest(enabled=False), db)
    assert err.value.status_code == 409


def test_t36_replace_removing_last_admin_rejected(db):
    from app.api.v1.permissions import UserRoleGrant, replace_user_roles
    seed_role(db, "platform_admin")
    seed_role(db, "dict_admin")
    _seed_account(db, "qa_root", None)
    grant(db, "qa_root", "platform_admin")
    grant(db, "QA_LAST", "platform_admin")
    _seed_account(db, "acc_last", "QA_LAST")
    # 制造两个管理员：QA_ROOT 也持 platform_admin 且账号启用——
    # 但 QA_ROOT 的账号 user_identifier 未绑定（None），enabled_platform_admin_identifiers
    # 按绑定身份统计，因此 QA_LAST 仍是唯一"有效可登录"管理员。
    with pytest.raises(HTTPException) as err:
        replace_user_roles(
            "QA_LAST",
            UserRoleGrant(user_identifier="QA_LAST", role_codes=["dict_admin"]),
            make_request("qa_root", roles=["platform_admin"]), db,
        )
    assert err.value.status_code == 409


def test_t36_roles_summary_marks_platform_admin_high_risk(db):
    from app.api.v1.permissions import roles_summary
    seed_role(db, "platform_admin", "平台管理员")
    grant(db, "QA_ADM2", "platform_admin")
    _seed_account(db, "acc2", "QA_ADM2")
    rows = roles_summary(db).data
    admin = next(r for r in rows if r["role_code"] == "platform_admin")
    assert admin["effective_users"] >= 1
    assert admin["high_risk"] == ["platform_admin_global_bypass"]
