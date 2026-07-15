"""Harvest CDMS paperless-record Oracle metadata in a read-only transaction."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def rows(cursor, sql: str, params: dict | None = None) -> list[dict]:
    cursor.execute(sql, params or {})
    names = [item[0].lower() for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner", default="CDMS")
    args = parser.parse_args()
    owner = args.owner.upper()

    import oracledb

    oracledb.init_oracle_client(lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"))
    user = os.environ["PAPERLESS_USER"]
    password = os.environ["PAPERLESS_PASSWORD"]
    dsn = os.environ.get("PAPERLESS_DSN", "10.10.10.93:1521/orcl")
    connection = oracledb.connect(user=user, password=password, dsn=dsn)
    connection.call_timeout = 60_000
    cursor = connection.cursor()
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        identity = rows(cursor, "SELECT SYS_CONTEXT('USERENV','DB_NAME') database_name, SYS_CONTEXT('USERENV','CURRENT_SCHEMA') current_schema FROM DUAL")[0]
        tables = rows(cursor, """
            SELECT t.OWNER, t.TABLE_NAME, 'TABLE' OBJECT_TYPE, t.NUM_ROWS,
                   t.LAST_ANALYZED, c.COMMENTS
              FROM ALL_TABLES t
              LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER=t.OWNER AND c.TABLE_NAME=t.TABLE_NAME
             WHERE t.OWNER=:owner ORDER BY t.TABLE_NAME
        """, {"owner": owner})
        views = rows(cursor, """
            SELECT v.OWNER, v.VIEW_NAME TABLE_NAME, 'VIEW' OBJECT_TYPE,
                   CAST(NULL AS NUMBER) NUM_ROWS, CAST(NULL AS DATE) LAST_ANALYZED,
                   c.COMMENTS
              FROM ALL_VIEWS v
              LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER=v.OWNER AND c.TABLE_NAME=v.VIEW_NAME
             WHERE v.OWNER=:owner ORDER BY v.VIEW_NAME
        """, {"owner": owner})
        columns = rows(cursor, """
            SELECT c.OWNER, c.TABLE_NAME, c.COLUMN_ID, c.COLUMN_NAME, c.DATA_TYPE,
                   c.DATA_LENGTH, c.DATA_PRECISION, c.DATA_SCALE, c.NULLABLE,
                   c.DATA_DEFAULT, m.COMMENTS
              FROM ALL_TAB_COLUMNS c
              LEFT JOIN ALL_COL_COMMENTS m ON m.OWNER=c.OWNER AND m.TABLE_NAME=c.TABLE_NAME AND m.COLUMN_NAME=c.COLUMN_NAME
             WHERE c.OWNER=:owner ORDER BY c.TABLE_NAME,c.COLUMN_ID
        """, {"owner": owner})
        constraints = rows(cursor, """
            SELECT ac.CONSTRAINT_NAME, ac.CONSTRAINT_TYPE, ac.TABLE_NAME,
                   acc.COLUMN_NAME, acc.POSITION, ac.R_OWNER, rc.TABLE_NAME R_TABLE_NAME,
                   rcc.COLUMN_NAME R_COLUMN_NAME
              FROM ALL_CONSTRAINTS ac
              JOIN ALL_CONS_COLUMNS acc ON acc.OWNER=ac.OWNER AND acc.CONSTRAINT_NAME=ac.CONSTRAINT_NAME
              LEFT JOIN ALL_CONSTRAINTS rc ON rc.OWNER=ac.R_OWNER AND rc.CONSTRAINT_NAME=ac.R_CONSTRAINT_NAME
              LEFT JOIN ALL_CONS_COLUMNS rcc ON rcc.OWNER=rc.OWNER AND rcc.CONSTRAINT_NAME=rc.CONSTRAINT_NAME AND rcc.POSITION=acc.POSITION
             WHERE ac.OWNER=:owner AND ac.CONSTRAINT_TYPE IN ('P','U','R')
             ORDER BY ac.TABLE_NAME,ac.CONSTRAINT_NAME,acc.POSITION
        """, {"owner": owner})
        indexes = rows(cursor, """
            SELECT i.TABLE_NAME,i.INDEX_NAME,i.UNIQUENESS,c.COLUMN_NAME,c.COLUMN_POSITION
              FROM ALL_INDEXES i JOIN ALL_IND_COLUMNS c ON c.INDEX_OWNER=i.OWNER AND c.INDEX_NAME=i.INDEX_NAME
             WHERE i.TABLE_OWNER=:owner ORDER BY i.TABLE_NAME,i.INDEX_NAME,c.COLUMN_POSITION
        """, {"owner": owner})
        # ALL_VIEWS.TEXT is LONG in Oracle 11g; python-oracledb thick mode can
        # fetch it directly without any source-side conversion or DDL.
        view_definitions = rows(cursor, "SELECT OWNER,VIEW_NAME,TEXT FROM ALL_VIEWS WHERE OWNER=:owner ORDER BY VIEW_NAME", {"owner": owner})
        payload = {
            "source": {"db_type": "oracle", "endpoint": "10.10.10.93:1521/orcl", "owner": owner, "database": identity["database_name"], "read_only": True},
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "views": views,
            "columns": columns,
            "constraints": constraints,
            "indexes": indexes,
            "view_definitions": view_definitions,
            "summary": {"tables": len(tables), "views": len(views), "columns": len(columns), "constraint_columns": len(constraints), "indexes_columns": len(indexes), "source_writes": 0},
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False))
    finally:
        cursor.close()
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
