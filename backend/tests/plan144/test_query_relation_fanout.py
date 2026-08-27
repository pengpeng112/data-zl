"""A08/A09/A10: JOIN evidence, composite keys, fanout detection."""
from __future__ import annotations

from app.services.query_semantic_validator import (
    derive_semantic_contract,
    validate_relation_layer,
)

_RELATIONS = [
    {
        "id": 101,
        "from_table": "HIS.PAT_VISIT",
        "from_columns": "PATIENT_ID,VISIT_ID",
        "to_table": "HIS.INP_BILL_DETAIL",
        "to_columns": "PATIENT_ID,VISIT_ID",
        "cardinality": "1:N",
        "validation_status": "validated",
    },
    {
        "id": 102,
        "from_table": "HIS.OPERATION_MASTER",
        "from_columns": "PATIENT_ID,VISIT_ID",
        "to_table": "HIS.OPERATION_DETAIL",
        "to_columns": "PATIENT_ID,VISIT_ID",
        "cardinality": "N:N",
        "validation_status": "validated",
    },
    {
        "id": 103,
        "from_table": "HIS.PAT_VISIT",
        "from_columns": "PATIENT_ID",
        "to_table": "HIS.SOMETHING_ELSE",
        "to_columns": "PATIENT_ID",
        "cardinality": "1:N",
        "validation_status": "candidate",  # never auto-passes
    },
]


def test_join_without_formal_relation_is_blocked():
    sql = "SELECT a.PATIENT_ID FROM HIS.PAT_MASTER_INDEX a JOIN HIS.PAT_VISIT b ON a.PATIENT_ID = b.PATIENT_ID"
    layer = validate_relation_layer(sql, "oracle", _RELATIONS)
    assert layer["status"] == "blocked"
    assert any(f["code"] == "E_RELATION" for f in layer["findings"])


def test_candidate_relation_does_not_satisfy_join_evidence():
    # relation 103 is candidate → JOIN evidence must not pass through it
    sql = "SELECT 1 FROM HIS.PAT_VISIT a JOIN HIS.SOMETHING_ELSE b ON a.PATIENT_ID = b.PATIENT_ID"
    layer = validate_relation_layer(sql, "oracle", _RELATIONS)
    assert layer["status"] == "blocked"


def test_composite_key_join_passes_with_full_key():
    sql = (
        "SELECT b.COST FROM HIS.PAT_VISIT v JOIN HIS.INP_BILL_DETAIL b "
        "ON v.PATIENT_ID = b.PATIENT_ID AND v.VISIT_ID = b.VISIT_ID"
    )
    layer = validate_relation_layer(sql, "oracle", _RELATIONS)
    assert layer["status"] == "pass"
    assert layer["used_relations"] == [101]


def test_composite_key_degrades_to_single_key_is_blocked():
    sql = (
        "SELECT b.COST FROM HIS.PAT_VISIT v JOIN HIS.INP_BILL_DETAIL b "
        "ON v.PATIENT_ID = b.PATIENT_ID"
    )
    layer = validate_relation_layer(sql, "oracle", _RELATIONS)
    assert layer["status"] == "blocked"
    assert any("组合键" in f["message"] for f in layer["findings"])


def test_many_to_many_without_dedup_is_fanout_blocked():
    sql = (
        "SELECT m.PATIENT_ID FROM HIS.OPERATION_MASTER m "
        "JOIN HIS.OPERATION_DETAIL d ON m.PATIENT_ID = d.PATIENT_ID AND m.VISIT_ID = d.VISIT_ID"
    )
    layer = validate_relation_layer(sql, "oracle", _RELATIONS)
    assert layer["status"] == "blocked"
    assert any(f["code"] == "E_FANOUT" for f in layer["findings"])


def test_many_to_many_with_distinct_explains_fanout():
    sql = (
        "SELECT DISTINCT m.PATIENT_ID FROM HIS.OPERATION_MASTER m "
        "JOIN HIS.OPERATION_DETAIL d ON m.PATIENT_ID = d.PATIENT_ID AND m.VISIT_ID = d.VISIT_ID"
    )
    layer = validate_relation_layer(sql, "oracle", _RELATIONS)
    assert layer["status"] == "pass"


def test_semantic_contract_reports_grain_and_aggregation():
    sql = (
        "SELECT v.DEPT_CODE, COUNT(*) AS CNT FROM HIS.PAT_VISIT v "
        "WHERE v.VISIT_ID = 1 GROUP BY v.DEPT_CODE"
    )
    contract = derive_semantic_contract(sql, "oracle")
    assert contract["grain"] == "one_row_per_group"
    assert contract["has_aggregation"] is True
    assert "V.DEPT_CODE" in contract["group_keys"] or "DEPT_CODE" in "".join(contract["group_keys"]).upper()
