"""计划层测试：keyset 同秒并列、二分拆窗、DAG、LIS 路由、月覆盖账。"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.planner import (
    KeysetCursor,
    MonthCoverageRecord,
    SplitNode,
    TimeWindow,
    affected_child_groups,
    build_dag,
    missing_months_in_scope,
    month_bounds,
    month_sequence,
    plan_capture_window,
    resolve_lis_route,
    split_tree_stats,
)

LIS_SEGMENTS = [
    {"start": None, "end_exclusive": "2023-10-01T00:00:00",
     "sources": ["ods__V_EMR_INSPECTION_TEST"]},
    {"start_inclusive": "2023-10-01T00:00:00", "end_exclusive": "2024-01-01T00:00:00",
     "sources": ["ods__V_EMR_INSPECTION_TEST", "lis__V_EMR_INSPECTION"],
     "mode": "PRESERVE_DOCUMENTED_OVERLAP_REVERIFY_BOUNDARIES"},
    {"start_inclusive": "2024-01-01T00:00:00", "end": None,
     "sources": ["lis__V_EMR_INSPECTION"]},
]


class TestTimeWindow(unittest.TestCase):
    def test_capture_window_with_overlap(self):
        w = plan_capture_window(
            date(2026, 10, 18),
            visibility_cutoff=datetime(2026, 10, 19, 2, 0, 0),
            overlap=timedelta(hours=2),
        )
        self.assertEqual(w.start, datetime(2026, 10, 17, 22, 0, 0))
        self.assertEqual(w.end_exclusive, datetime(2026, 10, 19, 2, 0, 0))

    def test_empty_window_rejected(self):
        with self.assertRaises(ContractViolation):
            plan_capture_window(
                date(2026, 10, 18),
                visibility_cutoff=datetime(2026, 10, 18, 0, 0, 0),
                overlap=timedelta(0),
            )

    def test_binary_split_seamless(self):
        w = TimeWindow(datetime(2026, 1, 1), datetime(2026, 1, 2))
        left, right = w.split_binary()
        self.assertEqual(left.end_exclusive, right.start)
        self.assertEqual((left.duration_seconds() + right.duration_seconds()),
                         w.duration_seconds())


class TestKeysetCursor(unittest.TestCase):
    def test_unverified_unique_rejected(self):
        with self.assertRaises(ContractViolation):
            KeysetCursor(order_columns=("CHANGE_TIME", "ID"), last_values=(1, 2))

    def test_same_second_same_id_not_skipped(self):
        """同秒同ID并列：严格字典序 > 保证 (ct, id) 相同的行不会在下一页重复
        也不会被跳过——唯一键下分页完备。"""
        cur = KeysetCursor(
            order_columns=("CHANGE_TIME", "ID"),
            last_values=("2026-10-18 08:00:00", "A100"),
            unique_verified=True,
        )
        # 同秒更大 ID：必须包含
        self.assertTrue(cur.row_after(("2026-10-18 08:00:00", "A101")))
        # 同秒同 ID（重试/重发同键）：不重复包含（已在上一页）
        self.assertFalse(cur.row_after(("2026-10-18 08:00:00", "A100")))
        # 更晚提交但时间戳早于游标（晚提交早时间戳）：keyset 按 (ct,id) 排序
        # 覆盖不到——该场景必须由 overlap 窗口或变更清单机制兜底，不由 keyset
        # 冒充（这里断言其行为并留给窗口测试覆盖）。
        self.assertFalse(cur.row_after(("2026-10-18 07:59:59", "ZZZ")))

    def test_column_count_mismatch(self):
        cur = KeysetCursor(("A",), (1,), unique_verified=True)
        with self.assertRaises(ContractViolation):
            cur.row_after((1, 2))


class TestSplitNode(unittest.TestCase):
    def test_split_and_complete(self):
        root = SplitNode(TimeWindow(datetime(2026, 1, 1), datetime(2026, 1, 2)))
        root.split(max_depth=2)
        for child in root.children:  # 递归拆第二层：持久树由 runner 逐层推进
            child.split(max_depth=1)
        self.assertFalse(root.all_leaves_complete())
        stats = split_tree_stats(root)
        self.assertEqual(stats["leaves"], 4)
        self.assertEqual(stats["complete"], 0)
        # 只完整一半叶：仍不完整
        for leaf in root.children[0].children:
            leaf.status = "LEAF_COMPLETE"
        self.assertFalse(root.all_leaves_complete())
        for leaf in root.children[1].children:
            leaf.status = "LEAF_COMPLETE"
        self.assertTrue(root.all_leaves_complete())

    def test_min_granularity_exhausted(self):
        root = SplitNode(
            TimeWindow(datetime(2026, 1, 1, 12), datetime(2026, 1, 1, 12, 0, 30))
        )
        root.split()
        self.assertEqual(root.status, "EXHAUSTED")
        self.assertIncomplete_parks(root)

    def assertIncomplete_parks(self, root):  # noqa: N802 - test helper
        self.assertEqual(root.incomplete_leaves(), [root])

    def test_depth_budget(self):
        root = SplitNode(TimeWindow(datetime(2026, 1, 1), datetime(2026, 6, 1)))
        root.split(max_depth=0)
        self.assertEqual(root.status, "EXHAUSTED")
        self.assertIn("深度", root.reason or "")


class TestDag(unittest.TestCase):
    def test_topological_order(self):
        parents = {
            "EMR_INSPECTION_ITEM": ["EMR_INSPECTION"],
            "EMR_INSPECTION_ALLERGY": ["EMR_INSPECTION"],
            "EMR_INSPECTION": [],
        }
        order = build_dag(parents)
        self.assertLess(order.index("EMR_INSPECTION"), order.index("EMR_INSPECTION_ITEM"))

    def test_cycle_rejected(self):
        with self.assertRaises(ContractViolation):
            build_dag({"A": ["B"], "B": ["A"]})

    def test_unknown_dep_rejected(self):
        with self.assertRaises(ContractViolation):
            build_dag({"A": ["GHOST"]})

    def test_parent_failure_blocks_only_children(self):
        parents = {
            "EMR_INSPECTION_ITEM": ["EMR_INSPECTION"],
            "EMR_ADMISSION_RECORD": [],
        }
        blocked = affected_child_groups("EMR_INSPECTION", parents)
        self.assertEqual(blocked, ["EMR_INSPECTION_ITEM"])
        self.assertNotIn("EMR_ADMISSION_RECORD", blocked)


class TestLisRoute(unittest.TestCase):
    def test_before_2023_10_history_only(self):
        sources, reverify = resolve_lis_route(LIS_SEGMENTS, datetime(2023, 5, 1))
        self.assertEqual(sources, ["ods__V_EMR_INSPECTION_TEST"])
        self.assertFalse(reverify)

    def test_q4_2023_overlap_preserved(self):
        sources, reverify = resolve_lis_route(LIS_SEGMENTS, datetime(2023, 11, 15))
        self.assertEqual(
            sources, ["ods__V_EMR_INSPECTION_TEST", "lis__V_EMR_INSPECTION"]
        )
        self.assertTrue(reverify)

    def test_after_2024_primary_only(self):
        sources, reverify = resolve_lis_route(LIS_SEGMENTS, datetime(2025, 6, 1))
        self.assertEqual(sources, ["lis__V_EMR_INSPECTION"])
        self.assertFalse(reverify)

    def test_no_segment_no_fallback(self):
        segs = [{"start_inclusive": "2024-01-01T00:00:00", "end": None, "sources": ["x"]}]
        with self.assertRaises(ContractViolation):
            resolve_lis_route(segs, datetime(2023, 1, 1))


class TestMonthCoverage(unittest.TestCase):
    def test_month_bounds_and_sequence(self):
        self.assertEqual(month_bounds("2025-03"), (date(2025, 3, 1), date(2025, 4, 1)))
        self.assertEqual(
            month_sequence("2025-11", "2026-02"), ["2025-11", "2025-12", "2026-01", "2026-02"]
        )

    def test_scope_unfrozen_returns_empty_not_guess(self):
        self.assertEqual(missing_months_in_scope(None, "2026-06", {"2025-01"}), [])

    def test_missing_months(self):
        missing = missing_months_in_scope("2025-01", "2025-04", {"2025-02", "2025-03"})
        self.assertEqual(missing, ["2025-01", "2025-04"])

    def test_overdue_rules(self):
        from datetime import timezone
        now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        never = MonthCoverageRecord(table="T", business_month="2025-05", route_or_origin="ods")
        self.assertTrue(never.is_overdue(now))  # 从未核：显式欠账
        done = MonthCoverageRecord(
            table="T", business_month="2025-05", route_or_origin="ods",
            last_reconciled_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            cycle_days=30,
        )
        self.assertTrue(done.is_overdue(now))
        fresh = MonthCoverageRecord(
            table="T", business_month="2025-05", route_or_origin="ods",
            last_reconciled_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
            cycle_days=30,
        )
        self.assertFalse(fresh.is_overdue(now))


if __name__ == "__main__":
    unittest.main()
