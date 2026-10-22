"""Pure logic coverage for the controlled field updater."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest

from app.services.reporting_pipeline.controlled_field_update import (
    EXECUTOR_CODE,
    GROUPS,
    TARGET,
    ControlledFieldUpdater,
    FieldChange,
    OracleFieldUpdateTransport,
    PlatformFieldUpdateAuthority,
    UpdateBatch,
    UpdateRefused,
    update_sql,
)


NOW = datetime(2026, 10, 21, 6, 0, tzinfo=timezone.utc)
BACKUP_HASH = "a" * 64
SOURCE_HASH = "b" * 64
RECORD_ID = "49557032X|case-001"


def grade_change(*, before=Decimal("1"), after=Decimal("2"), record_id=RECORD_ID):
    return FieldChange(
        "OP_GRADE",
        record_id,
        {"OPERATION_GRADE": before},
        {"OPERATION_GRADE": after},
    )


def fee_change(
    *,
    record_id="49557032X|charge-001|10",
    before_code="1003",
    after_code="10",
    before_name="旧分类",
    after_name="治疗费用",
    before_amount=Decimal("10.00"),
    after_amount=Decimal("8.00"),
):
    return FieldChange(
        "FEE_CLASS_AMOUNT",
        record_id,
        {
            "CHARGE_TYPE_CODE": before_code,
            "CHARGE_TYPE": before_name,
            "CHARGE_AMOUNT": before_amount,
        },
        {
            "CHARGE_TYPE_CODE": after_code,
            "CHARGE_TYPE": after_name,
            "CHARGE_AMOUNT": after_amount,
        },
    )


def batch_for(*changes, operation_id="op-001", approval_ref="approval-001"):
    return UpdateBatch(
        operation_id=operation_id,
        approval_ref=approval_ref,
        changes=tuple(changes or (grade_change(),)),
        backup_ref="/opt/data-asset/evidence/ich/backup.json",
        backup_sha256=BACKUP_HASH,
        source_sha256=SOURCE_HASH,
        fencing_token=7,
    )


def executor_row(**overrides):
    row = {
        "enabled": True,
        "executor_code": EXECUTOR_CODE,
        "execution_mode": "controlled_field_update",
        "target_system_code": "qianzhiji_874",
        "target_source_code": "dboper_orcl",
        "require_approval": True,
    }
    row.update(overrides)
    return row


def approval_row(batch, **overrides):
    row = {
        "valid": True,
        "expires_at": NOW + timedelta(minutes=10),
        "approval_ref": batch.approval_ref,
        "executor_code": EXECUTOR_CODE,
        "target": TARGET,
        "manifest_hash": batch.manifest_hash,
        "backup_sha256": batch.backup_sha256,
        "operations": ("UPDATE",),
        "groups": tuple({change.group for change in batch.changes}),
        "max_changes": len(batch.changes),
    }
    row.update(overrides)
    return row


def make_authority(batch, *, executor=None, approval=None):
    return PlatformFieldUpdateAuthority(
        lambda code: executor_row() if executor is None else executor,
        lambda ref, code: approval_row(batch) if approval is None else approval,
        now=lambda: NOW,
    )


class FakeTransport:
    """In-memory transaction model; it never opens a connection."""

    def __init__(self, changes, *, receipt=None, read_override=None, commit_error=False):
        self.current = {
            (change.group, change.record_id): dict(change.before)
            for change in changes
        }
        self.original = {key: dict(value) for key, value in self.current.items()}
        self.events = []
        self.receipt_row = receipt
        self.read_override = read_override
        self.commit_error = commit_error
        self.patch_count = 0
        self.receipt_count = 0
        self.committed = False
        self.rolled_back = False

    def verify_target(self):
        self.events.append("verify_target")

    def receipt(self, operation_id):
        self.events.append("receipt_lookup")
        return self.receipt_row

    def patch(self, change):
        self.events.append("patch")
        self.patch_count += 1
        key = (change.group, change.record_id)
        if self.current.get(key) != dict(change.before):
            return 0
        self.current[key] = dict(change.after)
        return 1

    def read(self, change):
        self.events.append("read")
        if self.read_override is not None:
            return self.read_override(change, self.current[(change.group, change.record_id)])
        return dict(self.current[(change.group, change.record_id)])

    def write_receipt(self, batch, affected):
        self.events.append("write_receipt")
        self.receipt_count += 1
        self.receipt_row = {
            "MANIFEST_HASH": batch.manifest_hash,
            "ROWS_AFFECTED": affected,
        }

    def commit(self):
        self.events.append("commit")
        if self.commit_error:
            # The caller cannot know whether a real server committed before
            # the connection failed, so preserve the in-memory outcome.
            self.committed = True
            raise RuntimeError("simulated lost commit response")
        self.committed = True

    def rollback(self):
        self.events.append("rollback")
        self.current = {key: dict(value) for key, value in self.original.items()}
        self.receipt_row = None
        self.rolled_back = True


def make_updater(batch, transport, *, lease_validator=None, audit=None, backup_ok=True):
    return ControlledFieldUpdater(
        make_authority(batch),
        transport,
        backup_verifier=lambda candidate: backup_ok,
        lease_validator=lease_validator or (lambda candidate: True),
        audit=audit or (lambda candidate, result: None),
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"group": "UNLISTED"},
        {"record_id": "someone-elses-row"},
        {"before": {"OPERATION_GRADE": Decimal("1"), "EXTRA": "x"}},
        {"after": {"OPERATION_GRADE": Decimal("2"), "EXTRA": "x"}},
        {"after": {"OPERATION_GRADE": None}},
        {"after": {"OPERATION_GRADE": ""}},
        {"after": {"OPERATION_GRADE": 0}},
        {"after": {"OPERATION_GRADE": 5}},
        {"after": {"OPERATION_GRADE": Decimal("2.5")}},
    ],
)
def test_rejects_unknown_group_bad_id_and_empty_or_invalid_grade(kwargs):
    args = {
        "group": "OP_GRADE",
        "before": {"OPERATION_GRADE": Decimal("1")},
        "after": {"OPERATION_GRADE": Decimal("2")},
        "record_id": RECORD_ID,
    }
    args.update(kwargs)
    with pytest.raises(UpdateRefused):
        FieldChange(**args)


def test_field_change_freezes_mapping_inputs_and_batch_freezes_change_sequence():
    before = {"OPERATION_GRADE": Decimal("1")}
    after = {"OPERATION_GRADE": Decimal("2")}
    change = FieldChange("OP_GRADE", RECORD_ID, before, after)
    before["OPERATION_GRADE"] = Decimal("3")
    after.clear()
    assert change.before["OPERATION_GRADE"] == Decimal("1")
    assert change.after["OPERATION_GRADE"] == Decimal("2")
    with pytest.raises(TypeError):
        change.after["OPERATION_GRADE"] = Decimal("4")

    supplied = [change]
    batch = batch_for(*supplied)
    supplied.clear()
    assert batch.changes == (change,)


def test_manifest_hash_keeps_distinct_large_integer_old_values_under_low_precision():
    first = batch_for(
        FieldChange(
            "HOME_STAY",
            RECORD_ID,
            {"INPATIENT_DAY": Decimal("1234567890123456789012345678901")},
            {"INPATIENT_DAY": Decimal("1")},
        )
    )
    second = batch_for(
        FieldChange(
            "HOME_STAY",
            RECORD_ID,
            {"INPATIENT_DAY": Decimal("1234567890123456789012345678902")},
            {"INPATIENT_DAY": Decimal("1")},
        )
    )

    default_hashes = (first.manifest_hash, second.manifest_hash)
    assert default_hashes[0] != default_hashes[1]
    with localcontext() as context:
        context.prec = 6
        low_precision_hashes = (first.manifest_hash, second.manifest_hash)
    assert low_precision_hashes == default_hashes


def test_manifest_hash_normalizes_numerically_equivalent_decimal_old_values():
    one_decimal_place = batch_for(
        grade_change(before=Decimal("1.0"), after=Decimal("2"))
    )
    two_decimal_places = batch_for(
        grade_change(before=Decimal("1.00"), after=Decimal("2"))
    )
    assert one_decimal_place.manifest_hash == two_decimal_places.manifest_hash


def test_update_sql_is_limited_to_four_tables_and_uses_id_plus_old_values():
    allowed_tables = {
        "EMR_ICH",
        "EMR_ICH_DIAGNOSIS",
        "EMR_ICH_OPERATION",
        "EMR_ICH_CHARGE",
    }
    for group, (table, columns) in GROUPS.items():
        sql = update_sql(group)
        assert table in allowed_tables
        assert sql.startswith(f"UPDATE DBOPER.{table} SET ")
        assert "WHERE ID=:record_id" in sql
        for index, column in enumerate(columns):
            assert f"{column}=:new_{index}" in sql
            assert f"{column}=:old_{index}" in sql
            assert f"{column} IS NULL AND :old_{index} IS NULL" in sql
        assert "DELETE" not in sql.upper()
    with pytest.raises(UpdateRefused):
        update_sql("EMR_ICH; DELETE FROM DBOPER.ASSET_APPLY_RECEIPTS")


@pytest.mark.parametrize(
    "code", [*(str(value) for value in range(1, 25)), "901", "101", "102", "131"]
)
def test_fee_class_amount_accepts_only_whitelisted_codes_and_id_suffix(code):
    change = fee_change(
        record_id=f"49557032X|charge-001|{code}",
        before_code="1003",
        after_code=code,
    )
    assert change.after["CHARGE_TYPE_CODE"] == code


def test_fee_class_amount_accepts_negative_refund_with_two_decimal_precision():
    change = fee_change(after_amount=Decimal("-125.40"))
    assert change.after["CHARGE_AMOUNT"] == Decimal("-125.40")


@pytest.mark.parametrize("code", ["0", "25", "1003", "1202", ""])
def test_fee_class_amount_rejects_unapproved_category_codes(code):
    with pytest.raises(UpdateRefused):
        fee_change(after_code=code)


@pytest.mark.parametrize(
    ("old_suffix", "new_code"), [("1003", "10"), ("1202", "12")]
)
def test_fee_category_merge_does_not_rewrite_or_accept_mismatched_id_suffix(
    old_suffix, new_code
):
    with pytest.raises(UpdateRefused, match="ID后缀"):
        fee_change(
            record_id=f"49557032X|charge-001|{old_suffix}",
            before_code=old_suffix,
            after_code=new_code,
        )


def test_fee_class_amount_refuses_name_longer_than_32_utf8_bytes():
    with pytest.raises(UpdateRefused, match="费用分类名称"):
        fee_change(after_name="费" * 11)


@pytest.mark.parametrize("field", ["CHARGE_TYPE_CODE", "CHARGE_TYPE", "CHARGE_AMOUNT"])
def test_fee_class_amount_refuses_null_in_each_required_field(field):
    before = {
        "CHARGE_TYPE_CODE": "1003",
        "CHARGE_TYPE": "旧分类",
        "CHARGE_AMOUNT": Decimal("10.00"),
    }
    after = {
        "CHARGE_TYPE_CODE": "10",
        "CHARGE_TYPE": "治疗费用",
        "CHARGE_AMOUNT": Decimal("8.00"),
    }
    after[field] = None
    with pytest.raises(UpdateRefused):
        FieldChange("FEE_CLASS_AMOUNT", "49557032X|charge-001|10", before, after)


@pytest.mark.parametrize("amount", [Decimal("1.001"), Decimal("10000000.00"), 1.23])
def test_fee_class_amount_refuses_excess_precision_or_magnitude(amount):
    with pytest.raises(UpdateRefused):
        fee_change(after_amount=amount)


def test_fee_class_amount_sql_updates_only_three_fields_with_id_and_old_value_guards():
    sql = update_sql("FEE_CLASS_AMOUNT")
    assert sql == (
        "UPDATE DBOPER.EMR_ICH_CHARGE SET CHARGE_TYPE_CODE=:new_0, "
        "CHARGE_TYPE=:new_1, CHARGE_AMOUNT=:new_2 WHERE ID=:record_id AND "
        "(CHARGE_TYPE_CODE=:old_0 OR (CHARGE_TYPE_CODE IS NULL AND :old_0 IS NULL)) AND "
        "(CHARGE_TYPE=:old_1 OR (CHARGE_TYPE IS NULL AND :old_1 IS NULL)) AND "
        "(CHARGE_AMOUNT=:old_2 OR (CHARGE_AMOUNT IS NULL AND :old_2 IS NULL))"
    )
    assert "UPDATE DBOPER.EMR_ICH_CHARGE SET ID" not in sql


@pytest.mark.parametrize(
    ("group", "column"),
    [("HOME_UNPLANNED", "SFFJHZRY"), ("HOME_DAY_WARD", "SFRJBF")],
)
@pytest.mark.parametrize(
    ("before", "after"),
    [("2", "1"), ("1", "2"), ("1", None)],
)
def test_new_home_flag_groups_accept_only_defined_values_and_explicit_null(
    group, column, before, after
):
    change = FieldChange(group, RECORD_ID, {column: before}, {column: after})
    assert change.before[column] == before
    assert change.after[column] == after


@pytest.mark.parametrize(
    ("group", "column"),
    [("HOME_UNPLANNED", "SFFJHZRY"), ("HOME_DAY_WARD", "SFRJBF")],
)
@pytest.mark.parametrize("invalid", ["0", "3", "9", "Y"])
def test_new_home_flag_groups_refuse_codes_outside_one_two_or_null(
    group, column, invalid
):
    with pytest.raises(UpdateRefused):
        FieldChange(group, RECORD_ID, {column: "1"}, {column: invalid})


@pytest.mark.parametrize(
    ("group", "column", "other_column"),
    [
        ("HOME_UNPLANNED", "SFFJHZRY", "SFRJBF"),
        ("HOME_DAY_WARD", "SFRJBF", "SFFJHZRY"),
    ],
)
def test_new_home_flag_groups_reject_cross_field_payloads(
    group, column, other_column
):
    with pytest.raises(UpdateRefused):
        FieldChange(
            group,
            RECORD_ID,
            {column: "1", other_column: "1"},
            {column: "2", other_column: "2"},
        )


@pytest.mark.parametrize(
    ("group", "column"),
    [("HOME_UNPLANNED", "SFFJHZRY"), ("HOME_DAY_WARD", "SFRJBF")],
)
def test_new_home_flag_sql_is_fixed_to_one_column_and_guards_id_and_old_value(
    group, column
):
    sql = update_sql(group)
    assert sql == (
        f"UPDATE DBOPER.EMR_ICH SET {column}=:new_0 WHERE ID=:record_id AND "
        f"({column}=:old_0 OR ({column} IS NULL AND :old_0 IS NULL))"
    )
    other_column = "SFRJBF" if column == "SFFJHZRY" else "SFFJHZRY"
    assert other_column not in sql


def test_null_home_flag_readback_is_compared_as_null_and_committed():
    change = FieldChange(
        "HOME_UNPLANNED",
        RECORD_ID,
        {"SFFJHZRY": "1"},
        {"SFFJHZRY": None},
    )
    batch = batch_for(change)
    transport = FakeTransport(batch.changes)
    result = make_updater(batch, transport).execute(batch)
    assert result.state == "COMMITTED"
    assert transport.current[(change.group, change.record_id)] == {"SFFJHZRY": None}
    assert transport.events.index("read") < transport.events.index("write_receipt")
    assert transport.events.index("write_receipt") < transport.events.index("commit")


def test_null_home_flag_readback_mismatch_rolls_back_every_change():
    null_change = FieldChange(
        "HOME_UNPLANNED",
        RECORD_ID,
        {"SFFJHZRY": "1"},
        {"SFFJHZRY": None},
    )
    later_change = FieldChange(
        "HOME_DAY_WARD",
        "49557032X|case-002",
        {"SFRJBF": "1"},
        {"SFRJBF": "2"},
    )
    batch = batch_for(null_change, later_change)
    transport = FakeTransport(
        batch.changes,
        read_override=lambda change, actual: (
            {"SFRJBF": "9"}
            if change.record_id == later_change.record_id
            else actual
        ),
    )
    with pytest.raises(UpdateRefused):
        make_updater(batch, transport).execute(batch)
    assert transport.rolled_back is True
    assert transport.committed is False
    assert transport.current == transport.original
    assert transport.patch_count == 2
    assert transport.receipt_count == 0


def test_outcome_change_preserves_padded_old_name_for_sql_binding():
    padded_old_name = "治愈   "
    change = FieldChange(
        "HOME_OUTCOME",
        RECORD_ID,
        {"DIS_OUTCOME_CODE": "1", "DIS_OUTCOME_NAME": padded_old_name},
        {"DIS_OUTCOME_CODE": "2", "DIS_OUTCOME_NAME": "好转"},
    )
    assert change.before["DIS_OUTCOME_NAME"] == padded_old_name
    assert change.after["DIS_OUTCOME_NAME"] == "好转"

    connection = VerifyConnection()
    OracleFieldUpdateTransport(connection).patch(change)
    sql, params = connection.verify_cursor.executed[-1]
    assert "DIS_OUTCOME_NAME=:old_1" in sql
    assert params["old_1"] == padded_old_name


def test_outcome_change_that_only_removes_trailing_spaces_is_refused():
    with pytest.raises(UpdateRefused, match="无差异"):
        FieldChange(
            "HOME_OUTCOME",
            RECORD_ID,
            {"DIS_OUTCOME_CODE": "1", "DIS_OUTCOME_NAME": "治愈   "},
            {"DIS_OUTCOME_CODE": "1", "DIS_OUTCOME_NAME": "治愈"},
        )


@pytest.mark.parametrize(
    "executor,approval,expected",
    [
        (None, None, "missing_executor"),
        ({"enabled": False}, None, "disabled_executor"),
        (executor_row(target_source_code="other"), None, "executor_scope"),
        (None, {"valid": False}, "invalid_approval"),
        (None, "expired", "expired_approval"),
        (None, "wrong_manifest", "wrong_manifest"),
        (None, "wrong_target", "wrong_target"),
        (None, "wrong_group", "wrong_group"),
        (None, "wrong_operation", "wrong_operation"),
        (None, "too_many", "too_many"),
    ],
)
def test_platform_authority_refuses_unregistered_or_out_of_scope_approval(
    executor, approval, expected
):
    batch = batch_for()
    if approval == "expired":
        approval = approval_row(batch, expires_at=NOW)
    elif approval == "wrong_manifest":
        approval = approval_row(batch, manifest_hash="f" * 64)
    elif approval == "wrong_target":
        approval = approval_row(batch, target="somewhere-else")
    elif approval == "wrong_group":
        approval = approval_row(batch, groups=("HOME_STAY",))
    elif approval == "wrong_operation":
        approval = approval_row(batch, operations=("UPDATE", "DELETE"))
    elif approval == "too_many":
        approval = approval_row(batch, max_changes=0)
    if expected == "missing_executor":
        authority = PlatformFieldUpdateAuthority(
            lambda code: None,
            lambda ref, code: approval_row(batch),
            now=lambda: NOW,
        )
    else:
        authority = make_authority(
            batch,
            executor=executor_row() if executor is None else executor,
            approval=approval_row(batch) if approval is None else approval,
        )
    transport = FakeTransport(batch.changes)
    with pytest.raises(UpdateRefused):
        ControlledFieldUpdater(
            authority,
            transport,
            backup_verifier=lambda candidate: True,
            lease_validator=lambda candidate: True,
            audit=lambda candidate, result: None,
        ).execute(batch)
    assert transport.patch_count == 0
    assert transport.receipt_count == 0
    assert "verify_target" not in transport.events


def test_missing_platform_approval_refuses_without_dml():
    batch = batch_for()
    authority = PlatformFieldUpdateAuthority(
        lambda code: executor_row(),
        lambda ref, code: None,
        now=lambda: NOW,
    )
    transport = FakeTransport(batch.changes)
    with pytest.raises(UpdateRefused):
        ControlledFieldUpdater(
            authority,
            transport,
            backup_verifier=lambda candidate: True,
            lease_validator=lambda candidate: True,
            audit=lambda candidate, result: None,
        ).execute(batch)
    assert transport.patch_count == 0
    assert transport.receipt_count == 0
    assert transport.events == []


def test_approval_manifest_binds_exact_content_and_cannot_be_reused_after_change():
    approved_batch = batch_for()
    changed_batch = batch_for(
        grade_change(after=Decimal("3")),
        operation_id=approved_batch.operation_id,
    )
    authority = make_authority(
        changed_batch, approval=approval_row(approved_batch)
    )
    with pytest.raises(UpdateRefused):
        authority.verify(changed_batch)


@pytest.mark.parametrize("failure", ["old_value", "readback", "lease"])
def test_conflict_readback_or_lease_failure_rolls_back_whole_batch(failure):
    first = grade_change(record_id=RECORD_ID)
    second = grade_change(record_id="49557032X|case-002")
    batch = batch_for(first, second)
    transport = FakeTransport(
        batch.changes,
        read_override=(
            lambda change, actual: (
                {"OPERATION_GRADE": Decimal("99")}
                if failure == "readback" and change.record_id == second.record_id
                else actual
            )
        ),
    )
    if failure == "old_value":
        transport.current[(second.group, second.record_id)] = {
            "OPERATION_GRADE": Decimal("0")
        }

    lease_calls = 0

    def lease(candidate):
        nonlocal lease_calls
        lease_calls += 1
        # execute checks before work, before each row, and immediately before
        # the receipt/commit boundary. Fail before row two, after row one changed.
        return not (failure == "lease" and lease_calls == 3)

    updater = make_updater(batch, transport, lease_validator=lease)
    with pytest.raises(UpdateRefused):
        updater.execute(batch)
    assert transport.rolled_back is True
    assert transport.committed is False
    assert transport.current == transport.original
    assert transport.receipt_count == 0
    assert transport.patch_count == (1 if failure == "lease" else 2)


def test_success_reads_back_then_writes_receipt_in_transaction_then_commits():
    batch = batch_for()
    transport = FakeTransport(batch.changes)
    result = make_updater(
        batch, transport, audit=lambda candidate, result: transport.events.append("audit")
    ).execute(batch)
    assert result.state == "COMMITTED"
    assert result.unique_records == 1
    assert result.field_groups == 1
    assert transport.events.index("read") < transport.events.index("write_receipt")
    assert transport.events.index("write_receipt") < transport.events.index("commit")
    assert transport.events.index("commit") < transport.events.index("audit")
    assert transport.receipt_row["MANIFEST_HASH"] == batch.manifest_hash


def test_commit_exception_returns_unknown_and_does_not_claim_rollback():
    batch = batch_for()
    transport = FakeTransport(batch.changes, commit_error=True)
    result = make_updater(batch, transport).execute(batch)
    assert result.state == "COMMIT_UNKNOWN"
    assert transport.receipt_count == 1
    assert transport.committed is True
    assert transport.rolled_back is False


def test_matching_receipt_replay_confirms_without_rewriting():
    batch = batch_for()
    transport = FakeTransport(
        batch.changes,
        receipt={
            "MANIFEST_HASH": batch.manifest_hash,
            "ROWS_AFFECTED": len(batch.changes),
        },
    )
    result = make_updater(batch, transport).execute(batch)
    assert result.state == "REPLAY_CONFIRMED"
    assert transport.patch_count == 0
    assert transport.receipt_count == 0
    assert "commit" not in transport.events


def test_operation_id_with_different_receipt_is_refused_without_rewrite():
    batch = batch_for()
    transport = FakeTransport(
        batch.changes,
        receipt={"MANIFEST_HASH": "f" * 64, "ROWS_AFFECTED": 1},
    )
    with pytest.raises(UpdateRefused):
        make_updater(batch, transport).execute(batch)
    assert transport.patch_count == 0
    assert transport.receipt_count == 0
    assert "commit" not in transport.events


def test_audit_failure_reports_committed_pending_without_rewriting():
    batch = batch_for()
    transport = FakeTransport(batch.changes)

    def failed_audit(candidate, result):
        raise RuntimeError("audit unavailable")

    result = make_updater(batch, transport, audit=failed_audit).execute(batch)
    assert result.state == "COMMITTED_AUDIT_PENDING"
    assert transport.committed is True
    assert transport.patch_count == 1
    assert transport.receipt_count == 1
    assert transport.rolled_back is False


class VerifyCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.executed = []
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class VerifyConnection:
    def __init__(
        self,
        *,
        autocommit=False,
        dsn="10.10.8.74:1521/orcl",
        call_timeout=1000,
        transaction_in_progress=False,
    ):
        self.autocommit = autocommit
        self.dsn = dsn
        self.call_timeout = call_timeout
        self.transaction_in_progress = transaction_in_progress
        self.verify_cursor = VerifyCursor(
            rows=[("DBOPER", "DBOPER"), (6,)]
        )

    def cursor(self):
        return self.verify_cursor


@pytest.mark.parametrize(
    "connection",
    [
        VerifyConnection(autocommit=True),
        VerifyConnection(dsn="10.10.8.75:1521/orcl"),
        VerifyConnection(dsn="10.10.8.74:1521/orcl.evil"),
        VerifyConnection(
            dsn="(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=10.10.8.74)(PORT=1521))"
            "(ADDRESS=(PROTOCOL=TCP)(HOST=10.10.8.75)(PORT=1521))"
            "(CONNECT_DATA=(SERVICE_NAME=orcl)))"
        ),
    ],
)
def test_oracle_transport_rejects_autocommit_and_wrong_target_before_queries(connection):
    transport = OracleFieldUpdateTransport(connection)
    with pytest.raises(UpdateRefused):
        transport.verify_target()
    assert connection.verify_cursor.executed == []


@pytest.mark.parametrize(
    "dsn",
    [
        "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=10.10.8.74)(PORT=1521))"
        "(CONNECT_DATA=(SERVICE_NAME=orcl)))",
        "//10.10.8.74:1521/orcl",
    ],
)
def test_oracle_transport_accepts_only_exact_single_target_dsn_forms(dsn):
    connection = VerifyConnection(dsn=dsn)
    OracleFieldUpdateTransport(connection).verify_target()
    assert len(connection.verify_cursor.executed) == 2


def test_oracle_transport_rejects_preexisting_transaction_before_any_sql():
    connection = VerifyConnection(transaction_in_progress=True)
    transport = OracleFieldUpdateTransport(connection)
    with pytest.raises(UpdateRefused, match="已有事务"):
        transport.verify_target()
    assert connection.verify_cursor.executed == []
