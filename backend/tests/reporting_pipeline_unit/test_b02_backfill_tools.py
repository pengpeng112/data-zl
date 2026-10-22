# -*- coding: utf-8 -*-
"""B02 离线工具测试：拆窗预演 / 键集差异框架 / 父子发布顺序编排。

全部隔离/模拟数据验收；不连生产源、不写目标（接续说明 §4-B02）。
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.backfill import (
    WindowEstimate,
    build_gap_diff,
    build_publish_order,
    gap_diff_keyset_sql,
    plan_backfill_windows,
    uniform_profile_estimate,
    verify_leaf_coverage,
)
from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.planner import TimeWindow


def _est(rows: int, bytes_: int = 1) -> WindowEstimate:
    return WindowEstimate(rows=rows, bytes=bytes_)


class TestBackfillWindowPlanning(unittest.TestCase):
    def test_month_first_layer_and_coverage(self):
        out = plan_backfill_windows(
            datetime(2026, 1, 1), datetime(2026, 10, 24), uniform_profile_estimate(100)
        )
        self.assertTrue(out["coverage"]["ok"], out["coverage"]["problems"])
        self.assertEqual(out["totals"]["leaves"], 10)  # 10 个日历月
        self.assertEqual(out["totals"]["keyset_leaves"], 0)
        # 首叶=1月整月、末叶=10月1-24日的部分月
        self.assertTrue(out["leaves"][0]["window_start"].startswith("2026-01-01"))
        self.assertTrue(out["leaves"][-1]["window_end_exclusive"].startswith("2026-10-24"))

    def test_estimate_split_month_to_days(self):
        # 3月画像超限 → 拆到日；其余月整月叶
        def estimate(w: TimeWindow) -> WindowEstimate:
            rows = 3_000_000 if (w.start.month == 3 and w.duration_seconds() > 86400 * 20) else 100
            return _est(rows)

        out = plan_backfill_windows(
            datetime(2026, 1, 1), datetime(2026, 4, 1), estimate, max_rows_per_leaf=2_000_000
        )
        self.assertTrue(out["coverage"]["ok"], out["coverage"]["problems"])
        day_leaves = [lf for lf in out["leaves"] if lf["duration_seconds"] <= 86400]
        self.assertEqual(len(day_leaves), 31)  # 3月31天
        self.assertEqual(out["totals"]["keyset_leaves"], 0)

    def test_estimate_split_day_to_hours_and_keyset_fallback(self):
        def estimate(w: TimeWindow) -> WindowEstimate:
            # 2月整体与单日都超限；某个小时仍超限 → 该小时 KEYSET
            if w.duration_seconds() > 86400:
                return _est(5_000_000)
            if w.duration_seconds() == 86400:
                return _est(3_000_000)
            if w.start.hour == 10:
                return _est(9_000_000)
            return _est(10)

        out = plan_backfill_windows(
            datetime(2026, 2, 1), datetime(2026, 3, 1), estimate, max_rows_per_leaf=2_000_000
        )
        self.assertTrue(out["coverage"]["ok"], out["coverage"]["problems"])
        keyset = [lf for lf in out["leaves"] if lf["status"] == "KEYSET"]
        self.assertEqual(len(keyset), 28)  # 每天10点那小时转KEYSET
        hour_leaves = [lf for lf in out["leaves"] if lf["duration_seconds"] in (3600, 1800, 900)]
        self.assertGreater(len(hour_leaves), 28 * 5)

    def test_coverage_detector_finds_hole_and_overlap(self):
        base = [
            {"window_start": "2026-01-01T00:00:00", "window_end_exclusive": "2026-01-02T00:00:00"},
            {"window_start": "2026-01-03T00:00:00", "window_end_exclusive": "2026-01-04T00:00:00"},  # 空洞
            {"window_start": "2026-01-04T00:00:00", "window_end_exclusive": "2026-01-05T00:00:00"},
            {"window_start": "2026-01-04T12:00:00", "window_end_exclusive": "2026-01-06T00:00:00"},  # 重叠
        ]
        cov = verify_leaf_coverage(base, datetime(2026, 1, 1), datetime(2026, 1, 6))
        self.assertFalse(cov["ok"])
        self.assertTrue(any("空洞" in p for p in cov["problems"]))
        self.assertTrue(any("重叠" in p for p in cov["problems"]))

    def test_naive_only_no_tz(self):
        from datetime import timezone

        with self.assertRaises(ContractViolation):
            plan_backfill_windows(
                datetime(2026, 1, 1),
                datetime(2026, 2, 1, tzinfo=timezone.utc),
                uniform_profile_estimate(10),
            )

    def test_year_boundary_range(self):
        out = plan_backfill_windows(
            datetime(2025, 11, 15), datetime(2026, 2, 10), uniform_profile_estimate(50)
        )
        self.assertTrue(out["coverage"]["ok"], out["coverage"]["problems"])
        self.assertEqual(out["totals"]["leaves"], 4)  # 11月部分/12月/1月/2月部分


class TestGapDiffFramework(unittest.TestCase):
    def test_classification_missing_extra_content_duplicate(self):
        window = TimeWindow(datetime(2026, 1, 1), datetime(2026, 2, 1))
        src = ["a", "b", "b", "c", "d"]
        tgt = {"b", "c", "e"}
        ledger = build_gap_diff("EMR_X", window, src, tgt, content_equal=lambda k: k != "c")
        self.assertEqual(ledger.missing_in_target, ["a", "d"])
        self.assertEqual(ledger.extra_in_target, ["e"])
        self.assertEqual(ledger.content_diff, ["c"])
        self.assertEqual(ledger.source_duplicate_keys, ["b"])
        self.assertEqual(ledger.source_keys, 5)
        self.assertEqual(ledger.target_keys, 3)
        d = ledger.to_dict()
        self.assertEqual(d["missing_in_target_count"], 2)
        self.assertIn("等批准后执行", d["note"])

    def test_keyset_sql_template_half_open(self):
        sql = gap_diff_keyset_sql("ODS.V_EMR_ICH", "ID")
        self.assertIn(">= :start", sql)
        self.assertIn("< :end", sql)
        self.assertIn("DATETIME", sql)


class TestPublishOrder(unittest.TestCase):
    def _tasks(self):
        return [
            {"index": 24, "canonical_table": "EMR_ICH_OPERATION",
             "declared_parent_candidates": [{"parent": "EMR_ICH", "child_key": "ICH_ID"}]},
            {"index": 3, "canonical_table": "EMR_ICH", "declared_parent_candidates": []},
            {"index": 27, "canonical_table": "EMR_ICH_DIAGNOSIS",
             "declared_parent_candidates": [{"parent": "EMR_ICH", "child_key": "DCS_ID"}]},
        ]

    def test_parent_wave_before_child(self):
        out = build_publish_order(self._tasks())
        waves = {w["wave"]: w["tables"] for w in out["waves"]}
        self.assertIn("EMR_ICH", waves[0])
        tbl = {t["table"]: t for t in out["tables"]}
        self.assertLess(tbl["EMR_ICH"]["wave"], tbl["EMR_ICH_DIAGNOSIS"]["wave"])
        self.assertLess(tbl["EMR_ICH"]["wave"], tbl["EMR_ICH_OPERATION"]["wave"])
        self.assertEqual(tbl["EMR_ICH"]["mode"], "PUBLISH")

    def test_reuse_existing_parent(self):
        out = build_publish_order(self._tasks(), existing_parent_checker=lambda p, c: True)
        tbl = {t["table"]: t for t in out["tables"]}
        for name in ("EMR_ICH_DIAGNOSIS", "EMR_ICH_OPERATION"):
            self.assertEqual(tbl[name]["mode"], "REUSE_EXISTING_PARENT")

    def test_missing_parent_waits_with_auto_wake(self):
        tasks = self._tasks()[:2] + [
            {"index": 5, "canonical_table": "EMR_DISCHARGE_RECORD_DIAGNOSIS",
             "declared_parent_candidates": [{"parent": "EMR_DISCHARGE_RECORD", "child_key": "DR_ID"}]},
        ]
        out = build_publish_order(tasks)
        tbl = {t["table"]: t for t in out["tables"]}
        self.assertEqual(tbl["EMR_DISCHARGE_RECORD_DIAGNOSIS"]["mode"], "WAITING_PARENT_AUTO_WAKE")
        self.assertIn("EMR_DISCHARGE_RECORD_DIAGNOSIS", out["waiting_parent_tables"])
        self.assertEqual(tbl["EMR_DISCHARGE_RECORD_DIAGNOSIS"]["blocked_by_missing_parents"], ["EMR_DISCHARGE_RECORD"])

    def test_cycle_rejected(self):
        tasks = [
            {"index": 1, "canonical_table": "A", "declared_parent_candidates": [{"parent": "B"}]},
            {"index": 2, "canonical_table": "B", "declared_parent_candidates": [{"parent": "A"}]},
        ]
        with self.assertRaises(ContractViolation):
            build_publish_order(tasks)


if __name__ == "__main__":
    unittest.main()
