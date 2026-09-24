"""195 缺陷1 补强（202 D2-3）：真实 HTTP 路由级测试。

经 FastAPI TestClient 走完整中间件（ApiKey 双凭证→身份→_enforce_rbac 195
豁免清单）+ 端点 require_permission("ai.context.read")：
1) 仅持 ai.context.read 的账号可访问六个豁免端点与 /context/*；
2) 无角色/无权限账号 403；
3) 未挂权限码的 AI 路由（/sessions）对 pilot 仍拒（粗门禁）；
4) ai-accuracy 前缀不受影响。

纯逻辑：独立 sqlite 文件库（多连接安全），不触外部数据库。
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

_TOKEN = "t195-ai-context-pilot-key-0001"
_TOKEN_NOROLE = "t195-no-role-key-0002"


@pytest.fixture()
def http_env(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="plan195_http_")
    db_file = Path(tmpdir) / "http_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})

    from app.core.db import Base
    from app.models import ai_collab as aic_models
    from app.models import asset as asset_models
    from app.models import asset_system as system_models
    from app.models import auth as auth_models
    from app.models import governance_base as gb_models
    from app.models import value_domain as vd_models
    from app.models.governance import ApiKey

    tables = [
        auth_models.AuthUser.__table__,
        gb_models.AssetRole.__table__,
        gb_models.AssetRolePermission.__table__,
        gb_models.AssetUserRole.__table__,
        ApiKey.__table__,
        system_models.AssetSystem.__table__,
        asset_models.AssetTable.__table__,
        asset_models.AssetColumn.__table__,
        asset_models.AssetRelation.__table__,
        vd_models.AssetColumnValueDomain.__table__,
        vd_models.AssetColumnValueDomainVersion.__table__,
        # ai 路由 handler 会话/调用/上下文表（history 等端点查询）
        aic_models.AiSession.__table__,
        aic_models.AiToolCall.__table__,
        aic_models.ViewDraft.__table__,
        aic_models.AiContextSnapshot.__table__,
    ]
    # ATTACH asset schema（模型表都在 asset 下）
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _attach(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute(f"ATTACH DATABASE '{db_file.as_posix()}' AS asset")
        cur.close()

    with engine.begin() as conn:
        Base.metadata.create_all(conn, tables=tables)

    # 种子：角色/权限/账号/ApiKey
    with Session(engine) as s:
        # effective_permissions 会回查 AuthUser：两个身份都要有账号行
        s.add(auth_models.AuthUser(username="qa_p195_pilot", password_hash="x", user_identifier="QA_P195_PILOT", enabled=True))
        s.add(auth_models.AuthUser(username="qa_p195_norole", password_hash="x", user_identifier="QA_P195_NOROLE", enabled=True))
        s.add(gb_models.AssetRole(role_code="ai195_pilot", role_name_cn="195 HTTP 测试试点", role_type="custom"))
        s.add(gb_models.AssetRolePermission(role_code="ai195_pilot", resource="ai.context.read", action="access"))
        s.add(gb_models.AssetUserRole(user_identifier="QA_P195_PILOT", role_code="ai195_pilot"))
        s.add(ApiKey(key_name="pilot", token_hash=hashlib.sha256(_TOKEN.encode()).hexdigest(),
                     enabled=True, user_identifier="QA_P195_PILOT"))
        s.add(ApiKey(key_name="norole", token_hash=hashlib.sha256(_TOKEN_NOROLE.encode()).hexdigest(),
                     enabled=True, user_identifier="QA_P195_NOROLE"))
        s.commit()

    import app.main as main_mod

    _orig = main_mod.SessionLocal
    monkeypatch.setattr(main_mod, "SessionLocal", lambda: Session(engine))

    # sqlite 读回 TIMESTAMP 为 naive，_check_token 节流分支的 aware 相减在
    # 二次请求会 TypeError（生产 PG 读回 aware 不触发）。本测聚焦权限链路，
    # 用免节流版 _check_token（认证/过期校验保留，仅跳过 last_used_at 更新）。
    import hashlib as _hl

    def _check_token_no_throttle(db, token):
        from app.models.governance import ApiKey as _AK
        from datetime import datetime, timezone as _tz
        token_hash = _hl.sha256(token.encode("utf-8")).hexdigest()
        key = db.scalar(
            __import__("sqlalchemy").select(_AK).where(
                _AK.enabled.is_(True),
                (_AK.token_hash == token_hash) | (_AK.token == token),
            )
        )
        if not key:
            return False, "无效或已禁用的 API Token", None
        if getattr(_AK, "expires_at", None) and key.expires_at and datetime.now(_tz.utc) > key.expires_at:
            return False, "API Token 已过期", None
        return True, None, key

    monkeypatch.setattr(main_mod, "_check_token", _check_token_no_throttle)

    from app.api.v1.ai import router as ai_router  # noqa: F401 确保已加载
    from app.core.db import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: Session(engine)
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_db, None)
    monkeypatch.setattr(main_mod, "SessionLocal", _orig)
    engine.dispose()


H = {"Authorization": f"Bearer {_TOKEN}"}
H_NOROLE = {"Authorization": f"Bearer {_TOKEN_NOROLE}"}

EXEMPT_GET = [
    "/api/v1/ai/system-context?system_code=DATA_CENTER",
    "/api/v1/ai/ai-sql/history",
    "/api/v1/ai/context/any-id",
]
EXEMPT_POST = [
    "/api/v1/ai/propose-sql",
    "/api/v1/ai/context/resolve",
]
UNARMED = "/api/v1/ai/sessions"


def test_pilot_can_access_exempted_endpoints(http_env):
    for url in EXEMPT_GET:
        r = http_env.get(url, headers=H)
        assert r.status_code != 403, (url, r.status_code, r.text[:150])
    for url in EXEMPT_POST:
        r = http_env.post(url, headers=H, json={"question": "q", "selected_tables": []})
        # 进入业务校验（400/422 均可），只要不是 401/403 权限拦截
        assert r.status_code not in (401, 403), (url, r.status_code, r.text[:150])


def test_norole_account_denied(http_env):
    for url in EXEMPT_GET + [UNARMED]:
        r = http_env.get(url, headers=H_NOROLE)
        assert r.status_code in (401, 403), (url, r.status_code, r.text[:200])


def test_unarmed_ai_route_still_coarse_gated_for_pilot(http_env):
    """仅持 ai.context.read 的账号在未挂码路由仍被粗门禁拒（豁免未扩大）。"""
    r = http_env.get(UNARMED, headers=H)
    assert r.status_code == 403, (r.status_code, r.text[:150])


def test_ai_accuracy_prefix_unaffected(http_env):
    r = http_env.get("/api/v1/ai-accuracy/feedback", headers=H)
    assert r.status_code == 403, (r.status_code, r.text[:150])
