from __future__ import annotations

from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.services.ai_context_builder import build_ai_sql_context


def _table(db, schema: str, name: str, columns: list[str]):
    db.add(AssetTable(system_code="DATA_CENTER", source_code="ods_test", schema_name=schema, table_name=name))
    db.add_all([AssetColumn(system_code="DATA_CENTER", source_code="ods_test", schema_name=schema, table_name=name, column_name=column) for column in columns])


def _relation(db, *, status="validated", layer="formal", from_cols="PATIENT_ID,VISIT_ID", to_cols="PATIENT_ID,VISIT_ID"):
    db.add(AssetRelation(
        from_table="R167.PAT_VISIT", to_table="R167.ORDERS", from_columns=from_cols, to_columns=to_cols,
        join_condition="p.PATIENT_ID=o.PATIENT_ID AND p.VISIT_ID=o.VISIT_ID", validation_status=status,
        relation_layer=layer, from_system_code="DATA_CENTER", to_system_code="DATA_CENTER",
        from_schema_name="R167", from_table_name="PAT_VISIT", to_schema_name="R167", to_table_name="ORDERS",
    ))


def test_ai_sql_context_includes_formal_join_triple_and_one_hop(db_session):
    _table(db_session, "R167", "PAT_VISIT", ["PATIENT_ID", "VISIT_ID", "ADMISSION_DATE_TIME"])
    _table(db_session, "R167", "ORDERS", ["PATIENT_ID", "VISIT_ID", "ORDER_NO"])
    _relation(db_session)
    db_session.commit()
    context = build_ai_sql_context(db_session, system_code="DATA_CENTER", selected_tables=["R167.PAT_VISIT"])
    assert {row["table_name"] for row in context["tables"]} == {"PAT_VISIT", "ORDERS"}
    assert context["relations"][0]["from_columns"] == ["PATIENT_ID", "VISIT_ID"]
    assert context["relations"][0]["to_columns"] == ["PATIENT_ID", "VISIT_ID"]
    assert "VISIT_ID" in context["relations"][0]["join_condition"]


def test_ai_sql_context_rejects_incomplete_combination_key_and_candidate(db_session):
    _table(db_session, "R167", "PAT_VISIT", ["PATIENT_ID", "VISIT_ID"])
    _table(db_session, "R167", "ORDERS", ["PATIENT_ID", "VISIT_ID"])
    _relation(db_session, from_cols="PATIENT_ID", to_cols="PATIENT_ID")
    _relation(db_session, status="validated", layer="candidate")
    db_session.commit()
    context = build_ai_sql_context(db_session, system_code="DATA_CENTER", selected_tables=["R167.PAT_VISIT"])
    assert context["relations"] == []


def test_ai_sql_context_obeys_all_caps(db_session):
    _table(db_session, "R167", "PAT_VISIT", ["PATIENT_ID", "VISIT_ID"])
    _table(db_session, "R167", "ORDERS", ["PATIENT_ID", "VISIT_ID"])
    _relation(db_session)
    db_session.commit()
    context = build_ai_sql_context(db_session, system_code="DATA_CENTER", selected_tables=["R167.PAT_VISIT"], max_tables=1, max_relations=1, max_payload_bytes=24 * 1024)
    assert len(context["tables"]) <= 1
    assert len(context["relations"]) <= 1
    assert context["payload_bytes"] <= 24 * 1024


def test_ai_sql_context_accepts_current_verified_status(db_session):
    _table(db_session, "R167", "PAT_VISIT", ["PATIENT_ID", "VISIT_ID"])
    _table(db_session, "R167", "ORDERS", ["PATIENT_ID", "VISIT_ID"])
    _relation(db_session, status="verified", layer="formal")
    db_session.commit()
    context = build_ai_sql_context(
        db_session,
        system_code="DATA_CENTER",
        selected_tables=["R167.PAT_VISIT"],
    )
    assert len(context["relations"]) == 1
    assert context["relations"][0]["validation_status"] == "verified"


def test_ai_sql_context_really_fits_small_budget(db_session):
    columns = ["PATIENT_ID", "VISIT_ID"] + [f"EXTRA_{index:03d}" for index in range(120)]
    _table(db_session, "R167", "PAT_VISIT", columns)
    _table(db_session, "R167", "ORDERS", columns)
    _relation(db_session, status="verified", layer="formal")
    db_session.commit()
    context = build_ai_sql_context(
        db_session,
        system_code="DATA_CENTER",
        selected_tables=["R167.PAT_VISIT"],
        max_payload_bytes=2200,
    )
    assert context["payload_bytes"] <= 2200
    assert context["truncated"] is True
    assert {"PATIENT_ID", "VISIT_ID"}.issubset(context["tables"][0]["columns"])
