from __future__ import annotations

import pytest

from scripts.import_his_view_relation_drafts import (
    _columns,
    metadata_check,
    prepare_recipe_groups,
    prepare_review_groups,
    qualify_table,
)


def _candidate(**overrides):
    row = {
        "owner": "MEDREC",
        "view": "V_TEST",
        "status": "VALID",
        "runtime_status": "runtime_skipped",
        "source_sql_sha256": "a" * 64,
        "intake_status": "candidate",
        "from_table": "PAT_VISIT",
        "from_columns": ["PATIENT_ID", "VISIT_ID"],
        "to_table": "MEDREC.DIAGNOSIS",
        "to_columns": ["PATIENT_ID", "VISIT_ID"],
        "qualifiers": [],
        "warnings": [],
        "join_condition": "p.PATIENT_ID=d.PATIENT_ID AND p.VISIT_ID=d.VISIT_ID",
    }
    row.update(overrides)
    return row


def test_qualify_and_columns_are_strict():
    assert qualify_table("MEDREC", "PAT_VISIT") == "MEDREC.PAT_VISIT"
    assert _columns("PATIENT_ID+VISIT_ID") == ("PATIENT_ID", "VISIT_ID")
    with pytest.raises(ValueError):
        qualify_table("MEDREC", "A.B.C")


def test_prepare_reviews_deduplicates_evidence_without_losing_direction():
    first = _candidate()
    second = _candidate(view="V_TEST_2", source_sql_sha256="b" * 64)
    groups, skipped = prepare_review_groups({"candidates": [first, second]})
    assert skipped == []
    assert len(groups) == 1
    assert groups[0]["from_table"] == "MEDREC.PAT_VISIT"
    assert len(groups[0]["evidence"]) == 2


def test_metadata_check_requires_both_tables_and_columns():
    groups, _ = prepare_review_groups({"candidates": [_candidate()]})
    row = groups[0]
    tables = {"MEDREC.PAT_VISIT", "MEDREC.DIAGNOSIS"}
    columns = {name: {"PATIENT_ID", "VISIT_ID"} for name in tables}
    assert metadata_check(row, tables, columns) == (True, [])
    ok, errors = metadata_check(row, tables, {"MEDREC.PAT_VISIT": {"PATIENT_ID"}})
    assert not ok and errors


def test_recipe_groups_only_valid_complex_evidence():
    row = _candidate(intake_status="recipe_candidate", warnings=["aggregation_or_grain_change"])
    recipes = prepare_recipe_groups({"recipe_candidates": [row]})
    assert len(recipes) == 1
    assert recipes[0]["recipe_id"].startswith("HIS_VIEW_MEDREC_V_TEST_")
