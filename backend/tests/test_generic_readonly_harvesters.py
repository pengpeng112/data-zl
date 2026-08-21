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
