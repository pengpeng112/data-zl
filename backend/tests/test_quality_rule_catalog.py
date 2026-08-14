from types import SimpleNamespace

from app.services.quality_rule_catalog import (
    all_seed_rules,
    finding_problem,
    finding_target_display,
    is_safe_executable_sql_rule,
    metric_zh,
    safe_identifiers,
    split_columns,
    unique_fields_for_table,
)
from app.services.quality_templates import (
    CORE_UNIQUE_KEYS,
    is_large_table_unbounded_forbidden,
    template_complete_required_any,
    template_relation_orphan_composite,
    template_unique_pk,
)


def test_catalog_covers_common_dimensions():
    merged = all_seed_rules([])
    categories = {item["rule_category"] for item in merged}
    assert {"UNIQUE", "COMPLETE", "RELATION", "ACCURACY", "STANDARD"} <= categories
    assert any(item["rule_code"] == "TABLE_NO_PK" for item in merged)
    assert any(item["rule_code"] == "R_COMMON_002" for item in merged)


def test_unique_fields_prefer_verified_composite_keys():
    assert unique_fields_for_table("PAT_VISIT", "PATIENT_ID") == ["PATIENT_ID", "VISIT_ID"]
    assert unique_fields_for_table("ORDERS", "PATIENT_ID") == [
        "PATIENT_ID",
        "VISIT_ID",
        "ORDER_NO",
        "ORDER_SUB_NO",
    ]
    assert unique_fields_for_table("DEPT_DICT", "DEPT_CODE") == ["DEPT_CODE"]
    assert CORE_UNIQUE_KEYS["PAT_VISIT"] == ["PATIENT_ID", "VISIT_ID"]


def test_large_tables_are_not_unbounded_unique_targets():
    assert is_large_table_unbounded_forbidden("LAB_RESULT") is True
    assert is_large_table_unbounded_forbidden("HIS.PAT_VISIT") is False


def test_split_and_identifier_guards():
    assert split_columns("PATIENT_ID+VISIT_ID") == ["PATIENT_ID", "VISIT_ID"]
    assert safe_identifiers(["PATIENT_ID", "VISIT_ID"]) is True
    assert safe_identifiers(["PATIENT ID"]) is False


def test_finding_problem_explains_the_issue():
    rule = SimpleNamespace(rule_name="表缺少主键定义")
    finding = SimpleNamespace(
        rule_code="TABLE_NO_PK",
        schema_name="HIS",
        namespace_name=None,
        table_name="PAT_VISIT",
        column_name=None,
        target_ref="共 12 张表未登记主键",
        metric_value="total=12",
        error_cnt=12,
    )
    text = finding_problem(finding, rule, table_names={("HIS", "PAT_VISIT"): "住院就诊"})
    assert "表缺少主键定义" in text
    assert "住院就诊" in text
    assert "SOURCE_METADATA_STALE" not in text
    assert metric_zh("never_checked") == "尚未做过连接检测"
    assert finding_target_display(
        SimpleNamespace(schema_name=None, namespace_name=None, table_name=None, source_code="paperless_cdms_oracle_10_10_10_93", target_ref="paperless_cdms_oracle_10_10_10_93"),
        source_names={"paperless_cdms_oracle_10_10_10_93": "无纸化病案"},
    ) == "无纸化病案"


def test_large_table_sql_is_not_auto_enabled():
    assert is_safe_executable_sql_rule(SimpleNamespace(
        check_sql="SELECT COUNT(*) FROM HIS.LAB_RESULT",
        target_table="LAB_RESULT",
    )) is False
    assert is_safe_executable_sql_rule(SimpleNamespace(
        check_sql="SELECT COUNT(*) FROM HIS.PAT_VISIT",
        target_table="PAT_VISIT",
    )) is True


def test_generated_sql_returns_total_and_error_counts():
    unique_sql = template_unique_pk("PAT_VISIT", "PATIENT_ID,VISIT_ID", "HIS")
    assert "TOTAL_CNT" in unique_sql and "ERROR_CNT" in unique_sql
    assert "GROUP BY PATIENT_ID, VISIT_ID" in unique_sql

    null_sql = template_complete_required_any("PAT_VISIT", ["PATIENT_ID", "VISIT_ID"], "HIS")
    assert "PATIENT_ID IS NULL OR VISIT_ID IS NULL" in null_sql

    rel_sql = template_relation_orphan_composite(
        "DIAGNOSIS",
        ["PATIENT_ID", "VISIT_ID"],
        "PAT_VISIT",
        ["PATIENT_ID", "VISIT_ID"],
        "HIS",
        "HIS",
    )
    assert "p.PATIENT_ID = c.PATIENT_ID" in rel_sql
    assert "p.VISIT_ID = c.VISIT_ID" in rel_sql
