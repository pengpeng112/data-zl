"""A03: structural big-table policy via SQL AST — regex WHERE no longer sufficient."""
from __future__ import annotations

import pytest

from app.services.sql_ast import (
    SQLParseError,
    UnsupportedDialectError,
    check_big_table_policy,
    extract_table_dependencies,
    parse_sql,
)


def test_lab_result_with_tautological_where_is_blocked():
    sql = "SELECT COUNT(*) FROM HIS.LAB_RESULT WHERE 1=1"
    result = check_big_table_policy(sql, "oracle")
    assert not result["ok"]
    assert any("LAB_RESULT" in v for v in result["violations"])


def test_lab_result_with_self_equal_predicate_is_blocked():
    sql = "SELECT COUNT(*) FROM HIS.LAB_RESULT WHERE TEST_NO = TEST_NO"
    result = check_big_table_policy(sql, "oracle")
    assert not result["ok"]


def test_lab_result_unbounded_without_where_is_blocked():
    sql = "SELECT COUNT(*) FROM HIS.LAB_RESULT"
    result = check_big_table_policy(sql, "oracle")
    assert not result["ok"]


def test_lab_result_with_test_no_subquery_bound_passes():
    sql = (
        "SELECT r.RESULT FROM HIS.LAB_RESULT r WHERE r.TEST_NO IN "
        "(SELECT m.TEST_NO FROM HIS.LAB_TEST_MASTER m WHERE m.TEST_NO = :test_no)"
    )
    result = check_big_table_policy(sql, "oracle")
    assert result["ok"], result["violations"]


def test_lab_result_with_test_no_bind_passes():
    sql = "SELECT * FROM HIS.LAB_RESULT WHERE TEST_NO = :test_no"
    result = check_big_table_policy(sql, "oracle")
    assert result["ok"], result["violations"]


def test_unparseable_sql_is_unresolved_not_allowed():
    with pytest.raises(SQLParseError):
        parse_sql("SELECT FROM WHERE @@garbage(((", "oracle")


def test_unsupported_dialect_fails_closed():
    with pytest.raises((UnsupportedDialectError, SQLParseError)):
        parse_sql("SELECT 1", "some_unknown_dialect")


def test_table_dependencies_include_cte_awareness():
    sql = (
        "WITH recent AS (SELECT PATIENT_ID FROM HIS.PAT_VISIT) "
        "SELECT * FROM recent r JOIN HIS.INP_BILL_DETAIL b ON b.PATIENT_ID = r.PATIENT_ID"
    )
    deps = extract_table_dependencies(sql, "oracle")
    tables = {d["name"] for d in deps["tables"]}
    assert tables == {"HIS.PAT_VISIT", "HIS.INP_BILL_DETAIL"}  # CTE recent excluded


def test_parser_version_is_recorded():
    result = parse_sql("SELECT 1 FROM HIS.DUAL", "oracle")
    assert result["parser_version"].startswith("sqlglot@")
