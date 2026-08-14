from types import SimpleNamespace

from app.services.quality_attribution import (
    infer_system_code,
    parse_finding_target,
    parse_relation_id,
    resolve_finding_location,
)


def test_parse_schema_table_and_dotted_schema():
    simple = parse_finding_target("HIS.PAT_VISIT")
    assert simple.schema_name == "HIS"
    assert simple.table_name == "PAT_VISIT"
    dotted = parse_finding_target("AnyImage.dbo.T_ITF_ES")
    assert dotted.schema_name == "AnyImage.dbo"
    assert dotted.table_name == "T_ITF_ES"
    summary = parse_finding_target("共 3358 张表缺中文名")
    assert summary.table_name is None


def test_infer_system_from_table_and_schema_maps():
    table_map = {("JHEMR", "PAT_VISIT"): "JHEMR_VASTBASE"}
    schema_map = {"HIS": "DATA_CENTER", "LUNA_MCS_SDSEY": "MOBILE_NURSING"}
    assert infer_system_code(
        system_code=None,
        target_ref="jhemr.pat_visit",
        table_map={("JHEMR", "PAT_VISIT"): "JHEMR_VASTBASE"},
        schema_map=schema_map,
    ) == "JHEMR_VASTBASE"
    assert infer_system_code(
        system_code=None,
        target_ref="HIS.术中体温监测",
        table_map=table_map,
        schema_map=schema_map,
    ) == "DATA_CENTER"
    assert infer_system_code(system_code=None, target_ref="共 10 张表缺中文名") == "UNASSIGNED"
    assert infer_system_code(system_code="HIS_SOURCE") == "HIS_SOURCE"
    assert infer_system_code(
        system_code=None,
        target_ref="HIS.FOO",
        schema_map={"HIS": "DATA_CENTER"},
    ) == "DATA_CENTER"


def test_resolve_finding_location_fills_schema_table_and_join_fields():
    loc = resolve_finding_location(SimpleNamespace(
        schema_name=None,
        namespace_name=None,
        table_name=None,
        column_name=None,
        target_ref="HIS.PAT_VISIT -> HIS.DIAGNOSIS (rel_id=12)",
        detail={"related_columns": "PATIENT_ID,VISIT_ID", "from_columns": "PATIENT_ID,VISIT_ID"},
    ))
    assert loc.schema_name == "HIS"
    assert loc.table_name == "PAT_VISIT"
    assert loc.related_schema == "HIS"
    assert loc.related_table == "DIAGNOSIS"
    assert loc.column_name == "PATIENT_ID,VISIT_ID"
    assert loc.related_column == "PATIENT_ID,VISIT_ID"
    assert parse_relation_id("HIS.PAT_VISIT -> HIS.EXAM_MASTER (rel_id=14)") == 14
    assert parse_relation_id("HIS.PAT_VISIT") is None

    from_rule = resolve_finding_location(
        SimpleNamespace(schema_name=None, namespace_name=None, table_name=None, column_name=None, target_ref=None, detail=None),
        SimpleNamespace(namespace_name="YDHL", target_table="MCS_VITAL_INFO", target_field="PATIENT_UID"),
    )
    assert from_rule.schema_name == "YDHL"
    assert from_rule.table_name == "MCS_VITAL_INFO"
    assert from_rule.column_name == "PATIENT_UID"
