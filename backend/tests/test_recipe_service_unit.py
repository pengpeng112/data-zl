import pytest
from fastapi import HTTPException

from app.services.recipe_service import assert_transition, canonical_recipe_payload, generate_select_sql, recipe_hash


def test_recipe_payload_is_canonical_and_hash_stable():
    first = {"joins": None, "primary_tables": [{"table": "HIS.PATIENT"}], "description": "患者"}
    second = {"description": "患者", "primary_tables": [{"table": "HIS.PATIENT"}], "joins": []}
    assert canonical_recipe_payload(first)["joins"] == []
    assert recipe_hash(first) == recipe_hash(second)


@pytest.mark.parametrize("current,target", [("draft", "submitted"), ("submitted", "approved"), ("approved", "active"), ("active", "deprecated")])
def test_recipe_transition_allows_expected_path(current, target):
    assert_transition(current, target) is None


def test_recipe_transition_rejects_editing_active_version():
    with pytest.raises(HTTPException) as exc:
        assert_transition("active", "draft")
    assert exc.value.status_code == 400


def test_generate_sql_requires_safe_join_condition():
    sql = generate_select_sql(["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"], [{"join_type": "inner", "on": "HIS.PAT_VISIT.PATIENT_ID = HIS.PAT_MASTER_INDEX.PATIENT_ID"}])
    assert "INNER JOIN HIS.PAT_MASTER_INDEX ON" in sql
    with pytest.raises(HTTPException):
        generate_select_sql(["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"], [])
    with pytest.raises(HTTPException):
        generate_select_sql(["HIS.PAT_VISIT; DROP TABLE x"], [])
