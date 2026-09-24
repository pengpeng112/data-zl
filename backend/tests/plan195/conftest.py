"""195 号 plan195 子目录 conftest：纯逻辑/内存 sqlite 测试，不连任何业务库。

- 覆盖根 conftest 的 autouse clean_test_database（no-op）；
- 未配置 APP_TEST_DB_URL 时注入一次性 sqlite 测试 URL；
- 内存 sqlite + ATTACH asset schema，只建本目录用到的资产元数据表。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：plan195 纯逻辑/内存库测试不触外部数据库。"""
    yield


def _ensure_pure_logic_config() -> None:
    if not (os.environ.get("APP_TEST_DB_URL") or "").strip():
        os.environ["APP_TEST_DB_URL"] = "sqlite:///plan195_pure_logic_test.db"
    if not (os.environ.get("APP_DB_URL") or "").strip():
        os.environ["APP_DB_URL"] = os.environ["APP_TEST_DB_URL"]
    os.environ.setdefault("APP_JWT_SECRET", "plan195-test-only-secret")


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
def plan195_engine():
    from app.models import asset as asset_models
    from app.models import asset_system as system_models
    from app.models import value_domain as vd_models

    tables = [
        system_models.AssetSystem.__table__,
        asset_models.AssetTable.__table__,
        asset_models.AssetColumn.__table__,
        asset_models.AssetRelation.__table__,
        vd_models.AssetColumnValueDomain.__table__,
        vd_models.AssetColumnValueDomainVersion.__table__,
    ]
    with _engine.begin() as conn:
        for t in tables:
            t.create(conn, checkfirst=True)
    yield _engine
    with _engine.begin() as conn:
        for t in reversed(tables):
            t.drop(conn, checkfirst=True)


@pytest.fixture()
def db(plan195_engine):
    """每用例独立会话：结束回滚 + 逐表清行（防跨用例污染）。"""
    conn = plan195_engine.connect()
    session = sqlalchemy.orm.Session(bind=conn)
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()
        from app.models import asset as asset_models
        from app.models import asset_system as system_models
        from app.models import value_domain as vd_models

        for model in (
            asset_models.AssetRelation,
            asset_models.AssetColumn,
            asset_models.AssetTable,
            system_models.AssetSystem,
            vd_models.AssetColumnValueDomainVersion,
            vd_models.AssetColumnValueDomain,
        ):
            try:
                session2 = sqlalchemy.orm.Session(bind=plan195_engine)
                session2.query(model).delete()
                session2.commit()
                session2.close()
            except Exception:
                pass
