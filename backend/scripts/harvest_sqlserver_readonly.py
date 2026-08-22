"""Configuration-driven, read-only SQL Server metadata harvester."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb", "resource"}
URL_SECRET_RE = re.compile(r"(?i)(://[^:/@\s]+:)[^@/\s]+(@)")
PARAM_SECRET_RE = re.compile(r"(?i)([?&#](?:password|passwd|pwd|token|secret|api[_-]?key)=)[^&#'\"\s]+")


def _sanitize(value: Any, *, limit: int) -> str:
    text = str(value or "")
    text = URL_SECRET_RE.sub(r"\1***\2", text)
    text = PARAM_SECRET_RE.sub(r"\1***", text)
    text = re.sub(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*[^,;\s]+", r"\1=***", text)
    return text[:limit]


def sanitize_text(value: Any) -> str:
    return _sanitize(value, limit=1000)


def sanitize_view_definition(value: Any) -> str | None:
    return None if value is None else _sanitize(value, limit=1_000_000)


def redact_string_literals(value: Any) -> str | None:
    """Mask quoted string contents so stored definitions stay evidence-only."""
    if value is None:
        return None
    return re.sub(r"'(?:''|[^'])*'", "'***REDACTED***'", str(value))


def load_config(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must contain a JSON object")
    source = data.get("source", data)
    if "source" not in data and isinstance(data.get("endpoint"), dict):
        source = {**{key: value for key, value in data.items() if key != "endpoint"}, **data["endpoint"]}
    if not isinstance(source, dict) or source.get("host") in (None, "") or source.get("port") in (None, ""):
        raise ValueError("config requires source.host and source.port")
    if "source" in data:
        source = {**{key: value for key, value in data.items() if key != "source"}, **source}
    return source


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


def load_credentials(config: Mapping[str, Any]) -> dict[str, str]:
    ref = config.get("credentials") or config.get("credential") or {}
    if not isinstance(ref, Mapping):
        raise ValueError("credentials must be an object containing env/file references")
    result: dict[str, str] = {}
    file_name = ref.get("file") or config.get("credential_file") or config.get("credentials_file")
    if file_name:
        result.update({key: value for key, value in read_credential_file(file_name).items() if key in {"user", "password"}})
    env_names = ref.get("env") or config.get("credential_env") or {}
    if isinstance(env_names, Mapping):
        for key, env_name in env_names.items():
            target = "user" if key in {"user", "username"} else key
            if target in {"user", "password"} and env_name and os.environ.get(str(env_name)) is not None:
                result[target] = os.environ[str(env_name)]
    user_env = ref.get("user_env") or ref.get("username_env") or config.get("user_env") or config.get("username_env")
    password_env = ref.get("password_env") or config.get("password_env")
    if not result.get("user") and user_env:
        result["user"] = os.environ.get(str(user_env), "")
    if not result.get("password") and password_env:
        result["password"] = os.environ.get(str(password_env), "")
    if not result.get("user") or not result.get("password"):
        raise RuntimeError("credentials unavailable; provide configured environment variables or credential file")
    return result


def _connect(config: Mapping[str, Any], credentials: Mapping[str, str], database: str | None = None,
             tds_version: str | None = None) -> Any:
    # pymssql is preferred because it does not require an ODBC driver.  The
    # import remains lazy so py_compile and offline tests need no connector.
    import pymssql
    kwargs: dict[str, Any] = {
        "server": str(config["host"]), "port": int(config["port"]), "user": credentials["user"],
        "password": credentials["password"], "database": database or config.get("database") or "master",
        "login_timeout": int(config.get("connect_timeout", 10)), "timeout": int(config.get("read_timeout", 90)),
        "autocommit": False, "appname": "DataAssetReadOnlyMetadataHarvest",
    }
    resolved = tds_version if tds_version is not None else config.get("tds_version")
    if resolved:
        kwargs["tds_version"] = str(resolved)
    return pymssql.connect(**kwargs)


def resolve_tds_version(config: Mapping[str, Any], credentials: Mapping[str, str]) -> tuple[str | None, list[dict[str, str]]]:
    """Probe the configured TDS version once; fall back only when configured.

    Returns ``(resolved_tds_or_None, sanitized_attempts)``.  The fallback is a
    controlled, config-driven downgrade (plan 139 S1) and is recorded.
    """
    attempts: list[dict[str, str]] = []
    configured = config.get("tds_version")
    try:
        probe = _connect(config, credentials, "master")
        probe.rollback()
        probe.close()
        label = str(configured) if configured else "driver_default"
        attempts.append({"tds_version": label, "result": "ok"})
        return (str(configured) if configured else None), attempts
    except Exception as exc:
        attempts.append({"tds_version": str(configured) if configured else "driver_default",
                         "result": "failed", "error": sanitize_text(exc)[:300]})
    fallback = config.get("tds_fallback")
    if fallback and str(fallback) != str(configured):
        try:
            probe = _connect(config, credentials, "master", tds_version=str(fallback))
            probe.rollback()
            probe.close()
            attempts.append({"tds_version": str(fallback), "result": "ok_fallback"})
            return str(fallback), attempts
        except Exception as exc:
            attempts.append({"tds_version": str(fallback), "result": "failed", "error": sanitize_text(exc)[:300]})
            raise RuntimeError(f"connection failed after tds fallback: {sanitize_text(exc)[:200]}") from None
    raise RuntimeError(f"connection failed: {attempts[-1].get('error', 'unknown')[:200]}")


def _rows(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    if rows and isinstance(rows[0], Mapping):
        return [dict(row) for row in rows]
    names = [str(item[0]).lower() for item in (getattr(cursor, "description", None) or [])]
    return [dict(zip(names, row)) for row in rows]


def _row(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = _rows(cursor, sql, params)
    return rows[0] if rows else {}


def _names(cursor: Any, configured: Iterable[str] | None) -> list[str]:
    if configured:
        return [str(item) for item in configured if str(item).lower() not in SYSTEM_DATABASES]
    return [str(row.get("database_name")) for row in _rows(cursor, """SELECT name AS database_name FROM sys.databases
        WHERE database_id > 4 AND state = 0 ORDER BY name""")
        if str(row.get("database_name")).lower() not in SYSTEM_DATABASES]


def _empty_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": {"db_type": "sqlserver", "endpoint": f"{config['host']}:{config['port']}", "read_only": True},
        "collected_at": datetime.now(timezone.utc).isoformat(), "database_version": None, "read_only": True,
        "databases": [], "schemas": [], "tables": [], "views": [], "columns": [], "keys": [], "unique_keys": [],
        "indexes": [], "foreign_keys": [], "dependencies": [], "routines": [], "triggers": [], "synonyms": [],
        "tds_version": None, "connection_attempts": [], "errors": [], "summary": {},
        "sanitization": {"view_definitions": "credential/url patterns masked", "errors": "bounded and masked",
                         "routine_definitions": "credential/url patterns masked; execution denied"},
        "source_writes": 0,
    }


def _session(cursor: Any, lock_timeout: int) -> None:
    cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    cursor.execute("SET LOCK_TIMEOUT %d" % max(1, min(int(lock_timeout), 600000)))
    cursor.execute("SET DEADLOCK_PRIORITY LOW")


def _collect_database(connection: Any, database: str, payload: dict[str, Any], config: Mapping[str, Any]) -> None:
    cursor = connection.cursor()
    try:
        _session(cursor, int(config.get("lock_timeout_ms", 5000)))
        identity = _row(cursor, """SELECT DB_NAME() AS database_name,
            CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) AS database_version,
            CAST(DATABASEPROPERTYEX(DB_NAME(),'Collation') AS nvarchar(128)) AS collation""")
        payload["database_version"] = payload.get("database_version") or sanitize_text(identity.get("database_version"))
        payload["databases"].append({"database_name": database, "collation": sanitize_text(identity.get("collation"))})
        payload["schemas"].extend(_rows(cursor, """SELECT DB_NAME() AS database_name,name AS schema_name FROM sys.schemas
            WHERE name NOT IN ('guest','INFORMATION_SCHEMA','sys') ORDER BY name"""))
        payload["tables"].extend(_rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,t.name table_name,
            CAST(SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) AS bigint) estimated_rows,
            CAST(ep.value AS nvarchar(4000)) comment FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
            LEFT JOIN sys.partitions p ON p.object_id=t.object_id LEFT JOIN sys.extended_properties ep
            ON ep.major_id=t.object_id AND ep.minor_id=0 AND ep.name='MS_Description'
            WHERE t.is_ms_shipped=0 GROUP BY s.name,t.name,ep.value ORDER BY s.name,t.name"""))
        for row in _rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,v.name view_name,m.definition view_definition,
            CAST(ep.value AS nvarchar(4000)) comment FROM sys.views v JOIN sys.schemas s ON s.schema_id=v.schema_id
            LEFT JOIN sys.sql_modules m ON m.object_id=v.object_id LEFT JOIN sys.extended_properties ep
            ON ep.major_id=v.object_id AND ep.minor_id=0 AND ep.name='MS_Description'
            WHERE v.is_ms_shipped=0 ORDER BY s.name,v.name"""):
            row["view_definition"] = sanitize_view_definition(row.get("view_definition"))
            payload["views"].append(row)
        payload["columns"].extend(_rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,o.name object_name,
            o.type_desc object_type,c.column_id,c.name column_name,ty.name data_type,c.max_length,c.precision,c.scale,
            c.is_nullable,c.is_identity,c.is_computed,CAST(dc.definition AS nvarchar(4000)) default_definition,
            CAST(ep.value AS nvarchar(4000)) comment FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
            JOIN sys.columns c ON c.object_id=o.object_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id
            LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id LEFT JOIN sys.extended_properties ep
            ON ep.major_id=o.object_id AND ep.minor_id=c.column_id AND ep.name='MS_Description'
            WHERE o.type IN ('U','V') AND o.is_ms_shipped=0 ORDER BY s.name,o.name,c.column_id"""))
        key_rows = _rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,t.name table_name,k.name constraint_name,
            k.type_desc,ic.key_ordinal,c.name column_name FROM sys.key_constraints k JOIN sys.tables t ON t.object_id=k.parent_object_id
            JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.index_columns ic ON ic.object_id=t.object_id AND ic.index_id=k.unique_index_id
            JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id ORDER BY s.name,t.name,k.name,ic.key_ordinal""")
        payload["keys"].extend(key_rows)
        payload["unique_keys"].extend(
            row for row in key_rows if "UNIQUE" in str(row.get("type_desc", "")).upper()
        )
        payload["indexes"].extend(_rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,t.name table_name,i.name index_name,
            i.is_unique,i.is_primary_key,i.type_desc,ic.key_ordinal,c.name column_name FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id
            JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
            JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id WHERE i.name IS NOT NULL
            ORDER BY s.name,t.name,i.name,ic.key_ordinal,c.column_id"""))
        payload["foreign_keys"].extend(_rows(cursor, """SELECT DB_NAME() database_name,fk.name constraint_name,cs.name child_schema,
            ct.name child_table,cc.name child_column,ps.name parent_schema,pt.name parent_table,pc.name parent_column,
            fkc.constraint_column_id ordinal_position,fk.is_disabled,fk.is_not_trusted FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id JOIN sys.tables ct ON ct.object_id=fk.parent_object_id
            JOIN sys.schemas cs ON cs.schema_id=ct.schema_id JOIN sys.columns cc ON cc.object_id=ct.object_id AND cc.column_id=fkc.parent_column_id
            JOIN sys.tables pt ON pt.object_id=fk.referenced_object_id JOIN sys.schemas ps ON ps.schema_id=pt.schema_id
            JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=fkc.referenced_column_id ORDER BY fk.name,fkc.constraint_column_id"""))
        payload["dependencies"].extend(_rows(cursor, """SELECT DB_NAME() database_name,OBJECT_SCHEMA_NAME(sed.referencing_id) referencing_schema,
            OBJECT_NAME(sed.referencing_id) referencing_object,sed.referenced_database_name referenced_database,
            sed.referenced_schema_name referenced_schema,sed.referenced_entity_name
            FROM sys.sql_expression_dependencies sed WHERE sed.referencing_id IS NOT NULL ORDER BY referencing_schema,referencing_object"""))
        # Routines/triggers/synonyms: metadata + definitions only.  The login
        # is explicitly DENY EXECUTE, so nothing here can run a module.
        routine_rows = _rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,o.name routine_name,
            o.type_desc routine_type,m.definition routine_definition FROM sys.objects o
            JOIN sys.schemas s ON s.schema_id=o.schema_id LEFT JOIN sys.sql_modules m ON m.object_id=o.object_id
            WHERE o.type IN ('P','FN','IF','TF') AND o.is_ms_shipped=0 ORDER BY s.name,o.name""")
        blocked_definitions = 0
        for row in routine_rows:
            definition = row.get("routine_definition")
            if definition in (None, ""):
                blocked_definitions += 1
                row["definition_status"] = "BLOCKED_ROUTINE_METADATA"
                row["routine_definition"] = None
            else:
                row["definition_status"] = "ok"
                row["routine_definition"] = sanitize_view_definition(redact_string_literals(definition))
        payload["routines"].extend(routine_rows)
        trigger_rows = _rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,t.name trigger_name,
            t.type_desc trigger_type,OBJECT_NAME(t.parent_id) parent_object,CASE WHEN t.is_disabled=1 THEN 'yes' ELSE 'no' END is_disabled,
            m.definition trigger_definition FROM sys.triggers t JOIN sys.objects o ON o.object_id=t.object_id
            JOIN sys.schemas s ON s.schema_id=o.schema_id LEFT JOIN sys.sql_modules m ON m.object_id=t.object_id
            WHERE t.is_ms_shipped=0 ORDER BY s.name,t.name""")
        for row in trigger_rows:
            row["trigger_definition"] = sanitize_view_definition(redact_string_literals(row.get("trigger_definition")))
        payload["triggers"].extend(trigger_rows)
        payload["synonyms"].extend(_rows(cursor, """SELECT DB_NAME() database_name,s.name schema_name,sy.name synonym_name,
            OBJECT_DEFINITION(sy.object_id) base_object FROM sys.synonyms sy JOIN sys.schemas s ON s.schema_id=sy.schema_id
            WHERE s.name NOT IN ('guest','INFORMATION_SCHEMA','sys') ORDER BY s.name,sy.name"""))
        if blocked_definitions:
            payload["errors"].append({
                "database": database, "scope": "routine_definitions",
                "status": "BLOCKED_ROUTINE_METADATA", "count": blocked_definitions,
                "error": f"{blocked_definitions} routine definitions not visible to this login; privileges not extended",
            })
    finally:
        cursor.close()


def harvest(config: Mapping[str, Any], *, check_connection: bool = False,
            discover_databases: bool = False) -> dict[str, Any]:
    credentials = load_credentials(config)
    payload = _empty_snapshot(config)
    tds_version, attempts = resolve_tds_version(config, credentials)
    payload["tds_version"] = tds_version or "driver_default"
    payload["connection_attempts"] = attempts
    control = _connect(config, credentials, "master", tds_version=tds_version)
    try:
        cursor = control.cursor()
        try:
            _session(cursor, int(config.get("lock_timeout_ms", 5000)))
            identity = _row(cursor, "SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) AS database_version")
            payload["database_version"] = sanitize_text(identity.get("database_version"))
            configured = config.get("databases") or config.get("database_list")
            if not configured and config.get("database"):
                configured = [str(config["database"])]
            names = _names(cursor, None if discover_databases else configured)
            if check_connection:
                payload["databases"] = names
                payload["summary"] = {"connected": True, "databases": len(names),
                                      "tds_version": payload.get("tds_version"), "source_writes": 0}
                if not discover_databases:
                    return payload
        finally:
            cursor.close()
    finally:
        control.rollback()
        control.close()
    if discover_databases:
        payload["databases"] = names
        payload["summary"] = {"databases": len(names), "tds_version": payload.get("tds_version"), "source_writes": 0}
        return payload
    for database in names:
        try:
            connection = _connect(config, credentials, database, tds_version=tds_version)
            try:
                _collect_database(connection, database, payload, config)
            finally:
                try:
                    connection.rollback()
                finally:
                    connection.close()
        except Exception as exc:
            payload["errors"].append({"database": database, "error": sanitize_text(exc), "status": "skipped"})
    payload["summary"] = {"databases": len(payload["databases"]), "tables": len(payload["tables"]),
        "views": len(payload["views"]), "columns": len(payload["columns"]), "keys": len(payload["keys"]),
        "unique_keys": len(payload["unique_keys"]),
        "indexes": len(payload["indexes"]), "foreign_keys": len(payload["foreign_keys"]),
        "dependencies": len(payload["dependencies"]), "routines": len(payload["routines"]),
        "triggers": len(payload["triggers"]), "synonyms": len(payload["synonyms"]),
        "tds_version": payload.get("tds_version"),
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
