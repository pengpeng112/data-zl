"""Harvest rmcloudlis7 SQL Server metadata without source writes."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def fetch(cursor, sql: str) -> list[dict]:
    cursor.execute(sql)
    names = [item[0].lower() for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import pymssql

    connection = pymssql.connect(
        server=os.environ.get("LIS_SQLSERVER_HOST", "10.10.10.73"), port=1433,
        user=os.environ["LIS_SQLSERVER_USER"], password=os.environ["LIS_SQLSERVER_PASSWORD"],
        database=os.environ.get("LIS_SQLSERVER_DATABASE", "rmcloudlis7"),
        login_timeout=10, timeout=60, autocommit=False, appname="DataAssetReadOnlyHarvest",
    )
    cursor = connection.cursor()
    try:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("SET LOCK_TIMEOUT 5000")
        identity = fetch(cursor, "SELECT DB_NAME() database_name, @@VERSION version")[0]
        tables = fetch(cursor, """
            SELECT s.name schema_name,t.name table_name,CAST(SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) AS BIGINT) row_count,
                   CAST(ep.value AS NVARCHAR(4000)) comment
              FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
              LEFT JOIN sys.partitions p ON p.object_id=t.object_id
              LEFT JOIN sys.extended_properties ep ON ep.major_id=t.object_id AND ep.minor_id=0 AND ep.name='MS_Description'
             WHERE t.is_ms_shipped=0 GROUP BY s.name,t.name,ep.value ORDER BY s.name,t.name
        """)
        views = fetch(cursor, """
            SELECT s.name schema_name,v.name view_name,m.definition,CAST(ep.value AS NVARCHAR(4000)) comment
              FROM sys.views v JOIN sys.schemas s ON s.schema_id=v.schema_id
              LEFT JOIN sys.sql_modules m ON m.object_id=v.object_id
              LEFT JOIN sys.extended_properties ep ON ep.major_id=v.object_id AND ep.minor_id=0 AND ep.name='MS_Description'
             WHERE v.is_ms_shipped=0 ORDER BY s.name,v.name
        """)
        columns = fetch(cursor, """
            SELECT s.name schema_name,o.name object_name,o.type_desc object_type,c.column_id,c.name column_name,
                   ty.name data_type,c.max_length,c.precision,c.scale,c.is_nullable,c.is_identity,
                   dc.definition default_definition,CAST(ep.value AS NVARCHAR(4000)) comment
              FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
              JOIN sys.columns c ON c.object_id=o.object_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id
              LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id
              LEFT JOIN sys.extended_properties ep ON ep.major_id=o.object_id AND ep.minor_id=c.column_id AND ep.name='MS_Description'
             WHERE o.type IN ('U','V') AND o.is_ms_shipped=0 ORDER BY s.name,o.name,c.column_id
        """)
        keys = fetch(cursor, """
            SELECT s.name schema_name,t.name table_name,k.name constraint_name,k.type_desc,ic.key_ordinal,c.name column_name
              FROM sys.key_constraints k JOIN sys.tables t ON t.object_id=k.parent_object_id
              JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.index_columns ic ON ic.object_id=t.object_id AND ic.index_id=k.unique_index_id
              JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id
             ORDER BY s.name,t.name,k.name,ic.key_ordinal
        """)
        foreign_keys = fetch(cursor, """
            SELECT fk.name constraint_name,cs.name child_schema,ct.name child_table,cc.name child_column,
                   ps.name parent_schema,pt.name parent_table,pc.name parent_column,fkc.constraint_column_id position
              FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
              JOIN sys.tables ct ON ct.object_id=fk.parent_object_id JOIN sys.schemas cs ON cs.schema_id=ct.schema_id
              JOIN sys.columns cc ON cc.object_id=ct.object_id AND cc.column_id=fkc.parent_column_id
              JOIN sys.tables pt ON pt.object_id=fk.referenced_object_id JOIN sys.schemas ps ON ps.schema_id=pt.schema_id
              JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=fkc.referenced_column_id
             ORDER BY fk.name,fkc.constraint_column_id
        """)
        indexes = fetch(cursor, """
            SELECT s.name schema_name,t.name table_name,i.name index_name,i.is_unique,i.type_desc,ic.key_ordinal,c.name column_name
              FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id
              JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
              JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id
             WHERE i.name IS NOT NULL ORDER BY s.name,t.name,i.name,ic.key_ordinal,c.column_id
        """)
        payload = {
            "source": {"db_type": "sqlserver", "endpoint": "10.10.10.73:1433", "database": identity["database_name"], "schema": "dbo", "read_only": True},
            "version": str(identity["version"]).splitlines()[0], "collected_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables, "views": views, "columns": columns, "keys": keys, "foreign_keys": foreign_keys, "indexes": indexes,
            "summary": {"tables": len(tables), "views": len(views), "columns": len(columns), "key_columns": len(keys), "foreign_key_columns": len(foreign_keys), "index_columns": len(indexes), "source_writes": 0},
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False))
    finally:
        cursor.close(); connection.rollback(); connection.close()


if __name__ == "__main__":
    main()
