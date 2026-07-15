"""SQL Server connector driver selection unit tests (no real DB)."""
import sys
from types import SimpleNamespace

from app.services.db_connectors import SqlServerConnector


def test_sqlserver_connect_masks_password_on_failure():
    c = SqlServerConnector(
        host="127.0.0.1",
        port=1433,
        database="no_such_db",
        user="sa",
        password="SuperSecretPwd!",
        timeout_ms=1000,
    )
    ok, msg, elapsed = c.test_connectivity()
    assert ok is False
    assert "SuperSecretPwd!" not in msg
    assert elapsed >= 0


def test_sqlserver_readonly_sql_validation():
    c = SqlServerConnector(host="x", port=1433, database="d", user="u", password="p")
    try:
        c._validate_readonly_sql("UPDATE t SET a=1")
        assert False, "should reject"
    except ValueError:
        pass
    assert c._validate_readonly_sql("SELECT 1") == "SELECT 1"


def test_sqlserver_legacy_tds_fallback(monkeypatch):
    calls = []
    connection = object()

    def connect(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tds_version") != "7.0":
            raise OSError("legacy protocol required")
        return connection

    monkeypatch.setitem(sys.modules, "pyodbc", None)
    monkeypatch.setitem(sys.modules, "pymssql", SimpleNamespace(connect=connect))
    connector = SqlServerConnector(host="db", port=1433, database="legacy", user="u", password="p")

    assert connector.connect() is connection
    assert connector._driver == "pymssql"
    assert len(calls) == 2
    assert "tds_version" not in calls[0]
    assert calls[1]["tds_version"] == "7.0"
