"""plan139: multi-dialect identifier support in the offline view relation parser."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_intake():
    path = ROOT / "scripts" / "intake_his_view_relations.py"
    spec = importlib.util.spec_from_file_location("intake_his_view_relations_plan139", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


intake = load_intake()


def test_bracket_qualified_ansi_join_is_parsed():
    sql = (
        "CREATE VIEW [dbo].[V_DEMO] AS "
        "SELECT a.* FROM [dbo].[T_VISIT] a JOIN [dbo].[T_MASTER] b "
        "ON [a].[PATIENT_ID] = [b].[PATIENT_ID] AND [a].[VISIT_ID] = [b].[VISIT_ID]"
    )
    parsed = intake.parse_sql(sql)
    assert sorted(parsed["tables"]) == ["DBO.T_MASTER", "DBO.T_VISIT"]
    assert len(parsed["relations"]) == 1
    rel = parsed["relations"][0]
    assert rel.from_columns == ["PATIENT_ID", "VISIT_ID"]
    assert rel.to_columns == ["PATIENT_ID", "VISIT_ID"]
    assert not rel.function_wrapped


def test_backtick_mysql_names_are_normalized():
    sql = (
        "SELECT p.* FROM `core2db`.`t_patient` p "
        "JOIN `core2db`.`t_visit` v ON p.`patient_id` = v.`patient_id`"
    )
    parsed = intake.parse_sql(sql)
    assert sorted(parsed["tables"]) == ["CORE2DB.T_PATIENT", "CORE2DB.T_VISIT"]
    rel = parsed["relations"][0]
    assert {rel.from_table, rel.to_table} == {"CORE2DB.T_PATIENT", "CORE2DB.T_VISIT"}
    assert rel.join_condition.upper().startswith("P.`PATIENT_ID`")


def test_bracket_comma_join_keeps_qualifiers_and_sanitizes_literals():
    sql = (
        "SELECT * FROM [dbo].[TA], [dbo].[TB] "
        "WHERE [TA].[X] = [TB].[X] AND [TB].[STATUS] = 'SECRETVALUE'"
    )
    parsed = intake.parse_sql(sql)
    assert len(parsed["relations"]) == 1
    rel = parsed["relations"][0]
    assert rel.qualifiers, "status filter must be retained as qualifier evidence"
    assert all("SECRETVALUE" not in q for q in rel.qualifiers)
    assert any("[REDACTED]" in q for q in rel.qualifiers)


def test_three_part_column_reference_resolves_last_two_parts():
    sql = (
        "SELECT * FROM dbo.T_A a JOIN dbo.T_B b "
        "ON EIS.dbo.T_A.COL = b.COL"
    )
    parsed = intake.parse_sql(sql)
    joined = [r for r in parsed["relations"] if r.function_wrapped]
    assert parsed["relations"], "join must still produce conservative evidence"


def test_quoted_oracle_style_still_parses():
    sql = (
        'SELECT * FROM "MEDREC"."PAT_VISIT" pv '
        'JOIN "ORDADM"."ORDERS" o ON o."PATIENT_ID" = pv."PATIENT_ID"'
    )
    parsed = intake.parse_sql(sql)
    assert sorted(parsed["tables"]) == ["MEDREC.PAT_VISIT", "ORDADM.ORDERS"]
    assert len(parsed["relations"]) == 1


def test_function_wrapped_key_remains_recipe_risk():
    sql = (
        "SELECT * FROM t_a JOIN t_b ON NVL(t_a.KEY, '0') = t_b.KEY"
    )
    parsed = intake.parse_sql(sql)
    assert parsed["relations"]
    assert any(r.function_wrapped for r in parsed["relations"])


def test_ingest_views_classifies_bracket_view_end_to_end():
    views = [
        {
            "owner": "dbo",
            "view_name": "V_BRACKET",
            "definition": (
                "CREATE VIEW [dbo].[V_BRACKET] AS "
                "SELECT a.* FROM [dbo].[T1] a JOIN [dbo].[T2] b ON [a].[K] = [b].[K]"
            ),
            "status": "VALID",
            "dialect": "sqlserver",
        }
    ]
    result = intake.ingest_views(views)
    assert result["summary"]["dependencies"] == 2
    assert result["summary"]["relations"] == 1
    assert result["candidates"][0]["intake_status"] == "candidate"


def test_mysql57_nested_parenthesized_ansi_join_is_parsed():
    """MySQL 5.7 normalizes view bodies with nested parens and backticks."""
    sql = (
        "select a.x from ((((`core2db`.`t1` a left join `core2db`.`t2` b "
        "on((b.id = a.t2_id))))) left join `core2db`.`t3` c on((c.id = a.t3_id))) "
        "where (a.x is not null)"
    )
    parsed = intake.parse_sql(sql)
    assert parsed["tables"] == ["CORE2DB.T1", "CORE2DB.T2", "CORE2DB.T3"]
    pairs = {(r.from_table, tuple(r.from_columns), r.to_table, tuple(r.to_columns))
             for r in parsed["relations"]}
    assert ("CORE2DB.T2", ("ID",), "CORE2DB.T1", ("T2_ID",)) in pairs
    assert ("CORE2DB.T3", ("ID",), "CORE2DB.T1", ("T3_ID",)) in pairs


def test_backtick_quoted_alias_resolves():
    sql = (
        "select `mc`.`id` from `core2db`.`clinic_api_x` `mc` "
        "join `core2db`.`data_api_y` `dap` on `dap`.`x_id` = `mc`.`id`"
    )
    parsed = intake.parse_sql(sql)
    assert sorted(parsed["tables"]) == ["CORE2DB.CLINIC_API_X", "CORE2DB.DATA_API_Y"]
    assert len(parsed["relations"]) == 1
    relation = parsed["relations"][0]
    assert {relation.from_table, relation.to_table} == {
        "CORE2DB.CLINIC_API_X", "CORE2DB.DATA_API_Y"}


def test_bracket_quoted_alias_resolves():
    sql = (
        "SELECT v.* FROM [dbo].[T_VISIT] v INNER JOIN [dbo].[T_MASTER] m "
        "ON v.MID = m.ID"
    )
    parsed = intake.parse_sql(sql)
    assert sorted(parsed["tables"]) == ["DBO.T_MASTER", "DBO.T_VISIT"]
    assert len(parsed["relations"]) == 1


def test_first_ansi_table_is_registered_before_any_join():
    """The first table after FROM has no JOIN keyword; anchor it explicitly."""
    sql = "SELECT a.x FROM dbo.T1 a JOIN dbo.T2 b ON b.id = a.t1_id"
    parsed = intake.parse_sql(sql)
    assert sorted(parsed["tables"]) == ["DBO.T1", "DBO.T2"]
    assert len(parsed["relations"]) == 1


def test_bare_keywords_are_not_tables():
    sql = (
        "select a.x from (select id from dbo.T1 group by id) a "
        "union all select b.x from dbo.T2 b"
    )
    parsed = intake.parse_sql(sql)
    assert "ALL" not in parsed["tables"]
    assert "FROM" not in parsed["tables"]
    assert "SELECT" not in parsed["tables"]
    assert all(not t.endswith(".PARTITION") for t in parsed["tables"])


def test_subquery_with_quoted_alias_does_not_leak_alias_as_table():
    sql = (
        "select x.id from dbo.T1 x join (select k from dbo.T2) `agg` "
        "on agg.k = x.id"
    )
    parsed = intake.parse_sql(sql)
    assert "AGG" not in parsed["tables"]
    # The derived table's FROM was removed with its subquery, so ``agg.k``
    # intentionally stays unresolved: the parser never guesses a key.
