"""plan139: read-only harvester enhancements (credential format, ssl/tds, modules)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str, alias: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


mysql = load_script("harvest_mysql_readonly.py", "plan139_harvest_mysql")
sqlserver = load_script("harvest_sqlserver_readonly.py", "plan139_harvest_sqlserver")


class FakeCursor:
    """Marker-based fake cursor returning canned rows per SQL substring."""

    def __init__(self, rows_by_marker=None, fail_markers=()):
        self.rows_by_marker = rows_by_marker or {}
        self.fail_markers = tuple(fail_markers)
        self.calls = []
        self.description = [("x",)]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        for marker in self.fail_markers:
            if marker in sql:
                raise RuntimeError(f"denied: {marker}")

    def fetchall(self):
        sql = self.calls[-1][0]
        for marker, rows in self.rows_by_marker.items():
            if marker in sql:
                return rows
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_credential_file_colon_format_is_supported(tmp_path):
    cred = tmp_path / "core2db.readonly"
    cred.write_text("asset_core2_ro:some-secret-value", encoding="utf-8")
    data = mysql.read_credential_file(str(cred))
    assert data == {"user": "asset_core2_ro", "password": "some-secret-value"}
    assert sqlserver.read_credential_file(str(cred)) == data


def test_credential_file_json_format_still_supported(tmp_path):
    cred = tmp_path / "exam.json"
    cred.write_text(json.dumps({"username": "u", "password": "p"}), encoding="utf-8")
    assert mysql.read_credential_file(str(cred)) == {"user": "u", "password": "p"}
    assert sqlserver.read_credential_file(str(cred)) == {"user": "u", "password": "p"}


def test_credential_file_rejects_unknown_format(tmp_path):
    cred = tmp_path / "bad.txt"
    cred.write_text("just-one-token", encoding="utf-8")
    with pytest.raises(ValueError):
        mysql.read_credential_file(str(cred))
    with pytest.raises(ValueError):
        sqlserver.read_credential_file(str(cred))


def test_mysql_ssl_disabled_is_per_connection_opt_in():
    base = {
        "host": "10.10.8.135", "port": 3306, "database": "core2db",
        "credential_env": {"username": "U", "password": "P"},
    }
    plain = mysql._connect_params(base, {"user": "u", "password": "p"})
    assert "ssl_disabled" not in plain
    disabled = mysql._connect_params({**base, "ssl_disabled": True}, {"user": "u", "password": "p"})
    assert disabled["ssl_disabled"] is True


def test_mysql_routine_metadata_blocked_is_recorded_not_extended(monkeypatch):
    cursor = FakeCursor(
        rows_by_marker={"information_schema.ROUTINES": [], "information_schema.TRIGGERS": []},
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(mysql, "_credential", lambda config: {"user": "ro", "password": "secret"})
    monkeypatch.setattr(mysql, "_connect", lambda *a, **k: connection)
    result = mysql.harvest({"host": "db.example", "port": 3306, "database": "core2db"})
    assert result["routine_metadata_status"] == "BLOCKED_ROUTINE_METADATA"
    assert any(e.get("status") == "BLOCKED_ROUTINE_METADATA" for e in result["errors"])
    assert result["source_writes"] == 0


def test_mysql_visible_routines_are_collected(monkeypatch):
    routines = [{"database_name": "core2db", "routine_name": "SP_X", "routine_type": "PROCEDURE"}]
    triggers = [{"database_name": "core2db", "trigger_name": "TR_X"}]
    cursor = FakeCursor(
        rows_by_marker={
            "information_schema.ROUTINES": routines,
            "information_schema.TRIGGERS": triggers,
        },
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(mysql, "_credential", lambda config: {"user": "ro", "password": "secret"})
    monkeypatch.setattr(mysql, "_connect", lambda *a, **k: connection)
    result = mysql.harvest({"host": "db.example", "port": 3306, "database": "core2db"})
    assert result["routines"] == routines
    assert result["triggers"] == triggers
    assert result["summary"]["routines"] == 1


def test_sqlserver_tds_fallback_is_controlled_and_recorded(monkeypatch):
    config = {"host": "db.example", "port": 1433, "tds_version": "7.4", "tds_fallback": "7.0"}
    credentials = {"user": "ro", "password": "secret"}
    attempts = []

    def flaky_connect(cfg, creds, database=None, tds_version=None):
        attempts.append(tds_version or cfg.get("tds_version"))
        if tds_version != "7.0":
            raise RuntimeError("login failed: TDS version mismatch")
        return FakeConnection(FakeCursor())

    monkeypatch.setattr(sqlserver, "_connect", flaky_connect)
    resolved, log = sqlserver.resolve_tds_version(config, credentials)
    assert resolved == "7.0"
    assert attempts == ["7.4", "7.0"]
    assert log[-1]["result"] == "ok_fallback"


def test_sqlserver_tds_failure_without_fallback_raises(monkeypatch):
    config = {"host": "db.example", "port": 1433}
    monkeypatch.setattr(
        sqlserver, "_connect",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no route")),
    )
    with pytest.raises(RuntimeError):
        sqlserver.resolve_tds_version(config, {"user": "ro", "password": "secret"})


def test_sqlserver_collects_modules_synonyms_and_masks_definitions():
    routine_rows = [
        {"database_name": "EIS", "schema_name": "dbo", "routine_name": "P_OK",
         "routine_type": "P", "routine_definition": "CREATE PROC [P_OK] AS SELECT 'X'"},
        {"database_name": "EIS", "schema_name": "dbo", "routine_name": "P_HIDDEN",
         "routine_type": "P", "routine_definition": None},
    ]
    trigger_rows = [
        {"database_name": "EIS", "schema_name": "dbo", "trigger_name": "TR_A",
         "trigger_type": "AFTER", "parent_object": "T1", "is_disabled": "no",
         "trigger_definition": "CREATE TRIGGER [TR_A] ON [T1] AFTER INSERT AS SELECT 'Y'"},
    ]
    synonym_rows = [
        {"database_name": "EIS", "schema_name": "dbo", "synonym_name": "SYN_REMOTE",
         "base_object": "[10_10_9_41].[pitaya].[dbo].[V_BLZLST]"},
    ]
    cursor = FakeCursor(
        rows_by_marker={
            "sys.objects o": routine_rows,
            "sys.triggers t": trigger_rows,
            "sys.synonyms sy": synonym_rows,
        }
    )
    payload = {
        "databases": [], "schemas": [], "tables": [], "views": [], "columns": [],
        "keys": [], "unique_keys": [], "indexes": [], "foreign_keys": [],
        "dependencies": [], "routines": [], "triggers": [], "synonyms": [],
        "errors": [], "database_version": None,
    }
    sqlserver._collect_database(FakeConnection(cursor), "EIS", payload, {"lock_timeout_ms": 1000})
    assert len(payload["routines"]) == 2
    statuses = {row["routine_name"]: row["definition_status"] for row in payload["routines"]}
    assert statuses == {"P_OK": "ok", "P_HIDDEN": "BLOCKED_ROUTINE_METADATA"}
    assert "SELECT 'X'" not in (payload["routines"][0]["routine_definition"] or "")
    assert payload["synonyms"] == synonym_rows
    assert any(e.get("status") == "BLOCKED_ROUTINE_METADATA" for e in payload["errors"])


def test_sqlserver_harvest_records_final_tds_protocol(monkeypatch):
    conn = FakeConnection(FakeCursor(rows_by_marker={"sys.databases": [{"database_name": "tjdatabase4"}]}))
    monkeypatch.setattr(sqlserver, "load_credentials", lambda config: {"user": "ro", "password": "secret"})
    monkeypatch.setattr(sqlserver, "resolve_tds_version", lambda cfg, creds: ("7.0", [{"tds_version": "7.0", "result": "ok_fallback"}]))
    monkeypatch.setattr(sqlserver, "_connect", lambda *a, **k: conn)
    result = sqlserver.harvest({"host": "db.example", "port": 1433, "database": "tjdatabase4"}, check_connection=True)
    assert result["tds_version"] == "7.0"
    assert result["connection_attempts"][0]["result"] == "ok_fallback"
    assert result["source_writes"] == 0
