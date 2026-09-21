"""186 v1.10 P1-5：/api/v1/identity/account-states 最新口径回归。

覆盖 §12.3 P1-5：
- 行集 = 每 (person_code, rule_version) 的最新一条决策（E→D→E→D 多代次
  只出最新；filters 作用于最新行，total = 最新行数）
- targets attempt 与当前决策行 transition_seq 严格对齐（fingerprint+
  rule_version+transition_seq），历史代次 attempt 不串用；同代
  disable/enable 并存取 id 最大；无记录 → status=no_attempt
- desired_state_summary 在最新行集上按唯一人员统计
- 旧响应字段名全部保留

SQLite 内存库直调路由函数（与 tests/test_identity_account_state_186.py
同模式）：模块级覆盖根 conftest 的 db_session 与数据库 autouse，
不连接 APP_TEST_DB_URL 指向的库。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.v1.identity import list_account_states
from app.core.db import Base
from app.models.identity import IdentityPerson
from app.models.identity_sync import (
    IdentityAccountStateAttempt,
    IdentityAccountStateDecision,
)
from app.services.identity_account_state import RULE_VERSION

RULE_V2 = "dual_source_v2"


@pytest.fixture(autouse=True)
def clean_test_database():
    """覆盖根 conftest 的数据库 autouse：本文件用 SQLite 内存引擎，
    不连接 APP_TEST_DB_URL 指向的库。"""
    yield


@pytest.fixture(autouse=True)
def hmac_test_key(monkeypatch):
    from app.core.config import settings
    from app.services.identity_hmac import reset_key_cache

    monkeypatch.setenv("TEST_HMAC_KEY", "test-only-hmac-key-not-for-prod-186")
    monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_KEY")
    reset_key_cache()
    yield
    reset_key_cache()


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    Base.metadata.create_all(
        engine,
        tables=[
            IdentityAccountStateDecision.__table__,
            IdentityAccountStateAttempt.__table__,
            IdentityPerson.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _decision(db, person_code, desired, *, seq, rule_version=RULE_VERSION):
    row = IdentityAccountStateDecision(
        person_code=person_code,
        rule_version=rule_version,
        employee_state="enabled",
        user_state="disabled" if desired == "disabled" else "enabled",
        desired_state=desired,
        decision_reason="seed",
        execution_allowed=desired == "disabled",
        evidence_fingerprint=f"fp-{person_code}-{rule_version}-{desired}-{seq}",
        transition_seq=seq,
        source_complete=True,
        captured_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture()
def seeded(db_session):
    from app.core.config import settings
    from app.services.identity_hmac import compute_account_fingerprint

    def fp(person: str, target: str) -> str:
        return compute_account_fingerprint(person, target, settings.identity_hmac_key_ref)

    # E001：E→D→E→D 多代次判定（v1），仅最新 seq=3 disabled 应出现
    _decision(db_session, "E001", "disabled", seq=1)
    _decision(db_session, "E001", "enabled", seq=2)
    _decision(db_session, "E001", "disabled", seq=3)
    # E002：单代 disabled（v1）
    _decision(db_session, "E002", "disabled", seq=1)
    # E003：单代 unknown（v1），无任何 attempt
    _decision(db_session, "E003", "unknown", seq=1)
    # E004：另一 rule_version（v2）的最新行——行集按 (person, rule) 分组
    _decision(db_session, "E004", "disabled", seq=1, rule_version=RULE_V2)
    # E005：同一人员在 v1/v2 各有最新行（验证 summary 按唯一人员统计）
    _decision(db_session, "E005", "disabled", seq=1)
    _decision(db_session, "E005", "disabled", seq=1, rule_version=RULE_V2)

    def attempt(person, target, action, *, seq, status="executed", run="RUN-186-P5"):
        db_session.add(IdentityAccountStateAttempt(
            run_id=run,
            person_code=person,
            target_system=target,
            target_account_fingerprint=fp(person, target),
            action=action,
            desired_state="disabled" if action == "disable" else "enabled",
            after_state="disabled" if action == "disable" else "enabled",
            status=status,
            lock_attribution="by_this_rule",
            rule_version=RULE_VERSION,
            transition_seq=seq,
            executed_at=datetime(2026, 9, 8, 1, 0, tzinfo=timezone.utc),
        ))

    # E001 历史代次（seq=1）双目标 attempt：不得串用到最新行（seq=3）
    attempt("E001", "JHEMR", "disable", seq=1)
    attempt("E001", "CDMS", "disable", seq=1)
    # E001 当前代次（seq=3）仅 JHEMR 有 attempt；CDMS → no_attempt
    attempt("E001", "JHEMR", "disable", seq=3)
    # E002 JHEMR 同代 disable→enable 并存：取 id 最大（enable）
    attempt("E002", "JHEMR", "disable", seq=1)
    attempt("E002", "JHEMR", "enable", seq=1)

    # 人员主档：employment_status 来自 IdentityPerson；E003 缺失 → None
    db_session.add_all([
        IdentityPerson(person_code="E001", employment_status="active"),
        IdentityPerson(person_code="E002", employment_status="inactive"),
        IdentityPerson(person_code="E004", employment_status="active"),
        IdentityPerson(person_code="E005", employment_status="active"),
    ])
    db_session.commit()
    return {"fp": fp}


def _call(db, **kwargs):
    params = dict(desired_state=None, person_code=None, page=1, page_size=30, db=db)
    params.update(kwargs)
    return list_account_states(**params).data


ALL_KEYS = {
    ("E001", RULE_VERSION),
    ("E002", RULE_VERSION),
    ("E003", RULE_VERSION),
    ("E004", RULE_V2),
    ("E005", RULE_VERSION),
    ("E005", RULE_V2),
}


def test_latest_decision_only_and_attempt_alignment(db_session, seeded):
    data = _call(db_session)
    # 行集 = 每 (person_code, rule_version) 最新一条；total = 最新行数
    assert data["total"] == 6
    by_key = {(i["person_code"], i["rule_version"]): i for i in data["items"]}
    assert set(by_key) == ALL_KEYS

    e1 = by_key[("E001", RULE_VERSION)]
    assert e1["transition_seq"] == 3  # E→D→E→D 只出最新代次
    assert e1["desired_state"] == "disabled"
    assert e1["employment_status"] == "active"
    assert by_key[("E003", RULE_VERSION)]["employment_status"] is None

    # attempt 与当前 transition_seq 严格对齐；历史代次（seq=1）不串用
    jhemr = e1["targets"]["JHEMR"]
    assert jhemr["status"] == "executed"
    assert jhemr["transition_seq"] == 3
    assert jhemr["after_state"] == "disabled"
    assert jhemr["action"] == "disable"
    cdms = e1["targets"]["CDMS"]
    assert cdms["status"] == "no_attempt"
    assert cdms["action"] is None
    assert cdms["transition_seq"] is None

    # 同代 disable/enable 并存 → 取 id 最大（enable）
    e2 = by_key[("E002", RULE_VERSION)]
    assert e2["targets"]["JHEMR"]["action"] == "enable"
    assert e2["targets"]["JHEMR"]["after_state"] == "enabled"
    assert e2["targets"]["CDMS"]["status"] == "no_attempt"

    # 无任何 attempt 的目标
    e3 = by_key[("E003", RULE_VERSION)]
    assert e3["targets"]["JHEMR"]["status"] == "no_attempt"
    assert e3["targets"]["CDMS"]["status"] == "no_attempt"


def test_legacy_dto_fields_preserved(db_session, seeded):
    data = _call(db_session)
    item = next(i for i in data["items"] if i["person_code"] == "E001")
    for key in (
        "person_code", "employment_status", "rule_version", "employee_state",
        "user_state", "desired_state", "decision_reason", "execution_allowed",
        "blocked_reason", "source_complete", "captured_at", "transition_seq",
        "targets",
    ):
        assert key in item
    for key in (
        "action", "status", "after_state", "reason_code", "lock_attribution",
        "transition_seq", "executed_at",
    ):
        assert key in item["targets"]["JHEMR"]
    for key in ("total", "page", "page_size", "items", "desired_state_summary"):
        assert key in data


def test_summary_counts_unique_persons_on_latest_rows(db_session, seeded):
    data = _call(db_session)
    # 最新行集上按唯一人员统计：disabled = E001/E002/E004/E005（4 人，E005
    # 双 rule_version 只计 1），unknown = E003（1 人）。历史 enabled 行不参与。
    assert data["desired_state_summary"] == {"disabled": 4, "unknown": 1}


def test_filters_apply_to_latest_rows(db_session, seeded):
    # E001 的 enabled 是历史代次而非最新行 → 过滤 enabled 命中 0
    enabled = _call(db_session, desired_state="enabled")
    assert enabled["total"] == 0
    assert enabled["items"] == []
    disabled = _call(db_session, desired_state="disabled")
    assert disabled["total"] == 5
    assert {i["person_code"] for i in disabled["items"]} == {"E001", "E002", "E004", "E005"}
    by_person = _call(db_session, person_code="E002")
    assert by_person["total"] == 1
    assert by_person["items"][0]["person_code"] == "E002"
    assert by_person["items"][0]["desired_state"] == "disabled"
    # 同一人员跨 rule_version 各出最新一条
    e5 = _call(db_session, person_code="E005")
    assert e5["total"] == 2
    assert {i["rule_version"] for i in e5["items"]} == {RULE_VERSION, RULE_V2}


def test_pagination_stable_no_dup_no_gap(db_session, seeded):
    page1 = _call(db_session, page=1, page_size=2)
    page2 = _call(db_session, page=2, page_size=2)
    page3 = _call(db_session, page=3, page_size=2)
    assert page1["total"] == 6
    keys1 = [(i["person_code"], i["rule_version"]) for i in page1["items"]]
    keys2 = [(i["person_code"], i["rule_version"]) for i in page2["items"]]
    keys3 = [(i["person_code"], i["rule_version"]) for i in page3["items"]]
    assert [len(keys1), len(keys2), len(keys3)] == [2, 2, 2]
    assert set(keys1).isdisjoint(keys2) and set(keys1).isdisjoint(keys3) and set(keys2).isdisjoint(keys3)
    assert set(keys1) | set(keys2) | set(keys3) == ALL_KEYS
    page4 = _call(db_session, page=4, page_size=2)
    assert page4["items"] == [] and page4["total"] == 6
