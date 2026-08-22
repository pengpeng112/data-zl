"""Pure-logic tests for plan-139 package builder, importer helpers and validator."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return _load("build_plan139_asset_package")


@pytest.fixture(scope="module")
def importer():
    return _load("import_plan139_sources_to_platform")


@pytest.fixture(scope="module")
def validator():
    return _load("run_plan139_validations")


# ---------------- build_plan139_asset_package ----------------

def test_namespace_single_db_vs_multi_db(builder):
    core = builder.SYSTEMS["CORE2DB"]
    exam = builder.SYSTEMS["PHYSICAL_EXAM"]
    assert builder.namespace_for(core, "core2db") == "CORE2DB"
    assert builder.namespace_for(exam, "EIS", "dbo") == "EIS.DBO"
    assert builder.namespace_for(exam, "jzcis", None) == "JZCIS.DBO"


def test_governance_flags_pending_but_never_excludes(builder):
    keep, reason = builder.governance_flag("PAT_VISIT")
    assert keep == "keep" and reason == ""
    status, reason = builder.governance_flag("LOG_20260101")
    assert status == "pending"
    assert reason == "log_name"
    status, _ = builder.governance_flag("MedRecord_bak")
    assert status == "pending"
    status, _ = builder.governance_flag("tmp_cache")
    assert status == "pending"


def _mysql_snapshot() -> dict:
    return {
        "source": {"db_type": "mysql", "endpoint": "10.10.8.135:3306", "read_only": True},
        "collected_at": "2026-08-22T00:00:00+00:00",
        "database_version": "5.7.20-log",
        "databases": ["core2db"],
        "tables": [{"database_name": "core2db", "table_name": "patient", "table_type": "BASE TABLE",
                    "engine": "InnoDB", "estimated_rows": 10, "comment": "患者"}],
        "views": [{"database_name": "core2db", "view_name": "v_patient",
                   "view_definition": "select `p`.`id` AS `id` from `core2db`.`patient` `p`"}],
        "columns": [{"database_name": "core2db", "table_name": "patient", "ordinal_position": 1,
                     "column_name": "id", "data_type": "bigint", "is_nullable": "NO",
                     "column_default": None, "column_key": "PRI", "extra": "", "comment": ""}],
        "keys": [{"database_name": "core2db", "table_name": "patient", "constraint_name": "PRIMARY",
                  "column_name": "id", "ordinal_position": 1, "constraint_type": "PRIMARY KEY"}],
        "unique_keys": [], "indexes": [], "foreign_keys": [
            {"database_name": "core2db", "table_name": "patient", "constraint_name": "fk_visit",
             "column_name": "visit_id", "ordinal_position": 1, "referenced_database": "core2db",
             "referenced_table": "visit", "referenced_column": "id"}],
        "dependencies": [], "routines": [], "triggers": [],
        "routine_metadata_status": "BLOCKED_ROUTINE_METADATA",
        "errors": [], "summary": {}, "source_writes": 0,
    }


def _sqlserver_snapshot() -> dict:
    return {
        "source": {"db_type": "sqlserver", "endpoint": "10.10.10.96:1433", "read_only": True},
        "collected_at": "2026-08-22T00:00:00+00:00",
        "database_version": "12.0.2000.8",
        "databases": [{"database_name": "EIS", "collation": "x"}],
        "schemas": [{"database_name": "EIS", "schema_name": "dbo"}],
        "tables": [{"database_name": "EIS", "schema_name": "dbo", "table_name": "ExamItem",
                    "estimated_rows": 5, "comment": None}],
        "views": [{"database_name": "EIS", "schema_name": "dbo", "view_name": "v_items",
                   "view_definition": "CREATE VIEW dbo.v_items AS SELECT a.ID, b.Name FROM dbo.ExamItem a "
                                      "JOIN dbo.ItemName b ON a.NameID = b.ID",
                   "comment": None}],
        "columns": [{"database_name": "EIS", "schema_name": "dbo", "object_name": "ExamItem",
                     "object_type": "USER_TABLE", "column_id": 1, "column_name": "ID",
                     "data_type": "int", "max_length": 4, "precision": 10, "scale": 0,
                     "is_nullable": 0, "is_identity": 1, "is_computed": 0,
                     "default_definition": None, "comment": None}],
        "keys": [{"database_name": "EIS", "schema_name": "dbo", "table_name": "ExamItem",
                  "constraint_name": "PK_ExamItem", "type_desc": "PRIMARY_KEY_CONSTRAINT",
                  "key_ordinal": 1, "column_name": "ID"}],
        "unique_keys": [], "indexes": [], "foreign_keys": [],
        "dependencies": [{"database_name": "EIS", "referencing_schema": "dbo",
                          "referencing_object": "v_items", "referenced_database": None,
                          "referenced_schema": "dbo", "referenced_entity_name": "ExamItem"}],
        "routines": [], "triggers": [], "synonyms": [], "tds_version": "7.0",
        "connection_attempts": [], "errors": [], "summary": {}, "source_writes": 0,
    }


def test_build_mysql_source_normalizes_fk_and_view(builder):
    system = builder.SYSTEMS["CORE2DB"]
    intake = {"dependencies": [], "candidates": [], "unresolved": [], "summary": {}}
    built = builder.build_source(system, _mysql_snapshot(), intake)
    objs = {(o["namespace"], o["object_name"], o["object_type"]) for o in built["objects"]}
    assert ("CORE2DB", "patient", "table") in objs
    assert ("CORE2DB", "v_patient", "view") in objs
    assert len(built["fk_relations"]) == 1
    fk = built["fk_relations"][0]
    assert fk["from_table"] == "CORE2DB.PATIENT"
    assert fk["to_table"] == "CORE2DB.VISIT"
    assert fk["from_columns"] == "VISIT_ID" and fk["to_columns"] == "ID"
    assert any(c["constraint_type"] == "FOREIGN KEY" for c in built["constraints"])


def test_build_sqlserver_source_namespaces_db_schema(builder):
    system = builder.SYSTEMS["PHYSICAL_EXAM"]
    intake = builder.__dict__.get("_intake_stub") or {
        "dependencies": [], "candidates": [], "unresolved": [], "summary": {}}
    built = builder.build_source(system, _sqlserver_snapshot(), intake)
    objs = {(o["namespace"], o["object_name"]) for o in built["objects"]}
    assert ("EIS.DBO", "ExamItem") in objs
    assert ("EIS.DBO", "v_items") in objs
    assert built["view_records"][0]["owner"] == "EIS.DBO"


def test_dependency_cross_check_matches_engine_names(builder):
    system = builder.SYSTEMS["PHYSICAL_EXAM"]
    intake = {"dependencies": [{"owner": "EIS.DBO", "view": "V_ITEMS", "table": "EIS.DBO.EXAMITEM"}]}
    built = builder.build_source(system, _sqlserver_snapshot(), intake)
    cross = builder.dependency_cross_check(built)
    assert cross["engine_reported"] >= 1
    assert cross["engine_matched_by_parser"] >= 1


# ---------------- import_plan139_sources_to_platform ----------------

def test_normalize_columns_handles_stringified_lists(importer):
    assert importer._normalize_columns("['A', 'B']") == "A,B"
    assert importer._normalize_columns("A,B") == "A,B"
    assert importer._normalize_columns("['ID']") == "ID"
    assert importer._normalize_columns("") == ""


def test_resolve_endpoint_prefers_full_namespace(importer):
    objects = [
        {"namespace": "JZCIS.DBO", "object_name": "JCXX"},
        {"namespace": "EIS.DBO", "object_name": "JCXX"},
    ]
    index = importer._full_name_index(objects)
    assert importer._resolve_endpoint(index, "DBO.JCXX") in {"JZCIS.DBO.JCXX", "EIS.DBO.JCXX"}
    assert importer._resolve_endpoint(index, "EIS.DBO.JCXX") == "EIS.DBO.JCXX"
    assert importer._resolve_endpoint(index, "DBO.NOTHING") is None


def test_confirmation_gate_rejects_wrong_string(importer, tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    for name, rows in (
        ("objects.csv", []), ("columns.csv", []), ("constraints.csv", []),
        ("view_dependencies.csv", []), ("relation_candidates.csv", []),
    ):
        (pkg / name).write_text(",".join(["x"]) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="confirm"):
        importer.execute(pkg, run_id="t", apply=True, confirm="WRONG")


# ---------------- run_plan139_validations ----------------

def test_validator_rejects_unsafe_identifiers(validator):
    item = {"from_table": "dbo.T; drop table x", "to_table": "dbo.U",
            "from_columns": "A", "to_columns": "B"}
    with pytest.raises(ValueError):
        validator.build_sqlserver_query(item)


def test_validator_builds_bounded_sqlserver_query(validator):
    item = {"_from": "JZCIS.dbo.JCXX", "_to": "JZCIS.dbo.DWMC",
            "from_columns": "DWDM", "to_columns": "DWDM"}
    sql = validator.build_sqlserver_query(item)
    assert "TOP (10000)" in sql
    assert "[JZCIS].[dbo].[JCXX]" in sql
    assert "COUNT(*) AS sampled" in sql
    assert "READ" not in sql.split("WITH")[0]


def test_validator_columns_parser(validator):
    assert validator._columns("['A']") == ["A"]
    assert validator._columns("A,B") == ["A", "B"]
    assert validator._columns("['A', 'B']") == ["A", "B"]


# ---------------- 143: OA source extension ----------------

def test_oa_system_registered_with_db_schema_namespace(builder):
    assert "OA" in builder.SYSTEMS
    oa = builder.SYSTEMS["OA"]
    assert oa["db_type"] == "sqlserver" and oa["databases"] == ["oa"]
    assert oa["source_code"] == "oa_sqlserver_10_10_10_69"
    # multi-schema source: namespace keeps db.schema (ezoffice/dbo), not bare db
    assert "OA" not in builder.SINGLE_DB_SYSTEMS
    assert builder.namespace_for(oa, "oa", "ezoffice") == "OA.EZOFFICE"
    assert builder.namespace_for(oa, "oa", None) == "OA.DBO"


def test_oa_import_profile_and_confirmation(importer):
    assert "OA" in importer.SOURCE_REGISTRY
    profile = importer.SOURCE_REGISTRY["OA"]
    assert profile["system_type"] == "OA"
    assert profile["default_schema"] == "oa.ezoffice"
    assert "APPLY-PLAN139-FOUR-SOURCES" in importer.CONFIRM_TEXTS
    assert "APPLY-PLAN139-OA-SOURCE" in importer.CONFIRM_TEXTS


def test_confirmation_rejects_unknown_string(importer, tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    for name in ("objects.csv", "columns.csv", "constraints.csv",
                 "view_dependencies.csv", "relation_candidates.csv"):
        (pkg / name).write_text("x\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="confirm"):
        importer.execute(pkg, run_id="t", apply=True, confirm="NOT-A-CONFIRM")
