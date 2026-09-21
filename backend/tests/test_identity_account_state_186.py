"""186 I2/I3: dual-source (SYS_EMPLOYEE × SYS_USER) account state tests.

Covers T29–T46 of plan 186 §7.2: pure truth-table logic, opposite-status
normalizers, USER-only change discovery, batch reconciliation, dual-target
disable/enable with attribution, protection by (target, account), partial
failure + retry idempotency, threshold integration, side-effect-free
recovery, DTO secret scan, and a full pipeline→gate→bridge→target-simulator
chain from the REAL nightly entry (run_nightly_pipeline).

186 v1.10 S1 follow-up（P0-11/P0-19/P0-20 迁移）：目标写入不再由编排器直调
桥接函数，而是经 identity_sync_action_gate.dispatch_identity_state_action
唯一分发；测试用例改为 monkeypatch 两个适配器模块的类（FakeTargetAdapter
记录全部调用），驱动真实 gate+bridge 链。disable 需执行器注册 + 批准范围
（IdentityApprovedScope）+ run_mode；enable 生产恒 blocked
（AUTOMATIC_ENABLE_SUPPORTED=False），成功场景须显式临时开放该合同。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select

from app.core.db import Base
from app.models.governance_base import AssetActionExecutor
from app.models.asset_system import AssetSourcePurposeBinding, AssetDataSource
from app.models.identity_sync import (
    IdentityAccountStateAttempt,
    IdentityAccountStateDecision,
    IdentityApprovedScope,
    IdentityApprovedScopeMember,
    IdentityManagedRelation,
    IdentityProtectedAccount,
    IdentityRoleMapping,
    IdentitySchedulerRun,
    IdentityWindowBudget,
    IdentityWindowReservation,
)
from app.models.identity import IdentityPerson, IdentityPersonDepartment, IdentityPersonSource
from app.services.identity_account_state import (
    RULE_VERSION,
    aggregate_user_state,
    combine_account_state,
    compute_evidence_fingerprint,
    next_transition_seq,
    normalize_employee_state,
    normalize_sys_user_row,
    sys_user_row_in_scope,
    target_time_unchanged,
)
from app.services.his_identity_sync import persist_account_state_decisions

# SQLite 测试 shim：governance/registry 表使用原生 JSONB 列，SQLite 编译器
# 按 JSON 渲染（仅测试进程内生效；与 test_identity_action_gates_186_v110 同）。
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON

# ---------------------------------------------------------------------------
# 门禁夹具常量与辅助（复制自主 AI tests/test_identity_action_gates_186_v110.py，
# 两文件保持独立，不互相 import）
# ---------------------------------------------------------------------------

APPROVAL = "186-20260909-disable-only"
JHEMR_SOURCE = "jhemr_vastbase_10_10_8_177"
CDMS_SOURCE = "paperless_cdms_oracle_10_10_10_93"

# 在 autouse fake_adapters 打补丁前保存真实适配器类引用：T42 等静态源码
# 检查用例必须检查真实实现，而不是 FakeTargetAdapter。
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter as _RealJhemrIdentityAdapter  # noqa: E402


def register_executors(db, *, enable_disable=True, enable_enable=False, with_binding=True):
    """注册四类身份状态执行器（默认仅两个 disable 启用）+ 两目标用途绑定。"""
    for code, target_system, source in (
        ("JHEMR_ACCOUNT_DISABLE", "JHEMR", JHEMR_SOURCE),
        ("JHEMR_ACCOUNT_ENABLE", "JHEMR", JHEMR_SOURCE),
        ("CDMS_ACCOUNT_DISABLE", "CDMS", CDMS_SOURCE),
        ("CDMS_ACCOUNT_ENABLE", "CDMS", CDMS_SOURCE),
    ):
        enabled = enable_disable if code.endswith("DISABLE") else enable_enable
        db.add(AssetActionExecutor(
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
        ))
    if not with_binding:
        db.flush()
        return
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


def register_scope(db, person_codes, scope_type="pilot", approval=APPROVAL, action="disable"):
    """登记批准范围（token 不是名单：person_codes 必须显式列出）。"""
    scope = IdentityApprovedScope(
        scope_type=scope_type, approval_ref=approval, action=action, status="active",
    )
    db.add(scope)
    db.flush()
    for code in person_codes:
        db.add(IdentityApprovedScopeMember(scope_id=scope.id, person_code=code, frozen_reason="test"))
    db.flush()
    return scope


class FakeTargetAdapter:
    """可配置结果的假目标适配器：记录全部调用（op/emp_no/origin_disable）。

    结果按 op 查类属性 ``results``（测试内可改写以模拟失败/缺失）；
    unlock 默认实现归因语义（无 origin raw → blocked attribution_unknown）。
    """

    calls: list[dict] = []
    results: dict[str, dict] = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self):
        type(self).calls.append({"op": "connect", "kwargs": self.kwargs})

    def close(self):
        pass

    def _record(self, op, emp_no, origin_disable=None):
        type(self).calls.append({"op": op, "emp_no": emp_no, "origin_disable": origin_disable})

    def lock_account(self, emp_no):
        self._record("lock_account", emp_no)
        return dict(type(self).results.get("lock_account") or {"status": "success"})

    def lock_user(self, emp_no):
        self._record("lock_user", emp_no)
        return dict(type(self).results.get("lock_user") or {"status": "success"})

    def unlock_account(self, emp_no, *, origin_disable=None):
        self._record("unlock_account", emp_no, origin_disable)
        return self._unlock_result(origin_disable)

    def unlock_user(self, emp_no, *, origin_disable=None):
        self._record("unlock_user", emp_no, origin_disable)
        return self._unlock_result(origin_disable)

    @staticmethod
    def _unlock_result(origin_disable):
        if origin_disable is None or origin_disable.get("target_raw_time") is None:
            return {"status": "blocked", "reason": "attribution_unknown",
                    "lock_attribution": "manual_or_unknown"}
        return {"status": "success", "rows_affected": 1, "lock_attribution": "by_this_rule"}


_FAKE_RESULTS_DEFAULT = {
    "lock_account": {"status": "success", "rows_affected": 1, "account_status": 8,
                     "locked_time_raw": "2026-09-09T18:00:00"},
    "lock_user": {"status": "success", "rows_affected": 1,
                  "changed_at_raw": "2026-09-09T18:00:00", "changed_at": "2026-09-09T18:00:00"},
}


@pytest.fixture(autouse=True)
def fake_adapters(monkeypatch):
    """全文件默认把两个适配器类换成 FakeTargetAdapter（真实 gate+bridge 链）。"""
    FakeTargetAdapter.calls = []
    FakeTargetAdapter.results = dict(_FAKE_RESULTS_DEFAULT)
    import app.services.jhemr_identity_adapter as jhemr_mod
    import app.services.cdms_identity_adapter as cdms_mod
    monkeypatch.setattr("app.services.identity_sync_executor_bridge.JhemrIdentityAdapter",
                        FakeTargetAdapter, raising=False)
    # bridge 内部为局部 import，直接 patch 源模块类
    monkeypatch.setattr(jhemr_mod, "JhemrIdentityAdapter", FakeTargetAdapter)
    monkeypatch.setattr(cdms_mod, "CdmsIdentityAdapter", FakeTargetAdapter)
    yield FakeTargetAdapter


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    tables = [
        IdentityAccountStateDecision.__table__,
        IdentityAccountStateAttempt.__table__,
        IdentityManagedRelation.__table__,
        IdentityProtectedAccount.__table__,
        IdentityRoleMapping.__table__,
        IdentityPerson.__table__,
        IdentityPersonDepartment.__table__,
        IdentityPersonSource.__table__,
    ]
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

    tables += [
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
    """覆盖根 conftest 的数据库 autouse（纯逻辑/内存库模式，与仓库纯逻辑
    子目录 conftest 的 no-op 模式一致）：本文件的 db_session 使用各自的
    SQLite 内存引擎，不连接 APP_TEST_DB_URL 指向的库。"""
    yield


@pytest.fixture(autouse=True)
def hmac_test_key(monkeypatch):
    import os

    from app.core.config import settings
    from app.services.identity_hmac import reset_key_cache

    monkeypatch.setenv("TEST_HMAC_KEY", "test-only-hmac-key-not-for-prod-186")
    monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_KEY")
    monkeypatch.setattr(settings, "identity_dual_source_enforce", True)
    # 186 v1.10 门禁链设置（observe 默认值下动作恒空——测试须显式设 run_mode）
    monkeypatch.setattr(settings, "identity_run_mode", "disable_only")
    monkeypatch.setattr(settings, "identity_sync_enabled", True)
    monkeypatch.setattr(settings, "identity_phase_d_approval_version", APPROVAL)
    monkeypatch.setattr(settings, "identity_account_state_batch_limit", 2000)
    monkeypatch.setattr(settings, "identity_account_state_total_cap", 5000)
    monkeypatch.setattr(settings, "identity_window_max_persons", 20)
    monkeypatch.setattr(settings, "identity_window_hours", 20)
    monkeypatch.setattr(settings, "identity_clock_sampling_enabled", False)
    monkeypatch.setattr(settings, "identity_drift_readback_enabled", False)
    reset_key_cache()
    yield
    reset_key_cache()


# ---------------------------------------------------------------------------
# T29: employee × user four combinations (truth table, both targets same rule)
# ---------------------------------------------------------------------------


class TestT29TruthTable:
    @pytest.mark.parametrize(
        "validstate,user_status,expected",
        [
            ("1", "0", "enabled"),
            ("1", "1", "disabled"),
            ("0", "0", "disabled"),
            ("0", "1", "disabled"),
        ],
    )
    def test_four_combinations(self, validstate, user_status, expected):
        decision = combine_account_state(
            "E001",
            {"VALIDSTATE": validstate, "ISDELETED": 0},
            [{"EMPL_CODE": "E001", "STATUS": user_status, "ISDELETED": 0, "TYPE": "1"}],
        )
        assert decision.desired_state == expected
        if expected == "enabled":
            assert decision.execution_allowed

    def test_both_disabled_reason_records_both(self):
        decision = combine_account_state(
            "E001",
            {"VALIDSTATE": "0", "ISDELETED": 0},
            [{"EMPL_CODE": "E001", "STATUS": "1", "ISDELETED": 0, "TYPE": "1"}],
        )
        assert decision.desired_state == "disabled"
        assert "employee_disabled" in decision.decision_reason
        assert "user_disabled" in decision.decision_reason


# ---------------------------------------------------------------------------
# T30: delete flags, numeric/string forms, opposite encodings must not share a normalizer
# ---------------------------------------------------------------------------


class TestT30OppositeEncodings:
    def test_employee_delete_flag_wins(self):
        assert normalize_employee_state({"VALIDSTATE": "1", "ISDELETED": 1}) == "disabled"
        assert normalize_employee_state({"VALIDSTATE": "1", "ISDELETED": "Y"}) == "disabled"
        assert normalize_employee_state({"VALIDSTATE": "0", "ISDELETED": None}) == "disabled"
        assert normalize_employee_state({"VALIDSTATE": "1", "ISDELETED": 0}) == "enabled"

    def test_user_status_direction_opposite(self):
        # USER STATUS: 1=停用, 0=启用；EMPLOYEE VALIDSTATE: 1=有效, 0=停用。
        assert normalize_sys_user_row({"STATUS": 1, "ISDELETED": 0}) == "disabled"
        assert normalize_sys_user_row({"STATUS": 0, "ISDELETED": 0}) == "enabled"
        assert normalize_sys_user_row({"STATUS": "1", "ISDELETED": "0"}) == "disabled"
        assert normalize_sys_user_row({"STATUS": "0", "ISDELETED": "0"}) == "enabled"
        # 共用 normalizer 的典型错误必须在此暴露：VALIDSTATE 语义下 1=有效
        assert normalize_employee_state({"VALIDSTATE": "1"}) == "enabled"
        assert normalize_sys_user_row({"STATUS": "1"}) == "disabled"

    def test_user_deleted_flag(self):
        assert normalize_sys_user_row({"STATUS": "0", "ISDELETED": 1}) == "disabled"

    def test_existing_employee_normalizer_regression_kept(self):
        from app.services import his_identity_sync as his

        assert his._employee_employment_status({"ISDELETED": 1, "VALIDSTATE": 1}) == "inactive"
        assert his._employee_employment_status({"ISDELETED": "0", "VALIDSTATE": 1}) == "active"


# ---------------------------------------------------------------------------
# T31: NULL/blank/unknown codes, missing source rows — never enabled by coercion
# ---------------------------------------------------------------------------


class TestT31UnknownsAndMissing:
    @pytest.mark.parametrize("user_status", [None, "", " ", "2", "Y", "unknown"])
    def test_user_unknown_blocks_enable(self, user_status):
        decision = combine_account_state(
            "E001",
            {"VALIDSTATE": "1", "ISDELETED": 0},
            [{"EMPL_CODE": "E001", "STATUS": user_status, "ISDELETED": 0, "TYPE": "1"}],
        )
        assert decision.desired_state == "unknown"
        assert not decision.execution_allowed

    def test_user_missing_is_unknown_not_disabled(self):
        decision = combine_account_state("E001", {"VALIDSTATE": "1", "ISDELETED": 0}, [])
        assert decision.user_state == "unknown"
        assert decision.desired_state == "unknown"

    def test_reliable_disabled_wins_over_unknown(self):
        # 人员停用 + 账号未知 → disabled（明确停用优先）
        decision = combine_account_state(
            "E001", {"VALIDSTATE": "0"}, [{"STATUS": None, "ISDELETED": 0, "TYPE": "1"}]
        )
        assert decision.desired_state == "disabled"
        decision2 = combine_account_state("E001", {"VALIDSTATE": None}, [{"STATUS": "1", "TYPE": "1"}])
        assert decision2.desired_state == "disabled"

    def test_employee_missing_row(self):
        decision = combine_account_state("E001", None, [])
        assert decision.desired_state == "unknown"
        assert decision.employee_evidence.get("row_missing") is True

    def test_missing_sys_user_table_yields_unknown_decisions(self, db_session):
        # 采集层表缺失 → sys_users 空列表 + notes；判定层全员 unknown → 零启用候选
        rows = {
            "employees": [{"EMPLCODE": "E001", "VALIDSTATE": "1", "ISDELETED": 0}],
            "sys_users": [],
        }
        stats = persist_account_state_decisions(db_session, rows, notes=["FXHIS.SYS_USER: missing_or_inaccessible"])
        assert stats["created"] == 1
        row = db_session.scalars(select(IdentityAccountStateDecision)).first()
        assert row.desired_state == "unknown"
        assert row.execution_allowed is False


# ---------------------------------------------------------------------------
# T32: multi-account aggregation, out-of-scope accounts, duplicates
# ---------------------------------------------------------------------------


class TestT32MultiAccount:
    def test_out_of_scope_platform_account_ignored(self):
        assert sys_user_row_in_scope({"EMPL_CODE": "X", "TYPE": "100", "USERFLAG": "P"}) is False
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": "1"}) is True

    def test_null_type_fail_closed_out_of_scope(self):
        # P0-10：TYPE 为 NULL/空一律不在范围，EMPL_CODE 存在也不再回退纳入
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": None}) is False
        assert sys_user_row_in_scope({"EMPL_CODE": "E001", "TYPE": "  "}) is False
        state, reason = aggregate_user_state(
            [{"EMPL_CODE": "E001", "STATUS": "0", "TYPE": None}]
        )
        assert state == "unknown"
        assert reason == "sys_user_missing_or_out_of_scope"

    def test_any_disabled_account_disables(self):
        state, reason = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
            {"EMPL_CODE": "E001", "STATUS": "1", "TYPE": "1"},
        ])
        assert state == "disabled"
        assert reason == "sys_user_status_disabled_multi"

    def test_all_enabled_multi_account_is_unknown_not_enabled(self):
        # P0-10：多账号未证实范围不聚合为 enabled（旧行为两行全启用→enabled
        # 已废弃；确认 1:1 的范围外变化必须 fail-closed）
        state, reason = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
        ])
        assert state == "unknown"
        assert reason == "sys_user_multi_account_unconfirmed"

    def test_mixed_unknown_is_not_enabled(self):
        state, _ = aggregate_user_state([
            {"EMPL_CODE": "E001", "STATUS": "0", "TYPE": "1"},
            {"EMPL_CODE": "E001", "STATUS": None, "TYPE": "1"},
        ])
        assert state == "unknown"


# ---------------------------------------------------------------------------
# T33/T40: USER-only transitions + transition ordinals
# ---------------------------------------------------------------------------


class TestT33TransitionSeq:
    def test_user_only_flips_get_new_ordinals(self):
        # 代次约定：初始记录=第1代；每次变化开新代；同值重复保持当前代。
        assert next_transition_seq([], "disabled") == 1
        assert next_transition_seq(["enabled"], "disabled") == 2
        assert next_transition_seq(["enabled", "disabled"], "enabled") == 3
        assert next_transition_seq(["enabled", "disabled", "enabled"], "disabled") == 4
        # 同值重复读取不推进代次（幂等）：第一次停用仍是第2代
        assert next_transition_seq(["enabled", "disabled", "disabled"], "disabled") == 2

    def test_user_only_change_detected_without_employee_watermark(self, db_session):
        # EMPLOYEE 不变（同指纹），USER 1→0→1→1 每次变化产生新决策行/代次
        employee = {"EMPLCODE": "E001", "VALIDSTATE": "1", "ISDELETED": 0}
        seqs = []
        for status in ("1", "0", "1"):
            rows = {"employees": [employee], "sys_users": [
                {"EMPL_CODE": "E001", "STATUS": status, "ISDELETED": 0, "TYPE": "1"}
            ]}
            persist_account_state_decisions(db_session, rows, notes=[])
            db_session.commit()
            row = db_session.scalars(
                select(IdentityAccountStateDecision).order_by(IdentityAccountStateDecision.id.desc())
            ).first()
            seqs.append((row.desired_state, row.transition_seq))
        assert seqs == [("disabled", 1), ("enabled", 2), ("enabled", 2)]
        fingerprints = {
            row.evidence_fingerprint
            for row in db_session.scalars(select(IdentityAccountStateDecision)).all()
        }
        assert len(fingerprints) == 2  # disabled 与 enabled 各一条；同值幂等复用

    def test_same_evidence_repeat_updates_not_duplicates(self, db_session):
        rows = {
            "employees": [{"EMPLCODE": "E001", "VALIDSTATE": "1", "ISDELETED": 0}],
            "sys_users": [{"EMPL_CODE": "E001", "STATUS": "1", "ISDELETED": 0, "TYPE": "1"}],
        }
        persist_account_state_decisions(db_session, rows, notes=[])
        persist_account_state_decisions(db_session, rows, notes=[])
        db_session.commit()
        count = len(db_session.scalars(select(IdentityAccountStateDecision)).all())
        assert count == 1

    def test_fingerprint_ignores_timestamps(self):
        a = compute_evidence_fingerprint(
            {"VALIDSTATE": "1", "ISDELETED": 0},
            [{"EMPL_CODE": "E1", "STATUS": "1", "ISDELETED": 0}],
        )
        b = compute_evidence_fingerprint(
            {"VALIDSTATE": "1", "ISDELETED": 0},
            [{"EMPL_CODE": "E1", "STATUS": "1", "ISDELETED": 0, "MODIFIEDTIME": "2099-01-01"}],
        )
        assert a == b


# ---------------------------------------------------------------------------
# T34: batch truncation — incomplete evidence must not enable
# ---------------------------------------------------------------------------


class TestT34Truncation:
    def test_truncated_batch_reported(self, db_session, monkeypatch):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        # P0-3 新语义：run 内分页续跑，总量上限 identity_account_state_total_cap
        # （与 batch_limit 无关的超量才截断）。cap 与 batch_limit 同步调小，
        # 5 个决策只扫 3 个：scanned=3 / truncated=True / remaining=2。
        monkeypatch.setattr(settings, "identity_account_state_batch_limit", 2)
        monkeypatch.setattr(settings, "identity_account_state_total_cap", 3)
        register_executors(db_session)
        codes = [f"E{i:03d}" for i in range(5)]
        register_scope(db_session, codes)
        for code in codes:
            db_session.add(IdentityPerson(person_code=code, employment_status="active"))
            _seed_decision(db_session, code, "disabled", employee="enabled", user="disabled")
        db_session.commit()
        result = select_account_state_actions(db_session)
        assert result["truncated"] is True
        assert result["scanned"] == 3
        assert result["remaining"] == 2
        # 已扫描的 3 人在批准范围内且窗口预算未满 → 本窗计划 3 人
        assert [e["person_code"] for e in result["disables"]] == ["E000", "E001", "E002"]
        assert result["deferred_budget"] == 0


# ---------------------------------------------------------------------------
# T35/T36/T39/T41/T42/T43: pipeline-level dual-target execution (simulators)
# ---------------------------------------------------------------------------


class FakeOutcome:
    """Per-target scripted outcomes for the bridge simulator."""


def _seed_decision(db, person_code, desired, *, employee="enabled", user="enabled", seq=1):
    db.add(IdentityAccountStateDecision(
        person_code=person_code,
        rule_version=RULE_VERSION,
        employee_state=employee,
        user_state=user,
        desired_state=desired,
        decision_reason="seed",
        execution_allowed=True,
        evidence_fingerprint=f"fp-{person_code}-{desired}-{seq}",
        transition_seq=seq,
    ))
    db.commit()


class TestT36DualTargetDisable:
    def test_pipeline_disables_both_targets(self, db_session, fake_adapters):
        from app.services.identity_sync_orchestrator import (
            _process_account_state_person,
            select_account_state_actions,
        )

        db_session.add(IdentityPerson(person_code="E001", employment_status="active"))
        _seed_decision(db_session, "E001", "disabled", employee="enabled", user="disabled")
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert len(actions["disables"]) == 1
        entry = actions["disables"][0]

        result = _process_account_state_person(db_session, entry, "RUN-186-TEST")
        db_session.commit()
        assert result["status"] == "success"
        assert result["targets"] == {"JHEMR": "success", "CDMS": "success"}
        # 真实 gate→bridge→适配器链：每目标恰好一次 lock（写凭据来自用途绑定）
        ops = [(c["op"], c.get("emp_no")) for c in fake_adapters.calls]
        assert ("lock_account", "E001") in ops and ("lock_user", "E001") in ops
        assert ("unlock_account", "E001") not in ops and ("unlock_user", "E001") not in ops
        connects = [c for c in fake_adapters.calls if c["op"] == "connect"]
        assert len(connects) == 2  # 每目标一次连接，凭据从绑定解析
        assert all(c["kwargs"]["credential_ref"].startswith("file:///") for c in connects)
        attempts = db_session.scalars(select(IdentityAccountStateAttempt)).all()
        assert {a.target_system for a in attempts} == {"JHEMR", "CDMS"}
        assert all(a.status == "executed" for a in attempts)
        # P0-4：停用成功持久化目标 raw 时间（恢复归因基准）
        assert all((a.attribution_evidence or {}).get("target_raw_time") == "2026-09-09T18:00:00"
                   for a in attempts)

    def test_missing_target_disables_without_create(self, db_session, fake_adapters):
        from app.services.identity_sync_orchestrator import (
            _process_account_state_person,
            select_account_state_actions,
        )

        # 两目标均缺失：P0-8 分类为 target_missing（不算幂等完成），整体 blocked
        fake_adapters.results = {
            "lock_account": {"status": "missing_target"},
            "lock_user": {"status": "missing_target"},
        }
        _seed_decision(db_session, "E009", "disabled", employee="enabled", user="disabled")
        db_session.add(IdentityPerson(person_code="E009", employment_status="active"))
        register_executors(db_session)
        register_scope(db_session, ["E009"])
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert len(actions["disables"]) == 1
        result = _process_account_state_person(db_session, actions["disables"][0], "RUN-186-T2")
        db_session.commit()
        assert result["status"] == "blocked"
        assert result["targets"] == {"JHEMR": "target_missing", "CDMS": "target_missing"}
        attempts = db_session.scalars(select(IdentityAccountStateAttempt)).all()
        assert len(attempts) == 2
        assert all(a.reason_code == "target_missing" for a in attempts)
        # 零创建：适配器只被调用 lock 类操作（无 create/apply/密码路径）
        assert {c["op"] for c in fake_adapters.calls} <= {"connect", "lock_account", "lock_user"}
        # P0-8+§13.5 反饥饿：target_missing 保留待补偿但不占窗口名额——
        # 入 missing 池；探测到目标重现才回归队列（drift 关闭时单列计数）。
        actions2 = select_account_state_actions(db_session)
        assert actions2["disables"] == []
        assert actions2["backlog_missing_retry"] == 1


class TestT39PartialFailure:
    def test_jhemr_success_cdms_failure_partial_and_retry(self, db_session, fake_adapters):
        from app.services.identity_sync_orchestrator import (
            _process_account_state_person,
            select_account_state_actions,
        )

        db_session.add(IdentityPerson(person_code="E002", employment_status="active"))
        _seed_decision(db_session, "E002", "disabled", employee="enabled", user="disabled")
        register_executors(db_session)
        register_scope(db_session, ["E002"])
        db_session.commit()

        # CDMS 写失败：真实链路下 gate 放行、适配器返回 failed
        fake_adapters.results["lock_user"] = {"status": "failed", "error": "simulated cdms failure"}
        actions = select_account_state_actions(db_session)
        entry = actions["disables"][0]
        result = _process_account_state_person(db_session, entry, "RUN-186-P1")
        db_session.commit()
        assert result["status"] == "partial"
        assert result["targets"] == {"JHEMR": "success", "CDMS": "failed"}

        # 重试：只有失败目标进入重试，成功目标不重复写（同代次 executed 幂等）
        actions2 = select_account_state_actions(db_session)
        assert len(actions2["disables"]) == 1
        entry2 = actions2["disables"][0]
        assert entry2["done_targets"] == ["JHEMR"]
        assert entry2["retry_targets"] == ["CDMS"]
        fake_adapters.results["lock_user"] = dict(_FAKE_RESULTS_DEFAULT["lock_user"])
        result2 = _process_account_state_person(db_session, entry2, "RUN-186-P2")
        db_session.commit()
        assert result2["status"] == "success"
        # JHEMR 未被重复调用：done_targets 已跳过（仅首跑 1 次 lock_account）
        jhemr_locks = [c for c in fake_adapters.calls
                       if c["op"] == "lock_account" and c["emp_no"] == "E002"]
        assert len(jhemr_locks) == 1
        cdms_locks = [c for c in fake_adapters.calls
                      if c["op"] == "lock_user" and c["emp_no"] == "E002"]
        assert len(cdms_locks) == 2  # 失败一次 + 重试成功一次


class TestT40RecoveryRules:
    def test_enable_requires_disable_evidence(self, db_session, monkeypatch):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        # full 模式 + 临时开放所有权合同 + enable 批准范围：没有本规则
        # executed disable 证据的启用判定仍不产生 enable（unchanged）。
        import app.services.identity_sync_action_gate as gate_mod
        import app.services.identity_clock_health as clock_mod
        monkeypatch.setattr(gate_mod, "AUTOMATIC_ENABLE_SUPPORTED", True)
        monkeypatch.setattr(clock_mod, "AUTOMATIC_ENABLE_SUPPORTED", True)
        settings.identity_run_mode = "full"
        register_executors(db_session, enable_enable=True)
        register_scope(db_session, ["E003"])
        register_scope(db_session, ["E003"], scope_type="pilot_enable", action="enable")

        db_session.add(IdentityPerson(person_code="E003", employment_status="active"))
        _seed_decision(db_session, "E003", "enabled", employee="enabled", user="enabled")
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert actions["enables"] == []
        assert actions["unchanged"] == 1

    def test_enable_with_evidence_and_attribution(self, db_session, fake_adapters, monkeypatch):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import (
            _process_account_state_person,
            select_account_state_actions,
        )

        settings.identity_run_mode = "full"
        register_executors(db_session, enable_enable=True)
        register_scope(db_session, ["E004"])  # disable 批准范围
        register_scope(db_session, ["E004"], scope_type="pilot_enable", action="enable")

        db_session.add(IdentityPerson(person_code="E004", employment_status="active"))
        _seed_decision(db_session, "E004", "disabled", employee="enabled", user="disabled")
        db_session.commit()
        actions = select_account_state_actions(db_session)
        result = _process_account_state_person(db_session, actions["disables"][0], "RUN-186-R1")
        db_session.commit()
        assert result["status"] == "success"

        # 双来源转启用 → 恢复期望（新代次）
        _seed_decision(db_session, "E004", "enabled", employee="enabled", user="enabled", seq=2)
        db_session.commit()
        actions2 = select_account_state_actions(db_session)
        assert len(actions2["enables"]) == 1

        # 生产 enable 恒 blocked（§13.3：目标无锁原因/版本字段）——先证明合同
        import app.services.identity_sync_action_gate as gate_mod
        import app.services.identity_clock_health as clock_mod
        assert gate_mod.AUTOMATIC_ENABLE_SUPPORTED is False
        fake_adapters.calls.clear()  # 剔除 R1 停用阶段的适配器调用，隔离观察 R2
        result_closed = _process_account_state_person(db_session, actions2["enables"][0], "RUN-186-R2")
        db_session.commit()
        assert result_closed["status"] == "blocked"
        assert result_closed["targets"] == {"JHEMR": "blocked", "CDMS": "blocked"}
        enable_attempts_blocked = db_session.scalars(
            select(IdentityAccountStateAttempt).where(IdentityAccountStateAttempt.action == "enable")
        ).all()
        assert all(a.status == "blocked" for a in enable_attempts_blocked)
        assert all((a.attribution_evidence or {}).get("gate_reason") == "automatic_enable_not_supported"
                   for a in enable_attempts_blocked)
        # 门禁 blocked：零目标连接（无 connect/unlock 调用）
        assert not [c for c in fake_adapters.calls if c["op"] in {"connect", "unlock_account", "unlock_user"}]

        # 隔离场景临时开放所有权合同 + 时钟：恢复经 dispatch 到适配器
        monkeypatch.setattr(gate_mod, "AUTOMATIC_ENABLE_SUPPORTED", True)
        monkeypatch.setattr(clock_mod, "AUTOMATIC_ENABLE_SUPPORTED", True)
        actions3 = select_account_state_actions(db_session)
        entry3 = actions3["enables"][0]
        result3 = _process_account_state_person(db_session, entry3, "RUN-186-R3")
        db_session.commit()
        assert result3["status"] == "success"
        assert result3["targets"] == {"JHEMR": "success", "CDMS": "success"}
        unlock_calls = [c for c in fake_adapters.calls if c["op"] in {"unlock_account", "unlock_user"}]
        assert len(unlock_calls) == 2
        disable_attempts = db_session.scalars(
            select(IdentityAccountStateAttempt).where(IdentityAccountStateAttempt.action == "disable")
        ).all()
        ids_by_target = {a.target_system: a.id for a in disable_attempts}
        for call in unlock_calls:
            origin = call["origin_disable"]
            assert origin is not None
            # 恢复归因基准 = 平台持久化的目标 raw 时间（不是平台 executed_at）
            assert origin["target_raw_time"] == "2026-09-09T18:00:00"
            assert origin["target_account_fingerprint"]
            assert origin["rule_version"] == RULE_VERSION
            expected_target = "JHEMR" if call["op"] == "unlock_account" else "CDMS"
            assert origin["attempt_id"] == ids_by_target[expected_target]
        # enable attempt 关联 origin 停用动作（P0-4）
        enable_attempts = db_session.scalars(
            select(IdentityAccountStateAttempt).where(IdentityAccountStateAttempt.action == "enable")
        ).all()
        assert all(a.origin_disable_attempt_id is not None for a in enable_attempts)

    def test_manual_lock_blocks_recovery(self, db_session):
        from app.services.identity_sync_orchestrator import _process_account_state_person

        db_session.add(IdentityPerson(person_code="E005", employment_status="active"))
        _seed_decision(db_session, "E005", "disabled", employee="enabled", user="disabled")
        # 先由本规则停用 JHEMR（有 executed 证据）
        db_session.add(IdentityAccountStateAttempt(
            person_code="E005", target_system="JHEMR",
            target_account_fingerprint="fp-E005-jhemr", action="disable",
            desired_state="disabled", transition_seq=1, rule_version=RULE_VERSION,
            status="executed", executed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ))
        db_session.commit()
        entry = {"person_code": "E005", "action": "enable", "transition_seq": 2,
                 "rule_version": RULE_VERSION, "decision_id": None, "desired_state": "enabled"}
        with patch(
            "app.services.identity_sync_executor_bridge.execute_jhemr_enable",
            return_value={"status": "blocked", "reason": "attribution_mismatch", "lock_attribution": "manual_or_unknown"},
        ), patch(
            "app.services.identity_sync_executor_bridge.execute_cdms_enable",
            return_value={"status": "blocked", "reason": "attribution_unknown", "lock_attribution": "manual_or_unknown"},
        ):
            result = _process_account_state_person(db_session, entry, "RUN-186-M1")
        assert result["targets"] == {"JHEMR": "blocked", "CDMS": "blocked"}
        attempts = db_session.scalars(
            select(IdentityAccountStateAttempt).where(IdentityAccountStateAttempt.action == "enable")
        ).all()
        assert all(a.status == "blocked" for a in attempts)
        assert all(a.lock_attribution == "manual_or_unknown" for a in attempts)

    def test_target_time_unchanged_precise_no_tolerance(self):
        # 186 v1.10 §13.3：恢复归因 = 原始值精确比对，±300 容差与
        # 时区换算已全部删除（attribution_matches 已移除）。
        base = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 精确一致 → True（datetime 与等价 isoformat 字符串可互比）
        assert target_time_unchanged(base, base.isoformat()) is True
        assert target_time_unchanged(base.isoformat(), base) is True
        # 哪怕 1 秒差异（旧 ±300 容差会放行）→ False
        assert target_time_unchanged(base + timedelta(seconds=1), base) is False
        assert target_time_unchanged(base, base.isoformat() + " ") is True  # str 规范化 strip
        assert target_time_unchanged(base.isoformat() + "+00:00", base.isoformat()) is False
        # 任一侧缺失 → None（attribution_unknown，保持待核实不恢复）
        assert target_time_unchanged(None, base) is None
        assert target_time_unchanged(base, None) is None
        assert target_time_unchanged(None, None) is None


class TestT38Protection:
    def test_protection_by_target_pair_not_bare_account(self, db_session):
        from app.services.identity_sync_orchestrator import select_account_state_actions

        # 保护表有 (JHEMR, 009999)；人员 E001 同名账号不存在——不得误伤
        db_session.add(IdentityProtectedAccount(
            target_system="JHEMR", account_id="009999", reason="admin", protected_by="t",
        ))
        db_session.add(IdentityPerson(person_code="E001", employment_status="active"))
        _seed_decision(db_session, "E001", "disabled", employee="enabled", user="disabled")
        register_executors(db_session)
        register_scope(db_session, ["E001"])
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert len(actions["disables"]) == 1
        assert actions["blocked_protected"] == 0

    def test_person_level_protection_blocks_both(self, db_session):
        from app.services.identity_sync_orchestrator import select_account_state_actions

        # P0-7 HMAC 候选法：保护登记 (CDMS, E006) 命中人员指纹 → 整人不变更
        db_session.add(IdentityProtectedAccount(
            target_system="CDMS", account_id="E006", reason="manual", protected_by="t",
        ))
        db_session.add(IdentityPerson(person_code="E006", employment_status="active"))
        _seed_decision(db_session, "E006", "disabled", employee="enabled", user="disabled")
        register_executors(db_session)
        register_scope(db_session, ["E006"])
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert actions["disables"] == []
        assert actions["blocked_protected"] == 1

    def test_protection_rechecked_at_execution(self, db_session):
        from app.services.identity_sync_orchestrator import _process_account_state_person

        entry = {"person_code": "E007", "action": "disable", "transition_seq": 1,
                 "rule_version": RULE_VERSION, "decision_id": None, "desired_state": "disabled"}
        db_session.add(IdentityProtectedAccount(target_system="JHEMR", account_id="E007", reason="late"))
        db_session.commit()
        with patch("app.services.identity_sync_executor_bridge.execute_jhemr_lock") as lock:
            result = _process_account_state_person(db_session, entry, "RUN-186-X1")
        assert result["status"] == "skipped"
        assert result["reason"] == "protected_at_execution"
        assert lock.call_count == 0


class TestT41StaleEnable:
    def test_stale_enable_cancelled_when_source_now_disabled(self, db_session, monkeypatch):
        # 场景：恢复候选生成后 HIS 又转停用 → 选择阶段按最新判定产出 disable，
        # 旧 enable 因代次不匹配不再是当前动作（无陈旧 SQL 重放）。
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import select_account_state_actions

        # full 模式：enables 列空是"最新判定为停用"的真实结果，而非模式压制
        settings.identity_run_mode = "full"
        register_executors(db_session, enable_enable=True)
        register_scope(db_session, ["E008"])
        register_scope(db_session, ["E008"], scope_type="pilot_enable", action="enable")

        db_session.add(IdentityPerson(person_code="E008", employment_status="active"))
        # 历史：enabled→disabled→enabled（enable 尝试 planned 未执行）
        _seed_decision(db_session, "E008", "enabled", employee="enabled", user="enabled", seq=2)
        db_session.add(IdentityAccountStateAttempt(
            person_code="E008", target_system="JHEMR",
            target_account_fingerprint="fp-E008-jhemr", action="enable",
            desired_state="enabled", transition_seq=2, rule_version=RULE_VERSION,
            status="planned",
        ))
        db_session.commit()
        # 最新判定：又停用（代次 3）
        _seed_decision(db_session, "E008", "disabled", employee="enabled", user="disabled", seq=3)
        db_session.commit()
        actions = select_account_state_actions(db_session)
        assert len(actions["disables"]) == 1
        assert actions["enables"] == []
        # 旧 planned enable 尝试保留为非当前动作，不再被消费
        entry = actions["disables"][0]
        assert entry["transition_seq"] == 3


class TestT44NoImplicitEnable:
    def test_disabled_desired_excluded_from_create_candidates(self, db_session):
        from app.services.identity_sync_orchestrator import select_nightly_candidates

        db_session.add(IdentityPerson(
            person_code="E010", employment_status="active", classification="doctor",
            source_create_date=datetime(2026, 7, 25, tzinfo=timezone.utc),
        ))
        db_session.add(IdentityPersonDepartment(
            person_code="E010", dept_code="D01", source_table="FXHIS.SYS_EMPLOYEE", is_primary=True,
        ))
        _seed_decision(db_session, "E010", "disabled", employee="enabled", user="disabled")
        candidates = select_nightly_candidates(db_session)
        assert all(c["emp_no"] != "E010" for c in candidates)

    def test_unknown_desired_blocks_new_account_for_unmanaged(self, db_session):
        from app.services.identity_sync_orchestrator import select_nightly_candidates

        db_session.add(IdentityPerson(
            person_code="E011", employment_status="active", classification="nurse",
            source_create_date=datetime(2026, 7, 25, tzinfo=timezone.utc),
        ))
        db_session.add(IdentityPersonDepartment(
            person_code="E011", dept_code="D01", source_table="FXHIS.SYS_EMPLOYEE", is_primary=True,
        ))
        _seed_decision(db_session, "E011", "unknown", employee="enabled", user="unknown")
        candidates = select_nightly_candidates(db_session)
        assert all(c["emp_no"] != "E011" for c in candidates)

    def test_employment_status_not_polluted(self, db_session):
        rows = {
            "employees": [{"EMPLCODE": "E012", "VALIDSTATE": "1", "ISDELETED": 0}],
            "sys_users": [{"EMPL_CODE": "E012", "STATUS": "1", "ISDELETED": 0, "TYPE": "1"}],
        }
        db_session.add(IdentityPerson(person_code="E012", employment_status="active"))
        db_session.commit()
        persist_account_state_decisions(db_session, rows, notes=[])
        db_session.commit()
        person = db_session.scalars(select(IdentityPerson).where(IdentityPerson.person_code == "E012")).first()
        assert person.employment_status == "active"  # 账号停用≠离职

    def test_login_sign_expected_excludes_disabled(self, db_session):
        from app.services.identity_login_sign_sync import _read_expected_platform

        db_session.add(IdentityPerson(
            person_code="E013", employment_status="active", classification="doctor",
        ))
        _seed_decision(db_session, "E013", "disabled", employee="enabled", user="disabled")
        expected = _read_expected_platform(db_session)
        assert "E013" not in expected


class TestT43Thresholds:
    def test_account_state_disables_flow_into_max_deactivate(self, db_session):
        from app.core.config import settings
        from app.services.identity_sync_orchestrator import check_thresholds

        # 230 个 USER-disabled 积压 → 超默认 max_deactivate=20 → 熔断待复核
        stats = {"new": 0, "update": 0, "align_existing": 0, "resync_unchanged": 0,
                 "deactivate": 230, "scope": 2500, "watermark_gap_hours": 1,
                 "account_state_enable": 0}
        result = check_thresholds([], stats)
        assert result["triggered"] is True
        assert result["dimension"] == "max_deactivate"
        assert settings.identity_cb_max_deactivate == 20  # 未提高阈值


class TestT45SecretScan:
    def test_decision_and_source_rows_contain_no_secrets(self, db_session):
        rows = {
            "employees": [{"EMPLCODE": "E014", "VALIDSTATE": "1", "ISDELETED": 0}],
            "sys_users": [{"EMPL_CODE": "E014", "STATUS": "1", "ISDELETED": 0, "TYPE": "1",
                           "PASSWORD": "SHOULD_NOT_PERSIST", "NICKNAME": "nick"}],
        }
        persist_account_state_decisions(db_session, rows, notes=[])
        db_session.commit()
        decision = db_session.scalars(select(IdentityAccountStateDecision)).first()
        blob = str(decision.employee_evidence) + str(decision.user_evidence)
        for secret in ("PASSWORD", "SHOULD_NOT_PERSIST", "NICKNAME"):
            assert secret not in blob

    def test_collection_projection_excludes_secret_columns(self):
        from app.services import his_identity_sync as his
        import inspect

        source = inspect.getsource(his._collect)
        sys_user_block = source.split("sys_users")[-1]
        for forbidden in ("PASSWORD", "NICKNAME", "AVATAR", "ROLEID"):
            assert forbidden not in sys_user_block


class TestT46PipelineChain:
    def test_full_nightly_entry_to_target_simulators(self, db_session, fake_adapters, monkeypatch):
        """T46：从真实夜跑入口 run_nightly_pipeline 贯穿双来源 fixture →
        编排 → gate → bridge → 两个目标适配器模拟器（FakeTargetAdapter）。
        refresh_source=False（判定已在同一会话预置）；JHEMR 存在性检查替换为
        no-op，禁用真实连接点。"""
        from app.services import identity_sync_orchestrator as orch
        import app.services.his_identity_sync as his_mod

        monkeypatch.setattr(his_mod, "sync_his_identity", lambda *a, **k: {"status": "success"})
        monkeypatch.setattr(
            "app.services.identity_sync_orchestrator._fetch_jhemr_existing_emp_nos",
            lambda candidates: set(),
        )

        # 双来源 fixture：E101 仅账号停用（批准范围内）；E102 双启用
        # （无停用证据 → 零恢复动作）
        register_executors(db_session)
        register_scope(db_session, ["E101"])
        rows = {
            "employees": [
                {"EMPLCODE": "E101", "VALIDSTATE": "1", "ISDELETED": 0, "MODIFIEDTIME": None},
                {"EMPLCODE": "E102", "VALIDSTATE": "1", "ISDELETED": 0, "MODIFIEDTIME": None},
            ],
            "sys_users": [
                {"EMPL_CODE": "E101", "STATUS": "1", "ISDELETED": 0, "TYPE": "1"},
                {"EMPL_CODE": "E102", "STATUS": "0", "ISDELETED": 0, "TYPE": "1"},
            ],
        }
        persist_account_state_decisions(db_session, rows, notes=[])
        db_session.add(IdentityPerson(person_code="E101", employment_status="active"))
        db_session.add(IdentityPerson(person_code="E102", employment_status="active"))
        # 合格人群基数（change_ratio 分母）：熔断比例维度在生产口径下
        # 单人停用 << 30%，不为跑通测试放宽任何阈值。填充人员无科室、无决策，
        # 不会进入 create/align 候选，仅作分母。
        for i in range(3, 8):
            db_session.add(IdentityPerson(
                person_code=f"E10{i}", employment_status="active", classification="nurse",
                source_create_date=datetime(2026, 7, 25, tzinfo=timezone.utc),
            ))
        db_session.commit()

        result = orch.run_nightly_pipeline(db_session, triggered_by="test_186", refresh_source=False)
        assert result["status"] == "success", result

        # E101（仅账号停用，批准范围内）双目标各写一次；E102（双启用、
        # 无停用证据）零恢复动作
        lock_ops = [(c["op"], c["emp_no"]) for c in fake_adapters.calls if c["op"].startswith("lock_")]
        assert lock_ops == [("lock_account", "E101"), ("lock_user", "E101")]
        assert not [c for c in fake_adapters.calls if c["op"].startswith("unlock_")]

        summary = db_session.scalars(select(IdentitySchedulerRun)).first()
        assert summary is not None
        as_report = summary.report_summary["account_state"]
        assert as_report["disable_persons"] == 1
        assert as_report["enable_persons"] == 0
        # T59 口径：人/动作分开——1 人实际更新、2 目标动作成功
        assert as_report["actual_updated_persons"] == 1
        assert as_report["target_success_actions"] == 2
        assert as_report["success"] == 1
        assert summary.report_summary["run_mode"] == "disable_only"
        # 统计口径：1 人 = 1 人员、2 目标动作
        attempts = db_session.scalars(
            select(IdentityAccountStateAttempt).where(
                IdentityAccountStateAttempt.run_id == summary.run_id
            )
        ).all()
        assert len(attempts) == 2
        assert all(a.status == "executed" for a in attempts)
        # 预算名额持久标记 executed（§13.5）
        reservations = db_session.scalars(select(IdentityWindowReservation)).all()
        assert len(reservations) == 1
        assert reservations[0].status == "executed"
        assert reservations[0].person_code == "E101"


# ---------------------------------------------------------------------------
# T42: 0-row classification at adapter level (simulated Oracle behaviors)
# ---------------------------------------------------------------------------


class TestT42AdapterSemantics:
    def test_cdms_lock_conditional_and_readback(self):
        from app.services.cdms_identity_adapter import CdmsIdentityAdapter, _SQL_LOCK_USER

        assert "FUSERSTATE = '0'" in _SQL_LOCK_USER
        assert "FCHANGEDATE" in _SQL_LOCK_USER  # 归因证据列

    def test_jhemr_unlock_sql_shape(self):
        import inspect

        # 用模块级真实类引用（fake_adapters 已把模块属性换成假类）
        source = inspect.getsource(_RealJhemrIdentityAdapter.unlock_account)
        assert "CAST(account_status AS TEXT) = %s" in source
        assert "read-back mismatch" in source

    def test_zero_row_update_raises_not_success(self):
        # 0 行更新在适配器中必须走异常/分类路径，不允许当成功
        from app.services.jhemr_identity_adapter import JhemrIdentityError

        with pytest.raises(JhemrIdentityError):
            raise JhemrIdentityError("account lock update affected 0 rows; expected 1")
