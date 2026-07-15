"""Harvest PACS MySQL metadata using read-only transactions."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}


def sanitize_view_definition(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"(?i)([?&#](?:pw|password|token|access_token)=)[^&#'\"\s]+", r"\1***", value)
    value = re.sub(r"(?i)(://[^:/@\s]+:)[^@/\s]+(@)", r"\1***\2", value)
    return value


def fetch_all(cursor, sql: str, params: tuple = ()) -> list[dict]:
    cursor.execute(sql, params)
    return list(cursor.fetchall())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    import pymysql

    connection = pymysql.connect(
        host=os.environ.get("PACS_MYSQL_HOST", "10.10.10.191"),
        port=int(os.environ.get("PACS_MYSQL_PORT", "3306")),
        user=os.environ["PACS_MYSQL_USER"],
        password=os.environ["PACS_MYSQL_PASSWORD"],
        charset="utf8mb4",
        connect_timeout=10,
        read_timeout=90,
        write_timeout=15,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        program_name="DataAssetReadOnlyMetadataHarvest",
    )
    payload: dict = {
        "source": {"host": os.environ.get("PACS_MYSQL_HOST", "10.10.10.191"), "port": 3306},
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "databases": {},
        "summary": {"databases": 0, "tables": 0, "views": 0, "columns": 0, "foreign_keys": 0, "source_writes": 0},
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            cursor.execute("SELECT VERSION() AS version, @@hostname AS hostname, @@port AS port, @@read_only AS server_read_only")
            payload["server"] = cursor.fetchone()
            databases = [
                row["SCHEMA_NAME"]
                for row in fetch_all(cursor, "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME")
                if row["SCHEMA_NAME"] not in SYSTEM_DATABASES
            ]
            for database in databases:
                tables = fetch_all(
                    cursor,
                    """SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS, TABLE_COMMENT
                         FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME""",
                    (database,),
                )
                columns = fetch_all(
                    cursor,
                    """SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE,
                              IS_NULLABLE, COLUMN_KEY, EXTRA, COLUMN_COMMENT
                         FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME, ORDINAL_POSITION""",
                    (database,),
                )
                foreign_keys = fetch_all(
                    cursor,
                    """SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME,
                              REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                         FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL
                        ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION""",
                    (database,),
                )
                views = fetch_all(
                    cursor,
                    """SELECT TABLE_NAME, VIEW_DEFINITION
                         FROM information_schema.VIEWS
                        WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME""",
                    (database,),
                )
                for view in views:
                    view["VIEW_DEFINITION"] = sanitize_view_definition(view.get("VIEW_DEFINITION"))
                payload["databases"][database] = {
                    "tables": tables,
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "views": views,
                }
                payload["summary"]["tables"] += sum(row["TABLE_TYPE"] == "BASE TABLE" for row in tables)
                payload["summary"]["views"] += sum(row["TABLE_TYPE"] == "VIEW" for row in tables)
                payload["summary"]["columns"] += len(columns)
                payload["summary"]["foreign_keys"] += len(foreign_keys)
            payload["summary"]["databases"] = len(databases)
    finally:
        connection.rollback()
        connection.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
