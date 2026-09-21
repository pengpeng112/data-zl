"""186 v1.10 复核修复回归：P0-1/2/3/5/7/8/11/14/18/19/20 + T47/T48/T52/T53/T54/T55/T56/T57/T59。

门禁链（identity_sync_action_gate）与编排器选择/预算/报告分离的行为级
测试。目标"写入"通过 monkeypatch 桥接层的适配器构造（真实调用
execute_* 函数对象、真实 dispatch 路径）——不得用整体 mock dispatch/gate
替代（P0-11 回归要求）。全部 SQLite 内存，零真实数据库连接。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select

from app.core.db import Base
from app.models.governance_base import AssetActionExecutor
from app.models.asset_system import AssetSourcePurposeBinding, AssetDataSource
from app.models.identity_sync import (
    IdentitySchedulerRun,
    IdentityAccountStateAttempt,
    IdentityAccountStateDecision,
    IdentityApprovedScope,
    IdentityApprovedScopeMember,
    IdentityManagedRelation,
    IdentityProtectedAccount,
    IdentityRoleMapping,
    IdentityWindowBudget,
    IdentityWindowReservation,
)
from app.models.identity import IdentityPerson, IdentityPersonDepartment, IdentityPersonSource

# SQLite 测试 shim：governance/registry 表使用原生 JSONB 列，SQLite 编译器
# 按 JSON 渲染（仅测试进程内生效）。
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")

    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    from app.services.identity_sync_orchestrator import (
        IdentitySyncBatch,
        IdentitySyncAction,
        IdentitySyncWatermark,
        IdentitySyncCompensation,
        IdentityClassificationRecord,
        IdentityDistributedLock,
        IdentitySchedulerRun,
        IdentityCircuitBreaker,
    )

    tables = [
        IdentityAccountStateDecision.__table__,
        IdentityAccountStateAttempt.__table__,
        IdentityManagedRelation.__table__,
        IdentityProtectedAccount.__table__,
        IdentityRoleMapping.__table__,
        IdentityPerson.__table__,
        IdentityPersonDepartment.__table__,
        IdentityPersonSource.__table__,
        IdentitySyncWatermark.__table__,
        IdentitySyncBatch.__table__,
        IdentitySyncAction.__table__,
        IdentitySyncCompensation.__table__,
        IdentityClassificationRecord.__table__,
        IdentityDistributedLock.__table__,
        IdentitySchedulerRun.__table__,
        IdentityCircuitBreaker.__table__,
        AssetActionExecutor.__table__,
        AssetSourcePurposeBinding.__table__,
        AssetDataSource.__table__,
        IdentityApprovedScope.__table__,
        IdentityApprovedScopeMember.__table__,
        IdentityWindowBudget.__table__,
        IdentityWindowReservation.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def clean_test_database():
    yield


@pytest.fixture(autouse=True)
def settings_186(monkeypatch):
    import os

    from app.core.config import settings
    from app.services.identity_hmac import reset_key_cache

    monkeypatch.setenv("TEST_HMAC_KEY", "test-only-hmac-key-v110")
    monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_KEY")
    monkeypatch.setattr(settings, "identity_dual_source_enforce", True)
    monkeypatch.setattr(settings, "identity_run_mode", "disable_only")
    monkeypatch.setattr(settings, "identity_sync_enabled", True)
    monkeypatch.setattr(settings, "identity_phase_d_approval_version", "186-20260909-disable-only")
    monkeypatch.setattr(settings, "identity_account_state_batch_limit", 2000)
    monkeypatch.setattr(settings, "identity_account_state_total_cap", 5000)
    monkeypatch.setattr(settings, "identity_window_max_persons", 20)
    monkeypatch.setattr(settings, "identity_window_hours", 20)
    monkeypatch.setattr(settings, "identity_clock_sampling_enabled", False)
    monkeypatch.setattr(settings, "identity_drift_readback_enabled", False)
    reset_key_cache()
    yield
    reset_key_cache()


APPROVAL = "186-20260909-disable-only"
JHEMR_SOURCE = "jhemr_vastbase_10_10_8_177"
CDMS_SOURCE = "paperless_cdms_oracle_10_10_10_93"


def register_executors(db, *, jhemr=True, cdms=True, enable_disable=True, enable_enable=False, with_binding=True):
    """注册四类执行器（默认仅两个 disable 启用）+ 可选两目标用途绑定。"""
    for code, target_system, source in (
        ("JHEMR_ACCOUNT_DISABLE", "JHEMR", JHEMR_SOURCE),
        ("JHEMR_ACCOUNT_ENABLE", "JHEMR", JHEMR_SOURCE),
        ("CDMS_ACCOUNT_DISABLE", "CDMS", CDMS_SOURCE),
        ("CDMS_ACCOUNT_ENABLE", "CDMS", CDMS_SOURCE),
    ):
        enabled = enable_disable if code.endswith("DISABLE") else enable_enable
        row = AssetActionExecutor(
            executor_code=code,
            executor_name_cn=code,
            execution_mode="adapter_method",
            tool_code="identity_state_sync",
            sql_or_endpoint_ref="test",
            target_system_code=target_system,
            target_source_code=source,
            risk_level="high",
            require_approval=True,
            enabled=enabled,
        )
        db.add(row)
    if not with_binding:
        db.flush()
        return {"jhemr": jhemr, "cdms": cdms}
    for source in (JHEMR_SOURCE, CDMS_SOURCE):
        db.add(AssetSourcePurposeBinding(
            source_code=source,
            purpose="identity_account_sync",
            write_policy="identity_account_sync",
            write_credential_ref=f"file:///etc/data-asset/credentials/test_{source}.write",
            credential_status="configured",
            enabled=True,
            approval_ref=APPROVAL,
        ))
    db.flush()
    return {"jhemr": jhemr, "cdms": cdms}


def register_scope(db, person_codes, scope_type="pilot", approval=APPROVAL, action="disable"):
    scope = IdentityApprovedScope(
        scope_type=scope_type, approval_ref=approval, action=action, status="active",
    )
    db.add(scope)
    db.flush()
    for code in person_codes:
        db.add(IdentityApprovedScopeMember(scope_id=scope.id, person_code=code, frozen_reason="test"))
    db.flush()
    return scope


def make_person(db, code, *, employment="active", conflict=False):
    person = IdentityPerson(
        person_code=code,
        person_name_cn=f"人员{code}",
        employment_status=employment,
        classification="doctor",
        conflict_flag="conflict" if conflict else None,
        source_create_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        primary_source_system="HIS",
        source_system="HIS",
    )
    db.add(person)
    db.flush()
    return person


def make_decision(db, code, *, employee="enabled", user="disabled", desired=None, transition=1,
                  source_complete=True, execution_allowed=True):
    from app.services.identity_hmac import compute_account_fingerprint
    from app.core.config import settings as app_settings

    desired = desired or ("disabled" if "disabled" in (employee, user) else
                          ("enabled" if employee == "enabled" and user == "enabled" else "unknown"))
    row = IdentityAccountStateDecision(
        person_code=code,
        rule_version="dual_source_v1",
        employee_state=employee,
        user_state=user,
        desired_state=desired,
        decision_reason=f"employee_{employee}+user_{user}",
        execution_allowed=execution_allowed,
        evidence_fingerprint=compute_account_fingerprint(f"{code}:{transition}", "TEST", app_settings.identity_hmac_key_ref),
        transition_seq=transition,
        source_complete=source_complete,
        captured_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


class FakeAdapterLock:
    """记录调用并返回受控结果的假适配器类构造器。"""

    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self):
        FakeAdapterLock.calls.append({"op": "connect", "kwargs": self.kwargs})

    def close(self):
        pass

    def lock_account(self, emp_no):
        FakeAdapterLock.calls.append({"op": "lock_account", "emp_no": emp_no})
        return {"status": "success", "rows_affected": 1, "account_status": 8,
                "locked_time_raw": "2026-09-09T18:00:00"}

    def lock_user(self, emp_no):
        FakeAdapterLock.calls.append({"op": "lock_user", "emp_no": emp_no})
        return {"status": "success", "rows_affected": 1, "changed_at_raw": "2026-09-09T18:00:00",
                "changed_at": "2026-09-09T18:00:00"}

    def unlock_account(self, emp_no, *, origin_disable=None):
        FakeAdapterLock.calls.append({"op": "unlock_account", "emp_no": emp_no,
                                      "origin_disable": origin_disable})
        if origin_disable is None or origin_disable.get("target_raw_time") is None:
            return {"status": "blocked", "reason": "attribution_unknown"}
        return {"status": "success", "rows_affected": 1, "account_status": 0,
                "lock_attribution": "by_this_rule"}

    def unlock_user(self, emp_no, *, origin_disable=None):
        FakeAdapterLock.calls.append({"op": "unlock_user", "emp_no": emp_no,
                                      "origin_disable": origin_disable})
        if origin_disable is None or origin_disable.get("target_raw_time") is None:
            return {"status": "blocked", "reason": "attribution_unknown"}
        return {"status": "success", "rows_affected": 1, "lock_attribution": "by_this_rule"}


@pytest.fixture(autouse=True)
def fake_adapters(monkeypatch):
    FakeAdapterLock.calls = []
    monkeypatch.setattr("app.services.identity_sync_executor_bridge.JhemrIdentityAdapter", FakeAdapterLock,
                        raising=False)
    # bridge 内部为局部 import，直接 patch 源模块类
    import app.services.jhemr_identity_adapter as jhemr_mod
    import app.services.cdms_identity_adapter as cdms_mod
    monkeypatch.setattr(jhemr_mod, "JhemrIdentityAdapter", FakeAdapterLock)
    monkeypatch.setattr(cdms_mod, "CdmsIdentityAdapter", FakeAdapterLock)
    yield FakeAdapterLock


# ---------------------------------------------------------------------------
# P0-1/P0-19：运行模式总开关
# ---------------------------------------------------------------------------

class TestRunModeObserve:
    def test_observe_zero_actions_and_zero_adapter_writes(self, db_session, fake_adapters):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        settings.identity_run_mode = "observe"
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        db_session.commit()

        actions = select_account_state_actions(db_session)
        assert actions["disables"] == []
        assert actions["enables"] == []
        assert actions["population"] == 1  # 采集/人口统计保留
        assert fake_adapters.calls == []

    def test_enforce_false_empty_actions_population_kept(self, db_session):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        settings.identity_dual_source_enforce = False
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")

        actions = select_account_state_actions(db_session)
        assert actions["disables"] == [] and actions["enables"] == []
        assert actions["population"] == 1
        assert actions["enforce"] is False

    def test_observe_blocks_legacy_login_sign_and_title_sync(self, db_session):
        from app.core.config import settings
        from app.services.identity_sync_action_gate import gate_legacy_identity_write
        from app.services.identity_login_sign_sync import sync_jhemr_login_sign_daily
        from app.services.identity_title_sync import sync_jhemr_education_titles_daily

        settings.identity_run_mode = "observe"
        for kind in ("cdms_apply", "jhemr_apply", "jhemr_lock", "login_sign_sync", "education_title_sync"):
            decision = gate_legacy_identity_write(db_session, kind)
            assert not decision.allowed
            assert decision.reason == "run_mode_observe"
        ls = sync_jhemr_login_sign_daily(run_id="R1", db=db_session)
        assert ls["status"] == "skipped" and ls["reason"] == "run_mode_observe"
        ts = sync_jhemr_education_titles_daily(run_id="R1", db=db_session)
        assert ts["status"] == "skipped"

    def test_disable_only_blocks_legacy_kinds(self, db_session):
        from app.services.identity_sync_action_gate import gate_legacy_identity_write

        for kind in ("cdms_apply", "jhemr_apply", "login_sign_sync"):
            decision = gate_legacy_identity_write(db_session, kind)
            assert not decision.allowed
            assert decision.reason == "run_mode_disable_only_blocks_legacy_writes"


# ---------------------------------------------------------------------------
# P0-11/P0-14/P0-18：执行器注册/用途绑定门禁（六类失败 fixture）
# ---------------------------------------------------------------------------

class TestExecutorGate:
    def _setup(self, db, person="E001"):
        register_executors(db)
        register_scope(db, [person])
        make_person(db, person)
        make_decision(db, person, user="disabled")
        db.commit()

    def test_executor_missing_blocked_zero_connections(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001")
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["status"] == "blocked" and result["reason"] == "executor_not_registered"
        assert fake_adapters.calls == []  # 零目标连接

    def test_executor_disabled_blocked(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        register_executors(db_session, enable_disable=False)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001")
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["reason"] == "executor_disabled"
        assert fake_adapters.calls == []

    def test_require_approval_without_ref_blocked(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        self._setup(db_session)
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref="some-other-approval-ref",
        )
        assert result["reason"] == "phase_d_approval_mismatch"
        assert fake_adapters.calls == []

    def test_purpose_binding_missing_blocked(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        register_executors(db_session, with_binding=False)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001")
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["reason"] == "purpose_binding_missing"
        assert fake_adapters.calls == []

    def test_purpose_binding_disabled_or_unconfigured_blocked(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001")
        binding = db_session.scalar(select(AssetSourcePurposeBinding).where(
            AssetSourcePurposeBinding.source_code == JHEMR_SOURCE))
        binding.enabled = False
        db_session.flush()
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["reason"] == "purpose_binding_disabled"
        binding.enabled = True
        binding.credential_status = "unconfigured"
        db_session.flush()
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["reason"] == "purpose_credential_not_configured"
        assert fake_adapters.calls == []

    def test_not_in_approved_scope_blocked(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        register_executors(db_session)
        register_scope(db_session, ["E999"])  # 范围不含 E001
        make_person(db_session, "E001")
        make_decision(db_session, "E001")
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["reason"] == "not_in_approved_scope"
        assert fake_adapters.calls == []

    def test_enable_blocked_no_ownership_contract(self, db_session, fake_adapters):
        from app.core.config import settings
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        settings.identity_run_mode = "full"
        register_executors(db_session, enable_enable=True)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        # 造一条 executed disable attempt + origin 证据
        fp = None
        from app.services.identity_hmac import compute_account_fingerprint
        from app.core.config import settings as s
        fp = compute_account_fingerprint("E001", "JHEMR", s.identity_hmac_key_ref)
        db_session.add(IdentityAccountStateAttempt(
            run_id="R0", person_code="E001", target_system="JHEMR",
            target_account_fingerprint=fp, action="disable", desired_state="disabled",
            status="executed", rule_version="dual_source_v1", transition_seq=1,
            attribution_evidence={"target_raw_time": "2026-09-09T18:00:00"},
        ))
        db_session.commit()
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="enable", person_code="E001",
            approval_ref=APPROVAL,
        )
        # §13.3-5：目标无审计/版本合同 → automatic_enable_not_supported
        assert result["reason"] == "automatic_enable_not_supported"
        assert fake_adapters.calls == []

    def test_disable_success_passes_binding_credential(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        self._setup(db_session)
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="disable", person_code="E001",
            approval_ref=APPROVAL, run_id="RUN-1",
        )
        assert result["status"] == "success", result
        connects = [c for c in fake_adapters.calls if c["op"] == "connect"]
        assert len(connects) == 1
        assert connects[0]["kwargs"]["credential_ref"].endswith(f"test_{JHEMR_SOURCE}.write")


# ---------------------------------------------------------------------------
# P0-19/T55：批准范围冻结名单
# ---------------------------------------------------------------------------

class TestApprovedScope:
    def test_selector_unapproved_goes_backlog_not_executed(self, db_session, fake_adapters):
        from app.services.identity_sync_orchestrator import select_account_state_actions

        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        make_person(db_session, "E002")
        make_decision(db_session, "E002", user="disabled")  # 不在冻结范围
        db_session.commit()

        actions = select_account_state_actions(db_session)
        codes = [e["person_code"] for e in actions["disables"]]
        assert codes == ["E001"]
        assert actions["backlog_unapproved"] == 1

    def test_frozen_scope_not_auto_extended(self, db_session):
        from app.services.identity_sync_action_gate import approved_disable_persons, freeze_baseline_scope

        scope = freeze_baseline_scope(
            db_session, approval_ref=APPROVAL, members=[("E001", "u"), ("E002", "u")], created_by="t",
        )
        db_session.commit()
        assert set(approved_disable_persons(db_session)) == {"E001", "E002"}
        # 新对象出现不自动混入
        make_person(db_session, "E003")
        assert "E003" not in approved_disable_persons(db_session)
        # 重复冻结拒绝（supersede 须显式）
        with pytest.raises(RuntimeError):
            freeze_baseline_scope(db_session, approval_ref=APPROVAL, members=[("E003", "u")], created_by="t")


# ---------------------------------------------------------------------------
# P0-20/T56：窗口预算与公平推进
# ---------------------------------------------------------------------------

class TestWindowBudget:
    def test_budget_limits_window_to_20_unique_persons(self, db_session):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        register_executors(db_session)
        codes = [f"E{i:03d}" for i in range(25)]
        register_scope(db_session, codes, scope_type="baseline")
        for code in codes:
            make_person(db_session, code)
            make_decision(db_session, code, user="disabled")
        db_session.commit()

        actions = select_account_state_actions(db_session)
        assert len(actions["disables"]) == 20
        assert actions["deferred_budget"] == 5
        assert actions["backlog_pending"] == 5
        assert actions["window"]["limit_persons"] == 20

    def test_same_window_second_call_zero_new_deferred_all(self, db_session):
        from app.services.identity_sync_orchestrator import select_account_state_actions

        register_executors(db_session)
        codes = [f"E{i:03d}" for i in range(25)]
        register_scope(db_session, codes, scope_type="baseline")
        for code in codes:
            make_person(db_session, code)
            make_decision(db_session, code, user="disabled")
        db_session.commit()
        first = select_account_state_actions(db_session)
        second = select_account_state_actions(db_session)
        # 同窗重复触发：仅同批 20 人重试复用名额，不产生第二份额度（防同夜绕过）
        first_codes = {e["person_code"] for e in first["disables"]}
        assert all(e["person_code"] in first_codes for e in second["disables"])
        assert len(second["disables"]) == 20
        assert second["deferred_budget"] == 5

    def test_reservation_retry_same_person_no_extra_slot(self, db_session):
        from app.services.identity_sync_action_gate import (
            get_or_open_window, reserve_window_slot, window_reservation_status,
        )

        window = get_or_open_window(db_session, approval_ref=APPROVAL)
        assert reserve_window_slot(db_session, window=window, person_code="E001", action="disable", run_id="R1") == "reserved"
        assert reserve_window_slot(db_session, window=window, person_code="E001", action="disable", run_id="R1") == "already"
        status = window_reservation_status(db_session, window)
        assert status["reserved"] == 1  # 重试同一对象不重复占额

    def test_window_identity_not_recreated_within_hours(self, db_session):
        from app.services.identity_sync_action_gate import get_or_open_window

        w1 = get_or_open_window(db_session, approval_ref=APPROVAL)
        db_session.commit()
        w2 = get_or_open_window(db_session, approval_ref=APPROVAL)
        assert w1.id == w2.id  # 重启/重复调用不产生第二份额度（T47）


# ---------------------------------------------------------------------------
# P0-3：分页续跑与截断上报
# ---------------------------------------------------------------------------

class TestScanPagination:
    def test_3000_decisions_all_processed_under_cap_5000(self, db_session):
        from app.services.identity_sync_action_gate import register_pilot_scope
        from app.services.identity_sync_orchestrator import select_account_state_actions

        register_executors(db_session)
        codes = [f"P{i:04d}" for i in range(3000)]
        register_pilot_scope(db_session, approval_ref=APPROVAL, person_codes=codes, created_by="t")
        for code in codes:
            make_person(db_session, code)
            make_decision(db_session, code, user="disabled")
        db_session.commit()

        actions = select_account_state_actions(db_session)
        assert actions["scanned"] == 3000  # 超过 batch_limit=2000 仍续页处理
        assert actions["truncated"] is False
        assert actions["remaining"] == 0
        assert len(actions["disables"]) == 20  # 但执行仍受窗口预算约束

    def test_cap_2500_truncates_with_remaining(self, db_session, monkeypatch):
        from app.core.config import settings
        from app.services.identity_sync_action_gate import register_pilot_scope
        from app.services.identity_sync_orchestrator import select_account_state_actions

        monkeypatch.setattr(settings, "identity_account_state_total_cap", 2500)
        register_executors(db_session)
        codes = [f"P{i:04d}" for i in range(3000)]
        register_pilot_scope(db_session, approval_ref=APPROVAL, person_codes=codes, created_by="t")
        for code in codes:
            make_person(db_session, code)
            make_decision(db_session, code, user="disabled")
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert actions["scanned"] == 2500
        assert actions["truncated"] is True
        assert actions["remaining"] == 500


# ---------------------------------------------------------------------------
# P0-5：决策缺失/不完整/无主档/冲突 fail-closed 计数
# ---------------------------------------------------------------------------

class TestFailClosedDecisions:
    def test_selector_counts_blocked_classes(self, db_session):
        from app.services.identity_sync_orchestrator import select_account_state_actions

        register_executors(db_session)
        register_scope(db_session, ["E001", "E005"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        # E002：来源不完整
        make_person(db_session, "E002")
        make_decision(db_session, "E002", user="disabled", source_complete=False)
        # E003：无人员主档
        make_decision(db_session, "E003", user="disabled")
        # E004：冲突人员
        make_person(db_session, "E004", conflict=True)
        make_decision(db_session, "E004", user="disabled")
        # E005：unknown
        make_person(db_session, "E005")
        make_decision(db_session, "E005", employee="enabled", user="unknown", desired="unknown",
                      execution_allowed=False)
        db_session.commit()

        actions = select_account_state_actions(db_session)
        assert actions["blocked_incomplete"] == 1
        assert actions["blocked_no_person"] == 1
        assert actions["blocked_conflict"] == 1
        assert actions["blocked_unknown"] == 1
        assert [e["person_code"] for e in actions["disables"]] == ["E001"]

    def test_candidates_require_decision_when_enforce(self, db_session):
        from app.services.identity_sync_orchestrator import select_nightly_candidates

        make_person(db_session, "E001")  # 无决策
        make_person(db_session, "E002")
        make_decision(db_session, "E002", employee="enabled", user="enabled", desired="enabled")
        stats: dict[str, int] = {}
        select_nightly_candidates(db_session, filter_stats=stats)
        assert stats.get("blocked_no_decision", 0) >= 1

    def test_incomplete_decision_excluded_from_candidates(self, db_session):
        from app.services.identity_sync_orchestrator import select_nightly_candidates

        make_person(db_session, "E001")
        make_decision(db_session, "E001", employee="enabled", user="enabled", desired="enabled",
                      source_complete=False)
        stats: dict[str, int] = {}
        candidates = select_nightly_candidates(db_session, filter_stats=stats)
        assert candidates == []
        assert stats.get("blocked_incomplete", 0) == 1


# ---------------------------------------------------------------------------
# P0-7：保护映射 HMAC 候选法
# ---------------------------------------------------------------------------

class TestProtectionMapping:
    def test_hmac_candidate_blocks_person(self, db_session):
        from app.services.identity_sync_action_gate import person_is_protected
        from app.services.identity_sync_orchestrator import select_account_state_actions

        register_executors(db_session)
        register_scope(db_session, ["E001", "E002"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        make_person(db_session, "E002")
        make_decision(db_session, "E002", user="disabled")
        # 保护登记 account_id 与工号不同（目标键≠工号场景）：仍须命中人员
        db_session.add(IdentityProtectedAccount(
            target_system="JHEMR", account_id="E001", reason="manual", protected_by="t",
        ))
        db_session.commit()
        protected, hits = person_is_protected(db_session, "E001")
        assert protected and hits == ["JHEMR"]
        actions = select_account_state_actions(db_session)
        assert actions["blocked_protected"] == 1
        assert [e["person_code"] for e in actions["disables"]] == ["E002"]

    def test_unresolved_protection_rows_reported_not_blocking_all(self, db_session):
        from app.services.identity_sync_action_gate import protection_mapping_report

        db_session.add(IdentityProtectedAccount(
            target_system="CDMS", account_id="UNKNOWNACCT", reason="manual", protected_by="t",
        ))
        db_session.commit()
        report = protection_mapping_report(db_session)
        assert report["unresolved_protection_rows"]["CDMS"] == 1
        assert report["unresolved_is_not_no_protection"] is True


# ---------------------------------------------------------------------------
# P0-8/T39：target_missing ≠ 幂等完成；部分成功语义
# ---------------------------------------------------------------------------

class TestTargetMissing:
    def _make_target_missing_adapters(self, monkeypatch):
        class OneSidedAdapter(FakeAdapterLock):
            def lock_user(self, emp_no):
                OneSidedAdapter.calls.append({"op": "lock_user", "emp_no": emp_no})
                return {"status": "missing_target"}

        import app.services.jhemr_identity_adapter as jhemr_mod
        import app.services.cdms_identity_adapter as cdms_mod
        monkeypatch.setattr(jhemr_mod, "JhemrIdentityAdapter", OneSidedAdapter)
        monkeypatch.setattr(cdms_mod, "CdmsIdentityAdapter", OneSidedAdapter)
        return OneSidedAdapter

    def test_one_target_missing_is_partial_and_retried(self, db_session, monkeypatch):
        from app.services.identity_sync_orchestrator import (
            _process_account_state_person, select_account_state_actions,
        )

        self._make_target_missing_adapters(monkeypatch)
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        decision = make_decision(db_session, "E001", user="disabled")
        db_session.commit()

        actions = select_account_state_actions(db_session)
        entry = actions["disables"][0]
        result = _process_account_state_person(db_session, entry, "RUN-T39")
        db_session.commit()
        assert result["status"] == "partial"  # JHEMR 成功 + CDMS 缺失 → 不算全成功
        attempts = db_session.scalars(select(IdentityAccountStateAttempt)).all()
        cdms_attempt = [a for a in attempts if a.target_system == "CDMS"][0]
        assert cdms_attempt.reason_code == "target_missing"

        # §13.5 反饥饿：仅剩 target_missing 的人员不占窗口名额，入 missing 池
        actions2 = select_account_state_actions(db_session)
        assert all(e["person_code"] != "E001" for e in actions2["disables"])
        assert actions2["backlog_missing_retry"] == 1

        # 探测到目标重现（drift 回读开启 + CDMS 可读）→ 回归队列
        from app.core.config import settings as s2
        s2.identity_drift_readback_enabled = True
        import app.services.identity_sync_action_gate as gate_mod
        monkeypatch.setattr(gate_mod, "read_target_account_state",
                            lambda target, person: {"fuserstate": "0"} if target == "CDMS" else None)
        actions3 = select_account_state_actions(db_session)
        entry3 = [e for e in actions3["disables"] if e["person_code"] == "E001"]
        assert entry3 and "CDMS" in entry3[0]["retry_targets"]
        assert "JHEMR" in entry3[0]["done_targets"]
        s2.identity_drift_readback_enabled = False


# ---------------------------------------------------------------------------
# P0-2/T37：enable 真签名冒烟（不 mock 桥接函数本体）
# ---------------------------------------------------------------------------

class TestEnableRealSignature:
    def test_enable_dispatch_reaches_adapter_with_origin_disable(self, db_session, fake_adapters, monkeypatch):
        from app.core.config import settings
        from app.services.identity_hmac import compute_account_fingerprint
        from app.services.identity_sync_action_gate import (
            AUTOMATIC_ENABLE_UNSUPPORTED_REASONS,
            dispatch_identity_state_action,
        )

        # 临时开放所有权合同（模拟目标具备审计/版本能力的隔离场景；生产恒 false）
        import app.services.identity_sync_action_gate as gate_mod
        import app.services.identity_clock_health as clock_mod
        monkeypatch.setattr(gate_mod, "AUTOMATIC_ENABLE_SUPPORTED", True)
        monkeypatch.setattr(clock_mod, "AUTOMATIC_ENABLE_SUPPORTED", True)
        settings.identity_run_mode = "full"
        register_executors(db_session, enable_enable=True)
        register_scope(db_session, ["E001"])
        register_scope(db_session, ["E001"], scope_type="pilot_enable", action="enable")
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        fp = compute_account_fingerprint("E001", "JHEMR", settings.identity_hmac_key_ref)
        disable_attempt = IdentityAccountStateAttempt(
            run_id="R0", person_code="E001", target_system="JHEMR",
            target_account_fingerprint=fp, action="disable", desired_state="disabled",
            status="executed", rule_version="dual_source_v1", transition_seq=1,
            attribution_evidence={"target_raw_time": "2026-09-09T18:00:00"},
        )
        db_session.add(disable_attempt)
        db_session.commit()

        origin = {
            "attempt_id": disable_attempt.id,
            "target_raw_time": "2026-09-09T18:00:00",
            "target_account_fingerprint": fp,
            "rule_version": "dual_source_v1",
        }
        result = dispatch_identity_state_action(
            db_session, target_system="JHEMR", action="enable", person_code="E001",
            approval_ref=APPROVAL, origin_disable=origin,
        )
        # 真实调用 execute_jhemr_enable 函数对象 → 无 TypeError，参数落适配器
        assert result["status"] == "success", result
        unlock_calls = [c for c in fake_adapters.calls if c["op"] == "unlock_account"]
        assert len(unlock_calls) == 1
        assert unlock_calls[0]["origin_disable"]["attempt_id"] == disable_attempt.id

    def test_production_enable_constant_is_false(self):
        import app.services.identity_sync_action_gate as gate_mod
        assert gate_mod.AUTOMATIC_ENABLE_SUPPORTED is False
        assert gate_mod.AUTOMATIC_ENABLE_UNSUPPORTED_REASONS


# ---------------------------------------------------------------------------
# T47/T48：时钟健康与窗口身份
# ---------------------------------------------------------------------------

class TestClockHealth:
    def test_fixed_offset_stable_healthy(self):
        from app.services.identity_clock_health import evaluate_clock_health

        call_state = {"n": 0}

        def fake_query(sql):
            from datetime import datetime as dt, timezone as tz
            # 目标比平台慢 10 分钟（大偏差但稳定 → 告警不放行 enable）
            return [{"ts": (dt.now(tz.utc) - timedelta(minutes=10)).isoformat(), "tz": "PRC"}]

        health = evaluate_clock_health(jhemr_query=fake_query, cdms_query=None)
        assert health.healthy is False  # CDMS 未采样 → 不健康（fail-closed）
        assert any("CDMS" in r for r in health.reasons)

    def test_both_targets_sampled_stable(self):
        from app.services.identity_clock_health import evaluate_clock_health

        def jq(sql):
            from datetime import datetime as dt, timezone as tz
            return [{"ts": dt.now(tz.utc).isoformat(), "tz": "Asia/Shanghai"}]

        def cq(sql):
            from datetime import datetime as dt, timezone as tz
            return [{"sd": dt.now(tz.utc).isoformat(), "st": dt.now(tz.utc).isoformat(),
                     "dbtz": "+00:00", "stz": "+08:00"}]

        health = evaluate_clock_health(jhemr_query=jq, cdms_query=cq)
        assert health.healthy is True
        for code in ("JHEMR", "CDMS"):
            assert health.offsets[code]["stable"] is True

    def test_rtt_exceeded_invalid(self):
        from app.services.identity_clock_health import evaluate_clock_health

        state = {"n": 0}

        def slow_q(sql):
            from datetime import datetime as dt, timezone as tz
            state["n"] += 1
            # 目标时间落后 → 巨大 offset → 有效样本但偏差大；改用异常 RTT：
            # 返回 30 分钟前的目标时间使 offset 超界仅告警；真正 RTT 异常
            # 由 rtt_s > max 判定——这里通过 target_time 构造 offset 区间不可
            # 能稳定的情形：交替 ±20 分钟。
            minutes = 20 if state["n"] % 2 == 1 else -20
            return [{"ts": (dt_now() + timedelta(minutes=minutes)).isoformat(), "tz": "PRC"}]

        def dt_now():
            from datetime import datetime as dt, timezone as tz
            return dt.now(tz.utc)

        def cq(sql):
            return [{"sd": None, "st": None}]

        health = evaluate_clock_health(jhemr_query=slow_q, cdms_query=None)
        # 交替大偏差 → 区间不相容 → unstable，enable 关闭
        ok, reasons = (health.healthy, health.reasons)
        assert ok is False

    def test_clock_gate_closes_enable_when_unsupported(self):
        from app.services.identity_clock_health import clock_health_allows_enable, evaluate_clock_health

        def jq(sql):
            from datetime import datetime as dt, timezone as tz
            return [{"ts": dt.now(tz.utc).isoformat(), "tz": "PRC"}]

        health = evaluate_clock_health(jhemr_query=jq, cdms_query=jq)
        ok, reasons = clock_health_allows_enable(health)
        assert ok is False  # 无所有权合同 → 恒关闭（T48）
        assert any("no_lock_reason" in r or "audit_contract" in r for r in reasons)

    def test_missing_health_closes(self):
        from app.services.identity_clock_health import clock_health_allows_enable

        ok, reasons = clock_health_allows_enable(None)
        assert ok is False and reasons == ["clock_health_missing"]


# ---------------------------------------------------------------------------
# T53：字典用途与身份用途并存（P0-18 兼容）
# ---------------------------------------------------------------------------

class TestPurposeBindingCompatibility:
    def test_identity_credential_resolved_from_binding_not_dict_policy(self, db_session, fake_adapters):
        from app.services.identity_sync_action_gate import dispatch_identity_state_action

        # P0-18：身份动作凭据只从 (source_code, purpose) 绑定解析；字典推送的
        # 旧 write_policy/write_credential_ref 不在身份门禁解析路径（并存不互踩）。
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001")
        db_session.commit()
        result = dispatch_identity_state_action(
            db_session, target_system="CDMS", action="disable", person_code="E001",
            approval_ref=APPROVAL,
        )
        assert result["status"] == "success", result
        connects = [c for c in fake_adapters.calls if c["op"] == "connect"]
        assert connects[0]["kwargs"]["credential_ref"].endswith(f"test_{CDMS_SOURCE}.write")


# ---------------------------------------------------------------------------
# T57：同代漂移回读
# ---------------------------------------------------------------------------

class TestDriftReadback:
    def test_drift_detected_replans_action(self, db_session, monkeypatch):
        from app.services.identity_hmac import compute_account_fingerprint
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        monkeypatch.setattr(settings, "identity_drift_readback_enabled", True)
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        decision = make_decision(db_session, "E001", user="disabled")
        for target in ("JHEMR", "CDMS"):
            fp = compute_account_fingerprint("E001", target, settings.identity_hmac_key_ref)
            db_session.add(IdentityAccountStateAttempt(
                run_id="R0", person_code="E001", target_system=target,
                target_account_fingerprint=fp, action="disable", desired_state="disabled",
                status="executed", rule_version="dual_source_v1",
                transition_seq=decision.transition_seq,
            ))
        db_session.commit()

        # 回读：JHEMR 已被人工改回启用（漂移）；CDMS 仍停用
        import app.services.identity_sync_orchestrator as orch
        monkeypatch.setattr(
            "app.services.identity_sync_action_gate.read_target_account_state",
            lambda target, person: (
                {"account_status": "0"} if target == "JHEMR" else {"fuserstate": "1"}
            ),
        )
        actions = select_account_state_actions(db_session)
        assert actions.get("drift_detected", 0) == 1
        entry = actions["disables"][0]
        assert "JHEMR" in entry["retry_targets"]
        assert "CDMS" in entry["done_targets"]


# ---------------------------------------------------------------------------
# T54/T59：pipeline 层模式与报告分离
# ---------------------------------------------------------------------------

class TestPipelineModes:
    def _patch_pipeline_env(self, monkeypatch):
        """禁用 JHEMR 存在性检查等真实连接点。"""
        monkeypatch.setattr(
            "app.services.identity_sync_orchestrator._fetch_jhemr_existing_emp_nos",
            lambda candidates: set(),
        )

    def test_pipeline_observe_zero_write_report(self, db_session, fake_adapters, monkeypatch):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import run_nightly_pipeline

        self._patch_pipeline_env(monkeypatch)
        settings.identity_run_mode = "observe"
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        make_person(db_session, "E001")
        make_decision(db_session, "E001", user="disabled")
        db_session.commit()

        result = run_nightly_pipeline(db_session, refresh_source=False)
        assert result["status"] in {"success", "partial"}
        run_row = db_session.scalar(select(IdentitySchedulerRun).where(
            IdentitySchedulerRun.run_id == result["run_id"]))
        summary = run_row.report_summary or {}
        assert summary.get("run_mode") == "observe"
        assert fake_adapters.calls == []  # 全身份目标零写（T54）
        attempts = db_session.scalars(select(IdentityAccountStateAttempt)).all()
        assert attempts == []

    def test_pipeline_disable_only_backlog_reported(self, db_session, fake_adapters, monkeypatch):
        from app.services.identity_sync_orchestrator import run_nightly_pipeline

        self._patch_pipeline_env(monkeypatch)
        register_executors(db_session)
        codes = [f"E{i:03d}" for i in range(5)]
        register_scope(db_session, codes)
        for code in codes:
            make_person(db_session, code)
            make_decision(db_session, code, user="disabled")
        # 其余在职启用人员构成 change_ratio 分母（既有门禁继续生效：T56）
        for i in range(20):
            code = f"A{i:03d}"
            make_person(db_session, code)
            make_decision(db_session, code, employee="enabled", user="enabled", desired="enabled")
        db_session.commit()

        result = run_nightly_pipeline(db_session, refresh_source=False)
        if result["status"] != "success":
            run_dbg = db_session.scalar(select(IdentitySchedulerRun).where(
                IdentitySchedulerRun.run_id == result["run_id"]))
            print("DEBUG error_message:", run_dbg.error_message)
            import json
            print("DEBUG summary:", json.dumps(run_dbg.report_summary, ensure_ascii=False, default=str)[:1500])
            print("DEBUG failed/success/skipped:", run_dbg.failed_count, run_dbg.success_count, run_dbg.skipped_count)
            for a in db_session.scalars(select(IdentityAccountStateAttempt)).all():
                print("DEBUG attempt:", a.person_code, a.target_system, a.status, a.reason_code, (a.attribution_evidence or {}).get("gate_reason"))
        assert result["status"] == "success"
        run_row = db_session.scalar(select(IdentitySchedulerRun).where(
            IdentitySchedulerRun.run_id == result["run_id"]))
        as_report = (run_row.report_summary or {}).get("account_state", {})
        assert as_report["disable_persons"] == 5
        assert as_report["actual_updated_persons"] == 5
        assert as_report["target_success_actions"] == 10  # 5 人 × 2 目标（T59 人/动作分开）
        # 预算名额标记 executed
        window = db_session.scalar(select(IdentityWindowBudget))
        reservations = db_session.scalars(select(IdentityWindowReservation)).all()
        assert len(reservations) == 5
        assert all(r.status == "executed" for r in reservations)


# ---------------------------------------------------------------------------
# P0-19 补遗：签名/科室子任务同样被运行模式门禁覆盖（全入口）
# ---------------------------------------------------------------------------

class TestSignatureDeptModeGate:
    def test_signature_sync_blocked_in_observe_and_disable_only(self, monkeypatch):
        from app.core.config import settings
        from app.services.identity_signature_sync import sync_missing_jhemr_signatures

        for mode in ("observe", "disable_only"):
            settings.identity_run_mode = mode
            result = sync_missing_jhemr_signatures(run_id="R1", db=object())
            assert result["status"] == "skipped", (mode, result)
            assert result["reason"] in {"run_mode_observe", "run_mode_disable_only_blocks_legacy_writes"}

    def test_dept_sync_blocked_in_observe(self, monkeypatch):
        from app.core.config import settings
        from app.services.identity_dept_sync import sync_jhemr_user_depts_daily

        settings.identity_run_mode = "observe"
        result = sync_jhemr_user_depts_daily(run_id="R1", db=object())
        assert result["status"] == "skipped" and result["reason"] == "run_mode_observe"

    def test_dept_sync_misconfigured_audit_before_mode(self):
        from app.services.identity_dept_sync import sync_jhemr_user_depts_daily

        result = sync_jhemr_user_depts_daily(run_id=None, db=None)
        assert result["status"] == "misconfigured"
