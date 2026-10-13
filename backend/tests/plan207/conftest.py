"""207 号 plan207 子目录 conftest：纯逻辑/内存 sqlite 测试，不连任何业务库。

- 覆盖根 conftest 的 autouse clean_test_database（no-op）；
- 内存 sqlite + ATTACH asset schema（模型表都在 asset schema 下）；
- JSONB→JSON、BigInteger→INTEGER 编译钩子（sqlite 方言）；
- nextval() 以 sqlite 自定义函数实现（issue_code 序列兼容）；
- 部分唯一索引（postgresql_where）在 sqlite 上不生效：活动唯一性靠服务层
  语义验证，真实约束由 PG 隔离库集成测试覆盖。
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    """no-op：plan207 纯逻辑/内存库测试不触外部数据库。"""
    yield


def _ensure_pure_logic_config() -> None:
    if not (os.environ.get("APP_TEST_DB_URL") or "").strip():
        os.environ["APP_TEST_DB_URL"] = "sqlite:///plan207_pure_logic_test.db"
    if not (os.environ.get("APP_DB_URL") or "").strip():
        os.environ["APP_DB_URL"] = os.environ["APP_TEST_DB_URL"]
    os.environ.setdefault("APP_JWT_SECRET", "plan207-test-only-secret")


_ensure_pure_logic_config()

from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


from sqlalchemy import BigInteger  # noqa: E402


@compiles(BigInteger, "sqlite")
def _bigint_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "INTEGER"


import sqlalchemy  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

_engine = sqlalchemy.create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

_seq_counter = {"n": 0}


@sqlalchemy.event.listens_for(_engine, "connect")
def _attach_asset_schema(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("ATTACH DATABASE ':memory:' AS asset")
    cursor.close()
    # nextval shim：PostgreSQL 序列在 sqlite 下的等价实现（测试并发安全语义
    # 由 PG 集成测试覆盖；这里保证服务层代码可直接运行）
    dbapi_conn.create_function(
        "nextval", 1,
        lambda name: (_seq_counter.__setitem__("n", _seq_counter["n"] + 1), _seq_counter["n"])[1],
    )


@pytest.fixture(scope="session")
def plan207_engine():
    from app.core.db import Base
    from app.models import governance_base as gb_models
    from app.models import identity as identity_models
    from app.models import auth as auth_models
    from app.models import quality_governance as qg_models
    from app.models.quality import QualityRule
    from app.models.asset_system import AssetDataSource
    from app.models.value_domain import AssetColumnValueDomain

    tables = [
        gb_models.GovernAuditLog.__table__,
        auth_models.AuthUser.__table__,
        identity_models.IdentityPerson.__table__,
        identity_models.IdentityDepartment.__table__,
        identity_models.IdentityPersonDepartment.__table__,
        QualityRule.__table__,
        qg_models.QualityControl.__table__,
        qg_models.QualityControlDetector.__table__,
        qg_models.QualityControlRevision.__table__,
        qg_models.QualityObservation.__table__,
        qg_models.QualityIssue.__table__,
        qg_models.QualityIssueEvent.__table__,
        qg_models.QualityRun.__table__,
        qg_models.QualityVendor.__table__,
        qg_models.QualityNotification.__table__,
        AssetColumnValueDomain.__table__,
        AssetDataSource.__table__,
    ]
    with _engine.begin() as conn:
        Base.metadata.create_all(conn, tables=tables, checkfirst=True)
        # sqlite 不支持 postgresql_where 部分索引：该索引会被渲染成普通唯一索引，
        # 连终态问题也会阻塞复发建单。这里显式移除；活动唯一性的真实约束由
        # PG 隔离库集成测试（tests/test_quality_execution_207.py）验证。
        conn.execute(sqlalchemy.text("DROP INDEX IF EXISTS asset.uq_asset_quality_issues_active"))
    yield _engine
    with _engine.begin() as conn:
        for t in reversed(tables):
            t.drop(conn, checkfirst=True)


@pytest.fixture()
def db(plan207_engine):
    """每用例独立会话：结束回滚 + 逐表清行（服务层会 commit，仅回滚不够）。"""
    from app.models import quality_governance as qg_models
    from app.models import value_domain as vd_models
    from app.models import asset_system as ds_models
    from app.models.quality import QualityRule

    conn = plan207_engine.connect()
    session = sqlalchemy.orm.Session(bind=conn)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        clear = sqlalchemy.orm.Session(bind=conn)
        try:
            for tbl in (
                qg_models.QualityNotification.__table__,
                qg_models.QualityVendor.__table__,
                qg_models.QualityRun.__table__,
                qg_models.QualityControlRevision.__table__,
                qg_models.QualityIssueEvent.__table__,
                qg_models.QualityObservation.__table__,
                qg_models.QualityIssue.__table__,
                qg_models.QualityControlDetector.__table__,
                qg_models.QualityControl.__table__,
                QualityRule.__table__,
                vd_models.AssetColumnValueDomain.__table__,
                ds_models.AssetDataSource.__table__,
            ):
                clear.execute(tbl.delete())
            clear.commit()
        finally:
            clear.close()
        conn.close()


@pytest.fixture()
def fake_executors(monkeypatch):
    """合成执行器注入点：返回 dict 供用例按检测器 ref 配置六态结果。"""
    from app.services import quality_execution_service as qes

    registry: dict[str, object] = {}

    def make(kind: str):
        def _exec(dbc, control, revision, run):
            outcome = registry.get(run.detector_ref)
            if outcome is None:
                return qes.DetectorOutcome("blocked", error_code="NO_FIXTURE",
                                           error_message_sanitized=f"no fixture for {run.detector_ref}")
            if callable(outcome):
                return outcome(dbc, control, revision, run)
            return outcome
        return _exec

    for kind in ("quality_rule", "probe_template", "manual", "external"):
        monkeypatch.setitem(qes.EXECUTOR_REGISTRY, kind, make(kind))
    return registry
