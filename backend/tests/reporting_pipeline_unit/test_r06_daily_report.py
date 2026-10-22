"""R06 日报与隐私回归：日报来自仓储状态 / SLA_UNKNOWN 单列 / 外发只安全码。

对应补充验收 RT1-031（离线部分）。真实 PG 仓储路径在隔离库核实后由
集成测试覆盖（RT1-030/031 隔离部分 NOT_RUN 保持）。
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.alerts_client import (
    build_event_body,
    verify_payload_privacy,
)
from app.services.reporting_pipeline.planner import TimeWindow
from app.services.reporting_pipeline.reports import build_daily_report
from app.services.reporting_pipeline.repositories import InMemoryControlRepository


class _TaskStub:
    def __init__(self, table: str) -> None:
        self.canonical_table = table
        self.applicability = type("A", (), {"value": "TO_VERIFY"})()
        self.associations = type(
            "Assoc",
            (),
            {"deadline_state": type("D", (), {"value": "UNCONFIGURED"})()},
        )()


class _BundleStub:
    def __init__(self) -> None:
        self.tasks = [_TaskStub("EMR_X"), _TaskStub("EMR_NURSE_PLAN")]
        self.package_id = "test"

    def rescan_tasks(self):
        return [self.tasks[0]]


class TestDailyReportFromRepositoryState(unittest.TestCase):
    def _repo(self) -> InMemoryControlRepository:
        # 2026 接续场景顺序：先有捕获水位（H0 后日常已捕获），
        # 再发现历史缺口（早于当前水位）——日捕获不受阻，连续完成受阻。
        repo = InMemoryControlRepository()
        repo.create_batch("b1", "EMR_X", "2026-10-19")
        repo.advance_capture_watermark("EMR_X", datetime(2026, 10, 20, tzinfo=timezone.utc))
        repo.record_gap(
            "EMR_X",
            TimeWindow(
                datetime(2026, 10, 5, tzinfo=timezone.utc),
                datetime(2026, 10, 6, tzinfo=timezone.utc),
            ),
            "source timeout",
        )
        repo.advance_capture_watermark("EMR_X", datetime(2026, 10, 21, tzinfo=timezone.utc))
        return repo

    def test_report_sections_from_repo(self):
        report = build_daily_report(
            business_day="2026-10-19",
            repository=self._repo(),
            bundle=_BundleStub(),
            simulation=False,
        ).to_dict()
        self.assertFalse(report["simulation"])
        # 待补最早窗来自缺口账本
        self.assertIn("EMR_X", report["earliest_open_gap"])
        self.assertIn("2026-10-05", report["earliest_open_gap"]["EMR_X"]["window"])
        # 连续完成与捕获水位分开展示
        wm = report["continuous_completion"]["EMR_X"]
        self.assertIsNotNone(wm["capture_h"])
        self.assertIsNone(wm["continuous_through"])  # 缺口未闭合
        # SLA_UNKNOWN 单列（不伪算 SLA_AT_RISK）
        self.assertEqual(report["deadline_unconfigured"]["sla"], "SLA_UNKNOWN")
        self.assertEqual(len(report["deadline_unconfigured"]["tables"]), 2)
        # 建议动作包含缺口补抽
        actions = [a["action"] for a in report["recommended_actions"]]
        self.assertIn("BACKFILL_OPEN_GAPS", actions)

    def test_simulation_flag_default_true_for_memory_repo(self):
        report = build_daily_report(
            business_day="2026-10-19",
            repository=InMemoryControlRepository(),
            bundle=_BundleStub(),
        ).to_dict()
        self.assertTrue(report["simulation"])

    def test_rescan_coverage_age_wired(self):
        report = build_daily_report(
            business_day="2026-10-19",
            repository=InMemoryControlRepository(),
            bundle=_BundleStub(),
            rescan_scope=("2021-10", "2026-09"),
        ).to_dict()
        age = report["rescan_coverage_age"]["EMR_X"]
        self.assertEqual(age["coverage_level"], "NO_HISTORY_VISIT")
        self.assertEqual(age["managed_months"], 60)


class TestAlertPayloadPrivacy(unittest.TestCase):
    """外发载荷只允许安全码/汇总/detail_ref，不含患者/SQL/密钥。"""

    def test_clean_metadata_passes(self):
        body = build_event_body(
            source_event_id="r189t1.INC-000001.OPENED.1",
            event_type="alert",
            category="EXTRACT_FAILED",
            severity="orange",
            title="EMR_X 2026-10-19 窗口失败",
            body="表 EMR_X 窗口 2026-10-19 读取超时，待补抽。",
            occurred_at="2026-10-20T08:00:00+08:00",
            metadata={
                "canonical_table": "EMR_X",
                "error_class": "FETCH_TIMEOUT",
                "detail_ref": "ticket://E01-123",
            },
        )
        verdict = verify_payload_privacy(body)
        self.assertTrue(verdict["ok"], verdict["problems"])

    def test_sensitive_metadata_rejected(self):
        with self.assertRaises(Exception):
            build_event_body(
                source_event_id="x",
                event_type="alert",
                category="EXTRACT_FAILED",
                severity="orange",
                title="t",
                body="b",
                occurred_at="2026-10-20T08:00:00+08:00",
                metadata={"patient_name": "张三"},  # 越白名单
            )

    def test_sql_in_body_flagged(self):
        body = build_event_body(
            source_event_id="r189t1.INC-000002.OPENED.1",
            event_type="alert",
            category="READ_SQL_OR_VIEW_ERROR",
            severity="orange",
            title="t",
            body="SELECT * FROM HIS.LAB_RESULT WHERE password=x",
            occurred_at="2026-10-20T08:00:00+08:00",
            metadata={"error_code": "ORA-00942"},
        )
        verdict = verify_payload_privacy(body)
        self.assertFalse(verdict["ok"])
        joined = " ".join(verdict["problems"])
        self.assertTrue("sql" in joined or "password" in joined)


if __name__ == "__main__":
    unittest.main()
