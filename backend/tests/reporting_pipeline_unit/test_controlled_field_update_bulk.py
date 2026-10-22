"""Pure logic tests for the bounded array-DML transport."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys

import pytest

from app.services.reporting_pipeline import controlled_field_update as core


ROOT = Path(__file__).resolve().parents[3]
BULK_PATH = (
    ROOT
    / "开发起步包"
    / "output_r189"
    / "r189-20261015-upload-audit"
    / "specialty_ods_view_audit_20261021"
    / "field_update_apply_20261021"
    / "full_history_sync_20261021"
    / "bulk_field_transport.py"
)
SPEC = importlib.util.spec_from_file_location("r189_bulk_transport_test", BULK_PATH)
assert SPEC is not None and SPEC.loader is not None
bulk = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bulk
SPEC.loader.exec_module(bulk)

NOW = datetime(2026, 10, 21, 7, 0, tzinfo=timezone.utc)
RECORD_ID = "49557032X|bulk-001"


def stay_change(*, record_id=RECORD_ID, before=None, after=Decimal("3")):
    return core.FieldChange(
        "HOME_STAY",
        record_id,
        {"INPATIENT_DAY": before},
        {"INPATIENT_DAY": after},
    )


def batch_for(*changes, operation_id="bulk-op-001"):
    return core.UpdateBatch(
        operation_id=operation_id,
        approval_ref="bulk-approval-001",
        changes=tuple(changes),
        backup_ref="/opt/data-asset/evidence/bulk/before.json",
        backup_sha256="a" * 64,
        source_sha256="b" * 64,
        fencing_token=21,
    )


def authority_for(batch):
    executor = {
        "enabled": True,
        "executor_code": core.EXECUTOR_CODE,
        "execution_mode": "controlled_field_update",
        "target_system_code": "qianzhiji_874",
        "target_source_code": "dboper_orcl",
        "require_approval": True,
    }
    approval = {
        "valid": True,
        "expires_at": NOW + timedelta(minutes=15),
        "approval_ref": batch.approval_ref,
        "executor_code": core.EXECUTOR_CODE,
        "target": core.TARGET,
        "manifest_hash": batch.manifest_hash,
        "backup_sha256": batch.backup_sha256,
        "operations": ("UPDATE",),
        "groups": tuple({change.group for change in batch.changes}),
        "max_changes": len(batch.changes),
    }
    return core.PlatformFieldUpdateAuthority(
        lambda code: executor,
        lambda ref, code: approval,
        now=lambda: NOW,
    )


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.executed = []
        self.executemany_calls = []
        self.input_sizes = []
        self.last_sql = ""
        self.closed = False

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.executed.append((sql, params))
        if sql.startswith("INSERT INTO DBOPER.ASSET_APPLY_RECEIPTS"):
            self.connection.receipt_written = True
            self.connection.pending_manifest = params["manifest"]
            self.connection.pending_affected = params["affected"]

    def fetchone(self):
        if "SYS_CONTEXT('USERENV','SESSION_USER')" in self.last_sql:
            return ("DBOPER", "DBOPER")
        if "FROM all_tab_columns" in self.last_sql:
            return (6,)
        if "FROM DBOPER.ASSET_APPLY_RECEIPTS WHERE OPERATION_ID" in self.last_sql:
            receipt = self.connection.receipt
            return (
                (receipt["MANIFEST_HASH"], receipt["ROWS_AFFECTED"])
                if receipt
                else None
            )
        return None

    def setinputsizes(self, **sizes):
        self.input_sizes.append(sizes)

    def executemany(self, sql, rows, *, arraydmlrowcounts=False):
        self.last_sql = sql
        self.executemany_calls.append((sql, list(rows), arraydmlrowcounts))
        if self.connection.executemany_error:
            raise RuntimeError("simulated array DML error")

    def getarraydmlrowcounts(self):
        return self.connection.array_counts

    def fetchall(self):
        if not self.last_sql.startswith("SELECT ID,"):
            return []
        fields = self.last_sql.split("SELECT ID,", 1)[1].split(" FROM DBOPER.", 1)[0].split(",")
        return [
            (
                record_id,
                *(
                    self.connection.actual[record_id].get(field)
                    for field in fields
                ),
            )
            for record_id in sorted(self.connection.actual)
        ]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        changes,
        *,
        array_counts=None,
        executemany_error=False,
        readback_override=None,
        receipt=None,
    ):
        self.autocommit = False
        self.dsn = "10.10.8.74:1521/orcl"
        self.call_timeout = 1000
        self.transaction_in_progress = False
        self.cursors = []
        self.array_counts = array_counts
        self.executemany_error = executemany_error
        self.readback_override = readback_override or {}
        self.receipt = receipt
        self.receipt_written = False
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.actual = {}
        for change in changes:
            self.actual.setdefault(change.record_id, {}).update(change.after)
        for record_id, values in self.readback_override.items():
            self.actual[record_id].update(values)
        if self.array_counts is None:
            self.array_counts = [1] * len(changes)

    def cursor(self):
        cursor = FakeCursor(self)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1
        if self.receipt_written:
            self.receipt = {
                "MANIFEST_HASH": self.pending_manifest,
                "ROWS_AFFECTED": self.pending_affected,
            }

    def rollback(self):
        self.rollbacks += 1
        self.receipt_written = False

    def close(self):
        self.closed = True


def make_transport(changes, **connection_options):
    connection = FakeConnection(changes, **connection_options)
    return connection, bulk.BatchedOracleFieldUpdateTransport(core, connection, changes)


def make_updater(batch, transport):
    return core.ControlledFieldUpdater(
        authority_for(batch),
        transport,
        backup_verifier=lambda candidate: True,
        lease_validator=lambda candidate: True,
        audit=lambda candidate, result: None,
    )


def test_array_update_preserves_old_value_guard_and_null_numeric_bind_types():
    change = stay_change(before=None, after=Decimal("3"))
    batch = batch_for(change)
    connection, transport = make_transport(batch.changes)
    result = make_updater(batch, transport).execute(batch)

    assert result.state == "COMMITTED"
    dml_cursor = next(cursor for cursor in connection.cursors if cursor.executemany_calls)
    update_sql, rows, arraydmlrowcounts = dml_cursor.executemany_calls[0]
    assert "WHERE ID=:record_id" in update_sql
    assert "INPATIENT_DAY=:old_0" in update_sql
    assert "INPATIENT_DAY IS NULL AND :old_0 IS NULL" in update_sql
    assert rows == [
        {"record_id": RECORD_ID, "old_0": None, "new_0": Decimal("3")}
    ]
    assert arraydmlrowcounts is True
    import oracledb

    assert dml_cursor.input_sizes == [
        {
            "record_id": 100,
            "old_0": oracledb.DB_TYPE_NUMBER,
            "new_0": oracledb.DB_TYPE_NUMBER,
        }
    ]
    assert connection.commits == 1
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    "options",
    [
        {"array_counts": [0]},
        {"executemany_error": True},
    ],
)
def test_array_zero_or_exception_rolls_back_core_batch(options):
    change = stay_change()
    batch = batch_for(change)
    connection, transport = make_transport(batch.changes, **options)
    with pytest.raises(core.UpdateRefused):
        make_updater(batch, transport).execute(batch)
    assert connection.rollbacks == 1
    assert connection.commits == 0
    assert connection.receipt_written is False


def test_bulk_actual_readback_mismatch_rolls_back_core_batch():
    change = stay_change(after=Decimal("3"))
    batch = batch_for(change)
    connection, transport = make_transport(
        batch.changes,
        readback_override={RECORD_ID: {"INPATIENT_DAY": Decimal("4")}},
    )
    with pytest.raises(core.UpdateRefused):
        make_updater(batch, transport).execute(batch)
    assert connection.rollbacks == 1
    assert connection.commits == 0
    assert connection.receipt_written is False


def test_bulk_transport_refuses_change_different_from_approved_plan():
    planned = stay_change(after=Decimal("3"))
    submitted = stay_change(after=Decimal("4"))
    batch = batch_for(submitted)
    connection, transport = make_transport((planned,))
    with pytest.raises(core.UpdateRefused):
        make_updater(batch, transport).execute(batch)
    assert all(not cursor.executemany_calls for cursor in connection.cursors)
    assert connection.rollbacks == 1


def test_bulk_transport_refuses_multiple_tables_duplicate_groups_and_over_200():
    home = stay_change(record_id="49557032X|home-001")
    operation = core.FieldChange(
        "OP_GRADE",
        "49557032X|operation-001",
        {"OPERATION_GRADE": Decimal("1")},
        {"OPERATION_GRADE": Decimal("2")},
    )
    with pytest.raises(core.UpdateRefused, match="one approved table"):
        bulk.BatchedOracleFieldUpdateTransport(core, FakeConnection((home, operation)), (home, operation))
    with pytest.raises(core.UpdateRefused, match="duplicate"):
        bulk.BatchedOracleFieldUpdateTransport(core, FakeConnection((home, home)), (home, home))

    many = tuple(
        stay_change(record_id=f"49557032X|home-{index:03d}")
        for index in range(201)
    )
    with pytest.raises(core.UpdateRefused, match="Bulk size"):
        bulk.BatchedOracleFieldUpdateTransport(core, FakeConnection(many), many)


def test_matching_receipt_replay_does_not_execute_array_dml():
    change = stay_change()
    batch = batch_for(change)
    connection, transport = make_transport(
        batch.changes,
        receipt={
            "MANIFEST_HASH": batch.manifest_hash,
            "ROWS_AFFECTED": len(batch.changes),
        },
    )
    result = make_updater(batch, transport).execute(batch)
    assert result.state == "REPLAY_CONFIRMED"
    assert all(not cursor.executemany_calls for cursor in connection.cursors)
    assert connection.commits == 0
    assert connection.rollbacks == 0


def test_context_exit_closes_all_cursors_without_closing_connection():
    change = stay_change()
    batch = batch_for(change)
    connection = FakeConnection(batch.changes)
    with bulk.BatchedOracleFieldUpdateTransport(core, connection, batch.changes) as transport:
        result = make_updater(batch, transport).execute(batch)
        assert result.state == "COMMITTED"
    assert connection.cursors
    assert all(cursor.closed for cursor in connection.cursors)
    assert connection.closed is False
