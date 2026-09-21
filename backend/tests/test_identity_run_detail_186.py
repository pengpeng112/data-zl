"""186 v1.10 P1-10：/api/v1/identity-sync/runs/{run_id} 详情接线回归。

覆盖 §12.3 P1-10：
- 新增 account_state_attempts：逐人/逐目标/transition_seq/status/reason/
  归因明细，不含 fingerprint 全文（仅 short_fingerprint ≤12 字符）；
  其他 run 的行不混入
- 新增 account_state_summary：按 status 与按 target_system 行级计数
  （success/partial 聚合概念在编排层，这里只做行级计数）
- 旧 IdentitySyncAction 序列化字段全部保留，新键并存
- 只读查询零写副作用；404 行为保持

SQLite 内存库直调路由函数（与 tests/test_identity_account_state_186.py
同模式）：模块级覆盖根 conftest 的 db_session 与数据库 autouse，
不连接 APP_TEST_DB_URL 指向的库。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.api.v1.identity_sync import get_run
from app.core.db import Base
from app.models.identity import IdentityPerson
from app.models.identity_sync import (
    IdentityAccountStateAttempt,
    IdentitySchedulerRun,
    IdentitySyncAction,
    IdentitySyncAlert,
    IdentitySyncBatch,
    IdentitySyncSubtask,
)

RUN_ID = "RUN-186-V110"


@pytest.fixture(autouse=True)
def clean_test_database():
    """覆盖根 conftest 的数据库 autouse：本文件用 SQLite 内存引擎，
    不连接 APP_TEST_DB_URL 指向的库。"""
    yield


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    Base.metadata.create_all(
        engine,
        tables=[
            IdentitySchedulerRun.__table__,
            IdentitySyncSubtask.__table__,
            IdentitySyncBatch.__table__,
            IdentitySyncAction.__table__,
            IdentitySyncAlert.__table__,
            IdentityAccountStateAttempt.__table__,
            IdentityPerson.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded(db_session):
    db_session.add(IdentitySchedulerRun(
        run_id=RUN_ID,
        triggered_by="nightly_cron",
        status="success",
        started_at=datetime(2026, 9, 8, 1, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 8, 1, 5, tzinfo=timezone.utc),
        duration_ms=300,
    ))
    # 一条旧 IdentitySyncAction（params_summary 带 run_id 溯源）
    db_session.add(IdentitySyncAction(
        batch_id="NTL-RUN-186-V110-1",
        action_seq=1,
        target_system="JHEMR",
        action_type="account_lock",
        target_table="DB_USER",
        account_fingerprint="f" * 64,
        params_summary={"run_id": RUN_ID, "emp_no": "E001"},
        status="executed",
        executed_at=datetime(2026, 9, 8, 1, 2, tzinfo=timezone.utc),
    ))
    db_session.add(IdentityPerson(person_code="E001", employment_status="active"))

    def attempt(person, target, action, status, *, seq=1, reason=None,
                attribution=None, origin=None, executed=None, run=RUN_ID):
        db_session.add(IdentityAccountStateAttempt(
            run_id=run,
            person_code=person,
            target_system=target,
            target_account_fingerprint=f"fp-{person}-{target}",
            action=action,
            desired_state="disabled" if action == "disable" else "enabled",
            after_state="disabled" if action == "disable" else "enabled",
            status=status,
            reason_code=reason,
            lock_attribution=attribution,
            rule_version="dual_source_v1",
            transition_seq=seq,
            origin_disable_attempt_id=origin,
            executed_at=executed,
        ))

    # 混合结果 fixture：success(executed)/skipped(target_missing)/blocked/failed
    attempt("E001", "JHEMR", "disable", "executed",
            attribution="by_this_rule",
            executed=datetime(2026, 9, 8, 1, 1, tzinfo=timezone.utc))
    attempt("E001", "CDMS", "disable", "failed", reason="db_error")
    attempt("E002", "JHEMR", "disable", "skipped", reason="target_missing")
    attempt("E003", "JHEMR", "enable", "blocked",
            attribution="manual_or_unknown", origin=11, seq=2)
    attempt("E004", "CDMS", "disable", "executed")
    # 其他 run 的行不得混入
    attempt("E009", "CDMS", "disable", "executed", run="RUN-OTHER")
    db_session.commit()


def _call(db):
    return get_run(run_id=RUN_ID, db=db, user="tester").data


def test_run_detail_includes_attempts_and_summary(db_session, seeded):
    data = _call(db_session)
    assert "account_state_attempts" in data
    assert "account_state_summary" in data
    rows = data["account_state_attempts"]
    assert len(rows) == 5  # 其他 run（RUN-OTHER）的 E009 不混入
    assert all(r["person_code"] != "E009" for r in rows)
    for key in (
        "person_code", "target_system", "action", "status", "reason_code",
        "transition_seq", "desired_state", "after_state", "lock_attribution",
        "origin_disable_attempt_id", "executed_at", "short_fingerprint",
    ):
        assert key in rows[0]
    # 不含 fingerprint 全文，仅短指纹（≤12 字符）
    assert "target_account_fingerprint" not in rows[0]
    assert all(len(r["short_fingerprint"]) <= 12 for r in rows)
    e3 = next(r for r in rows if r["person_code"] == "E003")
    assert e3["action"] == "enable"
    assert e3["status"] == "blocked"
    assert e3["lock_attribution"] == "manual_or_unknown"
    assert e3["origin_disable_attempt_id"] == 11
    assert e3["transition_seq"] == 2
    e2 = next(r for r in rows if r["person_code"] == "E002")
    assert e2["status"] == "skipped" and e2["reason_code"] == "target_missing"
    summary = data["account_state_summary"]
    assert summary["total_attempts"] == 5
    assert summary["by_status"] == {"blocked": 1, "executed": 2, "failed": 1, "skipped": 1}
    assert summary["by_target_system"] == {"CDMS": 2, "JHEMR": 3}


def test_run_detail_keeps_legacy_fields(db_session, seeded):
    data = _call(db_session)
    for key in (
        "run_id", "triggered_by", "status", "status_name", "started_at",
        "finished_at", "duration_ms", "subtasks", "batches", "actions", "alerts",
    ):
        assert key in data
    assert data["run_id"] == RUN_ID
    # 旧 IdentitySyncAction 序列化仍在（与 account_state_* 新键并存）
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_type"] == "account_lock"
    assert data["actions"][0]["target_system"] == "JHEMR"


def test_run_detail_is_read_only_zero_write(db_session, seeded):
    def _snapshot():
        return [
            (a.id, a.status, a.executed_at, a.lock_attribution)
            for a in db_session.scalars(
                select(IdentityAccountStateAttempt).order_by(IdentityAccountStateAttempt.id)
            ).all()
        ]

    before = _snapshot()
    _call(db_session)
    # 只读：无 ORM 新增/脏对象（页面打开零写副作用）
    assert len(db_session.new) == 0
    assert len(db_session.dirty) == 0
    assert _snapshot() == before


def test_run_detail_404_for_missing_run(db_session, seeded):
    with pytest.raises(HTTPException) as exc:
        get_run(run_id="RUN-NOT-EXIST", db=db_session, user="tester")
    assert exc.value.status_code == 404
