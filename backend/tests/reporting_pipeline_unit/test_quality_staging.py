"""暂存与质量测试：类型规整契约、组隔离继续、守恒、旧stage不覆新。"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import (
    ContractViolation,
    EndReason,
    RowClassification,
    BatchManifest,
)
from app.services.reporting_pipeline.quality import (
    DUPLICATE_CONFLICT,
    PENDING_PARENT,
    QUARANTINED,
    VALID,
    ByteLengthRule,
    EnumRule,
    PrecisionRule,
    QualityService,
    RequiredRule,
    verify_batch_conservation,
)
from app.services.reporting_pipeline.readback_types import (
    ColumnMeta,
    FloatComparisonRefused,
    byte_length,
    content_fingerprint,
    normalize_for_comparison,
    row_diff,
    values_equal,
)
from app.services.reporting_pipeline.staging import (
    StageStore,
    StagedSlice,
)


class TestReadbackTypes(unittest.TestCase):
    def test_char_rstrip_only_for_char_family(self):
        char_meta = ColumnMeta("CODE", "CHAR", char_length=10)
        vc_meta = ColumnMeta("NAME", "VARCHAR")
        # CHAR 右填充等价
        self.assertEqual(normalize_for_comparison("A100  ", char_meta), "A100")
        # VARCHAR 保留尾部空白（有意义空白不丢）
        self.assertEqual(normalize_for_comparison("报告 ", vc_meta), "报告 ")
        self.assertTrue(values_equal("A100   ", "A100", char_meta))
        self.assertFalse(values_equal("报告 ", "报告", vc_meta))

    def test_decimal_exact_no_float(self):
        num = ColumnMeta("AMOUNT", "NUMBER", precision=18, scale=2)
        self.assertTrue(values_equal(Decimal("120"), Decimal("120.00"), num))
        self.assertTrue(values_equal(120, Decimal("120.00"), num))
        self.assertFalse(values_equal(Decimal("120.01"), Decimal("120.02"), num))
        # 大整数差异不因 float 丢精度误判相等（gap_exec 教训）
        self.assertFalse(values_equal(
            Decimal("12345678901234567"), Decimal("12345678901234568"), num
        ))
        with self.assertRaises(FloatComparisonRefused):
            values_equal(0.1, Decimal("0.1"), num)

    def test_time_precision_not_normalized(self):
        ts = ColumnMeta("TS", "TIMESTAMP")
        dt_col = ColumnMeta("D", "DATE")
        t1 = datetime(2026, 10, 18, 8, 0, 0, 123456)
        t2 = datetime(2026, 10, 18, 8, 0, 0)
        self.assertFalse(values_equal(t1, t2, ts))
        self.assertTrue(values_equal(date(2026, 10, 18), date(2026, 10, 18), dt_col))

    def test_unicode_byte_length(self):
        self.assertEqual(byte_length("病案首页"), 12)  # 4 CJK × 3 bytes
        self.assertEqual(byte_length("abc"), 3)

    def test_content_fingerprint_stability_and_exclusions(self):
        metas = [
            ColumnMeta("ID", "VARCHAR"),
            ColumnMeta("BODY", "CLOB"),
            ColumnMeta("QUERY_TIME", "TIMESTAMP", dynamic_query_time=True),
        ]
        row_a = {"ID": "1", "BODY": "line1\nline2 ", "QUERY_TIME": "2026-10-19 01:00:00"}
        row_b = {"ID": "1", "BODY": "line1\nline2 ", "QUERY_TIME": "2026-10-19 09:00:00"}
        # 查询时刻不同、业务内容相同 → 指纹一致
        self.assertEqual(content_fingerprint(row_a, metas), content_fingerprint(row_b, metas))
        row_c = {"ID": "1", "BODY": "line1\nline2", "QUERY_TIME": "x"}
        self.assertNotEqual(content_fingerprint(row_a, metas), content_fingerprint(row_c, metas))

    def test_row_diff_clob_decimal(self):
        metas = [
            ColumnMeta("AMOUNT", "NUMBER", precision=18, scale=2),
            ColumnMeta("BODY", "CLOB"),
            ColumnMeta("FEE_TIME", "TIMESTAMP"),
        ]
        src = {"AMOUNT": Decimal("12.30"), "BODY": "a b", "FEE_TIME": datetime(2026, 1, 1, 1, 2, 3, 4)}
        same = {"AMOUNT": Decimal("12.3"), "BODY": "a b", "FEE_TIME": datetime(2026, 1, 1, 1, 2, 3, 4)}
        self.assertEqual(row_diff(src, same, metas), [])
        diff = {"AMOUNT": Decimal("12.31"), "BODY": "a b", "FEE_TIME": datetime(2026, 1, 1, 1, 2, 3, 4)}
        self.assertEqual([d["column"] for d in row_diff(src, diff, metas)], ["AMOUNT"])
        diff2 = {"AMOUNT": Decimal("12.30"), "BODY": "a b", "FEE_TIME": datetime(2026, 1, 1, 1, 2, 3)}
        self.assertEqual([d["column"] for d in row_diff(src, diff2, metas)], ["FEE_TIME"])


def _manifest(rows_read: int, *, quarantined: int = 0, attempt="A1") -> BatchManifest:
    return BatchManifest(
        batch_id="B1", attempt_id=attempt, task_id="T", config_version="v1",
        definition_fingerprint=None, source_identity="s", window_fingerprint="w",
        source_visibility_cutoff="cut",
        rows=RowClassification(
            source_read_rows=rows_read, valid=rows_read - quarantined,
            quarantined=quarantined,
        ),
        pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=99, schema_version="v",
        type_contract_version="t", payload_sha256="f" * 64,
    )


class TestQualityIsolationContinue(unittest.TestCase):
    def _service(self) -> QualityService:
        return QualityService(
            group_key_columns=("PATIENT_ID", "VISIT_ID"),
            parent_key_columns=("PATIENT_ID",),
            column_meta={
                "PATIENT_ID": ColumnMeta("PATIENT_ID", "VARCHAR"),
                "VISIT_ID": ColumnMeta("VISIT_ID", "VARCHAR"),
                "DIAG": ColumnMeta("DIAG", "VARCHAR"),
                "AMOUNT": ColumnMeta("AMOUNT", "NUMBER", precision=12, scale=2),
            },
        )

    def test_bad_group_isolated_independent_groups_continue(self):
        service = self._service()
        rows = [
            {"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": "ok", "AMOUNT": Decimal("1.00")},
            {"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": None, "AMOUNT": Decimal("2.00")},  # 坏组
            {"PATIENT_ID": "P2", "VISIT_ID": "1", "DIAG": "ok", "AMOUNT": Decimal("3.00")},   # 独立合法组
        ]
        outcome = service.verify(
            rows,
            rules=[RequiredRule(columns=("DIAG", "AMOUNT"))],
            known_parent_keys={("P1",), ("P2",)},
        )
        self.assertEqual(outcome.classifications[0], QUARANTINED)
        self.assertEqual(outcome.classifications[1], QUARANTINED)
        self.assertEqual(outcome.classifications[2], VALID)
        self.assertIn(("P2", "1"), outcome.valid_group_keys)
        self.assertIn(("P1", "1"), outcome.quarantined_group_keys)
        self.assertTrue(outcome.conservation_ok(len(rows)))
        self.assertIsNotNone(outcome.ticket_hint)

    def test_missing_parent_pending_not_quarantined(self):
        service = self._service()
        rows = [{"PATIENT_ID": "P9", "VISIT_ID": "1", "DIAG": "ok", "AMOUNT": Decimal("1.00")}]
        outcome = service.verify(
            rows, rules=[RequiredRule(columns=("DIAG",))],
            known_parent_keys={("P1",)},
        )
        self.assertEqual(outcome.classifications[0], PENDING_PARENT)
        self.assertNotIn(("P9", "1"), outcome.quarantined_group_keys)

    def test_same_key_different_content_conflict(self):
        service = self._service()
        rows = [
            {"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": "A", "AMOUNT": Decimal("1.00")},
            {"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": "B", "AMOUNT": Decimal("2.00")},
        ]
        outcome = service.verify(rows, rules=[], known_parent_keys={("P1",)})
        self.assertEqual(outcome.classifications[0], QUARANTINED)
        self.assertTrue(
            any(i.rule == DUPLICATE_CONFLICT for i in outcome.issues)
        )

    def test_byte_length_unicode(self):
        service = self._service()
        rows = [{"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": "长" * 5, "AMOUNT": Decimal("1.00")}]
        outcome = service.verify(
            rows, rules=[ByteLengthRule(column="DIAG", max_bytes=6)],  # 5 CJK=15 字节
            known_parent_keys={("P1",)},
        )
        self.assertEqual(outcome.classifications[0], QUARANTINED)
        self.assertTrue(any(i.rule == "BYTE_LENGTH" for i in outcome.issues))

    def test_precision_rule(self):
        service = self._service()
        rows = [{"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": "x", "AMOUNT": Decimal("1.001")}]
        outcome = service.verify(
            rows, rules=[PrecisionRule(column="AMOUNT", precision=12, scale=2)],
            known_parent_keys={("P1",)},
        )
        self.assertEqual(outcome.classifications[0], QUARANTINED)

    def test_enum_rule(self):
        service = self._service()
        rows = [{"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": "X", "AMOUNT": Decimal("1.00")}]
        outcome = service.verify(
            rows, rules=[EnumRule(column="DIAG", allowed=("A", "B"))],
            known_parent_keys={("P1",)},
        )
        self.assertEqual(outcome.classifications[0], QUARANTINED)

    def test_batch_conservation(self):
        service = self._service()
        rows = [
            {"PATIENT_ID": "P1", "VISIT_ID": "1", "DIAG": None, "AMOUNT": Decimal("1.00")},
            {"PATIENT_ID": "P2", "VISIT_ID": "1", "DIAG": "ok", "AMOUNT": Decimal("2.00")},
        ]
        outcome = service.verify(
            rows, rules=[RequiredRule(columns=("DIAG",))],
            known_parent_keys={("P1",), ("P2",)},
        )
        manifest = _manifest(2, quarantined=1)
        report = verify_batch_conservation(manifest, outcome, staged_rows=2)
        self.assertTrue(report["ok"], report)
        mismatch = _manifest(3, quarantined=1)
        report2 = verify_batch_conservation(mismatch, outcome, staged_rows=2)
        self.assertFalse(report2["ok"])


class TestStageStore(unittest.TestCase):
    def _slice(self, slice_id: str, rows: list, sha: str) -> StagedSlice:
        return StagedSlice(
            slice_id=slice_id, rows=rows,
            row_bytes=sum(byte_length(str(r)) for r in rows),
            payload_sha256=sha,
        )

    def test_incomplete_manifest_cannot_mark_complete(self):
        store = StageStore()
        attempt = store.begin_attempt("B1", "A1")
        attempt.add_slice(self._slice("S1", [(1,), (2,)], "ab" * 32))
        manifest = _manifest(2)
        manifest.pagination_complete = False  # 缺分片
        with self.assertRaises(ContractViolation) as ctx:
            store.mark_complete_against_manifest(manifest)
        self.assertIn("分页未完整", str(ctx.exception))

    def test_row_or_shard_mismatch_rejected(self):
        store = StageStore()
        attempt = store.begin_attempt("B1", "A1")
        attempt.add_slice(self._slice("S1", [(1,)], "ab" * 32))
        with self.assertRaises(ContractViolation):
            store.mark_complete_against_manifest(_manifest(2))

    def test_old_attempt_superseded_not_overriding(self):
        """旧 stage 不覆盖新内容：装载只选最新 COMPLETE，旧的显式 SUPERSEDED。"""
        import hashlib as _h
        store = StageStore()
        for attempt_id, marker in (("A1", b"old"), ("A2", b"new")):
            attempt = store.begin_attempt("B1", attempt_id)
            payload = marker * 16
            attempt.add_slice(StagedSlice(
                slice_id="S1", rows=[(marker,)], row_bytes=len(marker),
                payload_sha256=_h.sha256(payload).hexdigest(),
            ))
            manifest = _manifest(1, attempt=attempt_id)
            manifest.payload_sha256 = _h.sha256(
                bytes.fromhex(_h.sha256(payload).hexdigest())
            ).hexdigest()
            store.mark_complete_against_manifest(manifest)
        chosen = store.select_complete("B1")
        self.assertEqual(chosen.attempt_id, "A2")
        states = {a.attempt_id: a.state for a in store.attempts_of("B1")}
        self.assertEqual(states["A1"], "SUPERSEDED")
        self.assertEqual(states["A2"], "COMPLETE")

    def test_duplicate_slice_rejected(self):
        store = StageStore()
        attempt = store.begin_attempt("B1", "A1")
        attempt.add_slice(self._slice("S1", [], "ab" * 32))
        with self.assertRaises(ContractViolation):
            attempt.add_slice(self._slice("S1", [], "ab" * 32))

    def test_no_complete_attempts_rejects_load(self):
        store = StageStore()
        store.begin_attempt("B1", "A1")  # 只有 PARTIAL
        with self.assertRaises(ContractViolation):
            store.select_complete("B1")


if __name__ == "__main__":
    unittest.main()
