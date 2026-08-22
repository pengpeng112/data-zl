"""plan139 pure-logic tests for readonly harvester enhancements.

Covers credential-file parsing (JSON and single-line ``user:password``),
per-source ``ssl_disabled``, controlled TDS fallback, blocked routine
metadata status and secret sanitisation.  No database, no network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import harvest_mysql_readonly as mysql_h
from scripts import harvest_sqlserver_readonly as mssql_h


@pytest.fixture()
def text_cred_file(tmp_path: Path) -> Path:
    path = tmp_path / "cred.readonly"
    path.write_text("asset_some_ro:some-secret-value\n", encoding="utf-8")
    return path


@pytest.fixture()
def json_cred_file(tmp_path: Path) -> Path:
    path = tmp_path / "cred.json"
    path.write_text(json.dumps({"user": "u1", "password": "p1"}), encoding="utf-8")
    return path


class TestCredentialFileFormats:
    def test_text_user_password(self, text_cred_file: Path):
        parsed = mysql_h.read_credential_file(text_cred_file)
        assert parsed == {"user": "asset_some_ro", "password": "some-secret-value"}

    def test_json_format(self, json_cred_file: Path):
        assert mssql_h.read_credential_file(json_cred_file) == {"user": "u1", "password": "p1"}

    def test_unsupported_format_rejected(self, tmp_path: Path):
        path = tmp_path / "bad.readonly"
        path.write_text("just-a-password-without-colon", encoding="utf-8")
        with pytest.raises(ValueError):
            mysql_h.read_credential_file(path)

    def test_empty_file_rejected(self, tmp_path: Path):
        path = tmp_path / "empty.readonly"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            mssql_h.read_credential_file(path)

    def test_config_with_file_ref(self, text_cred_file: Path):
        config = {"credentials": {"file": str(text_cred_file)}}
        creds = mssql_h.load_credentials(config)
        assert creds["user"] == "asset_some_ro"
        assert creds["password"]


class TestMysqlSslDisabled:
    def test_ssl_disabled_only_when_configured(self):
        base = {"host": "10.10.8.135", "port": 3306}
        params_off = mysql_h._connect_params(base, {"user": "u", "password": "p"})
        assert "ssl_disabled" not in params_off
        params_on = mysql_h._connect_params(
            {**base, "ssl_disabled": True}, {"user": "u", "password": "p"}
        )
        assert params_on["ssl_disabled"] is True

    def test_transport_note_recorded(self):
        snapshot = mysql_h._empty_snapshot({"host": "h", "port": 1, "ssl_disabled": True})
        assert snapshot["transport"]["ssl_disabled"] is True
        assert snapshot["transport"]["note"]
        plain = mysql_h._empty_snapshot({"host": "h", "port": 1})
        assert plain["transport"]["ssl_disabled"] is False
        assert plain["transport"]["note"] is None


class _FakeCursor:
    """Return canned rows based on SQL fragments; no-op SET statements."""

    def __init__(self, plan: dict[str, Any]):
        self.plan = {key.lower(): value for key, value in plan.items()}
        self._result: list[dict] = []

    def execute(self, sql, params=()):
        lowered = str(sql).lower()
        if lowered.lstrip().startswith("set "):
            return None
        for fragment, outcome in self.plan.items():
            if fragment in lowered:
                if isinstance(outcome, Exception):
                    raise outcome
                self._result = list(outcome)
                return None
        raise AssertionError(f"unexpected SQL: {str(sql)[:120]}")

    def fetchall(self):
        return self._result

    def close(self):
        pass


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def rollback(self):
        pass

    def close(self):
        pass


def _mysql_plan(database: str) -> dict[str, list[dict]]:
    db = database
    return {
        "FROM information_schema.TABLES": [{"TABLE_SCHEMA": db, "TABLE_NAME": "t1"}],
        "FROM information_schema.COLUMNS": [],
        "TABLE_CONSTRAINTS tc": [],
        "information_schema.STATISTICS": [],
        "REFERENCED_TABLE_NAME IS NOT NULL": [],
        "FROM information_schema.VIEWS": [],
        "VIEW_TABLE_USAGE": [],
    }


class TestMysqlRoutineMetadataGate:
    def test_blocked_when_no_visibility(self):
        payload = mysql_h._empty_snapshot({"host": "h", "port": 1})
        cursor = _FakeCursor(_mysql_plan("core2db") | {
            "information_schema.routines": [],
            "information_schema.triggers": [],
        })
        mysql_h._collect_database(cursor, "core2db", payload)
        assert payload["routine_metadata_status"] == "BLOCKED_ROUTINE_METADATA"

    def test_visible_routines_not_blocked(self):
        payload = mysql_h._empty_snapshot({"host": "h", "port": 1})
        rows = [
            {"database_name": "core2db", "routine_name": "r1", "routine_type": "PROCEDURE"}
        ]
        cursor = _FakeCursor(_mysql_plan("core2db") | {
            "information_schema.routines": rows,
            "information_schema.triggers": [],
        })
        mysql_h._collect_database(cursor, "core2db", payload)
        assert payload["routine_metadata_status"] is None
        assert payload["routines"] == rows

    def test_error_records_blocked_status(self):
        payload = mysql_h._empty_snapshot({"host": "h", "port": 1})
        cursor = _FakeCursor(_mysql_plan("core2db") | {
            "information_schema.routines": RuntimeError("(1142) command denied"),
        })
        mysql_h._collect_database(cursor, "core2db", payload)
        assert payload["routine_metadata_status"] == "BLOCKED_ROUTINE_METADATA"
        assert any(e["scope"] == "routine_metadata" for e in payload["errors"])


class TestTdsFallback:
    config = {
        "host": "10.10.9.41",
        "port": 1433,
        "databases": ["pitaya"],
        "tds_fallback": "7.0",
    }
    creds = {"user": "u", "password": "p"}

    @staticmethod
    def _fake_probe(*_args, **_kwargs):
        class _Probe:
            def rollback(self):
                pass

            def close(self):
                pass

        return _Probe()

    def test_default_success_skips_fallback(self, monkeypatch):
        made: list[Any] = []

        def fake_connect(config, credentials, database=None, tds_version=None):
            made.append(tds_version)
            return self._fake_probe()

        monkeypatch.setattr(mssql_h, "_connect", fake_connect)
        resolved, attempts = mssql_h.resolve_tds_version(self.config, self.creds)
        assert resolved is None
        assert attempts[0]["result"] == "ok"
        assert len(made) == 1

    def test_fallback_used_when_default_fails(self, monkeypatch):
        calls: list[str | None] = []

        def fake_connect(config, credentials, database=None, tds_version=None):
            calls.append(tds_version)
            if tds_version != "7.0":
                raise RuntimeError("login failed: unsupported TDS negotiation")
            return self._fake_probe()

        monkeypatch.setattr(mssql_h, "_connect", fake_connect)
        resolved, attempts = mssql_h.resolve_tds_version(self.config, self.creds)
        assert resolved == "7.0"
        assert [a["result"] for a in attempts] == ["failed", "ok_fallback"]

    def test_both_fail_raise(self, monkeypatch):
        def fake_connect(config, credentials, database=None, tds_version=None):
            raise RuntimeError("no route to host")

        monkeypatch.setattr(mssql_h, "_connect", fake_connect)
        with pytest.raises(RuntimeError):
            mssql_h.resolve_tds_version(self.config, self.creds)


def _mssql_plan(extra: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "db_name() as database_name": [
            {"database_name": "pitaya", "database_version": "10.50.4000", "collation": "Chinese_PRC_CI_AS"}
        ],
        "from sys.schemas": [],
        "from sys.tables t join": [],
        "from sys.views v": [],
        "o.type in ('u','v')": [],
        "sys.key_constraints": [],
        "from sys.indexes i": [],
        "from sys.foreign_keys fk": [],
        "sys.sql_expression_dependencies": [],
        "from sys.synonyms sy": [],
        "from sys.triggers t": [],
    }
    plan.update({key.lower(): value for key, value in extra.items()})
    return plan


def _collect_mssql(extra: dict[str, Any], database: str = "pitaya"):
    payload = mssql_h._empty_snapshot({"host": "h", "port": 1})
    cursor = _FakeCursor(_mssql_plan(extra))
    mssql_h._collect_database(_FakeConnection(cursor), database, payload, {"host": "h", "port": 1})
    return payload


class TestSqlServerRoutineDefinitionGate:
    def test_null_definition_marked_blocked(self):
        payload = _collect_mssql({
            "o.type in ('p','fn','if','tf')": [
                {"database_name": "pitaya", "schema_name": "dbo", "routine_name": "vis",
                 "routine_type": "SQL_STORED_PROCEDURE",
                 "routine_definition": "CREATE PROCEDURE vis AS SELECT 1"},
                {"database_name": "pitaya", "schema_name": "dbo", "routine_name": "hidden",
                 "routine_type": "SQL_SCALAR_FUNCTION", "routine_definition": None},
            ],
        })
        statuses = {row["routine_name"]: row["definition_status"] for row in payload["routines"]}
        assert statuses == {"vis": "ok", "hidden": "BLOCKED_ROUTINE_METADATA"}
        hidden = next(row for row in payload["routines"] if row["routine_name"] == "hidden")
        assert hidden["routine_definition"] is None
        assert any(
            e.get("status") == "BLOCKED_ROUTINE_METADATA" and e.get("count") == 1
            for e in payload["errors"]
        )

    def test_definitions_sanitised(self):
        payload = _collect_mssql({
            "o.type in ('p','fn','if','tf')": [
                {"database_name": "pitaya", "schema_name": "dbo", "routine_name": "p1",
                 "routine_type": "SQL_STORED_PROCEDURE",
                 "routine_definition": "SELECT 'http://admin:hunter2@host/x' AS a"},
            ],
        })
        definition = payload["routines"][0]["routine_definition"]
        assert definition is not None
        assert "hunter2" not in definition
        assert "***" in definition


class TestSanitisation:
    def test_url_and_param_masks(self):
        dirty = "http://app:hunter2@host/p?a=1&token=abc123 password=Sup3rSecret"
        clean = mssql_h.sanitize_view_definition(dirty)
        assert "hunter2" not in clean
        assert "token=***" in clean
        assert "abc123" not in clean
        assert "Sup3r" not in clean

    def test_bounded_length(self):
        out = mysql_h.sanitize_view_definition("x" * 2_000_000)
        assert len(out) <= 1_000_000

    def test_none_passthrough(self):
        assert mysql_h.sanitize_view_definition(None) is None


class TestHarvesterSqlRegression:
    """Guard against dialect-level SQL bugs found during plan139 S3."""

    def test_mysql_key_query_qualifies_ambiguous_columns(self):
        source = Path(mysql_h.__file__).read_text(encoding="utf-8")
        keys_query = source[source.index("SELECT tc.TABLE_SCHEMA database_name") : source.index('batch["keys"].extend')]
        assert "USING (" not in keys_query, "USING join makes TABLE_SCHEMA ambiguous on MySQL 5.7"
        assert "tc.TABLE_SCHEMA database_name" in keys_query
        assert "ku.COLUMN_NAME column_name" in keys_query

    def test_sqlserver_dependency_query_uses_real_columns(self):
        source = Path(mssql_h.__file__).read_text(encoding="utf-8")
        deps_query = source[source.index('payload["dependencies"].extend') :]
        deps_query = deps_query[deps_query.index('"""') + 3 :]
        deps_query = deps_query[: deps_query.index('"""')]
        assert "sed.referenced_database_name" in deps_query
        assert "sed.referenced_schema_name" in deps_query
        assert "sed.referenced_entity_name" in deps_query
        assert "sed.referenced_database," not in deps_query
