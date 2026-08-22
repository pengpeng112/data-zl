"""Configuration-driven, read-only MySQL metadata harvester.

The script deliberately keeps the driver import and all network activity inside
``main``/``harvest``.  This makes the module safe to import in tests and makes
it possible to exercise the metadata normalisation without a database.

Configuration is JSON (or a mapping passed to :func:`harvest`).  Credentials
are never accepted as configuration values: use environment variable names or
the path to a short-lived JSON credential file instead.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}
SECRET_KEY_RE = re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)")
URL_SECRET_RE = re.compile(r"(?i)(://[^:/@\s]+:)[^@/\s]+(@)")
PARAM_SECRET_RE = re.compile(
    r"(?i)([?&#](?:password|passwd|pwd|token|secret|api[_-]?key)=)[^&#'\"\s]+"
)


def _sanitize(value: Any, *, limit: int) -> str:
    text = str(value or "")
    text = URL_SECRET_RE.sub(r"\1***\2", text)
    text = PARAM_SECRET_RE.sub(r"\1***", text)
    text = re.sub(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*[^,;\s]+", r"\1=***", text)
    return text[:limit]


def sanitize_text(value: Any) -> str:
    """Return a bounded, credential-free diagnostic string."""
    return _sanitize(value, limit=1000)


def sanitize_view_definition(value: Any) -> str | None:
    if value is None:
        return None
    return _sanitize(value, limit=1_000_000)


def read_credential_file(file_name: Any) -> dict[str, str]:
    """Read a credential file as JSON or as the single-line ``user:password``."""
    text = Path(str(file_name)).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("credential file is empty")
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, Mapping):
            raise ValueError("credential file must contain an object")
        result: dict[str, str] = {}
        for key in ("user", "username", "password"):
            if data.get(key) is not None:
                result["user" if key in {"user", "username"} else key] = str(data[key])
        return result
    if "\n" not in text and ":" in text:
        user, password = text.split(":", 1)
        return {"user": user.strip(), "password": password.strip()}
    raise ValueError("unsupported credential file format")


def _credential(config: Mapping[str, Any]) -> dict[str, str]:
    """Load credentials from an env mapping or a credential file only."""
    ref = config.get("credentials") or config.get("credential") or {}
    if not isinstance(ref, Mapping):
        raise ValueError("credentials must be an object containing env/file references")
    result: dict[str, str] = {}
    file_name = ref.get("file") or config.get("credential_file") or config.get("credentials_file")
    if file_name:
        data = read_credential_file(file_name)
        result.update({key: value for key, value in data.items() if key in {"user", "password"}})
    env_names = ref.get("env") or config.get("credential_env") or {}
    if isinstance(env_names, Mapping):
        for key, env_name in env_names.items():
            if key in {"user", "username"}:
                target = "user"
            elif key == "password":
                target = key
            else:
                continue
            if env_name and os.environ.get(str(env_name)) is not None:
                result[target] = os.environ[str(env_name)]
    # Conventional names are opt-in through config, but support the compact
    # form useful for one-off controlled execution.
    user_env = ref.get("user_env") or ref.get("username_env") or config.get("user_env") or config.get("username_env")
    password_env = ref.get("password_env") or config.get("password_env")
    if not result.get("user") and user_env:
        result["user"] = os.environ.get(str(user_env), "")
    if not result.get("password") and password_env:
        result["password"] = os.environ.get(str(password_env), "")
    if not result.get("user") or not result.get("password"):
        raise RuntimeError("credentials unavailable; provide configured environment variables or credential file")
    return result


def load_config(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must contain a JSON object")
    source = data.get("source", data)
    if "source" not in data and isinstance(data.get("endpoint"), dict):
        source = {**{key: value for key, value in data.items() if key != "endpoint"}, **data["endpoint"]}
    if not isinstance(source, dict):
        raise ValueError("config.source must be an object")
    required = ("host", "port")
    if any(source.get(key) in (None, "") for key in required):
        raise ValueError("config requires source.host and source.port")
    if "source" in data:
        source = {**{key: value for key, value in data.items() if key != "source"}, **source}
    return source


def _rows(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], Mapping):
        return [dict(row) for row in rows]
    names = [str(item[0]).lower() for item in (getattr(cursor, "description", None) or [])]
    return [dict(zip(names, row)) for row in rows]


def _row(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = _rows(cursor, sql, params)
    return rows[0] if rows else {}


def _connect_params(config: Mapping[str, Any], credentials: Mapping[str, str], database: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "host": str(config["host"]), "port": int(config["port"]), "user": credentials["user"],
        "password": credentials["password"], "database": database or config.get("database"),
        "charset": str(config.get("charset", "utf8mb4")), "connect_timeout": int(config.get("connect_timeout", 10)),
        "read_timeout": int(config.get("read_timeout", 90)), "write_timeout": int(config.get("write_timeout", 15)),
        "autocommit": False, "cursorclass": None,
        "program_name": "DataAssetReadOnlyMetadataHarvest",
    }
    if config.get("ssl_disabled") is True:
        # Per-source opt-in only (plan 139 S1): never a global downgrade.
        params["ssl_disabled"] = True
    return params


def _connect(config: Mapping[str, Any], credentials: Mapping[str, str], database: str | None = None) -> Any:
    import pymysql

    params = _connect_params(config, credentials, database)
    params["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**params)


def _database_names(cursor: Any, configured: Iterable[str] | None) -> list[str]:
    if configured:
        return [str(item) for item in configured if str(item).lower() not in SYSTEM_DATABASES]
    return [str(row.get("SCHEMA_NAME", row.get("schema_name"))) for row in _rows(
        cursor, "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME"
    ) if str(row.get("SCHEMA_NAME", row.get("schema_name"))).lower() not in SYSTEM_DATABASES]


def _empty_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": {"db_type": "mysql", "endpoint": f"{config['host']}:{config['port']}", "read_only": True},
        "collected_at": datetime.now(timezone.utc).isoformat(), "database_version": None,
        "read_only": True, "databases": [], "schemas": [], "tables": [], "views": [], "columns": [],
        "keys": [], "unique_keys": [], "indexes": [], "foreign_keys": [], "dependencies": [],
        "routines": [], "triggers": [], "routine_metadata_status": None,
        "transport": {"ssl_disabled": bool(config.get("ssl_disabled") is True),
                      "note": "ssl_disabled requested per source connection only" if config.get("ssl_disabled") is True else None},
        "summary": {}, "errors": [], "sanitization": {"view_definitions": "credential/url patterns masked", "errors": "bounded and masked"},
        "source_writes": 0,
    }


def _collect_database(cursor: Any, database: str, payload: dict[str, Any]) -> None:
    batch: dict[str, list[dict[str, Any]]] = {
        key: [] for key in (
            "schemas", "tables", "views", "columns", "keys", "unique_keys",
            "indexes", "foreign_keys", "dependencies", "routines", "triggers",
        )
    }
    batch["schemas"].append({"database": database, "schema": database})
    batch["tables"].extend(_rows(cursor, """SELECT TABLE_SCHEMA database_name,TABLE_NAME table_name,TABLE_TYPE table_type,
        ENGINE engine,TABLE_ROWS estimated_rows,TABLE_COMMENT comment FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME""", (database,)))
    batch["columns"].extend(_rows(cursor, """SELECT TABLE_SCHEMA database_name,TABLE_NAME table_name,ORDINAL_POSITION ordinal_position,
        COLUMN_NAME column_name,COLUMN_TYPE data_type,IS_NULLABLE is_nullable,COLUMN_DEFAULT column_default,
        COLUMN_KEY column_key,EXTRA extra,COLUMN_COMMENT comment FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,ORDINAL_POSITION""", (database,)))
    key_rows = _rows(cursor, """SELECT tc.TABLE_SCHEMA database_name,tc.TABLE_NAME table_name,tc.CONSTRAINT_NAME constraint_name,
        ku.COLUMN_NAME column_name,ku.ORDINAL_POSITION ordinal_position,tc.CONSTRAINT_TYPE constraint_type
        FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.KEY_COLUMN_USAGE ku
        ON ku.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND ku.TABLE_NAME=tc.TABLE_NAME AND ku.CONSTRAINT_NAME=tc.CONSTRAINT_NAME
        WHERE tc.CONSTRAINT_SCHEMA=%s AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY','UNIQUE')
        ORDER BY tc.TABLE_NAME,tc.CONSTRAINT_NAME,ku.ORDINAL_POSITION""", (database,))
    batch["keys"].extend(key_rows)
    batch["unique_keys"].extend(row for row in key_rows if str(row.get("constraint_type", "")).upper() == "UNIQUE")
    batch["indexes"].extend(_rows(cursor, """SELECT TABLE_SCHEMA database_name,TABLE_NAME table_name,INDEX_NAME index_name,
        NON_UNIQUE non_unique,SEQ_IN_INDEX ordinal_position,COLUMN_NAME column_name,INDEX_TYPE index_type
        FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX""", (database,)))
    batch["foreign_keys"].extend(_rows(cursor, """SELECT CONSTRAINT_SCHEMA database_name,TABLE_NAME table_name,CONSTRAINT_NAME constraint_name,
        COLUMN_NAME column_name,ORDINAL_POSITION ordinal_position,REFERENCED_TABLE_SCHEMA referenced_database,
        REFERENCED_TABLE_NAME referenced_table,REFERENCED_COLUMN_NAME referenced_column
        FROM information_schema.KEY_COLUMN_USAGE WHERE CONSTRAINT_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION""", (database,)))
    for row in _rows(cursor, """SELECT TABLE_SCHEMA database_name,TABLE_NAME view_name,VIEW_DEFINITION view_definition
        FROM information_schema.VIEWS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME""", (database,)):
        row["view_definition"] = sanitize_view_definition(row.get("view_definition"))
        batch["views"].append(row)
    try:
        batch["dependencies"].extend(_rows(cursor, """SELECT VIEW_SCHEMA database_name,VIEW_NAME view_name,
            TABLE_SCHEMA referenced_database,TABLE_NAME referenced_table FROM information_schema.VIEW_TABLE_USAGE
            WHERE VIEW_SCHEMA=%s ORDER BY VIEW_NAME,TABLE_SCHEMA,TABLE_NAME""", (database,)))
    except Exception as exc:
        payload["errors"].append({
            "database": database, "scope": "view_dependencies", "error": sanitize_text(exc),
            "status": "skipped_optional",
        })
    # Routine/trigger metadata: MySQL 5.7 hides ROUTINES without EXECUTE and
    # TRIGGERS without TRIGGER privilege.  An empty result is recorded as
    # BLOCKED_ROUTINE_METADATA; privileges are never extended for completeness.
    try:
        routines = _rows(cursor, """SELECT ROUTINE_SCHEMA database_name,ROUTINE_NAME routine_name,
            ROUTINE_TYPE routine_type,CREATED created_at,SECURITY_TYPE security_type
            FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s
            ORDER BY ROUTINE_TYPE,ROUTINE_NAME""", (database,))
        triggers = _rows(cursor, """SELECT TRIGGER_SCHEMA database_name,TRIGGER_NAME trigger_name,
            EVENT_MANIPULATION event_manipulation,EVENT_OBJECT_TABLE event_object_table,ACTION_TIMING action_timing
            FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME""", (database,))
        if not routines and not triggers:
            payload["routine_metadata_status"] = "BLOCKED_ROUTINE_METADATA"
            payload["errors"].append({
                "database": database, "scope": "routine_metadata",
                "status": "BLOCKED_ROUTINE_METADATA",
                "error": "no routine/trigger rows visible to this login; privileges not extended",
            })
        batch["routines"].extend(routines)
        batch["triggers"].extend(triggers)
    except Exception as exc:
        payload["routine_metadata_status"] = "BLOCKED_ROUTINE_METADATA"
        payload["errors"].append({
            "database": database, "scope": "routine_metadata", "error": sanitize_text(exc),
            "status": "BLOCKED_ROUTINE_METADATA",
        })
    for key, rows in batch.items():
        payload[key].extend(rows)


def harvest(config: Mapping[str, Any], *, check_connection: bool = False,
            discover_databases: bool = False) -> dict[str, Any]:
    credentials = _credential(config)
    connection = _connect(config, credentials)
    payload = _empty_snapshot(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            if check_connection:
                identity = _row(cursor, "SELECT VERSION() AS version, DATABASE() AS database_name")
                payload["database_version"] = sanitize_text(identity.get("version"))
                payload["summary"] = {"connected": True, "source_writes": 0}
                if not discover_databases:
                    return payload
            configured = config.get("databases") or config.get("database_list")
            if not configured and config.get("database"):
                configured = [str(config["database"])]
            names = _database_names(cursor, None if discover_databases else configured)
            payload["databases"] = names
            if discover_databases and not (config.get("databases") or config.get("database_list")):
                payload["summary"] = {"databases": len(names), "source_writes": 0}
                return payload
            identity = _row(cursor, "SELECT VERSION() AS version")
            payload["database_version"] = sanitize_text(identity.get("version"))
            for database in names:
                try:
                    _collect_database(cursor, database, payload)
                except Exception as exc:
                    payload["errors"].append({
                        "database": database, "scope": "metadata", "error": sanitize_text(exc), "status": "skipped",
                    })
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
    payload["summary"] = {"databases": len(payload["databases"]), "tables": len(payload["tables"]),
        "views": len(payload["views"]), "columns": len(payload["columns"]), "keys": len(payload["keys"]),
        "unique_keys": len(payload["unique_keys"]),
        "indexes": len(payload["indexes"]), "foreign_keys": len(payload["foreign_keys"]),
        "dependencies": len(payload["dependencies"]), "routines": len(payload["routines"]),
        "triggers": len(payload["triggers"]), "routine_metadata_status": payload.get("routine_metadata_status"),
        "errors": len(payload["errors"]), "source_writes": 0}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="explicit JSON output path; omitted means no file is written")
    parser.add_argument("--check-connection", action="store_true")
    parser.add_argument("--discover-databases", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = harvest(load_config(args.config), check_connection=args.check_connection, discover_databases=args.discover_databases)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(result.get("summary", {}), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": sanitize_text(exc), "source_writes": 0}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
