"""受控装载与对账测试：门禁拒写、版本保护、COMMIT_UNKNOWN、月原子替换、键内容核对。"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.apply_port import (
    ApplyPort,
    ApplyRefused,
    ApplyRequest,
    InMemoryApplyExecutor,
    MonthPublishPlan,
    VersionGuard,
    NO_CHANGE,
    UPDATE,
    CONFLICT,
)
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.readback_types import ColumnMeta
from app.services.reporting_pipeline.reconcile import ReconcileService

META = {
    "ID": ColumnMeta("ID", "VARCHAR"),
    "AMOUNT": ColumnMeta("AMOUNT", "NUMBER", precision=12, scale=2),
    "BODY": ColumnMeta("BODY", "CLOB"),
}


def _manifest(*, complete: bool = True, payload_sha: str | None = None) -> BatchManifest:
    return BatchManifest(
        batch_id="B1", attempt_id="A1", task_id="T", config_version="v1",
        definition_fingerprint=None, source_identity="s", window_fingerprint="w",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=1, valid=1),
        pagination_complete=complete,
        end_reason=EndReason.WINDOW_COMPLETE if complete else EndReason.ROW_CAP,
        shard_count=1, file_count=1, total_bytes=10, schema_version="v",
        type_contract_version="t", payload_sha256=payload_sha or "a" * 64,
    )


def _request(**overrides) -> ApplyRequest:
    base = dict(
        manifest=_manifest(),
        quality_verified=True,
        approval_ref="APPROVAL-1",
        executor_id="sim-apply-1",
        target_object="DBOPER.T",
        allowed_operations=("MERGE",),
        idempotency_key_columns=("ID",),
        rows=({"ID": "K1", "AMOUNT": Decimal("1.00"), "BODY": "x"},),
        column_meta=META,
        version_order="1000",
    )
    base.update(overrides)
    return ApplyRequest(**base)


class TestApplyGates(unittest.TestCase):
    def _port(self) -> ApplyPort:
        return ApplyPort(
            whitelisted_executors=["sim-apply-1"],
            approved_refs={"APPROVAL-1"},
        )

    def test_happy_path_insert(self):
        port = self._port()
        executor = InMemoryApplyExecutor()
        result = port.apply(_request(), executor, target_rows={})
        self.assertTrue(result.committed)
        self.assertIn(("K1",), executor.target)
        self.assertEqual(executor.receipts[0]["manifest_hash"], "a" * 64)

    def test_incomplete_manifest_refused(self):
        port = self._port()
        with self.assertRaises(ApplyRefused) as ctx:
            port.apply(_request(manifest=_manifest(complete=False)),
                       InMemoryApplyExecutor(), target_rows={})
        self.assertIn("分页未完整", str(ctx.exception))

    def test_unapproved_ref_refused(self):
        port = self._port()
        with self.assertRaises(ApplyRefused):
            port.apply(_request(approval_ref="GHOST"),
                       InMemoryApplyExecutor(), target_rows={})

    def test_off_whitelist_executor_refused(self):
        port = self._port()
        executor = InMemoryApplyExecutor()
        executor.executor_id = "rogue"
        with self.assertRaises(ApplyRefused):
            port.apply(_request(), executor, target_rows={})

    def test_unverified_quality_refused(self):
        port = self._port()
        with self.assertRaises(ApplyRefused):
            port.apply(_request(quality_verified=False),
                       InMemoryApplyExecutor(), target_rows={})

    def test_commit_unknown_refused_replay(self):
        port = self._port()
        executor = InMemoryApplyExecutor(force_unknown=True)
        with self.assertRaises(ApplyRefused) as ctx:
            port.apply(_request(), executor, target_rows={})
        self.assertIn("COMMIT_UNKNOWN", str(ctx.exception))

    def test_fence_validation_enforced(self):
        def failing_validator(resource, token):
            raise ApplyRefused("围栏不匹配")

        port = ApplyPort(
            whitelisted_executors=["sim-apply-1"],
            approved_refs={"APPROVAL-1"},
            lease_validator=failing_validator,
        )
        with self.assertRaises(ApplyRefused) as ctx:
            port.apply(_request(lease_resource="target:DBOPER.T", fencing_token=1),
                       InMemoryApplyExecutor(), target_rows={})
        self.assertIn("围栏", str(ctx.exception))


class TestVersionGuard(unittest.TestCase):
    def test_old_version_cannot_override(self):
        guard = VersionGuard()
        guard.register_applied(("K1",), "1000")
        # 版本落后 → 冲突隔离，不覆盖
        verdict = guard.check(("K1",), "900")
        self.assertEqual(verdict, CONFLICT)
        self.assertEqual(guard.check(("K1",), "1000"), NO_CHANGE)
        self.assertEqual(guard.check(("K1",), "1100"), UPDATE)

    def test_hash_is_not_version_order(self):
        """无已核版本顺序时，同键不同内容 → CONFLICT（hash/采集时间不作顺序）。"""
        guard = VersionGuard()
        guard.register_applied(("K1",), "hash-aaaa")
        verdict = guard.check(("K1",), None)
        self.assertEqual(verdict, CONFLICT)


class TestMonthReplace(unittest.TestCase):
    def test_replace_month_requires_explicit_scope(self):
        port = ApplyPort(
            whitelisted_executors=["sim-apply-1"], approved_refs={"APPROVAL-1"}
        )
        with self.assertRaises(ApplyRefused) as ctx:
            port.apply(
                _request(mode="REPLACE_MONTH"),
                InMemoryApplyExecutor(),
                target_rows={},
            )
        self.assertIn("显式发布范围键清单", str(ctx.exception))

    def test_replace_month_atomic_delete_and_insert(self):
        """月替换：同事务删发布范围+插 stage；目标原有范围外键保留。"""
        port = ApplyPort(
            whitelisted_executors=["sim-apply-1"], approved_refs={"APPROVAL-1"}
        )
        executor = InMemoryApplyExecutor()
        # 既有目标：OLD1 在发布范围内（应被替换），KEEP 在范围外（应保留）
        executor.target.update({
            ("OLD1",): {"ID": "OLD1", "AMOUNT": Decimal("9.99"), "BODY": "旧"},
            ("KEEP",): {"ID": "KEEP", "AMOUNT": Decimal("1.00"), "BODY": "范围外保留"},
        })
        request = _request(
            mode="REPLACE_MONTH",
            replace_scope_keys=(("OLD1",),),
            rows=(
                {"ID": "NEW1", "AMOUNT": Decimal("1.00"), "BODY": "新"},
                {"ID": "NEW2", "AMOUNT": Decimal("2.00"), "BODY": "新2"},
            ),
        )
        result = port.apply(request, executor, target_rows=dict(executor.target))
        self.assertTrue(result.committed)
        final_keys = set(executor.target)
        self.assertNotIn(("OLD1",), final_keys)      # 发布范围内旧键被同事务删除
        self.assertIn(("KEEP",), final_keys)          # 范围外键保留（双源/范围保护）
        self.assertIn(("NEW1",), final_keys)
        self.assertIn(("NEW2",), final_keys)
        self.assertEqual(executor.receipts[0]["mode"], "REPLACE_MONTH")

    def test_month_publish_plan_readiness(self):
        """发布检查单：stage 未完整/隔离未解释/无写锁 → 不可发布。"""
        not_ready = MonthPublishPlan(
            table="EMR_DOC_ORDER_CHECK", business_month="2025-03",
            route_origins=("ods",),
            stage_complete=False,
            quality_unexplained_isolated=True,
            scope_keys=(),
        )
        self.assertFalse(not_ready.can_publish())
        ready = MonthPublishPlan(
            table="EMR_DOC_ORDER_CHECK", business_month="2025-03",
            route_origins=("ods__V_TEST", "lis__V"),
            stage_complete=True,
            quality_unexplained_isolated=False,
            scope_keys=(("K1",), ("K2",)),
            writer_lease_resource="target:DBOPER.EMR_DOC_ORDER_CHECK",
        )
        checks = ready.readiness()
        self.assertTrue(ready.can_publish())
        self.assertFalse(checks["approved_atomic_replace"])  # 尚未执行，不能预标


class TestReconcile(unittest.TestCase):
    def _service(self) -> ReconcileService:
        return ReconcileService(("ID",), META)

    def test_missing_and_extra_keys(self):
        service = self._service()
        source = [{"ID": "K1", "AMOUNT": Decimal("1.00"), "BODY": "a"}]
        target = {("K2",): {"ID": "K2", "AMOUNT": Decimal("1.00"), "BODY": "a"}}
        result = service.compare(source, target)
        self.assertEqual(result.keys_missing_in_target, [("K1",)])
        self.assertEqual(result.keys_extra_in_target, [("K2",)])
        self.assertFalse(result.complete)

    def test_content_diff_decimal_and_clob(self):
        service = self._service()
        source = [{"ID": "K1", "AMOUNT": Decimal("1.00"), "BODY": "line1 "}]
        target = {("K1",): {"ID": "K1", "AMOUNT": Decimal("1.01"), "BODY": "line1 "}}
        result = service.compare(source, target)
        self.assertEqual(len(result.content_diffs), 1)
        self.assertEqual(result.content_diffs[0]["diffs"][0]["column"], "AMOUNT")
        # CLOB 尾随空格差异必须被捕获（不统一 rstrip）
        target2 = {("K1",): {"ID": "K1", "AMOUNT": Decimal("1.00"), "BODY": "line1"}}
        result2 = service.compare(source, target2)
        self.assertEqual(result2.content_diffs[0]["diffs"][0]["column"], "BODY")

    def test_counts_equal_is_not_completeness(self):
        verdict = ReconcileService.counts_equal_is_not_completeness(
            {("A",), ("B",)}, {("B",), ("C",)}
        )
        self.assertTrue(verdict["counts_equal"])
        self.assertFalse(verdict["key_sets_equal"])
        self.assertEqual(verdict["missing_in_target"], [("A",)])
        self.assertEqual(verdict["extra_in_target"], [("C",)])

    def test_summary_note_no_extrapolation(self):
        service = self._service()
        result = service.compare([], {})
        self.assertTrue(result.complete)
        self.assertIn("不外推", result.summary()["note"])


if __name__ == "__main__":
    unittest.main()
