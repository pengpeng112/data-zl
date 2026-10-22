"""R02 耐久暂存与游标回归：重启恢复 / 半截拒绝 / 连续完成游标 / 覆盖年龄。

对应补充验收 RT1-003（离线部分：A 捕获后退出、B 恢复同一完整清单）、
RT1-025（capture 与连续完成分开，缺口不越）、RT1-026（覆盖年龄按月实际
被重访的最长间隔计算）。
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    ContractViolation,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.durable_staging import DurableFileStageStore
from app.services.reporting_pipeline.planner import (
    TimeWindow,
    coverage_age_report,
    month_sequence,
)
from app.services.reporting_pipeline.repositories import InMemoryControlRepository


def _manifest(rows: int, *, payload_sha: str | None = None) -> BatchManifest:
    return BatchManifest(
        batch_id="B1", attempt_id="A1", task_id="EMR_X", config_version="v1",
        definition_fingerprint=None, source_identity="ods__V",
        window_fingerprint="win:2026-10-19T00:00:00/2026-10-20T00:00:00",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=rows, valid=rows),
        pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=64, schema_version="v",
        type_contract_version="t", payload_sha256=payload_sha or "a" * 64,
    )


class TestDurableFileStageStore(unittest.TestCase):
    """RT1-003 离线部分：进程 A/B 语义用两次打开同目录模拟。"""

    def _payload(self, rows: int) -> tuple[bytes, str]:
        payload = b"".join(
            json.dumps([i, f"row-{i}"]).encode("utf-8") + b"\n"
            for i in range(rows)
        )
        return payload, hashlib.sha256(payload).hexdigest()

    def test_capture_exit_then_recover_same_manifest(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            # 进程 A：写块后"退出"（store 对象销毁）
            payload, sha = self._payload(100)
            store_a = DurableFileStageStore(root)
            store_a.begin_attempt("B1", "A1")
            store_a.write_chunk("B1", "A1", "c1", payload, 100)
            # 进程 B：重新打开同一目录恢复
            store_b = DurableFileStageStore(root)
            infos = store_b.read_chunk_infos("B1", "A1")
            self.assertEqual(len(infos), 1)
            self.assertEqual(infos[0].row_count, 100)
            document = store_b.mark_complete_against_manifest(
                "B1", "A1",
                _manifest(100, payload_sha=sha),
                source_identity="ods__V",
                definition_fingerprint=None,
            )
            self.assertEqual(document["total_rows"], 100)
            self.assertTrue(document["completion_evidence"]["pagination_complete"])
            # 装载选择：恢复出的 COMPLETE 清单可用
            chosen = store_b.select_complete("B1")
            self.assertEqual(chosen["payload_sha256"], sha)
            # 流式读回：行数守恒
            rows = list(store_b.iter_chunk_rows("B1", "A1"))
            self.assertEqual(len(rows), 100)

    def test_partial_attempt_never_complete(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A2")
            payload, _sha = self._payload(50)
            store.write_chunk("B1", "A2", "c1", payload, 50)
            # 行数对不上 manifest → 拒绝
            with self.assertRaises(ContractViolation):
                store.mark_complete_against_manifest(
                    "B1", "A2", _manifest(100),
                    source_identity="ods__V", definition_fingerprint=None,
                )
            self.assertFalse(store.is_complete("B1", "A2"))

    def test_cancelled_attempt_cannot_recover_as_complete(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A3")
            payload, sha = self._payload(10)
            store.write_chunk("B1", "A3", "c1", payload, 10)
            store.cancel_attempt("B1", "A3")
            with self.assertRaises(ContractViolation):
                store.mark_complete_against_manifest(
                    "B1", "A3", _manifest(10, payload_sha=sha),
                    source_identity="ods__V", definition_fingerprint=None,
                )

    def test_duplicate_chunk_rejected_and_attempt_append_only(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A4")
            store.write_chunk("B1", "A4", "c1", b"x\n", 1)
            with self.assertRaises(ContractViolation):
                store.write_chunk("B1", "A4", "c1", b"x\n", 1)
            with self.assertRaises(ContractViolation):
                store.begin_attempt("B1", "A4")  # attempt 只增不覆写

    def test_truncated_chunk_detected_before_load(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A5")
            payload, sha = self._payload(20)
            store.write_chunk("B1", "A5", "c1", payload, 20)
            # 外力截断块文件
            chunk = root + "/B1/A5/chunk-c1.bin"
            Path(chunk).write_bytes(payload[:10])
            verdict = store.verify_chunk_integrity("B1", "A5")
            self.assertEqual(verdict["mismatch"], ["c1"])
            with self.assertRaises(ContractViolation):
                store.mark_complete_against_manifest(
                    "B1", "A5", _manifest(20, payload_sha=sha),
                    source_identity="ods__V", definition_fingerprint=None,
                )


class TestContinuousCompletionCursor(unittest.TestCase):
    """RT1-025：捕获水位与连续完成分开；缺口不越。"""

    def _repo_with_gap(self) -> InMemoryControlRepository:
        repo = InMemoryControlRepository()
        day = datetime(2026, 10, 1, tzinfo=timezone.utc)
        repo.advance_capture_watermark("EMR_X", day + timedelta(days=10))
        # 10-03 留 OPEN 缺口
        repo.record_gap(
            "EMR_X",
            TimeWindow(
                datetime(2026, 10, 3, tzinfo=timezone.utc),
                datetime(2026, 10, 4, tzinfo=timezone.utc),
            ),
            "source outage",
        )
        return repo

    def test_capture_advances_but_continuous_blocked_by_gap(self):
        repo = self._repo_with_gap()
        # H0 后日常捕获继续前进（成功窗可先落地）
        repo.advance_capture_watermark("EMR_X", datetime(2026, 10, 20, tzinfo=timezone.utc))
        # 连续完成游标不得越过 10-03 缺口
        with self.assertRaises(ContractViolation):
            repo.advance_continuous_completion(
                "EMR_X", datetime(2026, 10, 19, tzinfo=timezone.utc)
            )

    def test_continuous_can_reach_gap_start(self):
        repo = self._repo_with_gap()
        repo.advance_continuous_completion(
            "EMR_X", datetime(2026, 10, 3, tzinfo=timezone.utc)
        )
        wm = repo.get_watermarks("EMR_X")
        self.assertIsNotNone(wm.continuous_through)
        # 快照两者分开可见（日报据此不冒充连续完成）
        snap = repo.snapshot()["watermarks"]["EMR_X"]
        self.assertGreater(snap["capture_h"], snap["continuous_through"])

    def test_close_gap_then_continuous_advances(self):
        repo = self._repo_with_gap()
        gap = repo.open_gaps("EMR_X")[0]
        repo.close_gap(gap.gap_id, evidence="补抽完成")
        repo.advance_continuous_completion(
            "EMR_X", datetime(2026, 10, 19, tzinfo=timezone.utc)
        )
        snap = repo.snapshot()["watermarks"]["EMR_X"]
        self.assertEqual(snap["continuous_through"], "2026-10-19T00:00:00+00:00")


class TestCoverageAgeReport(unittest.TestCase):
    """RT1-026：只扫当月/单月轮转不得冒充全历史保障。"""

    def test_current_month_only_is_no_history_visit(self):
        months = month_sequence("2021-10", "2026-09")  # 60 个月
        report = coverage_age_report(
            managed_months=months,
            last_visit_month_by_key={},  # 各月从未被重访
            now_month="2026-10",
            cycle_days=30,
        )
        self.assertEqual(report["coverage_level"], "NO_HISTORY_VISIT")
        self.assertEqual(report["never_visited"], 60)
        self.assertGreater(report["max_days_since_any_visit"], 30)

    def test_one_month_per_cycle_rotation_is_degraded(self):
        months = month_sequence("2021-11", "2026-10")
        # 60 个月每月只轮访 1 个月：只有当前月刚被重访
        report = coverage_age_report(
            managed_months=months,
            last_visit_month_by_key={"2026-10": "2026-10"},
            now_month="2026-10",
            cycle_days=30,
        )
        self.assertEqual(
            report["coverage_level"], "DEGRADED_BEYOND_DECLARED_CYCLE"
        )

    def test_full_cycle_within_declared(self):
        months = month_sequence("2025-08", "2025-10")
        report = coverage_age_report(
            managed_months=months,
            last_visit_month_by_key={m: "2025-11" for m in months},
            now_month="2025-11",
            cycle_days=30,
        )
        self.assertEqual(report["coverage_level"], "WITHIN_DECLARED_CYCLE")

    def test_scope_unfrozen_reported_explicitly(self):
        report = coverage_age_report(
            managed_months=[], last_visit_month_by_key={},
            now_month="2026-10", cycle_days=30,
        )
        self.assertEqual(report["coverage_level"], "SCOPE_UNFROZEN")


class TestPerTableSnapshot(unittest.TestCase):
    """快照逐表行：隔离/待父/装载与最早缺口可查（日报数据源）。"""

    def test_per_table_states_and_earliest_gap(self):
        from app.services.reporting_pipeline.contracts import BatchState

        repo = InMemoryControlRepository()
        repo.create_batch("b1", "EMR_A", "2026-10-19")
        repo.transition_batch("b1", BatchState.CAPTURING, reason="start")
        repo.attach_attempt_manifest("b1", _manifest(1))
        repo.select_manifest("b1")
        for state in (BatchState.CAPTURED, BatchState.VALIDATING,
                      BatchState.QUARANTINED):
            repo.transition_batch("b1", state, reason="walk to quarantined")
        repo.record_gap(
            "EMR_A",
            TimeWindow(
                datetime(2026, 10, 5, tzinfo=timezone.utc),
                datetime(2026, 10, 6, tzinfo=timezone.utc),
            ),
            "timeout",
        )
        snap = repo.snapshot()["per_table"]["EMR_A"]
        self.assertEqual(snap["quarantined"], 1)
        self.assertEqual(snap["earliest_open_gap"]["open_gap_count"], 1)
        self.assertIn("2026-10-05", snap["earliest_open_gap"]["window"])


if __name__ == "__main__":
    unittest.main()
