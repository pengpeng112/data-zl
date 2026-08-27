"""A12: result digest must distinguish content, not only row counts."""
from __future__ import annotations

from app.services.query_result_digest import (
    compute_result_digest,
    compute_schema_digest,
)


def test_same_rowcount_different_content_different_digest():
    a = compute_result_digest(["N"], [{"N": 1}])
    b = compute_result_digest(["N"], [{"N": 2}])
    assert a != b


def test_digest_is_sha256_hex():
    d = compute_result_digest(["N"], [{"N": 1}])
    assert len(d) == 64 and int(d, 16) >= 0


def test_stable_digest_under_row_and_column_reordering():
    rows1 = [{"A": 1, "B": 2}, {"A": 3, "B": 4}]
    rows2 = [{"B": 4, "A": 3}, {"B": 2, "A": 1}]
    assert compute_result_digest(["A", "B"], rows1) == compute_result_digest(
        ["A", "B"], rows2
    )


def test_different_column_set_different_digest():
    a = compute_result_digest(["A"], [{"A": 1}])
    b = compute_result_digest(["A", "B"], [{"A": 1, "B": None}])
    assert a != b


def test_schema_digest_stable_for_same_columns():
    assert compute_schema_digest(["A", "B"]) == compute_schema_digest(["B", "A"])
    assert compute_schema_digest(["A"]) != compute_schema_digest(["B"])


def test_decimal_and_float_normalize_identically():
    import decimal

    a = compute_result_digest(["V"], [{"V": decimal.Decimal("1.0")}])
    b = compute_result_digest(["V"], [{"V": 1.0}])
    assert a == b
