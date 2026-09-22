"""200 号 plan200 子目录 conftest：纯逻辑/内存 sqlite 测试，不连任何业务库。

- 覆盖根 conftest 的 autouse clean_test_database（no-op）；
- 未配置 APP_TEST_DB_URL 时注入一次性 sqlite 测试 URL（database_guard 仅
  校验 URL 形态；引擎惰性构造，本目录从不使用 core.db 引擎）；
- 用专用内存 sqlite 引擎建权限/账号/字典下发相关表（JSONB 在 sqlite 上
  编译为 JSON），服务层与 TestClient（dependency override）共用。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：plan200 纯逻辑/内存库测试不触外部数据库。"""
    yield


def _ensure_pure_logic_config() -> None:
    if not (os.environ.get("APP_TEST_DB_URL") or "").strip():
        os.environ["APP_TEST_DB_URL"] = "sqlite:///pure_logic_test.db"
    if not (os.environ.get("APP_DB_URL") or "").strip():
        os.environ["APP_DB_URL"] = os.environ["APP_TEST_DB_URL"]
    os.environ.setdefault("APP_JWT_SECRET", "plan200-test-only-secret")


_ensure_pure_logic_config()

# JSONB → JSON（仅 sqlite 方言；PostgreSQL 行为不受影响）
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover - 编译钩子
    return "JSON"


from sqlalchemy import BigInteger  # noqa: E402


@compiles(BigInteger, "sqlite")
def _bigint_sqlite(type_, compiler, **kw):  # pragma: no cover - 编译钩子
    # sqlite 仅 INTEGER PRIMARY KEY 为 rowid 别名（可自增）。
    return "INTEGER"


import sqlalchemy  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# 内存 sqlite + ATTACH asset schema（模型表都在 asset schema 下）。
_engine = sqlalchemy.create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@sqlalchemy.event.listens_for(_engine, "connect")
def _attach_asset_schema(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("ATTACH DATABASE ':memory:' AS asset")
    cursor.close()


@pytest.fixture(scope="session")
def plan200_engine():
    from app.core.db import Base
    from app.models import auth as auth_models
    from app.models import governance_base as gb_models
    from app.models import identity as identity_models
    from app.models.governance import ApiKey
    from app.models import dict_medical as dm_models
    from app.models import dict_medical_push as dmp_models
    from app.models import dict_sync_outbox as outbox_models

    tables = [
        auth_models.AuthUser.__table__,
        auth_models.AuthSession.__table__,
        auth_models.AuthLoginEvent.__table__,
        gb_models.AssetRole.__table__,
        gb_models.AssetUserRole.__table__,
        gb_models.AssetRolePermission.__table__,
        gb_models.AssetPermissionResource.__table__,
        gb_models.AssetUserDataScope.__table__,
        gb_models.GovernChangeRequest.__table__,
        gb_models.GovernAuditLog.__table__,
        ApiKey.__table__,
        identity_models.IdentityPerson.__table__,
        dm_models.DictMedicalCodeItem.__table__,
        dm_models.DictMedicalCodeMapping.__table__,
        dm_models.DictMedicalCodeSet.__table__ if hasattr(dm_models, "DictMedicalCodeSet") else None,
        dmp_models.DictMedicalPushPlan.__table__,
        dmp_models.DictMedicalPushAction.__table__,
        dmp_models.DictMedicalPushRun.__table__,
        outbox_models.DictSyncOutboxEvent.__table__,
    ]
    with _engine.begin() as conn:
        for t in tables:
            if t is not None:
                t.create(conn, checkfirst=True)
    yield _engine
    with _engine.begin() as conn:
        for t in reversed(tables):
            if t is not None:
                t.drop(conn, checkfirst=True)


@pytest.fixture()
def db(plan200_engine):
    """每用例独立会话：结束回滚 + 逐表清行（服务层会 commit，仅回滚不够）。"""
    conn = plan200_engine.connect()
    session = sqlalchemy.orm.Session(bind=conn)
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()
        # 服务层内部 commit 过的数据需显式清理，避免跨用例污染
        from app.models import auth as auth_models
        from app.models import governance_base as gb_models
        from app.models.governance import ApiKey
        from app.models import identity as identity_models
        from app.models import dict_medical as dm_models
        from app.models import dict_medical_push as dmp_models
        from app.models import dict_sync_outbox as outbox_models

        cleanup = sqlalchemy.orm.Session(bind=conn)
        try:
            for table in (
                outbox_models.DictSyncOutboxEvent.__table__,
                dmp_models.DictMedicalPushRun.__table__,
                dmp_models.DictMedicalPushAction.__table__,
                dmp_models.DictMedicalPushPlan.__table__,
                dm_models.DictMedicalCodeMapping.__table__,
                dm_models.DictMedicalCodeItem.__table__,
                dm_models.DictMedicalCodeSet.__table__,
                identity_models.IdentityPerson.__table__,
                ApiKey.__table__,
                gb_models.GovernAuditLog.__table__,
                gb_models.GovernChangeRequest.__table__,
                gb_models.AssetUserDataScope.__table__,
                gb_models.AssetUserRole.__table__,
                gb_models.AssetRolePermission.__table__,
                gb_models.AssetPermissionResource.__table__,
                gb_models.AssetRole.__table__,
                auth_models.AuthSession.__table__,
                auth_models.AuthLoginEvent.__table__,
                auth_models.AuthUser.__table__,
            ):
                cleanup.execute(table.delete())
            cleanup.commit()
        finally:
            cleanup.close()
        conn.close()
