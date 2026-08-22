from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name[:-3]] = module
    spec.loader.exec_module(module)
    return module


mysql = load_script("harvest_mysql_readonly.py")
sqlserver = load_script("harvest_sqlserver_readonly.py")


class FakeCursor:
    def __init__(self, rows_by_sql):
        self.rows_by_sql = rows_by_sql
        self.calls = []
        self.description = [("version",)]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        for marker, rows in self.rows_by_sql.items():
            if marker in self.calls[-1][0]:
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


def test_sanitizers_remove_secrets_and_bound_errors():
    text = "https://user:super-secret@example.test/a?password=also-secret token=third-secret"
    assert "super-secret" not in mysql.sanitize_text(text)
    assert "also-secret" not in mysql.sanitize_text(text)
    assert "third-secret" not in mysql.sanitize_text(text)
    assert len(mysql.sanitize_text("x" * 5000)) == 1000
    assert len(mysql.sanitize_view_definition("x" * 5000)) == 5000
    assert mysql.sanitize_view_definition(None) is None


def test_credentials_are_only_loaded_from_env_or_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GENERIC_DB_USER", "reader")
    monkeypatch.setenv("GENERIC_DB_PASSWORD", "not-in-output")
    config = {"credential_env": {"username": "GENERIC_DB_USER", "password": "GENERIC_DB_PASSWORD"}}
    assert mysql._credential(config) == {"user": "reader", "password": "not-in-output"}
    with pytest.raises(RuntimeError):
        mysql._credential({"user": "reader", "password": "inline-is-not-accepted"})
    credential_file = tmp_path / "credentials.json"
    credential_file.write_text(json.dumps({"username": "file-reader", "password": "file-secret"}), encoding="utf-8")
    assert sqlserver.load_credentials({"credential_file": str(credential_file)})["user"] == "file-reader"


def test_mysql_check_connection_rolls_back_without_writing(monkeypatch):
    cursor = FakeCursor({"VERSION()": [{"version": "MySQL 8.0", "database_name": "core2db"}]})
    connection = FakeConnection(cursor)
    monkeypatch.setattr(mysql, "_credential", lambda config: {"user": "reader", "password": "secret"})
    monkeypatch.setattr(mysql, "_connect", lambda *args, **kwargs: connection)
    result = mysql.harvest({"host": "db.example", "port": 3306}, check_connection=True)
    assert result["read_only"] is True
    assert result["source_writes"] == 0
    assert result["summary"]["connected"] is True
    assert connection.rolled_back and connection.closed
    assert any("TRANSACTION READ ONLY" in sql for sql, _ in cursor.calls)


def test_configured_database_does_not_expand_to_instance(monkeypatch):
    cursor = FakeCursor({"VERSION()": [{"version": "MySQL 8.0"}]})
    connection = FakeConnection(cursor)
    monkeypatch.setattr(mysql, "_credential", lambda config: {"user": "reader", "password": "secret"})
    monkeypatch.setattr(mysql, "_connect", lambda *args, **kwargs: connection)
    result = mysql.harvest({"host": "db.example", "port": 3306, "database": "core2db"})
    assert result["databases"] == ["core2db"]
    assert not any("information_schema.SCHEMATA" in sql for sql, _ in cursor.calls)


def test_sqlserver_discovery_is_non_system_and_rolls_back(monkeypatch):
    cursor = FakeCursor({"sys.databases": [{"database_name": "master"}, {"database_name": "exam"}, {"database_name": "occupational"}]})
    connection = FakeConnection(cursor)
    monkeypatch.setattr(sqlserver, "load_credentials", lambda config: {"user": "reader", "password": "secret"})
    monkeypatch.setattr(sqlserver, "_connect", lambda *args, **kwargs: connection)
    result = sqlserver.harvest({"host": "db.example", "port": 1433}, discover_databases=True)
    assert result["databases"] == ["exam", "occupational"]
    assert result["source_writes"] == 0
    assert connection.rolled_back and connection.closed
    assert any("READ UNCOMMITTED" in sql for sql, _ in cursor.calls)
    assert any("LOCK_TIMEOUT" in sql for sql, _ in cursor.calls)


def test_credential_file_supports_user_password_line(tmp_path):
    file_one_line = tmp_path / "cred.readonly"
    file_one_line.write_text("asset_ro:s3cret-value\n", encoding="utf-8")
    assert mysql.read_credential_file(file_one_line) == {"user": "asset_ro", "password": "s3cret-value"}
    assert sqlserver.read_credential_file(file_one_line) == {"user": "asset_ro", "password": "s3cret-value"}
    file_json = tmp_path / "cred.json"
    file_json.write_text(json.dumps({"username": "u2", "password": "p2"}), encoding="utf-8")
    assert mysql.read_credential_file(file_json) == {"user": "u2", "password": "p2"}
    bad = tmp_path / "bad.txt"
    bad.write_text("only-user-no-separator", encoding="utf-8")
    with pytest.raises(ValueError):
        mysql.read_credential_file(bad)


def test_mysql_ssl_disabled_is_per_source_optin_only():
    credentials = {"user": "reader", "password": "secret"}
    base = mysql._connect_params({"host": "db.example", "port": 3306}, credentials)
    assert "ssl_disabled" not in base
    optin = mysql._connect_params({"host": "db.example", "port": 3306, "ssl_disabled": True}, credentials)
    assert optin["ssl_disabled"] is True


class FlakyConnect:
    def __init__(self, fail_first):
        self.fail_first = fail_first
        self.calls = []

    def __call__(self, config, credentials, database=None, tds_version=None):
        self.calls.append(tds_version or "default")
        if self.fail_first and (tds_version or "default") != "7.0":
            raise RuntimeError("login failed: version check")
        return FakeConnection(FakeCursor({}))


def test_sqlserver_tds_fallback_is_controlled_and_recorded(monkeypatch):
    connect = FlakyConnect(fail_first=True)
    monkeypatch.setattr(sqlserver, "_connect", connect)
    tds, attempts = sqlserver.resolve_tds_version(
        {"host": "db.example", "port": 1433, "tds_version": "auto", "tds_fallback": "7.0"},
        {"user": "reader", "password": "secret"},
    )
    assert tds == "7.0"
    assert [a["result"] for a in attempts] == ["failed", "ok_fallback"]
    assert all("password" not in json.dumps(a).lower() or "s3cret" not in json.dumps(a) for a in attempts)

    connect_ok = FlakyConnect(fail_first=False)
    monkeypatch.setattr(sqlserver, "_connect", connect_ok)
    tds2, attempts2 = sqlserver.resolve_tds_version(
        {"host": "db.example", "port": 1433}, {"user": "reader", "password": "secret"}
    )
    assert tds2 is None and attempts2[0]["result"] == "ok"

    always_fail = FlakyConnect(fail_first=True)
    monkeypatch.setattr(sqlserver, "_connect", always_fail)
    with pytest.raises(RuntimeError):
        sqlserver.resolve_tds_version(
            {"host": "db.example", "port": 1433, "tds_version": "auto"},
            {"user": "reader", "password": "secret"},
        )


def test_mysql_routine_metadata_blocked_is_recorded(monkeypatch):
    cursor = FakeCursor({"VERSION()": [{"version": "5.7.40"}]})
    connection = FakeConnection(cursor)
    monkeypatch.setattr(mysql, "_credential", lambda config: {"user": "reader", "password": "secret"})
    monkeypatch.setattr(mysql, "_connect", lambda *args, **kwargs: connection)
    result = mysql.harvest({"host": "db.example", "port": 3306, "database": "core2db"})
    assert result["routine_metadata_status"] == "BLOCKED_ROUTINE_METADATA"
    assert result["routines"] == [] and result["triggers"] == []
    assert result["source_writes"] == 0
    assert not any("ROUTINE_DEFINITION" in sql for sql, _ in cursor.calls)


def test_sqlserver_routine_definitions_are_sanitized_and_blocked_flagged(monkeypatch):
    cursor = FakeCursor({
        "SERVERPROPERTY": [{"database_version": "14.0.3041"}],
        "sys.objects o": [{"database_name": "EIS", "schema_name": "dbo", "routine_name": "sp_x",
                           "routine_type": "SQL_STORED_PROCEDURE", "routine_definition": "CREATE PROC sp_x AS SELECT 'a'"}],
        "sys.triggers": [],
        "sys.synonyms": [{"database_name": "EIS", "schema_name": "dbo", "synonym_name": "syn_remote",
                          "base_object": "[10.0.0.1].db.dbo.t"}],
    })
    connection = FakeConnection(cursor)
    monkeypatch.setattr(sqlserver, "load_credentials", lambda config: {"user": "reader", "password": "secret"})
    monkeypatch.setattr(sqlserver, "_connect", lambda *args, **kwargs: connection)
    result = sqlserver.harvest({"host": "db.example", "port": 1433, "databases": ["EIS"], "lock_timeout_ms": 1000})
    assert result["routines"][0]["definition_status"] == "ok"
    assert "'a'" not in result["routines"][0]["routine_definition"]
    assert result["synonyms"][0]["base_object"].startswith("[")
    assert result["summary"]["routines"] == 1
    assert result["source_writes"] == 0
    assert not any("EXECUTE " in sql.upper().replace("EXECUTE IMMEDIATE", "") for sql, _ in cursor.calls if "EXEC (" in sql.upper())


def test_sqlserver_blocked_routine_definitions_reported(monkeypatch):
    cursor = FakeCursor({
        "SERVERPROPERTY": [{"database_version": "10.50.4000"}],
        "sys.objects o": [{"database_name": "pitaya", "schema_name": "dbo", "routine_name": "hidden_proc",
                           "routine_type": "SQL_STORED_PROCEDURE", "routine_definition": None}],
        "sys.triggers": [],
        "sys.synonyms": [],
    })
    connection = FakeConnection(cursor)
    monkeypatch.setattr(sqlserver, "load_credentials", lambda config: {"user": "reader", "password": "secret"})
    monkeypatch.setattr(sqlserver, "_connect", lambda *args, **kwargs: connection)
    result = sqlserver.harvest({"host": "db.example", "port": 1433, "databases": ["pitaya"], "lock_timeout_ms": 1000})
    assert result["routines"][0]["definition_status"] == "BLOCKED_ROUTINE_METADATA"
    assert result["routines"][0]["routine_definition"] is None
    assert any(e.get("status") == "BLOCKED_ROUTINE_METADATA" for e in result["errors"])
