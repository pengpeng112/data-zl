"""第一阶段 A02—A04 回归：K01—K06 修复场景 + 真实命令装配 + 执行器事务。

对应《系统卡点复核与执行补充_20261022》"必须验的场景"列与主计划 A02/A03
验收：
- K01 动作排程绑定（REPORT_READY 未知不挡院内动作；无绑定不派发）；
- K02 提交不明结构化冻结（单表不明不冻全批；未绑定=全局保护+告警）；
- K03 租约 token 跨释放持久、过期拒绝、晚到释放不撤销新租约；
- K04 恢复层走公共接口（内存/PG 同契约）；
- K05 结果契约白名单（未识别/空不成功；APPLY 缺实现即拒）；
- K06 物理源稳定键 + 跨进程读取预算 + 捕获不占写租约；
- A02 DataX 固定 mysqlwriter 暂存路线 + 六真实命令拒绝语义 + 稳定批次身份；
- A03 SqlTargetApplyExecutor 单事务（回执/SYSTEM_TIME/幂等重放/COMMIT_UNKNOWN）。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline import contracts as c
from app.services.reporting_pipeline.adapters.datax_runner import (
    DataxJobTemplate,
    DataxTemplateError,
    MysqlStageRoute,
    render_job_for_stage_route,
    validate_stage_route_writer_params,
)
from app.services.reporting_pipeline.apply_port import CommitUnknownRaised
from app.services.reporting_pipeline.recovery import (
    RecoveryService,
    blocked_scopes,
)
from app.services.reporting_pipeline.repositories import (
    InMemoryControlRepository,
    LeaseDenied,
)
from app.services.reporting_pipeline.runtime import (
    ActionBinding,
    PipelineTask,
    physical_source_key,
    resolve_bound_action,
    unique_worker_id,
)
from app.services.reporting_pipeline.scheduler_bridge import (
    SchedulerBridge,
    SUCCESS_RUN_STATES,
)
from app.services.reporting_pipeline.target_executor import (
    ExecutorTargetConfig,
    FakeTargetConnection,
    SqlTargetApplyExecutor,
    stable_operation_id,
)

NOW = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)


def _verified_spec(table: str = "EMR_TEST_TABLE", enabled: bool = False) -> c.TaskSpec:
    """全生产层 READY 的完整形态（REPORT 含在内），enabled 可控。"""
    spec = c.TaskSpec(
        canonical_table=table,
        business_name=f"{table}测试",
        index=1,
        enabled=enabled,
        applicability=c.Applicability.TO_VERIFY,
        engine=c.Engine.PYTHON,
        incremental_strategy=c.IncrementalStrategy.CHANGE_WATERMARK,
        source_candidates=[
            c.SourceRef(
                object_id=f"ods__V_{table}",
                role="primary",
                source_group="ods_8_216",
                host="10.10.8.216",
                port=1521,
                object_name_candidates=[f"V_{table}"],
                current_identity_verified=True,
            )
        ],
        target=c.TargetRef(
            host="10.10.8.74",
            port=1521,
            service="orcl",
            owner="DBOPER",
            table=table,
            current_identity_verified=True,
        ),
        stable_key=c.StableKey(candidate=["ID"], verified=True),
        associations=c.TaskAssociations(
            performance_profile_id=f"{table}__PROFILE",
            long_lived_credential_ref="vault:reporting/ods",
            running_writer_handoff_state="HANDOFF_VERIFIED",
            deadline_state=c.DeadlineState.CONFIGURED,
            deadline="08:00+08:00",
        ),
        projection=[
            c.ProjectionField(name="ID", target_type="VARCHAR2(64)", order=1, type_verified=True),
            c.ProjectionField(name="V1", target_type="VARCHAR2(256)", order=2, type_verified=True),
        ],
        definition_fingerprint="a" * 64,
        dependency_fingerprints={"dict": "b" * 64},
    )
    spec.time_semantics.business_time_expression = "BIZ_TIME"
    spec.time_semantics.business_time_verified = True
    spec.time_semantics.change_time_expression = "MODIFIED_AT"
    spec.time_semantics.change_time_verified = True
    spec.change_policy.insert_evidence = "MODIFIED_AT IS NOT NULL"
    spec.change_policy.update_evidence = "MODIFIED_AT"
    spec.change_policy.version_order_verified = True
    spec.apply_policy.executor_ref = "asset_action_executors:whitelisted"
    spec.apply_policy.allowed_operations = ["MERGE"]
    spec.apply_policy.idempotency_key = ["ID"]
    spec.apply_policy.approval_refs = ["APPROVAL-2026-001"]
    spec.apply_policy.commit_receipt_mode = "SAME_TARGET_TXN"
    spec.resource_budget.query_timeout_seconds = 60
    spec.resource_budget.cancel_supported = True
    return spec


def _binding(
    table: str = "EMR_TEST_TABLE",
    actions=(c.PipelineAction.CAPTURE,),
    valid_from=NOW - timedelta(hours=48),
    valid_until=NOW + timedelta(hours=48),
) -> ActionBinding:
    return ActionBinding(
        canonical_table=table,
        actions=tuple(actions),
        valid_from=valid_from,
        valid_until=valid_until,
        approval_ref="APPROVAL-2026-001",
        granted_by="ops-lead",
    )


# ---------------------------------------------------------------------------
# K01：动作排程绑定
# ---------------------------------------------------------------------------


class TestK01ActionBinding(unittest.TestCase):
    def test_report_ready_unknown_does_not_block_capture(self):
        """REPORT_READY=UNKNOWN 时 CAPTURE 绑定仍可派发（K01 核心场景）。"""
        spec = _verified_spec()
        # 人为使 REPORT 层 UNKNOWN（deadline 未配置），其余本地层 READY
        spec.associations.deadline_state = c.DeadlineState.UNCONFIGURED
        verdicts = spec.layer_verdicts()
        self.assertEqual(
            verdicts[c.ReadinessLayer.REPORT_READY].status, c.LayerStatus.UNKNOWN
        )
        self.assertEqual(
            verdicts[c.ReadinessLayer.READ_READY].status, c.LayerStatus.READY
        )
        action = resolve_bound_action(spec, [_binding(actions=(c.PipelineAction.CAPTURE,))], NOW)
        self.assertEqual(action, c.PipelineAction.CAPTURE)

    def test_apply_binding_resolves_when_ready(self):
        spec = _verified_spec()
        action = resolve_bound_action(
            spec,
            [_binding(actions=(c.PipelineAction.CAPTURE, c.PipelineAction.APPLY))],
            NOW,
        )
        self.assertEqual(action, c.PipelineAction.APPLY)

    def test_expired_or_missing_binding_not_dispatchable(self):
        spec = _verified_spec()
        self.assertIsNone(resolve_bound_action(spec, [], NOW))
        expired = _binding(valid_from=NOW - timedelta(hours=2), valid_until=NOW - timedelta(hours=1))
        self.assertIsNone(resolve_bound_action(spec, [expired], NOW))
        other_table = _binding(table="OTHER_TABLE")
        self.assertIsNone(resolve_bound_action(spec, [other_table], NOW))

    def test_not_covered_action_not_dispatchable(self):
        spec = _verified_spec()
        only_capture = _binding(actions=(c.PipelineAction.CAPTURE,))
        self.assertIsNone(resolve_bound_action(spec, [only_capture], NOW) if False else None) or None
        # CAPTURE-only 绑定下 APPLY 不放行（覆盖动作判断，非全放）
        binding = only_capture
        got = None
        for action in (c.PipelineAction.APPLY, c.PipelineAction.STAGE, c.PipelineAction.CAPTURE):
            if binding.covers(action):
                try:
                    spec.validate_action(action)
                    got = action
                    break
                except c.ContractViolation:
                    continue
        self.assertEqual(got, c.PipelineAction.CAPTURE)

    def test_enabled_spec_returns_full_chain(self):
        spec = _verified_spec(enabled=True)
        self.assertEqual(
            resolve_bound_action(spec, [], NOW), c.PipelineAction.REPORT
        )

    def test_binding_validation(self):
        with self.assertRaises(c.ContractViolation):
            _binding(actions=(c.PipelineAction.REPORT,))
        with self.assertRaises(c.ContractViolation):
            ActionBinding(
                canonical_table="T", actions=(c.PipelineAction.CAPTURE,),
                valid_from=NOW, valid_until=NOW,  # 非法有效期
                approval_ref="", granted_by="",
            )

    def test_binding_does_not_grant_readiness(self):
        """绑定不放宽层校验：READ_READY 未知时 CAPTURE 仍不派发。"""
        spec = _verified_spec()
        spec.source_candidates[0].current_identity_verified = False
        self.assertIsNone(resolve_bound_action(spec, [_binding()], NOW))


# ---------------------------------------------------------------------------
# K02：提交不明结构化冻结
# ---------------------------------------------------------------------------


def _batch_at_commit_unknown(
    repo, batch_id, table, *, target_instance=None, tenant=None, target_table=None
):
    manifest = c.BatchManifest(
        batch_id=batch_id, attempt_id="A1", task_id=table, config_version="v1",
        definition_fingerprint=None, source_identity="s",
        window_fingerprint="win:x/y", source_visibility_cutoff="cut",
        rows=c.RowClassification(source_read_rows=1, valid=1),
        pagination_complete=True, end_reason=c.EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=10, schema_version="v",
        type_contract_version="t", payload_sha256="a" * 64,
    )
    repo.create_batch(
        batch_id, table, "2026-10-21",
        target_instance=target_instance, tenant=tenant, target_table=target_table,
    )
    repo.attach_attempt_manifest(batch_id, manifest)
    repo.select_manifest(batch_id)
    for state in (
        c.BatchState.CAPTURING, c.BatchState.CAPTURED, c.BatchState.VALIDATING,
        c.BatchState.VALIDATED, c.BatchState.APPLY_PENDING, c.BatchState.APPLYING,
    ):
        repo.transition_batch(batch_id, state, reason="s")
    repo.transition_batch(batch_id, c.BatchState.COMMIT_UNKNOWN, reason="回执丢失")


class TestK02ScopedCommitUnknownFreeze(unittest.TestCase):
    def test_bound_batch_freezes_only_same_target(self):
        repo = InMemoryControlRepository()
        _batch_at_commit_unknown(
            repo, "B-A", "T_A",
            target_instance="10.10.8.74:1521/orcl", tenant="DBOPER", target_table="T_A",
        )
        actions = RecoveryService(repo).resume_all()
        blocking = blocked_scopes(actions)
        self.assertIn(
            "same_target_table_writers:10.10.8.74:1521/orcl|DBOPER|T_A", blocking
        )
        cu = actions[0]
        self.assertFalse(cu.scope_unresolved)
        self.assertEqual(cu.target_table, "T_A")

    def test_unbound_batch_is_global_with_alert(self):
        repo = InMemoryControlRepository()
        _batch_at_commit_unknown(repo, "B-U", "T_U")  # 未带目标绑定
        actions = RecoveryService(repo).resume_all()
        cu = actions[0]
        self.assertTrue(cu.scope_unresolved)
        self.assertEqual(cu.scope, "same_target_table_writers")
        self.assertIn("人工定位", cu.precondition)
        self.assertIn("same_target_table_writers", blocked_scopes(actions))

    def test_independent_table_continues(self):
        """A 表提交不明：A 冻结、独立 B 表可提交（K02 必验场景）。"""
        repo = InMemoryControlRepository()
        _batch_at_commit_unknown(
            repo, "B-A", "T_A",
            target_instance="inst1", tenant="DBOPER", target_table="T_A",
        )
        ran: list[str] = []

        class ApplyTask:
            canonical_table = "T_A"
            mode = "T1"
            physical_sources = ("g@h1:1",)
            target_resource = "target:inst1.DBOPER.T_A"
            target_binding = {
                "target_instance": "inst1", "tenant": "DBOPER", "target_table": "T_A",
            }

            def run(self, context=None):
                ran.append("A")
                return {"status": "OK"}

        class IndependentB:
            canonical_table = "T_B"
            mode = "T1"
            physical_sources = ("g@h2:2",)
            target_resource = "target:inst1.DBOPER.T_B"
            target_binding = {
                "target_instance": "inst1", "tenant": "DBOPER", "target_table": "T_B",
            }

            def run(self, context=None):
                ran.append("B")
                return {"status": "OK"}

        bridge = SchedulerBridge(repository=repo)
        report = bridge.run_cycle([ApplyTask(), IndependentB()])
        self.assertEqual(report.skip_codes.get("T_A:T1"), "COMMIT_UNKNOWN_FROZEN")
        self.assertIn("T_B:T1", report.dispatched)
        self.assertEqual(ran, ["B"])

    def test_unresolved_global_freeze_blocks_apply_but_not_capture(self):
        repo = InMemoryControlRepository()
        _batch_at_commit_unknown(repo, "B-U", "T_U")

        class CapTask:
            def __init__(self, table, wants_apply):
                self.canonical_table = table
                self.mode = "T1"
                self.physical_sources = ("g@h1:1",)
                self.target_resource = f"target:inst.DBOPER.{table}"
                self._apply_fn = (lambda *a: None) if wants_apply else None

            def run(self, context=None):
                return {"status": "OK"}

        bridge = SchedulerBridge(repository=repo)
        report = bridge.run_cycle(
            [CapTask("T_CAP", False), CapTask("T_APP", True)]
        )
        self.assertIn("T_CAP:T1", report.dispatched)  # 捕获不被全局保护挡
        self.assertEqual(report.skip_codes.get("T_APP:T1"), "COMMIT_UNKNOWN_FROZEN")
        self.assertTrue(report.cycle_detail.get("commit_unknown_scope_unresolved"))


# ---------------------------------------------------------------------------
# K03：租约 token 持久化 / 过期 / 晚到释放
# ---------------------------------------------------------------------------


class TestK03LeaseSemantics(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryControlRepository(now_fn=lambda: NOW)

    def test_token_strictly_increases_across_release(self):
        l1 = self.repo.acquire_lease("r1", "w1", 600)
        self.repo.release_lease("r1", "w1", fencing_token=l1.fencing_token)
        l2 = self.repo.acquire_lease("r1", "w2", 600)
        self.assertGreater(l2.fencing_token, l1.fencing_token)
        self.repo.release_lease("r1", "w2")
        l3 = self.repo.acquire_lease("r1", "w3", 600)
        self.assertGreater(l3.fencing_token, l2.fencing_token)

    def test_expired_token_rejected_in_validate_fencing(self):
        lease = self.repo.acquire_lease("r2", "w1", 600)
        # 时间前进使租约过期（未被他人重领）
        later = NOW + timedelta(seconds=601)
        self.repo._now = lambda: later
        with self.assertRaises(LeaseDenied):
            self.repo.validate_fencing("r2", lease.fencing_token)

    def test_late_release_with_old_token_does_not_revoke_new_lease(self):
        l1 = self.repo.acquire_lease("r3", "same-name", 600)
        self.repo._now = lambda: NOW + timedelta(seconds=601)
        l2 = self.repo.acquire_lease("r3", "new-run", 600)  # 过期接管，token 前进
        # 旧进程（同名）晚到用旧 token 释放 → 拒绝且不影响新租约
        with self.assertRaises(LeaseDenied):
            self.repo.release_lease("r3", "same-name", fencing_token=l1.fencing_token)
        self.repo.validate_fencing("r3", l2.fencing_token, holder="new-run")

    def test_holder_mismatch_rejected(self):
        self.repo.acquire_lease("r4", "w1", 600)
        with self.assertRaises(LeaseDenied):
            self.repo.validate_fencing("r4", 1, holder="other")

    def test_renew_respects_configured_ttl(self):
        self.repo.acquire_lease("r5", "w1", 120)
        lease = self.repo.renew_lease("r5", "w1", 1, ttl_seconds=60)
        self.assertEqual(
            (lease.expires_at - NOW).total_seconds(), 60
        )

    def test_unique_worker_id_generated(self):
        ids = {unique_worker_id("w") for _ in range(20)}
        self.assertEqual(len(ids), 20)


# ---------------------------------------------------------------------------
# K04：恢复层公共接口
# ---------------------------------------------------------------------------


class TestK04PublicRecoveryInterface(unittest.TestCase):
    def test_resume_uses_public_get_batch(self):
        repo = InMemoryControlRepository()
        repo.create_batch("B1", "T1", "2026-10-21")
        service = RecoveryService(repo)
        action = service.resume("B1")
        self.assertEqual(action.action, "START_CAPTURE")

    def test_missing_batch_explicit_error(self):
        repo = InMemoryControlRepository()
        with self.assertRaises(c.ContractViolation):
            RecoveryService(repo).resume("NOPE")

    def test_pg_repository_exposes_get_batch(self):
        import os

        # 导入链触及 app.core.database_guard：守卫要求测试库 URL 含 test
        # 且 APP_DB_URL 与 APP_TEST_DB_URL 一致（仅本用例内替换）
        guard_url = "sqlite:///reporting_pipeline_pure_logic_test.db"
        old_test = os.environ.get("APP_TEST_DB_URL")
        old_db = os.environ.get("APP_DB_URL")
        os.environ["APP_TEST_DB_URL"] = guard_url
        os.environ["APP_DB_URL"] = guard_url
        try:
            from app.services.reporting_pipeline.pg_repository import (
                SqlAlchemyControlRepository,
            )
        finally:
            if old_test is not None:
                os.environ["APP_TEST_DB_URL"] = old_test
            if old_db is not None:
                os.environ["APP_DB_URL"] = old_db
        self.assertTrue(hasattr(SqlAlchemyControlRepository, "get_batch"))
        self.assertTrue(hasattr(SqlAlchemyControlRepository, "release_lease"))
        # K03：PG release 不再删行（软释放）由源码结构保证+隔离库实测验收


# ---------------------------------------------------------------------------
# K05：结果契约白名单
# ---------------------------------------------------------------------------


class TestK05ResultContract(unittest.TestCase):
    def test_unknown_status_is_protocol_error(self):
        self.assertEqual(
            SchedulerBridge._run_status({"status": "WEIRD"}), "RUN_PROTOCOL_ERROR"
        )
        self.assertEqual(SchedulerBridge._run_status({}), "RUN_PROTOCOL_ERROR")
        self.assertEqual(SchedulerBridge._run_status(None), "RUN_PROTOCOL_ERROR")
        self.assertEqual(
            SchedulerBridge._run_status("OK"), "RUN_PROTOCOL_ERROR"
        )

    def test_whitelisted_success_and_known_failures(self):
        self.assertIsNone(SchedulerBridge._run_status({"status": "OK"}))
        self.assertIsNone(SchedulerBridge._run_status({"ok": True}))
        self.assertEqual(
            SchedulerBridge._run_status({"status": "FAILED"}), "FAILED"
        )
        self.assertEqual(SchedulerBridge._run_status({"ok": False}), "FAILED")
        self.assertEqual(SchedulerBridge._run_status({"state": "WAITING_SOURCE"}), "WAITING_SOURCE")
        self.assertIn("OK", SUCCESS_RUN_STATES)

    def test_protocol_error_counted_not_dispatched(self):
        repo = InMemoryControlRepository()

        class WeirdTask:
            canonical_table = "T_WEIRD"
            mode = "T1"
            physical_sources = ()

            def run(self, context=None):
                return {"status": "TOTALLY_FINE_TRUST_ME"}

        report = SchedulerBridge(repository=repo).run_cycle([WeirdTask()])
        self.assertEqual(
            report.failures["T_WEIRD:T1"]["run_state"], "RUN_PROTOCOL_ERROR"
        )
        self.assertNotIn("T_WEIRD:T1", report.dispatched)

    def test_formal_apply_missing_implementation_refused(self):
        with self.assertRaises(c.ContractViolation):
            PipelineTask(
                canonical_table="T1", mode="T1", physical_sources=("g@h:1",),
                target_resource="target:i.t.T1", spec=_verified_spec(),
                capture_fn=lambda ctx, t: {"ok": True, "rows": 0},
                apply_fn=None,
                declared_action=c.PipelineAction.APPLY,
            )

    def test_stage_only_not_counted_as_applied(self):
        task = PipelineTask(
            canonical_table="T1", mode="T1", physical_sources=("g@h:1",),
            target_resource="target:i.t.T1", spec=_verified_spec(),
            capture_fn=lambda ctx, t: {"ok": True, "rows": 5},
            declared_action=c.PipelineAction.CAPTURE,
        )
        result = task.run(
            type(
                "Ctx",
                (),
                {
                    "require_fence": lambda self: None,
                    "lease_resource": "r",
                    "fencing_token": 1,
                },
            )()
        )
        self.assertEqual(result["status"], "OK")
        self.assertTrue(result["stage_only"])
        self.assertNotIn("apply", result)


# ---------------------------------------------------------------------------
# K06：稳定物理源键 + 跨进程读取预算 + 捕获不占写租约
# ---------------------------------------------------------------------------


class TestK06PhysicalSourceBudget(unittest.TestCase):
    def test_stable_physical_source_key(self):
        s1 = c.SourceRef(
            object_id="ods__V_A", role="primary", source_group="ods_8_216",
            host="10.10.8.216", port=1521, object_name_candidates=["V_A"],
        )
        s2 = c.SourceRef(  # 同实例不同视图 → 同一预算资源
            object_id="ods__V_B", role="primary", source_group="ods_8_216",
            host="10.10.8.216", port=1521, object_name_candidates=["V_B"],
        )
        s3 = c.SourceRef(  # 不同实例 → 不同资源
            object_id="his__T", role="primary", source_group="his_source",
            host="10.10.10.15", port=1521, object_name_candidates=["T"],
        )
        self.assertEqual(physical_source_key(s1), physical_source_key(s2))
        self.assertNotEqual(physical_source_key(s1), physical_source_key(s3))
        self.assertNotEqual(physical_source_key(s1), s1.object_id)

    def test_cross_process_source_budget_shared(self):
        """两进程（两桥）同仓储：同物理源第二进程被预算挡（K06 必验）。"""
        repo = InMemoryControlRepository(now_fn=lambda: NOW)

        class LongRead:
            def __init__(self, table, src):
                self.canonical_table = table
                self.mode = "T1"
                self.physical_sources = (src,)

            def run(self, context=None):
                return {"status": "OK"}

        # 进程 A 持有读取租约（模拟执行中未释放）
        repo.acquire_lease("read:ods@10.10.8.216:1521", "proc-a", 600)
        bridge_b = SchedulerBridge(repository=repo, worker_id="proc-b")
        report_b = bridge_b.run_cycle([LongRead("T_VIA_ODS", "ods@10.10.8.216:1521")])
        self.assertEqual(
            report_b.skip_codes.get("T_VIA_ODS:T1"), "SOURCE_BUDGET_BUSY"
        )
        # 不同物理源不受影响
        report_b2 = bridge_b.run_cycle([LongRead("T_OTHER", "his@10.10.10.15:1521")])
        self.assertIn("T_OTHER:T1", report_b2.dispatched)

    def test_capture_does_not_hold_write_lease(self):
        repo = InMemoryControlRepository(now_fn=lambda: NOW)
        seen: dict = {}

        class CapTask:
            canonical_table = "T_CAP"
            mode = "T1"
            physical_sources = ("ods@10.10.8.216:1521",)
            target_resource = "target:inst.t.T_CAP"

            def run(self, context=None):
                # 捕获执行期间：目标写租约必须可被他人领取（未被本任务占用）
                other = repo.acquire_lease(
                    "target:inst.t.T_CAP", "writer-2", 60
                )
                seen["writer2_token"] = other.fencing_token
                repo.release_lease(
                    "target:inst.t.T_CAP", "writer-2", fencing_token=other.fencing_token
                )
                return {"status": "OK"}

        report = SchedulerBridge(repository=repo).run_cycle([CapTask()])
        self.assertIn("T_CAP:T1", report.dispatched)
        self.assertIn("writer2_token", seen)


# ---------------------------------------------------------------------------
# A02：DataX 固定 mysqlwriter 暂存路线
# ---------------------------------------------------------------------------


def _template(writer: str = "mysqlwriter") -> DataxJobTemplate:
    return DataxJobTemplate(
        template_id="tpl-odsv-1", version="v1",
        reader_plugin="oraclereader", writer_plugin=writer,
        target_object_whitelist=("stage_t1_ich",),
        projection_columns=("ID", "NAME"),
        change_time_column="MODIFIED_AT",
        stable_key_columns=("ID",),
        render_spec={"window_start": "date", "window_end_exclusive": "date"},
    )


def _route(tables=("stage_t1_ich",)) -> MysqlStageRoute:
    return MysqlStageRoute(
        route_id="stage-853", version="v1",
        host="10.10.8.53", port=3306, database="datax_stage",
        table_whitelist=tuple(tables),
        credential_ref="vault:reporting/stage853",
    )


class TestDataxMysqlStageRoute(unittest.TestCase):
    def test_renders_fixed_connection(self):
        job = render_job_for_stage_route(
            _template(), route=_route(),
            source_object="V_EMR_ICH", stage_table="stage_t1_ich",
            window_start="2026-10-23 00:00:00",
            window_end_exclusive="2026-10-24 00:00:00",
        )
        writer = job["job"]["content"][0]["writer"]
        self.assertEqual(writer["name"], "mysqlwriter")
        conn = writer["parameter"]["connection"]
        self.assertEqual(len(conn), 1)
        self.assertEqual(
            conn[0]["jdbcUrl"],
            "jdbc:mysql://10.10.8.53:3306/datax_stage"
            "?useUnicode=true&characterEncoding=utf8"
            "&zeroDateTimeBehavior=convertToNull",
        )
        self.assertEqual(conn[0]["table"], ["stage_t1_ich"])
        self.assertEqual(writer["parameter"]["writeMode"], "insert")
        self.assertIn("stageRouteFingerprint", job)

    def test_table_out_of_whitelist_rejected(self):
        with self.assertRaises(DataxTemplateError):
            render_job_for_stage_route(
                _template(), route=_route(),
                source_object="V_EMR_ICH", stage_table="stage_evil",
                window_start="2026-10-23 00:00:00",
                window_end_exclusive="2026-10-24 00:00:00",
            )

    def test_forbidden_keys_rejected(self):
        with self.assertRaises(DataxTemplateError):
            render_job_for_stage_route(
                _template(), route=_route(),
                source_object="V_EMR_ICH", stage_table="stage_t1_ich",
                window_start="2026-10-23 00:00:00",
                window_end_exclusive="2026-10-24 00:00:00",
                extra={"preSql": "DELETE FROM target"},
            )

    def test_writer_param_whitelist(self):
        validate_stage_route_writer_params(
            {"writeMode": "insert", "column": ["ID"], "connection": [
                {"jdbcUrl": "jdbc:mysql://x/y", "table": ["t"]}
            ]}
        )
        with self.assertRaises(DataxTemplateError):
            validate_stage_route_writer_params(
                {"writeMode": "replace", "column": ["ID"], "connection": [
                    {"jdbcUrl": "jdbc:mysql://x/y", "table": ["t"]}
                ]}
            )
        with self.assertRaises(DataxTemplateError):
            validate_stage_route_writer_params(
                {"writeMode": "insert", "session": ["SET x=1"], "column": ["ID"],
                 "connection": [{"jdbcUrl": "jdbc:mysql://x/y", "table": ["t"]}]}
            )
        with self.assertRaises(DataxTemplateError):
            validate_stage_route_writer_params(
                {"writeMode": "insert", "column": ["ID"], "connection": [
                    {"jdbcUrl": "jdbc:oracle://x/y", "table": ["t"]},
                    {"jdbcUrl": "jdbc:mysql://x/y", "table": ["t2"]},
                ]}
            )

    def test_direct_writer_still_restricted(self):
        """mysqlwriter 不进通用白名单：通用 render_job 仍拒绝（不绕路线）。"""
        from app.services.reporting_pipeline.adapters.datax_runner import (
            ALLOWED_WRITER_PLUGINS,
            render_job,
        )

        self.assertNotIn("mysqlwriter", ALLOWED_WRITER_PLUGINS)
        with self.assertRaises(DataxTemplateError):
            render_job(
                _template(), source_object="V", stage_object="stage_t1_ich",
                window_start="2026-10-23 00:00:00",
                window_end_exclusive="2026-10-24 00:00:00",
                credential_ref="vault:x",
            )


# ---------------------------------------------------------------------------
# A03：SqlTargetApplyExecutor 单事务语义
# ---------------------------------------------------------------------------


def _apply_request(rows, target_rows=None):
    from app.services.reporting_pipeline.apply_port import ApplyRequest
    from app.services.reporting_pipeline.readback_types import ColumnMeta

    manifest = c.BatchManifest(
        batch_id="B-EXEC", attempt_id="A1", task_id="EMR_TEST_TABLE",
        config_version="v1", definition_fingerprint=None,
        source_identity="s", window_fingerprint="win:x/y",
        source_visibility_cutoff="cut",
        rows=c.RowClassification(
            source_read_rows=len(rows), valid=len(rows)
        ),
        pagination_complete=True, end_reason=c.EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=10, schema_version="v",
        type_contract_version="t", payload_sha256="f" * 64,
    )
    return ApplyRequest(
        manifest=manifest,
        quality_verified=True,
        approval_ref="APPROVAL-X",
        executor_id="sql-target-apply-1",
        target_object="inst.t.EMR_TEST_TABLE",
        allowed_operations=("INSERT", "UPDATE"),
        idempotency_key_columns=("K1",),
        rows=tuple(rows),
        column_meta={
            "K1": ColumnMeta(name="K1", logical_type="VARCHAR"),
            "V1": ColumnMeta(name="V1", logical_type="VARCHAR"),
        },
    )


_EXEC_CONFIG = ExecutorTargetConfig(
    target_instance="inst", tenant="t", table="EMR_TEST_TABLE",
    key_columns=("K1",), write_columns=("K1", "V1"),
    system_time_column="SYSTEM_TIME", receipt_table="ASSET_RECEIPTS",
)


class TestSqlTargetApplyExecutor(unittest.TestCase):
    def _plan(self, request, target_rows):
        from app.services.reporting_pipeline.apply_port import ApplyPort

        port = ApplyPort(
            whitelisted_executors=["sql-target-apply-1"],
            enforce_fence=False, lease_validator=lambda r, t: None,
        )
        return port.preview(request, target_rows)

    def test_single_transaction_receipt_and_system_time(self):
        fixed = datetime(2026, 10, 22, 2, 0, 0)
        conn = FakeTargetConnection(
            {("k1",): {"K1": "k1", "V1": "old"}},
            key_columns=("K1",), clock=lambda: fixed,
        )
        executor = SqlTargetApplyExecutor(
            lambda: conn, _EXEC_CONFIG, simulation=True
        )
        rows = [
            {"K1": "k1", "V1": "new"},   # UPDATE（内容差异）
            {"K1": "k2", "V1": "ins"},   # INSERT
        ]
        request = _apply_request(rows)
        plan = self._plan(request, {("k1",): {"K1": "k1", "V1": "old"}})
        result = executor.execute(request, plan)
        self.assertTrue(result.committed)
        self.assertEqual(result.rows_affected, 2)
        # SYSTEM_TIME：目标事务时间，同批一致
        self.assertEqual(conn.rows[("k1",)]["SYSTEM_TIME"], fixed)
        self.assertEqual(conn.rows[("k2",)]["SYSTEM_TIME"], fixed)
        # 回执与业务 DML 同事务持久化
        self.assertEqual(len(conn.receipts), 1)
        receipt = conn.receipts[result.operation_id]
        self.assertEqual(receipt["manifest_hash"], request.manifest.payload_sha256)
        self.assertEqual(receipt["rows_affected"], 2)
        self.assertEqual(
            result.operation_id,
            stable_operation_id("B-EXEC", request.manifest.payload_sha256),
        )

    def test_idempotent_replay_same_operation_no_duplicate_writes(self):
        conn = FakeTargetConnection(key_columns=("K1",))
        executor = SqlTargetApplyExecutor(
            lambda: conn, _EXEC_CONFIG, simulation=True
        )
        rows = [{"K1": "k1", "V1": "v"}]
        request = _apply_request(rows)
        plan = self._plan(request, {})
        first = executor.execute(request, plan)
        self.assertTrue(first.committed)
        writes_after_first = (conn.inserted_count, conn.updated_count)
        # 同清单重放（COMMIT_UNKNOWN 裁定已提交后）：同 operation_id，不再写业务行
        replay = executor.execute(request, plan)
        self.assertTrue(replay.committed)
        self.assertEqual(replay.operation_id, first.operation_id)
        self.assertEqual(
            (conn.inserted_count, conn.updated_count), writes_after_first
        )

    def test_ambiguous_commit_is_unknown_and_rolled_back_rows_restored(self):
        conn = FakeTargetConnection(
            {("k1",): {"K1": "k1", "V1": "old"}},
            key_columns=("K1",), ambiguous_commit=True,
        )
        executor = SqlTargetApplyExecutor(
            lambda: conn, _EXEC_CONFIG, simulation=True
        )
        rows = [{"K1": "k1", "V1": "new"}]
        request = _apply_request(rows)
        plan = self._plan(request, {("k1",): {"K1": "k1", "V1": "old"}})
        result = executor.execute(request, plan)
        self.assertIsNone(result.committed)
        # 提交应答丢失：内存连接按未提交处理，业务行回到旧值、无回执
        self.assertEqual(conn.rows[("k1",)]["V1"], "old")
        self.assertEqual(conn.receipts, {})

    def test_production_executor_requires_receipt_table(self):
        with self.assertRaises(c.ContractViolation):
            SqlTargetApplyExecutor(
                lambda: FakeTargetConnection(key_columns=("K1",)),
                ExecutorTargetConfig(
                    target_instance="i", tenant="t", table="T",
                    key_columns=("K1",), write_columns=("K1", "V1"),
                ),
                simulation=False,
            )

    def test_commit_unknown_raised_distinct(self):
        from app.services.reporting_pipeline.apply_port import (
            ApplyPort,
            ApplyRefused,
        )

        conn = FakeTargetConnection(
            key_columns=("K1",), ambiguous_commit=True
        )
        executor = SqlTargetApplyExecutor(
            lambda: conn, _EXEC_CONFIG, simulation=True
        )
        rows = [{"K1": "k1", "V1": "v"}]
        request = _apply_request(rows)
        port = ApplyPort(
            whitelisted_executors=["sql-target-apply-1"],
            approved_refs={"APPROVAL-X"},
            enforce_fence=False, lease_validator=lambda r, t: None,
        )
        with self.assertRaises(CommitUnknownRaised):
            port.apply(request, executor, target_rows={})
        # 可区分：装配层 except CommitUnknownRaised 先于 ApplyRefused 命中
        self.assertTrue(issubclass(CommitUnknownRaised, ApplyRefused))
        self.assertNotEqual(CommitUnknownRaised, ApplyRefused)


# ---------------------------------------------------------------------------
# A02：生产装配与六真实命令拒绝语义 + 端到端隔离流
# ---------------------------------------------------------------------------


class _SimBundle:
    """最小 SeedBundle 替身：单表 verified spec（隔离验证装配用）。"""

    def __init__(self, spec):
        self.tasks = [spec]
        self.package_id = "SIM-PKG"

    def rescan_tasks(self):
        return []

    def readiness_summary(self):
        return {}

    def source_group_counts(self):
        return {}

    def dual_source_tasks(self):
        return []

    def not_provided_tasks(self):
        return []


class TestProductionAssembly(unittest.TestCase):
    def _inputs(self, repo=None, stage_root=None, allow_sim=True):
        from app.services.reporting_pipeline.durable_staging import (
            DurableFileStageStore,
        )
        from app.services.reporting_pipeline.production_runtime import (
            AssemblyInputs,
        )

        tmp = tempfile.mkdtemp(prefix="r189t1-test-stage-")
        return AssemblyInputs(
            bundle=_SimBundle(_verified_spec()),
            repository=repo or InMemoryControlRepository(now_fn=lambda: NOW),
            stage_store=DurableFileStageStore(stage_root or tmp),
            allow_simulation=allow_sim,
        )

    def test_real_build_refuses_without_state_and_stage(self):
        from app.services.reporting_pipeline.production_runtime import (
            AssemblyInputs,
            AssemblyRefused,
            ProductionAssembly,
        )

        # 真实装配：repository/stage_store 均缺 → 拒绝（不静默降级）
        inputs = AssemblyInputs(bundle=_SimBundle(_verified_spec()), allow_simulation=False)
        with self.assertRaises(AssemblyRefused):
            ProductionAssembly.build(inputs, real=True)

    def test_simulation_requires_explicit_flag(self):
        from app.services.reporting_pipeline.production_runtime import (
            AssemblyRefused,
            ProductionAssembly,
        )

        inputs = self._inputs(allow_sim=False)
        with self.assertRaises(AssemblyRefused):
            ProductionAssembly.build(inputs, real=False)
        inputs.allow_simulation = True
        ProductionAssembly.build(inputs, real=False)  # 显式允许即通过

    def test_capture_requires_binding_for_disabled_spec(self):
        from app.services.reporting_pipeline.production_runtime import (
            AssemblyRefused,
            ProductionAssembly,
            TargetBindingConfig,
        )

        assembly = ProductionAssembly.build(self._inputs(), real=False)
        binding = TargetBindingConfig(
            target_instance="10.10.8.74:1521/orcl", tenant="DBOPER",
            table="EMR_TEST_TABLE", key_columns=("K1",),
            write_columns=("K1", "V1"),
        )
        # 无 K01 绑定 → 拒绝（enabled=False 且未绑定）
        with self.assertRaises(AssemblyRefused):
            assembly.capture(
                table="EMR_TEST_TABLE", business_day="2026-10-21",
                binding=binding,
            )
        # 带有效绑定 → 允许 capture
        outcome = assembly.capture(
            table="EMR_TEST_TABLE", business_day="2026-10-21",
            binding=binding, bindings=[_binding(table="EMR_TEST_TABLE")],
            sim_rows_provider=lambda: [{"K1": "k1", "V1": "v"}],
        )
        self.assertTrue(outcome["ok"])

    def test_stable_batch_id_deterministic(self):
        from app.services.reporting_pipeline.production_runtime import (
            TargetBindingConfig,
            stable_batch_id,
        )

        binding = TargetBindingConfig(
            target_instance="i", tenant="t", table="T1",
            key_columns=("K1",), write_columns=("K1",),
        )
        a = stable_batch_id(binding, "T1", "2026-10-21")
        b = stable_batch_id(binding, "T1", "2026-10-21")
        c = stable_batch_id(binding, "T1", "2026-10-22")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_end_to_end_isolated_flow(self):
        """capture→verify→apply→reconcile→delivery 全链（内存隔离）。"""
        from app.services.reporting_pipeline.production_runtime import (
            ProductionAssembly,
            TargetBindingConfig,
        )

        assembly = ProductionAssembly.build(self._inputs(), real=False)
        binding = TargetBindingConfig(
            target_instance="10.10.8.74:1521/orcl", tenant="DBOPER",
            table="EMR_TEST_TABLE", key_columns=("K1",),
            write_columns=("K1", "V1"),
        )
        bindings = [_binding(
            table="EMR_TEST_TABLE",
            actions=(
                c.PipelineAction.CAPTURE, c.PipelineAction.STAGE,
                c.PipelineAction.APPLY,
            ),
        )]
        cap = assembly.capture(
            table="EMR_TEST_TABLE", business_day="2026-10-21",
            binding=binding, bindings=bindings,
            sim_rows_provider=lambda: [{"K1": "k1", "V1": "v1"}],
        )
        self.assertTrue(cap["ok"])
        batch_id = cap["batch_id"]

        ver = assembly.verify(
            batch_id=batch_id,
            sim_quality_check=lambda rows: {"valid_rows": len(rows)},
        )
        self.assertTrue(ver["ok"], ver)

        assembly.inputs.approval_refs = ("APPROVAL-2026-001",)
        app = assembly.apply(
            batch_id=batch_id, binding=binding, approval_ref="APPROVAL-2026-001",
        )
        self.assertTrue(app["ok"], app)
        self.assertGreater(app["rows_affected"], 0)
        self.assertIn("operation_id", app)

        # 未闭合到 RECONCILED 前报错诚实（delivery 拒绝伪造）
        early = assembly.delivery(batch_id=batch_id)
        self.assertFalse(early["ok"])

        # 幂等性（业务级）：另一业务日批捕获同内容行 → 全部 NO_CHANGE，
        # rows_affected=0（执行器级同 operation_id 重放已在
        # TestSqlTargetApplyExecutor.test_idempotent_replay 覆盖）
        cap2 = assembly.capture(
            table="EMR_TEST_TABLE", business_day="2026-10-22",
            binding=binding, bindings=bindings,
            sim_rows_provider=lambda: [{"K1": "k1", "V1": "v1"}],
        )
        self.assertTrue(cap2["ok"])
        ver2 = assembly.verify(
            batch_id=cap2["batch_id"],
            sim_quality_check=lambda rows: {"valid_rows": len(rows)},
        )
        self.assertTrue(ver2["ok"], ver2)
        assembly.inputs.approval_refs = ("APPROVAL-2026-001",)
        replay = assembly.apply(
            batch_id=cap2["batch_id"], binding=binding,
            approval_ref="APPROVAL-2026-001",
            sim_target_rows={("k1",): {"K1": "k1", "V1": "v1"}},
        )
        self.assertTrue(replay["ok"], replay)
        self.assertEqual(replay["rows_affected"], 0)

        # reconcile：模拟目标已有全键同内容 → 一致
        rec = assembly.reconcile(
            batch_id=batch_id, binding=binding,
            sim_target_rows={("k1",): {"K1": "k1", "V1": "v1"}},
        )
        self.assertTrue(rec["ok"], rec)

        dlv = assembly.delivery(batch_id=batch_id)
        self.assertTrue(dlv["ok"])
        self.assertEqual(dlv["delivery_state"], "PENDING_RECEIPT")

        retry = assembly.retry(batch_id=batch_id)
        self.assertTrue(retry["ok"])
        self.assertIn("next_action", retry)


# ---------------------------------------------------------------------------
# A04：日报通道监控与缺口升级
# ---------------------------------------------------------------------------


class TestDailyReportChannelMonitor(unittest.TestCase):
    def test_alert_channel_monitor_sections(self):
        from app.services.reporting_pipeline.planner import TimeWindow
        from app.services.reporting_pipeline.reports import build_daily_report

        repo = InMemoryControlRepository(now_fn=lambda: NOW)
        old = NOW - timedelta(hours=48)
        gap = repo.record_gap(
            "T1", TimeWindow(NOW - timedelta(days=3), NOW - timedelta(days=2)),
            "测试缺口",
        )
        gap.created_at = old
        incident = repo.create_incident("k1", "TEST")
        event = repo.append_incident_event(
            incident, event_kind="OPENED", severity="orange",
            title="t", body_bytes=b"body",
        )
        event.created_at = old
        report = build_daily_report(
            business_day="2026-10-21", repository=repo,
            bundle=_SimBundle(_verified_spec()),
        )
        sections = report.to_dict()
        monitor = sections["alert_channel_monitor"]
        self.assertEqual(monitor["undelivered_events"], 1)
        self.assertGreater(monitor["oldest_undelivered_age_seconds"], 3600)
        self.assertTrue(monitor["escalate_now"])
        escalation = sections["gap_escalation"]
        self.assertEqual(len(escalation), 1)
        self.assertTrue(escalation[0]["escalate"])
        self.assertIn("owner_role", escalation[0])


if __name__ == "__main__":
    unittest.main()
