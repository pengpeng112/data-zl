"""Harvest Docare anesthesia-system metadata from business owners, read-only."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


OWNERS = ("MEDSURGERY", "MEDICU", "MEDCOMM")


def fetch(cursor, sql: str, params: dict | None = None) -> list[dict]:
    cursor.execute(sql, params or {})
    names = [item[0].lower() for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import oracledb

    oracledb.init_oracle_client(lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"))
    connection = oracledb.connect(
        user=os.environ["DOCARE_USER"], password=os.environ["DOCARE_PASSWORD"],
        dsn=os.environ.get("DOCARE_DSN", "10.10.10.68:1521/docare"),
    )
    connection.call_timeout = 60_000
    cursor = connection.cursor()
    binds = {f"o{i}": owner for i, owner in enumerate(OWNERS)}
    owner_sql = ",".join(f":o{i}" for i in range(len(OWNERS)))
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        identity = fetch(cursor, "SELECT SYS_CONTEXT('USERENV','DB_NAME') database_name FROM DUAL")[0]
        tables = fetch(cursor, f"""
            SELECT t.OWNER,t.TABLE_NAME,'TABLE' OBJECT_TYPE,t.NUM_ROWS,t.LAST_ANALYZED,c.COMMENTS
              FROM ALL_TABLES t LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER=t.OWNER AND c.TABLE_NAME=t.TABLE_NAME
             WHERE t.OWNER IN ({owner_sql}) ORDER BY t.OWNER,t.TABLE_NAME
        """, binds)
        views = fetch(cursor, f"""
            SELECT v.OWNER,v.VIEW_NAME TABLE_NAME,'VIEW' OBJECT_TYPE,
                   CAST(NULL AS NUMBER) NUM_ROWS,CAST(NULL AS DATE) LAST_ANALYZED,c.COMMENTS
              FROM ALL_VIEWS v LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER=v.OWNER AND c.TABLE_NAME=v.VIEW_NAME
             WHERE v.OWNER IN ({owner_sql}) ORDER BY v.OWNER,v.VIEW_NAME
        """, binds)
        columns = fetch(cursor, f"""
            SELECT c.OWNER,c.TABLE_NAME,c.COLUMN_ID,c.COLUMN_NAME,c.DATA_TYPE,c.DATA_LENGTH,
                   c.DATA_PRECISION,c.DATA_SCALE,c.NULLABLE,c.DATA_DEFAULT,m.COMMENTS
              FROM ALL_TAB_COLUMNS c LEFT JOIN ALL_COL_COMMENTS m
                ON m.OWNER=c.OWNER AND m.TABLE_NAME=c.TABLE_NAME AND m.COLUMN_NAME=c.COLUMN_NAME
             WHERE c.OWNER IN ({owner_sql}) ORDER BY c.OWNER,c.TABLE_NAME,c.COLUMN_ID
        """, binds)
        constraints = fetch(cursor, f"""
            SELECT ac.OWNER,ac.CONSTRAINT_NAME,ac.CONSTRAINT_TYPE,ac.TABLE_NAME,acc.COLUMN_NAME,acc.POSITION,
                   ac.R_OWNER,rc.TABLE_NAME R_TABLE_NAME,rcc.COLUMN_NAME R_COLUMN_NAME
              FROM ALL_CONSTRAINTS ac JOIN ALL_CONS_COLUMNS acc ON acc.OWNER=ac.OWNER AND acc.CONSTRAINT_NAME=ac.CONSTRAINT_NAME
              LEFT JOIN ALL_CONSTRAINTS rc ON rc.OWNER=ac.R_OWNER AND rc.CONSTRAINT_NAME=ac.R_CONSTRAINT_NAME
              LEFT JOIN ALL_CONS_COLUMNS rcc ON rcc.OWNER=rc.OWNER AND rcc.CONSTRAINT_NAME=rc.CONSTRAINT_NAME AND rcc.POSITION=acc.POSITION
             WHERE ac.OWNER IN ({owner_sql}) AND ac.CONSTRAINT_TYPE IN ('P','U','R')
             ORDER BY ac.OWNER,ac.TABLE_NAME,ac.CONSTRAINT_NAME,acc.POSITION
        """, binds)
        indexes = fetch(cursor, f"""
            SELECT i.OWNER,i.TABLE_NAME,i.INDEX_NAME,i.UNIQUENESS,c.COLUMN_NAME,c.COLUMN_POSITION
              FROM ALL_INDEXES i JOIN ALL_IND_COLUMNS c ON c.INDEX_OWNER=i.OWNER AND c.INDEX_NAME=i.INDEX_NAME
             WHERE i.TABLE_OWNER IN ({owner_sql}) ORDER BY i.OWNER,i.TABLE_NAME,i.INDEX_NAME,c.COLUMN_POSITION
        """, binds)
        view_definitions = fetch(cursor, f"SELECT OWNER,VIEW_NAME,TEXT FROM ALL_VIEWS WHERE OWNER IN ({owner_sql}) ORDER BY OWNER,VIEW_NAME", binds)
        payload = {
            "source": {"db_type": "oracle", "endpoint": "10.10.10.68:1521/docare", "database": identity["database_name"], "owners": list(OWNERS), "read_only": True},
            "collected_at": datetime.now(timezone.utc).isoformat(), "tables": tables, "views": views,
            "columns": columns, "constraints": constraints, "indexes": indexes, "view_definitions": view_definitions,
            "summary": {"tables": len(tables), "views": len(views), "columns": len(columns), "constraint_columns": len(constraints), "index_columns": len(indexes), "source_writes": 0},
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False))
    finally:
        cursor.close(); connection.rollback(); connection.close()


if __name__ == "__main__":
    main()
