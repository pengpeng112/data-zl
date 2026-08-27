"""A07: tables/columns must exist exactly in the current metadata snapshot."""
from __future__ import annotations

from app.services.query_semantic_validator import (
    build_validation_report,
    resolve_table,
    validate_metadata_layer,
)

_METADATA = {
    ("HIS", "PAT_VISIT"): {"columns": {"PATIENT_ID", "VISIT_ID"}, "system_code": "HIS", "source_code": "his_src"},
    ("HIS", "INP_BILL_DETAIL"): {"columns": {"PATIENT_ID", "VISIT_ID", "COST"}, "system_code": "HIS", "source_code": "his_src"},
    ("ODS", "PAT_VISIT"): {"columns": {"PATIENT_ID"}, "system_code": "DATA_CENTER", "source_code": "ods_src"},
}


def test_exact_schema_qualified_table_resolves():
    assert resolve_table(_METADATA, "HIS.PAT_VISIT") == ("HIS", "PAT_VISIT")


def test_ambiguous_bare_name_fails_closed():
    # PAT_VISIT exists in two schemas → bare name must not guess
    assert resolve_table(_METADATA, "PAT_VISIT") is None


def test_unknown_table_blocks_g1():
    sql = "SELECT PATIENT_ID FROM HIS.NOT_A_TABLE"
    layer = validate_metadata_layer(sql, "oracle", _METADATA)
    assert layer["status"] == "blocked"
    assert any("NOT_A_TABLE" in f["message"] for f in layer["findings"])


def test_existing_tables_pass_g1():
    sql = "SELECT v.PATIENT_ID FROM HIS.PAT_VISIT v"
    layer = validate_metadata_layer(sql, "oracle", _METADATA)
    assert layer["status"] == "pass"
    assert {t["object_name"] for t in layer["tables"]} == {"PAT_VISIT"}


def test_stale_snapshot_reported_as_stale():
    sql = "SELECT PATIENT_ID FROM HIS.PAT_VISIT"
    report = build_validation_report(
        sql, "oracle", metadata_tables=_METADATA, relations=[], snapshot_stale=True
    )
    assert report["overall"] == "stale"
    assert any(f.get("code") == "E_METADATA_STALE" for l in report["layers"] for f in l["findings"])


def test_report_carries_validation_digest():
    report = build_validation_report(
        "SELECT PATIENT_ID FROM HIS.PAT_VISIT", "oracle", metadata_tables=_METADATA, relations=[]
    )
    assert len(report["validation_digest"]) == 64
