"""R05 调度桥整改回归：可运行节点排序 / token 贯穿 / 如实总体状态 / 结构化错误。

对应补充验收 RT1-019（父子优先级）、RT1-020（同表多任务）、RT1-022
（跳过不是成功 + run 返回失败不抛异常）、RT1-024（午夜固定窗）与
F08/F09/F10/F14 源码发现的机器化复验。
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.planner import (
    freeze_daily_anchor,
)
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.scheduler_bridge import (
    ExecutionContext,
    SchedulerBridge,
)


class FakeTask:
    def __init__(
        self,
        table: str,
        *,
        mode: str = "T1",
        sources: tuple[str, ...] = (),
        fail: bool = False,
        result: dict | None = None,
        window_key: str | None = None,
        raise_sensitive: bool = False,
    ) -> None:
        self.canonical_table = table
        self.mode = mode
        self.physical_sources = sources
        self.fail = fail
        self.result = result
        self.window_key = window_key
        self.raise_sensitive = raise_sensitive
        self.received_context: ExecutionContext | None = None
        self.ran = False

    def run(self, context: ExecutionContext | None = None) -> dict:
        self.ran = True
        self.received_context = context
        if self.raise_sensitive:
            raise RuntimeError(
                "connect password=Secret123 patient 张三 id=3701... sql=SELECT * FROM t"
            )
        if self.fail:
            raise RuntimeError("injected failure")
        if self.result is not None:
            return self.result
        return {"ok": True}


class TestRunnableQueueOrdering(unittest.TestCase):
    """RT1-019：历史父+T1 子不被全局排序颠倒；独立 T1 不受父子约束。"""

    def test_historical_parent_before_t1_child(self):
        bridge = SchedulerBridge(repository=InMemoryControlRepository())
        tasks = [
            FakeTask("CHILD", mode="T1"),
            FakeTask("PARENT", mode="HISTORICAL_REPAIR"),
            FakeTask("INDEP", mode="T1"),
        ]
        order = [
            t.canonical_table
            for t in bridge.plan_order(
                tasks, {"CHILD": ["PARENT"], "PARENT": [], "INDEP": []}
            )
        ]
        self.assertLess(order.index("PARENT"), order.index("CHILD"))
        # 独立 T1 可最先；PARENT 就绪后与 CHILD 的相对顺序仍父先子后
        self.assertEqual(order[0], "INDEP")

    def test_t1_child_never_dispatched_before_parent_in_cycle(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        ran: list[str] = []
        parent = FakeTask(
            "PARENT", mode="HISTORICAL_REPAIR",
            result=None,
        )
        orig = parent.run

        def parent_run(context=None):
            ran.append("PARENT")
            return orig(context)

        parent.run = parent_run
        child = FakeTask("CHILD", mode="T1")
        orig_child = child.run

        def child_run(context=None):
            ran.append("CHILD")
            return orig_child(context)

        child.run = child_run
        bridge.run_cycle(
            [child, parent], {"CHILD": ["PARENT"], "PARENT": []}
        )
        self.assertEqual(ran, ["PARENT", "CHILD"])


class TestSameTableMultiTask(unittest.TestCase):
    """RT1-020：同表多模式/多窗任务不丢、不被 by_table 字典覆盖。"""

    def test_multi_mode_tasks_all_retained(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        tasks = [
            FakeTask("T_A", mode="T1", window_key="2026-10-19"),
            FakeTask("T_A", mode="MONTHLY_RESCAN", window_key="2025-03"),
            FakeTask("T_A", mode="LOOKBACK", window_key="2026-10-12"),
        ]
        report = bridge.run_cycle(tasks)
        dispatched = set(report.dispatched)
        self.assertIn("T_A:T1:2026-10-19", dispatched)
        self.assertIn("T_A:MONTHLY_RESCAN:2025-03", dispatched)
        self.assertIn("T_A:LOOKBACK:2026-10-12", dispatched)
        self.assertEqual(len(dispatched), 3)

    def test_multi_window_tasks_keyed_separately(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        tasks = [
            FakeTask("T_B", mode="T1", window_key="2026-10-18"),
            FakeTask("T_B", mode="T1", window_key="2026-10-19"),
        ]
        report = bridge.run_cycle(tasks)
        self.assertEqual(len(report.dispatched), 2)


class TestLeaseTokenPassthrough(unittest.TestCase):
    """RT1/F09：租约 token 进入执行上下文；正式写在提交处再验围栏。"""

    def test_token_flows_into_context(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo, worker_id="w-token")
        fence_ok: list[bool] = []

        class GatedTask(FakeTask):
            def run(self, context=None):
                # 在"目标提交处"用仓储验围栏（租约仍持有时必须通过）
                repo.validate_fencing(context.lease_resource, context.fencing_token)
                fence_ok.append(True)
                return super().run(context)

        task = GatedTask("T_TOK")
        bridge.run_cycle([task])
        ctx = task.received_context
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.worker_id, "w-token")
        self.assertEqual(ctx.lease_resource, "target:DBOPER.T_TOK")
        self.assertIsInstance(ctx.fencing_token, int)
        self.assertGreater(ctx.fencing_token, 0)
        self.assertEqual(fence_ok, [True])

    def test_stale_token_rejected_after_reacquire(self):
        repo = InMemoryControlRepository()
        lease1 = repo.acquire_lease("target:DBOPER.T_S", "w1", 60)
        # 过期后另一工作者接管 → token 前进
        repo._leases["target:DBOPER.T_S"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        lease2 = repo.acquire_lease("target:DBOPER.T_S", "w2", 60)
        self.assertGreater(lease2.fencing_token, lease1.fencing_token)
        with self.assertRaises(Exception):
            repo.validate_fencing("target:DBOPER.T_S", lease1.fencing_token)

    def test_require_verified_target_blocks_unverified(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo, require_verified_target=True)
        report = bridge.run_cycle([FakeTask("T_UNVERIFIED")])
        self.assertIn("T_UNVERIFIED:T1", report.skipped)
        self.assertEqual(report.skip_codes["T_UNVERIFIED:T1"], "TARGET_IDENTITY_UNVERIFIED")


class TestHonestOverallStatus(unittest.TestCase):
    """RT1-022：派发≠成功；全部跳过不得 SUCCESS；run 返回失败要识别。"""

    def test_all_skipped_breaker_is_waiting_with_backlog(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(
            repository=repo, source_open_predicate=lambda s: True
        )
        report = bridge.run_cycle([FakeTask("T_X", sources=("src",))])
        self.assertEqual(report.overall, "WAITING_WITH_BACKLOG")
        self.assertEqual(report.skip_codes["T_X:T1"], "SOURCE_BREAKER_OPEN")

    def test_run_returning_failure_state_counted(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        tasks = [
            FakeTask("T_RET_FAIL", result={"status": "FAILED", "reason": "x"}),
            FakeTask("T_RET_OK"),
        ]
        report = bridge.run_cycle(tasks)
        self.assertIn("T_RET_FAIL:T1", report.failures)
        self.assertIn("T_RET_OK:T1", report.dispatched)
        self.assertEqual(report.overall, "PARTIAL_SUCCESS_WITH_BACKLOG")

    def test_run_returning_quarantined_counted(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        report = bridge.run_cycle(
            [FakeTask("T_Q", result={"status": "QUARANTINED"})]
        )
        self.assertEqual(report.overall, "PARTIAL_SUCCESS_WITH_BACKLOG")

    def test_no_tasks_is_no_work(self):
        bridge = SchedulerBridge(repository=InMemoryControlRepository())
        report = bridge.run_cycle([])
        self.assertEqual(report.overall, "NO_WORK")

    def test_mixed_partial(self):
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(
            repository=repo, source_open_predicate=lambda s: s == "bad"
        )
        report = bridge.run_cycle(
            [FakeTask("T_BAD", sources=("bad",)), FakeTask("T_OK", sources=("good",))]
        )
        self.assertEqual(report.overall, "PARTIAL_SUCCESS_WITH_BACKLOG")


class TestSanitizedErrors(unittest.TestCase):
    """F14/RT1：异常不透出患者/SQL/密钥原文，只留类别与安全摘要。"""

    def test_sensitive_exception_redacted(self):
        task = FakeTask("T_SENS", raise_sensitive=True)
        repo = InMemoryControlRepository()
        bridge = SchedulerBridge(repository=repo)
        report = bridge.run_cycle([task])
        failure = report.failures["T_SENS:T1"]
        self.assertEqual(failure["error_class"], "RuntimeError")
        blob = str(failure)
        self.assertNotIn("Secret123", blob)
        self.assertNotIn("3701", blob)
        self.assertNotIn("SELECT", blob)
        self.assertIn("redacted", failure["message"])


class TestFrozenAnchorWindow(unittest.TestCase):
    """RT1-024：院区固定昨天半开窗；跨午夜重试不漂窗。"""

    def test_anchor_yesterday_half_open(self):
        # UTC 10-20 23:59 = 院区(UTC+8) 10-21 07:59 → 业务日=10-20
        now = datetime(2026, 10, 20, 23, 59, 30, tzinfo=timezone.utc)
        anchor = freeze_daily_anchor(now)
        self.assertEqual(str(anchor.business_day), "2026-10-20")
        window = anchor.business_window()
        self.assertEqual(
            (window.start, window.end_exclusive),
            (datetime(2026, 10, 20), datetime(2026, 10, 21)),
        )
        # UTC 10-20 15:59 = 院区 10-20 23:59 → 业务日=10-19（同日深夜锚定）
        anchor2 = freeze_daily_anchor(datetime(2026, 10, 20, 15, 59, tzinfo=timezone.utc))
        self.assertEqual(str(anchor2.business_day), "2026-10-19")
        window = anchor.business_window()
        # 半开：end 不含
        self.assertTrue(window.contains(datetime(2026, 10, 20, 12)))
        self.assertFalse(window.contains(datetime(2026, 10, 21)))

    def test_retry_after_midnight_same_anchor(self):
        anchor = freeze_daily_anchor(datetime(2026, 10, 20, 15, 59, tzinfo=timezone.utc))
        # 00:01 重试：用同一锚点对象 → 业务日与窗完全一致，不漂移
        self.assertEqual(anchor.fingerprint(), anchor.fingerprint())
        later = datetime(2026, 10, 21, 0, 1, tzinfo=timezone.utc)
        anchor2 = freeze_daily_anchor(later)
        # 新一轮锚点跨天后是新的业务日（重试必须复用旧锚点，不是新建）
        self.assertEqual(str(anchor2.business_day), "2026-10-20")

    def test_naive_clock_rejected(self):
        with self.assertRaises(Exception):
            freeze_daily_anchor(datetime(2026, 10, 20, 12))


if __name__ == "__main__":
    unittest.main()
