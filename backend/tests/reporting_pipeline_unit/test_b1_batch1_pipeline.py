# -*- coding: utf-8 -*-
"""批1-4/1-5/1-2c/1-6/1-3 单元测试：CAS 分区、恢复执行化、REPLACE_MONTH
执行器、生产 ApplyPort 组装、outbox 守护、DataX 路由。

纯逻辑（内存仓储/假执行器/假进程/假传输）；数据库集成见隔离 PG 目录。
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 纯逻辑模式（同 test_maintenance_ops 模式）：本文件导入 production_apply →
# pg_repository → app.models 链，需要满足 pytest 进程的测试库标记。
_pure_logic_db_url = "sqlite:///data_asset_test_pure_logic.db"
os.environ["APP_TEST_DB_URL"] = _pure_logic_db_url
os.environ["APP_DB_URL"] = _pure_logic_db_url

from app.services.reporting_pipeline.apply_policy import (
    ApplyPartition,
    build_parent_presence,
    record_partition_ledger,
    snapshot_diff_partition,
)
from app.services.reporting_pipeline.apply_port import ApplyRequest
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.readback_types import ColumnMeta
from app.services.reporting_pipeline.recovery import RecoveryExecutor
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.target_executor import (
    ExecutorTargetConfig,
    FakeTargetConnection,
    SqlTargetApplyExecutor,
)

META = {
    "ID": ColumnMeta("ID", "VARCHAR"),
    "V1": ColumnMeta("V1", "VARCHAR"),
}


def _manifest(batch_id: str = "B1") -> BatchManifest:
    return BatchManifest(
        batch_id=batch_id, attempt_id="A1", task_id="EMR_TEST", config_version="v1",
        definition_fingerprint=None, source_identity="s", window_fingerprint="w",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=1, valid=1),
        pagination_complete=True,
        end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=10, schema_version="v",
        type_contract_version="t", payload_sha256="a" * 64,
    )


def _request(rows, **overrides) -> ApplyRequest:
    base = dict(
        manifest=_manifest(),
        quality_verified=True,
        approval_ref="AP-1",
        executor_id="sql-target-apply-1",
        target_object="db_test.t1.EMR_TEST",
        allowed_operations=("INSERT", "UPDATE"),
        idempotency_key_columns=("ID",),
        rows=tuple(rows),
        column_meta=META,
        mode="MERGE",
    )
    base.update(overrides)
    return ApplyRequest(**base)


# ---------------------------------------------------------------------------
# 批1-4 SNAPSHOT_DIFF CAS 分区
# ---------------------------------------------------------------------------


class TestSnapshotDiffPartition(unittest.TestCase):
    def _partition(self, rows, target_rows, registered, parent=None):
        return snapshot_diff_partition(
            rows=rows,
            key_columns=("ID",),
            metas=list(META.values()),
            target_rows=target_rows,
            registered_version=registered,
            parent_present=parent,
            parent_key_column="PARENT_ID" if parent else None,
        )

    def test_insert_nochange_cas_pass_conflict(self):
        registered = {}  # key -> last applied source content hash

        def reg(key):
            return registered.get(key)

        # 先为 K_update/K_conflict 计算登记值：用分区自身的证据函数逻辑
        from app.services.reporting_pipeline.readback_types import content_fingerprint

        old_update = {"ID": "K_update", "V1": "old"}
        drifted = {"ID": "K_conflict", "V1": "someone_else_wrote"}
        registered[("K_update",)] = content_fingerprint(old_update, list(META.values()))
        registered[("K_conflict",)] = content_fingerprint(
            {"ID": "K_conflict", "V1": "ours_before"}, list(META.values())
        )
        rows = [
            {"ID": "K_new", "V1": "a"},
            {"ID": "K_same", "V1": "same"},
            {"ID": "K_update", "V1": "new"},
            {"ID": "K_conflict", "V1": "new2"},
        ]
        target_rows = {
            ("K_same",): {"ID": "K_same", "V1": "same"},
            ("K_update",): old_update,
            ("K_conflict",): drifted,
        }
        partition = self._partition(rows, target_rows, reg)
        self.assertEqual(partition.insert_keys, [("K_new",)])
        self.assertEqual(partition.no_change_keys, [("K_same",)])
        self.assertEqual(partition.update_keys, [("K_update",)])
        self.assertEqual(partition.conflict_keys, [("K_conflict",)])
        self.assertEqual(len(partition.ok_rows), 2)  # 合法组继续
        # 版本证据 = 源内容哈希（不是采集时间）
        self.assertNotEqual(
            partition.row_version_evidences[("K_update",)],
            partition.row_version_evidences[("K_new",)],
        )

    def test_target_row_never_written_by_pipeline_is_conflict(self):
        partition = self._partition(
            [{"ID": "K", "V1": "v"}],
            {("K",): {"ID": "K", "V1": "other_writer"}},
            lambda key: None,
        )
        self.assertEqual(partition.conflict_keys, [("K",)])
        self.assertEqual(partition.ok_rows, [])

    def test_missing_parent_blocks_only_those_keys(self):
        present = build_parent_presence(
            parent_rows={("P1",): {"ID": "P1"}},
            parent_key_columns=("ID",),
        )
        rows = [
            {"ID": "C1", "V1": "x", "PARENT_ID": "P1"},
            {"ID": "C2", "V1": "y", "PARENT_ID": "P_MISSING"},
        ]
        partition = self._partition(rows, {}, lambda key: None, parent=present)
        self.assertEqual(partition.missing_parent_keys, [("C2",)])
        self.assertEqual(partition.insert_keys, [("C1",)])

    def test_ledger_records_groups(self):
        repo = InMemoryControlRepository()
        repo.create_batch("B1", "EMR_TEST", "2026-10-22")
        partition = ApplyPartition()
        partition.conflict_keys = [("K1",)]
        partition.missing_parent_keys = [("K2",), ("K3",)]
        recorded = record_partition_ledger(
            repo, batch_id="B1", canonical_table="EMR_TEST", partition=partition,
        )
        self.assertEqual(len(recorded), 2)
        groups = repo.open_quarantine_groups("B1")
        self.assertEqual({g["group_key"] for g in groups}, {"cas-conflict", "missing-parent"})
        # 幂等：重复留账不炸
        record_partition_ledger(
            repo, batch_id="B1", canonical_table="EMR_TEST", partition=partition,
        )
        self.assertEqual(len(repo.open_quarantine_groups("B1")), 2)
        repo.resolve_quarantine_group("B1", "cas-conflict", evidence="人工处置")
        self.assertEqual(len(repo.open_quarantine_groups("B1")), 1)


# ---------------------------------------------------------------------------
# 批1-5 REPLACE_MONTH 执行器
# ---------------------------------------------------------------------------


class TestReplaceMonthExecutor(unittest.TestCase):
    EXEC_CONFIG = ExecutorTargetConfig(
        target_instance="db_test", tenant="t1", table="EMR_TEST",
        key_columns=("ID",), write_columns=("ID", "V1"),
        system_time_column=None, receipt_table=None,
    )

    def test_requires_scope_keys(self):
        executor = SqlTargetApplyExecutor(
            lambda: None, self.EXEC_CONFIG, simulation=True
        )
        with self.assertRaises(Exception) as ctx:
            executor.execute(_request([], mode="REPLACE_MONTH"), _plan([]))
        self.assertIn("REPLACE_MONTH", str(ctx.exception))

    def test_atomic_delete_and_insert_with_rowcount_fence(self):
        conn = FakeTargetConnection(
            {("OLD1",): {"ID": "OLD1", "V1": "a"}, ("KEEP_OUT",): {"ID": "KEEP_OUT", "V1": "z"}},
            key_columns=("ID",),
        )

        class _Factory:
            def __call__(self_inner):  # noqa: N805
                return conn

        executor = SqlTargetApplyExecutor(_Factory(), self.EXEC_CONFIG, simulation=True)
        rows = [{"ID": "NEW1", "V1": "x"}, {"ID": "OLD1", "V1": "updated"}]
        scope = [("NEW1",), ("OLD1",)]
        result = executor.execute(
            _request(rows, mode="REPLACE_MONTH", replace_scope_keys=tuple(scope)),
            _plan([(("NEW1",), "INSERT"), (("OLD1",), "UPDATE")]),
        )
        self.assertTrue(result.committed)
        self.assertIn(("KEEP_OUT",), conn.rows)  # 范围外的键不被误删（只删范围键）
        self.assertEqual(conn.rows[("OLD1",)]["V1"], "updated")
        self.assertIn(("NEW1",), conn.rows)

    def test_scope_missing_batch_keys_rejected(self):
        conn = FakeTargetConnection(key_columns=("ID",))

        class _Factory:
            def __call__(self_inner):  # noqa: N805
                return conn

        executor = SqlTargetApplyExecutor(_Factory(), self.EXEC_CONFIG, simulation=True)
        with self.assertRaises(Exception) as ctx:
            executor.execute(
                _request(
                    [{"ID": "OUTSIDE", "V1": "x"}],
                    mode="REPLACE_MONTH",
                    replace_scope_keys=(("OTHER",),),
                ),
                _plan([(("OUTSIDE",), "INSERT")]),
            )
        self.assertIn("REPLACE_MONTH", str(ctx.exception))
        self.assertEqual(conn.rows, {})  # 回滚后无残留


def _plan(actions):
    from app.services.reporting_pipeline.apply_port import ApplyPlan

    return ApplyPlan(actions=list(actions), counts={})


# ---------------------------------------------------------------------------
# 批1-5 恢复执行化
# ---------------------------------------------------------------------------


class TestRecoveryExecutor(unittest.TestCase):
    def _repo_with_gap(self):
        from app.services.reporting_pipeline.planner import TimeWindow

        repo = InMemoryControlRepository()
        repo.create_batch("B1", "EMR_TEST", "2026-10-22")
        window = TimeWindow(
            datetime(2026, 10, 22, tzinfo=timezone(timedelta(hours=8))),
            datetime(2026, 10, 23, tzinfo=timezone(timedelta(hours=8))),
        )
        repo.record_gap("EMR_TEST", window, "SCHEDULER_TASK_FAILED")
        return repo, window

    def test_close_success_closes_only_matching_gap_and_advances(self):
        repo, window = self._repo_with_gap()
        # 另一业务日的缺口：不应被关闭，且水位不得越过
        from app.services.reporting_pipeline.planner import TimeWindow

        other = TimeWindow(
            datetime(2026, 10, 20, tzinfo=timezone(timedelta(hours=8))),
            datetime(2026, 10, 21, tzinfo=timezone(timedelta(hours=8))),
        )
        repo.record_gap("EMR_TEST", other, "SCHEDULER_TASK_FAILED")
        executor = RecoveryExecutor(repo)
        result = executor.close_success(
            batch_id="B1", task_id="EMR_TEST", business_day="2026-10-22",
            window_fingerprint=window.fingerprint(), evidence="reconcile",
        )
        self.assertEqual(len(result["closed_gaps"]), 1)
        self.assertGreaterEqual(len(repo.open_gaps("EMR_TEST")), 1)  # 旧缺口仍在
        # 捕获水位被 10-20 缺口挡住 → blocked 如实记录
        self.assertTrue(result["blocked"])
        wm = repo.get_watermarks("EMR_TEST")
        self.assertIsNone(wm.continuous_through)  # 连续完成不推进

    def test_recovered_event_emitted_once(self):
        repo, window = self._repo_with_gap()
        runtime_style = repo.create_incident(
            incident_key="T1:2026-10-22:EMR_TEST", category="EXTRACT_FAILED"
        )

        repo.append_incident_event(
            runtime_style, event_kind="OPENED", severity="yellow",
            title="t", body_bytes=b"{}", metadata={},
        )
        executor = RecoveryExecutor(repo)
        first = executor.close_success(
            batch_id="B1", task_id="EMR_TEST", business_day="2026-10-22",
            window_fingerprint=window.fingerprint(), evidence="reconcile",
        )
        self.assertIsNotNone(first["recovered_incident"])
        # 幂等：再跑不重复发（incident 已 RECOVERED，返回 None 且不新增事件）
        second = executor.close_success(
            batch_id="B1", task_id="EMR_TEST", business_day="2026-10-22",
            window_fingerprint=window.fingerprint(), evidence="reconcile",
        )
        self.assertIsNone(second["recovered_incident"])
        recovered_events = [
            e for e in repo.pending_outbox() + repo.queued_outbox()
            if e.event_kind == "RECOVERED"
        ]
        self.assertEqual(len(recovered_events), 1)

    def test_retry_windows_queue_and_rescan_ledger(self):
        repo, window = self._repo_with_gap()
        repo.create_batch("B2", "OTHER", "2026-10-21")
        executor = RecoveryExecutor(repo)
        plan = executor.plan_retry_windows()
        self.assertTrue(any(item["task_id"] == "EMR_TEST" for item in plan))
        # RESCAN 覆盖账独立登记
        executor.record_rescan_coverage(
            table="EMR_TEST", business_month="2026-09",
            reconciled_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        )
        records = repo.month_coverage("EMR_TEST")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].route_or_origin, "RESCAN")


# ---------------------------------------------------------------------------
# 批1-2c 生产 ApplyPort 组装
# ---------------------------------------------------------------------------


class TestProductionApplyWiring(unittest.TestCase):
    def test_scoped_verifier_rejects_scope_and_ops_mismatch(self):
        from app.services.reporting_pipeline.production_apply import (
            ScopedApprovalVerifier,
        )

        verifier = ScopedApprovalVerifier(
            executor_lookup=lambda code, target: {
                "executor_code": code, "enabled": True,
            },
            approval_lookup=lambda ref, code: {
                "valid": True, "target_scope": "db.t.T1",
                "allowed_operations": "INSERT,UPDATE",
            },
        )
        ok = verifier.verify(
            approval_ref="AP", executor_id="e1", target_object="db.t.T1",
            allowed_operations=("INSERT", "UPDATE"),
        )
        self.assertTrue(ok.approved)
        wrong_scope = verifier.verify(
            approval_ref="AP", executor_id="e1", target_object="db.t.T2",
            allowed_operations=("INSERT",),
        )
        self.assertFalse(wrong_scope.approved)
        self.assertIn("范围", wrong_scope.reason)
        wrong_ops = verifier.verify(
            approval_ref="AP", executor_id="e1", target_object="db.t.T1",
            allowed_operations=("DELETE",),
        )
        self.assertFalse(wrong_ops.approved)

    def test_verifier_expiry(self):
        from app.services.reporting_pipeline.production_apply import (
            ScopedApprovalVerifier,
        )

        verifier = ScopedApprovalVerifier(
            executor_lookup=lambda code, target: {"enabled": True},
            approval_lookup=lambda ref, code: {
                "valid": False,  # 过期
                "target_scope": "db.t.T1", "allowed_operations": "INSERT",
            },
        )
        decision = verifier.verify(
            approval_ref="AP", executor_id="e", target_object="db.t.T1",
            allowed_operations=("INSERT",),
        )
        self.assertFalse(decision.approved)

    def test_production_mode_gate_still_enforced(self):
        """生产模式三要件：静态批准核验直接拒绝（模拟批准不可入生产门）。"""
        from app.services.reporting_pipeline.apply_port import (
            ApplyPort,
            ApplyRefused,
            StaticApprovalVerifier,
            VersionGuard,
        )
        from app.services.reporting_pipeline.apply_port import (
            InMemoryVersionRegistry,
        )

        with self.assertRaises(ApplyRefused):
            ApplyPort(
                whitelisted_executors=["e1"],
                approval_verifier=StaticApprovalVerifier({"AP"}),
                version_guard=VersionGuard(InMemoryVersionRegistry()),
                lease_validator=lambda r, t: None,
                enforce_fence=True,
                production_mode=True,
            )
        with self.assertRaises(ApplyRefused):
            ApplyPort(
                whitelisted_executors=["e1"],
                approval_verifier=None,  # 缺省落 Static → 拒
                lease_validator=lambda r, t: None,
                enforce_fence=True,
                production_mode=True,
            )


# ---------------------------------------------------------------------------
# 批1-6 outbox 守护
# ---------------------------------------------------------------------------


class _StaticTransport:
    """假传输：按事件序返回预设响应（401/503/202/超时）。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, headers, body, *, timeout_seconds):
        self.calls.append(("POST", url))
        response = self.responses.pop(0) if self.responses else ("202", b"{}", {})
        code, payload, headers_ = response
        if code == "TIMEOUT":
            from app.services.reporting_pipeline.alerts_client import (
                TransportUnavailable,
            )

            raise TransportUnavailable("simulated timeout")
        return _resp(code, payload, headers_)

    def get(self, url, headers, *, timeout_seconds):
        self.calls.append(("GET", url))
        response = self.responses.pop(0) if self.responses else ("200", b"{}", {})
        code, payload, headers_ = response
        if code == "TIMEOUT":
            from app.services.reporting_pipeline.alerts_client import (
                TransportUnavailable,
            )

            raise TransportUnavailable("simulated timeout")
        return _resp(code, payload, headers_)


def _resp(code, payload=b"{}", headers=None):
    from app.services.reporting_pipeline.alerts_client import TransportResponse

    return TransportResponse(
        status_code=int(code), body=payload, headers=dict(headers or {})
    )


def _relay_client(transport):
    from app.services.reporting_pipeline.alerts_client import (
        RelayConfig,
        RelayV2Client,
    )

    return RelayV2Client(
        transport=transport,
        config=RelayConfig(base_url="http://relay", source_id="src", secret_ref="SECRET"),
        secret_resolver=lambda ref: b"secret",
    )


def _enqueue_failure_event(repo):
    incident = repo.create_incident("T1:2026-10-22:EMR_TEST", "EXTRACT_FAILED")
    _ids = []
    from app.services.reporting_pipeline.alerts_client import build_event_body

    event = repo.append_incident_event(
        incident, event_kind="OPENED", severity="yellow", title="t",
        body_bytes=build_event_body(
            source_event_id="evt-1", event_type="alert", category="EXTRACT_FAILED",
            severity="yellow", title="t", body="b",
            occurred_at=datetime.now(timezone.utc).isoformat(), metadata={},
        ),
        metadata={},
    )
    return event


class TestOutboxDaemon(unittest.TestCase):
    def test_timeout_then_backoff_persisted(self):
        from app.services.reporting_pipeline.outbox_daemon import (
            DaemonConfig,
            OutboxDaemon,
        )

        repo = InMemoryControlRepository()
        evt = _enqueue_failure_event(repo)
        transport = _StaticTransport([("TIMEOUT", b"", {})])
        daemon = OutboxDaemon(
            repo, _relay_client(transport), config=DaemonConfig(),
            sleep_fn=lambda s: None,
        )
        summary = daemon.run_once()
        self.assertEqual(summary["send_attempted"], 1)
        event = repo.get_outbox_event(evt.source_event_id)
        self.assertIsNotNone(event.next_attempt_at)  # 退避已持久化
        self.assertEqual(event.delivery_state, "NOT_SENT")

    def test_401_pauses_and_persists_across_restart(self):
        from app.services.reporting_pipeline.outbox_daemon import (
            DaemonConfig,
            OutboxDaemon,
        )

        repo = InMemoryControlRepository()
        evt = _enqueue_failure_event(repo)
        transport = _StaticTransport([("401", b"{}", {})])
        daemon = OutboxDaemon(
            repo, _relay_client(transport), config=DaemonConfig(),
            sleep_fn=lambda s: None,
        )
        daemon.run_once()
        self.assertEqual(
            repo.get_outbox_event(evt.source_event_id).delivery_state, "PAUSED_AUTH"
        )
        # 进程退出后重启（新守护实例）：状态来自持久化仓储；PAUSED_AUTH
        # 事件不被重发（鉴权未修复前不反复打 relay）
        transport2 = _StaticTransport([("401", b"{}", {})])
        daemon2 = OutboxDaemon(
            repo, _relay_client(transport2), config=DaemonConfig(),
            sleep_fn=lambda s: None,
        )
        summary = daemon2.run_once()
        self.assertEqual(summary["send_attempted"], 0)
        self.assertEqual(
            repo.get_outbox_event(evt.source_event_id).delivery_state, "PAUSED_AUTH"
        )

    def test_503_retry_after_respected(self):
        from app.services.reporting_pipeline.outbox_daemon import (
            DaemonConfig,
            OutboxDaemon,
        )

        repo = InMemoryControlRepository()
        evt = _enqueue_failure_event(repo)
        transport = _StaticTransport([
            ("503", b"{}", {"Retry-After": "120"}),
        ])
        daemon = OutboxDaemon(
            repo, _relay_client(transport), config=DaemonConfig(),
            sleep_fn=lambda s: None,
        )
        daemon.run_once()
        event = repo.get_outbox_event(evt.source_event_id)
        self.assertEqual(event.delivery_state, "NOT_SENT")
        self.assertIsNotNone(event.next_attempt_at)

    def test_inspect_groups_and_recovery_notification(self):
        from app.services.reporting_pipeline.outbox_daemon import inspect_outbox

        repo = InMemoryControlRepository()
        _enqueue_failure_event(repo)
        view = inspect_outbox(repo)
        self.assertGreaterEqual(view["summary"]["not_sent"], 1)
        # 恢复通知：缺口闭合后 RECOVERED 进入 outbox（同一 incident 不再 OPENED）
        from app.services.reporting_pipeline.planner import TimeWindow

        repo.create_batch("B1", "EMR_TEST", "2026-10-22")
        window = TimeWindow(
            datetime(2026, 10, 22, tzinfo=timezone(timedelta(hours=8))),
            datetime(2026, 10, 23, tzinfo=timezone(timedelta(hours=8))),
        )
        repo.record_gap("EMR_TEST", window, "SCHEDULER_TASK_FAILED")
        RecoveryExecutor(repo).close_success(
            batch_id="B1", task_id="EMR_TEST", business_day="2026-10-22",
            window_fingerprint=window.fingerprint(), evidence="reconcile",
        )
        repo.get_outbox_event(
            f"r189t1.{repo.find_open_incident('T1:2026-10-22:EMR_TEST').incident_id if repo.find_open_incident('T1:2026-10-22:EMR_TEST') else 'INC-000001'}.RECOVERED.1"
        ) if False else None
        # 直接断言：RECOVERED 事件已入 outbox
        queued_or_pending = repo.pending_outbox() + repo.queued_outbox()
        kinds = [e.event_kind for e in queued_or_pending]
        self.assertIn("RECOVERED", kinds)


# ---------------------------------------------------------------------------
# 批1-3 DataX 路由（假进程 + 假暂存访问）
# ---------------------------------------------------------------------------


class _FakeProcessRunner:
    def __init__(self, results):
        self.results = list(results)
        self.argv_log = []

    def run(self, argv, *, timeout_seconds):

        self.argv_log.append(list(argv))
        return self.results.pop(0)


class _FakeStageAccess:
    def __init__(self, rows_by_table):
        self.rows_by_table = dict(rows_by_table)
        self.dropped = []

    def read_rows(self, stage_table, columns):
        rows = self.rows_by_table.get(stage_table, [])
        return [tuple(row[c] for c in columns) for row in rows]

    def drop_table(self, stage_table):
        self.dropped.append(stage_table)


def _ok_result(read, written):
    from app.services.reporting_pipeline.adapters.datax_runner import ProcessResult

    stdout = (
        f"读出记录总数 : {read}\n总计写入总数 : {written}\n读写失败总数 : 0\n"
    )
    return ProcessResult(exit_code=0, stdout=stdout, stderr="")


def _bad_result(code=1):
    from app.services.reporting_pipeline.adapters.datax_runner import ProcessResult

    return ProcessResult(exit_code=code, stdout="", stderr="boom")


def _route(stage_access, runner, budget=None):
    import tempfile

    from app.services.reporting_pipeline.adapters.datax_runner import (
        DataXRunner,
        DataxJobTemplate,
        JobFileWorkspace,
        MysqlStageRoute,
    )
    from app.services.reporting_pipeline.adapters.python_reader import ReadBudget
    from app.services.reporting_pipeline.datax_route import DataXCaptureRoute

    route = MysqlStageRoute(
        route_id="r1", version="v1", host="10.10.8.53", port=3306,
        database="stage", table_whitelist=("t1_emr_test_att1",),
        credential_ref="container-credentials:stage",
    )
    template = DataxJobTemplate(
        template_id="t1", version="v1", reader_plugin="oraclereader",
        writer_plugin="mysqlwriter", target_object_whitelist=("t1_emr_test",),
        projection_columns=("ID", "V1"), change_time_column="DATETIME",
        stable_key_columns=("ID",), render_spec={},
    )
    return DataXCaptureRoute(
        template=template,
        route=route,
        runner=DataXRunner(runner, datax_home="/opt/datax"),
        workspace=JobFileWorkspace(
            tempfile.mkdtemp(prefix="b1dx-"),
            credential_resolver=lambda job: {"user": "u", "password": "p", "stage_user": "su", "stage_password": "sp"},
        ),
        stage_access=stage_access,
        source_object="ODS.V_TEST",
        stage_table_prefix="t1_emr_test",
        column_names=["ID", "V1"],
        budget=budget or ReadBudget(max_rows_per_slice=100),
    )


class TestDataxCaptureRoute(unittest.TestCase):
    def _window(self):
        from app.services.reporting_pipeline.planner import TimeWindow

        start = datetime(2026, 10, 22, tzinfo=timezone(timedelta(hours=8)))
        return TimeWindow(start, start + timedelta(days=1))

    def test_success_harvest_and_recycle(self):
        access = _FakeStageAccess({"t1_emr_test_att1": [
            {"ID": "K1", "V1": "a"}, {"ID": "K2", "V1": "b"},
        ]})
        runner = _FakeProcessRunner([_ok_result(2, 2)])
        route = _route(access, runner)
        outcome = route.capture_window(self._window(), attempt_id="att1")
        self.assertTrue(outcome.complete)
        self.assertEqual(len(outcome.rows), 2)
        self.assertEqual(outcome.rows[0], {"ID": "K1", "V1": "a"})
        self.assertIn("t1_emr_test_att1", access.dropped)  # 导出回收

    def test_rowcount_mismatch_refused(self):
        access = _FakeStageAccess({"t1_emr_test_att1": [
            {"ID": "K1", "V1": "a"},
        ]})
        runner = _FakeProcessRunner([_ok_result(2, 2)])  # DataX 说写2，暂存只有1
        route = _route(access, runner)
        with self.assertRaises(Exception) as ctx:
            route.capture_window(self._window(), attempt_id="att1")
        self.assertIn("STAGE_ROW_MISMATCH", str(ctx.exception))

    def test_dirty_or_nonzero_exit_incomplete(self):
        from app.services.reporting_pipeline.adapters.datax_runner import ProcessResult

        access = _FakeStageAccess({})
        dirty_stdout = "读出记录总数 : 5\n总计写入总数 : 4\n读写失败总数 : 1\n"
        runner = _FakeProcessRunner([
            ProcessResult(exit_code=0, stdout=dirty_stdout, stderr=""),
        ])
        route = _route(access, runner)
        outcome = route.capture_window(self._window(), attempt_id="att1")
        self.assertFalse(outcome.complete)
        self.assertEqual(outcome.end_reason, "DATAX_DIRTY")

    def test_over_budget_splits_window(self):
        from app.services.reporting_pipeline.adapters.python_reader import ReadBudget

        # 每个子窗写 60 行（≤预算100），整窗会写 120 → 拆二分
        _FakeStageAccess({
            # 第二个子窗先跑（右侧先？以实现为准）——两个子窗各给同款数据
            **{f"t1_emr_test_att1-{node}": [
                {"ID": f"K{i}", "V1": "v"} for i in range(60)
            ] for node in ["x", "y", "z", "w"]}
        })
        # stage_table 命名含节点 id，先给一个宽松字典：read_rows 按列返回
        class _Loose(_FakeStageAccess):
            def read_rows(self, stage_table, columns):
                return [tuple(f"{c}-{i}" for c in columns) for i in range(60)]

        loose = _Loose({})
        runner = _FakeProcessRunner([
            _ok_result(120, 120),  # 整窗超限 → 拆
            _ok_result(60, 60),    # 子窗1
            _ok_result(60, 60),    # 子窗2
        ])
        route = _route(loose, runner, budget=ReadBudget(max_rows_per_slice=100))
        outcome = route.capture_window(self._window(), attempt_id="att1")
        self.assertTrue(outcome.complete)
        self.assertEqual(len(outcome.rows), 120)
        self.assertIsNotNone(outcome.split_root)


if __name__ == "__main__":
    unittest.main()
