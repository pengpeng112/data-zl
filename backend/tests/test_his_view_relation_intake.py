from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.intake_his_view_relations import ingest_views, parse_sql, sanitize_sql, source_sql_sha256


def test_ansi_join_extracts_composite_key_and_qualifier() -> None:
    sql = """
        SELECT p.PATIENT_ID, p.VISIT_ID FROM MEDREC.PAT_VISIT p
        JOIN MEDREC.DIAGNOSIS d
          ON p.PATIENT_ID = d.PATIENT_ID AND p.VISIT_ID = d.VISIT_ID
         AND d.DIAGNOSIS_TYPE = '真实患者值'
    """
    parsed = parse_sql(sql)
    assert parsed["tables"] == ["MEDREC.DIAGNOSIS", "MEDREC.PAT_VISIT"]
    assert len(parsed["relations"]) == 1
    relation = parsed["relations"][0]
    assert relation.from_columns == ["PATIENT_ID", "VISIT_ID"]
    assert relation.to_columns == ["PATIENT_ID", "VISIT_ID"]
    assert relation.qualifiers == ["d.DIAGNOSIS_TYPE = '[REDACTED]'"]


def test_oracle_comma_join_and_outer_join_are_partial() -> None:
    sql = (
        "SELECT p.PATIENT_ID FROM MEDREC.PAT_VISIT p, MEDREC.PAT_MASTER_INDEX i "
        "WHERE p.PATIENT_ID = i.PATIENT_ID(+) AND p.VISIT_ID = 0"
    )
    parsed = parse_sql(sql)
    assert parsed["tables"] == ["MEDREC.PAT_MASTER_INDEX", "MEDREC.PAT_VISIT"]
    assert "oracle_comma_join" in parsed["warnings"]
    assert "oracle_outer_join" in parsed["warnings"]
    assert parsed["relations"][0].outer_join == "right_optional"
    assert parsed["relations"][0].from_columns == ["PATIENT_ID"]


def test_function_union_and_aggregation_route_to_recipe_candidate() -> None:
    sql = """
      SELECT a.X, COUNT(*) FROM A a JOIN B b ON TRIM(a.X) = b.X GROUP BY a.X
      UNION ALL
      SELECT a.X, COUNT(*) FROM A a JOIN B b ON a.X = b.X GROUP BY a.X
    """
    parsed = parse_sql(sql)
    assert parsed["branch_count"] == 2
    assert "union_branch_semantics" in parsed["warnings"]
    assert "aggregation_or_grain_change" in parsed["warnings"]
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_X", "definition": sql}]})
    assert result["summary"]["recipe_candidate"] == 2
    assert all(x["intake_status"] == "recipe_candidate" for x in result["recipe_candidates"])


def test_whitespace_inside_function_key_is_retained_as_risk() -> None:
    parsed = parse_sql("SELECT * FROM A a JOIN B b ON NVL(a.X, '0') = b.X AND TRIM(a.Y) = b.Y")
    assert len(parsed["relations"]) == 1
    assert parsed["relations"][0].from_columns == ["X", "Y"]
    assert parsed["relations"][0].function_wrapped is True


def test_existing_reverse_match_and_subset_conflict() -> None:
    sql = "SELECT * FROM CHILD c JOIN PARENT p ON c.A = p.A AND c.B = p.B"
    formal = [{"id": 7, "from_table": "PARENT", "from_columns": "A", "to_table": "CHILD", "to_columns": "A"}]
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_C", "definition": sql}]}, formal=formal)
    assert result["summary"]["partial"] == 1
    assert result["summary"]["conflicts"] == 1
    assert result["conflicts"][0]["conflict_type"] == "existing_relation_missing_composite_key"

    exact = [{"id": 8, "from_table": "PARENT", "from_columns": "A|B", "to_table": "CHILD", "to_columns": "A|B"}]
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_C", "definition": sql}]}, formal=exact)
    assert result["summary"]["existing"] == 1
    assert result["existing"][0]["existing_relation_id"] == 8

    legacy = [{"relationship_id": "R1", "from_table": "PARENT", "to_table": "CHILD", "join_keys": "A+B"}]
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_C", "definition": sql}]}, formal=legacy)
    assert result["summary"]["existing_formal"] == 1
    assert result["existing"][0]["existing_relation_id"] == "R1"


def test_sensitive_constants_are_clean_and_hash_is_original() -> None:
    sql = "SELECT * FROM A a WHERE a.ID = '123456789' AND a.URL = 'https://secret.example/p?id=123'"
    assert "secret.example" not in sanitize_sql(sql)
    assert source_sql_sha256(sql) != source_sql_sha256(sanitize_sql(sql))
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_A", "definition": sql}]})
    assert result["candidates"] == []
    assert result["summary"]["unresolved"] >= 0
    serialized = json.dumps(result, ensure_ascii=False)
    assert "secret.example" not in serialized
    assert "123456" not in sanitize_sql("SELECT 123456 FROM dual")


def test_missing_or_invalid_view_is_unresolved_and_no_formal_write() -> None:
    result = ingest_views(
        {
            "views": [
                {"owner": "HIS", "view_name": "V_BAD", "status": "INVALID", "definition": "SELECT * FROM A"},
                {"owner": "HIS", "view_name": "V_NONE", "definition": ""},
            ]
        }
    )
    assert result["formal_assets_modified"] is False
    assert result["summary"]["unresolved"] >= 2
    assert result["candidates"] == []


def test_harvester_view_definitions_shape_is_supported() -> None:
    result = ingest_views(
        {
            "view_definitions": [
                {
                    "owner": "MEDREC",
                    "view_name": "V_JOIN",
                    "status": "VALID",
                    "text": "SELECT * FROM MEDREC.A a JOIN MEDREC.B b ON a.ID=b.ID",
                    "definition_truncated": False,
                }
            ]
        }
    )
    assert result["summary"]["views"] == 1
    assert result["summary"]["candidate"] == 1
    assert result["candidates"][0]["runtime_status"] == "runtime_skipped"


def test_native_snapshot_shape_and_create_view_ddl_are_supported() -> None:
    result = ingest_views(
        {
            "schemas": {
                "HIS": {
                    "views": {
                        "V_DDL": {
                            "ddl": "CREATE OR REPLACE FORCE VIEW HIS.V_DDL AS "
                            "SELECT a.ID FROM HIS.A a JOIN HIS.B b ON a.ID=b.ID"
                        }
                    }
                }
            }
        }
    )
    assert result["summary"]["views"] == 1
    assert result["summary"]["candidate"] == 1
    assert result["candidates"][0]["owner"] == "HIS"
    assert result["candidates"][0]["view"] == "V_DDL"
    assert "non_select_statement" not in result["candidates"][0]["warnings"]


def test_dynamic_sql_is_rejected_without_execution() -> None:
    sql = "SELECT * FROM A a JOIN B b ON a.ID=b.ID /* dynamic */ EXECUTE IMMEDIATE :sql"
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_DYN", "definition": sql}]})
    assert result["summary"]["rejected"] == 1
    assert result["rejected"][0]["intake_status"] == "rejected"
    assert result["formal_assets_modified"] is False


def test_oracle_expression_concatenation_is_recipe_not_dynamic_sql() -> None:
    sql = "SELECT a.ID || b.ID FROM A a JOIN B b ON a.ID=b.ID"
    result = ingest_views({"views": [{"owner": "HIS", "view_name": "V_CAT", "definition": sql}]})
    assert result["summary"]["rejected"] == 0
    assert result["summary"]["recipe_candidate"] == 1
    assert "expression_concatenation" in result["recipe_candidates"][0]["warnings"]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM A a LEFT JOIN B b ON a.ID=b.ID",
        "SELECT * FROM A a RIGHT OUTER JOIN B b ON a.ID=b.ID AND b.STATE IN (1,2)",
    ],
)
def test_ansi_join_forms_are_supported(sql: str) -> None:
    parsed = parse_sql(sql)
    assert len(parsed["relations"]) == 1
    assert parsed["relations"][0].from_columns == ["ID"]
