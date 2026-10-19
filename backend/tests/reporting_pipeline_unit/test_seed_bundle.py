"""种子包装载测试：77项不漏不重、双源/未提供单列、关联一致、未知不可变READY。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import (
    Applicability,
    ReadinessLayer,
    summarize_verdicts,
)
from app.services.reporting_pipeline.seed_loader import (
    DATETIME_DEPENDENCY_TABLES,
    load_seed_bundle,
    validate_bundle,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = (
    _REPO_ROOT / "开发起步包" / "output_r189" / "r189-20261015-upload-audit"
    / "daily_t1_20261015" / "python_datax_execution_20261019"
)


class TestSeedBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_seed_bundle(PACKAGE_DIR)

    def test_package_dir_exists(self):
        self.assertTrue(PACKAGE_DIR.exists(), f"执行包目录缺失: {PACKAGE_DIR}")

    def test_77_unique_no_missing_no_duplicate(self):
        tables = [t.canonical_table for t in self.bundle.tasks]
        self.assertEqual(len(tables), 77)
        self.assertEqual(len(set(tables)), 77)

    def test_all_disabled_unknown(self):
        for task in self.bundle.tasks:
            self.assertFalse(task.enabled, task.canonical_table)

    def test_no_production_layer_ready(self):
        """未知不能变READY：种子期生产层 READY 数必须为 0。"""
        summary = summarize_verdicts(self.bundle.tasks)
        for layer in (
            ReadinessLayer.READ_READY,
            ReadinessLayer.STAGE_READY,
            ReadinessLayer.APPLY_READY,
            ReadinessLayer.REPORT_READY,
        ):
            self.assertEqual(summary[layer.value]["READY"], 0, layer)
        self.assertEqual(summary[ReadinessLayer.CONFIG_VALID.value]["READY"], 77)

    def test_dual_source_separated(self):
        dual = self.bundle.dual_source_tasks()
        self.assertEqual(len(dual), 4)
        self.assertEqual(
            {t.canonical_table for t in dual},
            {"EMR_INSPECTION", "EMR_INSPECTION_IMAGE",
             "EMR_INSPECTION_ALLERGY", "EMR_INSPECTION_ITEM"},
        )
        for task in dual:
            self.assertTrue(task.associations.route_policy_ref, task.canonical_table)

    def test_not_provided_pending_applicability_separated(self):
        pending = self.bundle.not_provided_tasks()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].canonical_table, "EMR_NURSE_PLAN")
        self.assertEqual(
            pending[0].applicability, Applicability.WAITING_BUSINESS_CONFIRMATION
        )
        self.assertEqual(pending[0].source_candidates, [])

    def test_source_groups_frozen(self):
        groups = self.bundle.source_group_counts()
        self.assertLessEqual(len(groups), 11)
        self.assertIn("ods", groups)
        self.assertIn("lis", groups)

    def test_rescan_tables_associated(self):
        rescan = self.bundle.rescan_tasks()
        self.assertEqual(
            {t.canonical_table for t in rescan},
            {"EMR_DOC_ORDER_CHECK", "EMR_IN_FEE_INFO_CHILD"},
        )

    def test_datetime_dependency_registered(self):
        dep = self.bundle.datetime_dependency_tasks()
        self.assertEqual(
            {t.canonical_table for t in dep}, set(DATETIME_DEPENDENCY_TABLES)
        )
        for task in dep:
            self.assertEqual(
                task.associations.datetime_dependency_ticket, "E01-DATETIME-DEPENDENCY"
            )

    def test_profiles_all_pending_measurement(self):
        for table, profile in self.bundle.profiles.items():
            self.assertEqual(
                profile.get("measurement_state"), "PENDING_CURRENT_ROUTE_MEASUREMENT",
                table,
            )
            self.assertFalse(profile.get("verified_for_production", False), table)

    def test_validate_bundle_passes_offline(self):
        report = validate_bundle(self.bundle)
        self.assertTrue(report["validation"]["structure_ok"], report["validation"])
        self.assertEqual(report["validation"]["ready_violations"], [])
        self.assertTrue(report["offline"])
        counts = report["counts"]
        self.assertEqual(counts["canonical_items"], 77)
        self.assertEqual(counts["not_provided_pending_applicability"], ["EMR_NURSE_PLAN"])

    def test_writer_snapshot_pending_not_assumed(self):
        report = self.bundle.inventory_report()
        self.assertFalse(report["writer_handoff"]["snapshot_captured"])
        self.assertEqual(
            report["writer_handoff"]["state"],
            "LIVE_SNAPSHOT_REQUIRED_AT_E01_AND_REFRESH_AT_CUTOVER",
        )

    def test_credentials_not_tmp_env(self):
        report = self.bundle.inventory_report()
        self.assertEqual(
            report["long_lived_credentials"]["policy"],
            "APPROVED_SECRET_STORE_REF_NOT_TMP_ENV",
        )


if __name__ == "__main__":
    unittest.main()
