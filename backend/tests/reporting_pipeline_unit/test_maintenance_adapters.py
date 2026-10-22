"""回归覆盖：T+1 适配器的载荷完整性、类型保真和限量证据。"""

from __future__ import annotations

import hashlib
import os
import stat
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.adapters.datax_runner import (
    DataXRunner,
    ProcessResult,
)
from app.services.reporting_pipeline.adapters.python_reader import (
    ControlledConnectorRowSource,
)
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    ContractViolation,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.durable_staging import (
    DurableFileStageStore,
    encode_json_rows,
)
from app.services.reporting_pipeline.planner import TimeWindow


def _manifest(rows: int, payload: bytes) -> BatchManifest:
    return BatchManifest(
        batch_id="B1", attempt_id="A1", task_id="T1", config_version="v1",
        definition_fingerprint=None, source_identity="ods__V",
        window_fingerprint="win:2026-10-19T00:00:00/2026-10-20T00:00:00",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=rows, valid=rows),
        pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=len(payload), schema_version="v1",
        type_contract_version="v1", payload_sha256=hashlib.sha256(payload).hexdigest(),
    )


class _ProcessRunner:
    def __init__(self, stdout: str):
        self.stdout = stdout

    def run(self, argv, *, timeout_seconds):
        return ProcessResult(0, self.stdout, "")


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.offset = 0
        self.limit = None

    def execute(self, sql, params):
        self.limit = int(sql)
        self.offset = 0

    def fetchmany(self, size):
        end = min(self.offset + size, self.limit, len(self.rows))
        result = self.rows[self.offset:end]
        self.offset = end
        return result

    def close(self):
        pass


class _Provider:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class TestDurableStageIntegrity(unittest.TestCase):
    def test_actual_payload_row_count_must_match_metadata_and_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A1")
            payload = b'["one"]\n'
            store.write_chunk("B1", "A1", "c1", payload, row_count=2)

            with self.assertRaises(ContractViolation):
                store.mark_complete_against_manifest(
                    "B1", "A1", _manifest(2, payload),
                    source_identity="ods__V", definition_fingerprint=None,
                )

    def test_stream_writer_rejects_mismatched_row_count(self):
        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A1")
            with self.assertRaises(ContractViolation):
                store.write_chunk_stream("B1", "A1", "c1", [["one"]], 2)

    def test_typed_values_round_trip_and_legacy_json_stays_readable(self):
        with tempfile.TemporaryDirectory() as root:
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A1")
            original = {
                "decimal": Decimal("123.400"),
                "date": date(2026, 10, 22),
                "timestamp": datetime(2026, 10, 22, 12, 30, 1, 123456,
                                       tzinfo=timezone.utc),
                "binary": b"\x00\xff",
                "nested": {"$reporting_pipeline_value_v1": "literal"},
            }
            info = store.write_json_rows("B1", "A1", "c1", [original])
            self.assertEqual(info.row_count, 1)
            decoded = list(store.iter_chunk_rows("B1", "A1"))[0]
            self.assertEqual(decoded, original)
            self.assertIsInstance(decoded["decimal"], Decimal)
            self.assertIsInstance(decoded["date"], date)
            self.assertIsInstance(decoded["timestamp"], datetime)
            self.assertIsInstance(decoded["binary"], bytes)

            store.begin_attempt("B1", "A2")
            legacy = b'{"id":1,"text":"kept"}\n'
            store.write_chunk("B1", "A2", "c1", legacy, row_count=1)
            self.assertEqual(
                list(store.iter_chunk_rows("B1", "A2")),
                [{"id": 1, "text": "kept"}],
            )

    def test_unknown_scalar_type_is_rejected(self):
        class UnknownValue:
            pass

        with self.assertRaises(ContractViolation):
            encode_json_rows([[UnknownValue()]])

    @unittest.skipIf(os.name == "nt", "Windows permissions are enforced by deployment ACLs")
    def test_new_stage_directories_and_files_are_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "new-parent" / "stage"
            store = DurableFileStageStore(root)
            store.begin_attempt("B1", "A1")
            payload = encode_json_rows([["x"]])
            store.write_json_rows("B1", "A1", "c1", [["x"]])
            store.mark_complete_against_manifest(
                "B1", "A1", _manifest(1, payload),
                source_identity="ods__V", definition_fingerprint=None,
            )

            attempt = root / "B1" / "A1"
            for directory in (root.parent, root, root / "B1", attempt):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            for filename in (
                "chunk-c1.bin", "chunk-c1.meta.json", "complete.json",
            ):
                self.assertEqual(
                    stat.S_IMODE((attempt / filename).stat().st_mode), 0o600
                )

    @unittest.skipIf(os.name == "nt", "Windows permissions are enforced by deployment ACLs")
    def test_existing_root_mode_is_not_changed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "existing-stage"
            root.mkdir()
            root.chmod(0o500)
            before = stat.S_IMODE(root.stat().st_mode)
            DurableFileStageStore(root)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), before)


class TestAdapterCompletenessEvidence(unittest.TestCase):
    def test_datax_dirty_metric_without_read_write_counts_is_incomplete(self):
        job = {
            "job": {"content": [{"reader": {"parameter": {"querySql": [
                "SELECT ID FROM T WHERE DT >= TO_DATE('2026-10-01','YYYY-MM-DD') "
                "AND DT < TO_DATE('2026-10-02','YYYY-MM-DD')"
            ]}}}]}
        }
        runner = DataXRunner(_ProcessRunner("读写失败总数 : 0\n"))
        result = runner.run_capture(job, "A1")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "METRICS_MISSING")

    def test_connector_passes_exact_sql_limit_requested_by_completeness_probe(self):
        rows = [(i,) for i in range(20)]
        cursor = _Cursor(rows)
        built_limits = []

        def query_builder(window, keyset, sql_limit):
            built_limits.append(sql_limit)
            return str(sql_limit), ()

        source = ControlledConnectorRowSource(
            physical_source="ods__V", provider=_Provider(cursor),
            query_builder=query_builder, page_size=5,
        )
        page = source.fetch_page(
            TimeWindow(datetime(2026, 10, 1), datetime(2026, 10, 2)),
            limit_rows=13,
        )
        self.assertEqual(built_limits, [14])
        self.assertEqual(len(page.rows), 13)
        self.assertTrue(page.has_more)


if __name__ == "__main__":
    unittest.main()
