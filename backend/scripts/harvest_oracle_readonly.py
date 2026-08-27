"""Generic, read-only Oracle metadata harvester (config/env driven).

Same payload shape as the Docare/Paperless harvesters so downstream
plan139-style packaging and importers keep working.  Credentials are only
accepted through environment variables or a short-lived credential file -
never through the JSON config itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Oracle-maintained accounts excluded from --auto-owners discovery.
SYSTEM_OWNER_PREFIXES = ("APEX_", "FLOWS_", "OLAPSYS", "ORDDATA", "ORDSYS", "MDDATA", "CTXSYS")
SYSTEM_OWNERS = {
    "SYS", "SYSTEM", "SYSAUX", "XDB", "OUTLN", "DBSNMP", "APPQOSSYS", "WMSYS",
    "EXFSYS", "ORDPLUGINS", "SI_INFORMTN_SCHEMA", "ANONYMOUS", "XS$NULL",
    "GSMADMIN_INTERNAL", "LBACSYS", "DVSYS", "DVF", "AUDSYS", "OJVMSYS",
    "DBSFWUSER", "REMOTE_SCHEDULER_AGENT", "SYS$UMF", "MGMT_VIEW",
    "SYSMAN", "OWBSYS", "OWBSYS_AUDIT", "FLOWS_FILES", "APEX_PUBLIC_USER",
}


def rows(cursor, sql: str, params: dict | None = None) -> list[dict]:
    cursor.execute(sql, params or {})
    names = [item[0].lower() for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def read_credential_file(file_name: str) -> dict[str, str]:
    text = Path(file_name).read_text(encoding="utf-8").strip()
    if text.startswith("{"):
        data = json.loads(text)
        return {k: str(data[k]) for k in ("user", "username", "password") if data.get(k) is not None}
    if "\n" not in text and ":" in text:
        user, password = text.split(":", 1)
        return {"user": user.strip(), "password": password.strip()}
    raise ValueError("unsupported credential file format")


def _credentials() -> dict[str, str]:
    result: dict[str, str] = {}
    file_name = os.environ.get("ORA_HARVEST_CRED_FILE", "")
    if file_name:
        result.update(read_credential_file(file_name))
    if os.environ.get("ORA_HARVEST_USER"):
        result["user"] = os.environ["ORA_HARVEST_USER"]
    if os.environ.get("ORA_HARVEST_PASSWORD"):
        result["password"] = os.environ["ORA_HARVEST_PASSWORD"]
    if not result.get("user") or not result.get("password"):
        raise RuntimeError("credentials unavailable; set ORA_HARVEST_USER/ORA_HARVEST_PASSWORD or ORA_HARVEST_CRED_FILE")
    return result


def discover_owners(cursor, include_user: bool) -> list[str]:
    accounts = rows(cursor, """
        SELECT username FROM all_users
         WHERE oracle_maintained = 'N'
         ORDER BY username
    """) if _has_oracle_maintained(cursor) else rows(cursor, """
        SELECT username FROM all_users ORDER BY username
    """)
    owners = []
    for row in accounts:
        name = str(row["username"]).upper()
        if name in SYSTEM_OWNERS or name.startswith(SYSTEM_OWNER_PREFIXES):
            continue
        owners.append(name)
    current = _current_user(cursor)
    if include_user and current and current not in owners:
        owners.insert(0, current)
    return owners


def _has_oracle_maintained(cursor) -> bool:
    try:
        cursor.execute("SELECT column_name FROM all_tab_columns WHERE owner='SYS' AND table_name='USER$' AND column_name='SPARE11' AND ROWNUM=1")
        # oracle_maintained exists on 12c+; detect via all_users columns instead
    except Exception:
        pass
    try:
        cursor.execute("SELECT oracle_maintained FROM all_users WHERE ROWNUM=1")
        cursor.fetchall()
        return True
    except Exception:
        return False


def _current_user(cursor) -> str:
    cursor.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') c FROM DUAL")
    row = cursor.fetchone()
    return str(row[0]).upper() if row else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="JSON output path; omitted means no file")
    parser.add_argument("--owners", default="", help="comma separated owner list; empty = auto discover")
    parser.add_argument("--check-connection", action="store_true")
    parser.add_argument("--list-owners", action="store_true")
    parser.add_argument("--dsn", default="", help="override ORA_HARVEST_DSN")
    parser.add_argument("--use-user-views", action="store_true",
                        help="harvest the connected schema via USER_* dictionary views (for memory-starved servers where ALL_* joins hit ORA-04030)")
    args = parser.parse_args()

    import oracledb

    lib_dir = os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle")
    if lib_dir and os.path.isdir(lib_dir):
        try:
            oracledb.init_oracle_client(lib_dir=lib_dir)
        except Exception as exc:  # already initialized is fine
            if "already" not in str(exc).lower():
                print(f"oracle client init failed: {exc}", file=sys.stderr)

    credentials = _credentials()
    dsn = args.dsn or os.environ.get("ORA_HARVEST_DSN", "")
    if not dsn:
        raise SystemExit("DSN required: set ORA_HARVEST_DSN or pass --dsn host:port/service")

    connection = oracledb.connect(user=credentials["user"], password=credentials["password"], dsn=dsn)
    connection.call_timeout = 120_000
    cursor = connection.cursor()
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        identity = rows(cursor, "SELECT SYS_CONTEXT('USERENV','DB_NAME') database_name, SYS_CONTEXT('USERENV','SERVER_HOST') server_host, SYS_CONTEXT('USERENV','INSTANCE_NAME') instance_name, SYS_CONTEXT('USERENV','SERVICE_NAME') service_name FROM DUAL")[0]

        if args.check_connection:
            print(json.dumps({"ok": True, **identity}, ensure_ascii=False))
            return 0

        current = _current_user(cursor)

        if args.use_user_views:
            # USER_* views scope to the connected schema; every query is kept
            # join-free because this path targets memory-starved servers where
            # even small dictionary hash joins fail with ORA-04030.
            owner = current
            table_stats = {r["table_name"]: r for r in rows(cursor, "SELECT TABLE_NAME, NUM_ROWS, LAST_ANALYZED FROM USER_TABLES")}
            table_comments = {r["table_name"]: r["comments"] for r in rows(cursor, "SELECT TABLE_NAME, COMMENTS FROM USER_TAB_COMMENTS")}
            view_names = {r["view_name"] for r in rows(cursor, "SELECT VIEW_NAME FROM USER_VIEWS")}
            tables = [
                {"owner": owner, "table_name": name, "object_type": "TABLE",
                 "num_rows": stats.get("num_rows"), "last_analyzed": stats.get("last_analyzed"),
                 "comments": table_comments.get(name)}
                for name, stats in sorted(table_stats.items())
            ]
            views = [
                {"owner": owner, "table_name": name, "object_type": "VIEW",
                 "num_rows": None, "last_analyzed": None, "comments": table_comments.get(name)}
                for name in sorted(view_names)
            ]

            col_comments: dict[tuple[str, str], str] = {
                (r["table_name"], r["column_name"]): r["comments"]
                for r in rows(cursor, "SELECT TABLE_NAME, COLUMN_NAME, COMMENTS FROM USER_COL_COMMENTS")
            }
            columns = [
                {"owner": owner, **{
                    "table_name": r["table_name"], "column_id": r["column_id"], "column_name": r["column_name"],
                    "data_type": r["data_type"], "data_length": r["data_length"], "data_precision": r["data_precision"],
                    "data_scale": r["data_scale"], "nullable": r["nullable"], "data_default": r["data_default"],
                    "comments": col_comments.get((r["table_name"], r["column_name"])),
                }}
                for r in rows(cursor, """
                    SELECT TABLE_NAME, COLUMN_ID, COLUMN_NAME, DATA_TYPE, DATA_LENGTH,
                           DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT
                      FROM USER_TAB_COLUMNS ORDER BY TABLE_NAME, COLUMN_ID
                """)
            ]

            cons_def = {r["constraint_name"]: r for r in rows(cursor,
                "SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, TABLE_NAME, R_CONSTRAINT_NAME FROM USER_CONSTRAINTS WHERE CONSTRAINT_TYPE IN ('P','U','R')")}
            cons_cols = rows(cursor, "SELECT CONSTRAINT_NAME, COLUMN_NAME, POSITION FROM USER_CONS_COLUMNS ORDER BY CONSTRAINT_NAME, POSITION")
            constraints = []
            for cc in cons_cols:
                definition = cons_def.get(cc["constraint_name"])
                if not definition:
                    continue
                referenced = cons_def.get(definition.get("r_constraint_name") or "")
                constraints.append({
                    "owner": owner, "constraint_name": cc["constraint_name"],
                    "constraint_type": definition["constraint_type"], "table_name": definition["table_name"],
                    "column_name": cc["column_name"], "position": cc["position"],
                    "r_owner": owner if referenced else None,
                    "r_table_name": referenced["table_name"] if referenced else None,
                    "r_column_name": None,
                })

            idx_meta = {r["index_name"]: r for r in rows(cursor, "SELECT INDEX_NAME, TABLE_NAME, UNIQUENESS FROM USER_INDEXES")}
            idx_cols = rows(cursor, "SELECT INDEX_NAME, COLUMN_NAME, COLUMN_POSITION FROM USER_IND_COLUMNS ORDER BY INDEX_NAME, COLUMN_POSITION")
            indexes = [
                {"owner": owner, "table_name": idx_meta[ic["index_name"]]["table_name"],
                 "index_name": ic["index_name"], "uniqueness": idx_meta[ic["index_name"]]["uniqueness"],
                 "column_name": ic["column_name"], "column_position": ic["column_position"]}
                for ic in idx_cols if ic["index_name"] in idx_meta
            ]
            view_definitions = rows(cursor, f"SELECT :owner OWNER, VIEW_NAME, TEXT FROM USER_VIEWS ORDER BY VIEW_NAME", {"owner": owner})
            owners = [owner]
        else:
            owners = [o.strip().upper() for o in args.owners.split(",") if o.strip()] if args.owners else discover_owners(cursor, include_user=True)
            if not owners:
                raise SystemExit("no accessible non-system owners discovered")

            if args.list_owners:
                print(json.dumps({"ok": True, "current_schema": current, "owners": owners}, ensure_ascii=False))
                return 0

            binds = {f"o{i}": owner for i, owner in enumerate(owners)}
            owner_sql = ",".join(f":{name}" for name in binds)

            tables = rows(cursor, f"""
                SELECT t.OWNER, t.TABLE_NAME, 'TABLE' OBJECT_TYPE, t.NUM_ROWS, t.LAST_ANALYZED, c.COMMENTS
                  FROM ALL_TABLES t
                  LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER=t.OWNER AND c.TABLE_NAME=t.TABLE_NAME
                 WHERE t.OWNER IN ({owner_sql}) ORDER BY t.OWNER, t.TABLE_NAME
            """, binds)
            views = rows(cursor, f"""
                SELECT v.OWNER, v.VIEW_NAME TABLE_NAME, 'VIEW' OBJECT_TYPE,
                       CAST(NULL AS NUMBER) NUM_ROWS, CAST(NULL AS DATE) LAST_ANALYZED, c.COMMENTS
                  FROM ALL_VIEWS v LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER=v.OWNER AND c.TABLE_NAME=v.VIEW_NAME
                 WHERE v.OWNER IN ({owner_sql}) ORDER BY v.OWNER, v.VIEW_NAME
            """, binds)
            columns = rows(cursor, f"""
                SELECT c.OWNER, c.TABLE_NAME, c.COLUMN_ID, c.COLUMN_NAME, c.DATA_TYPE, c.DATA_LENGTH,
                       c.DATA_PRECISION, c.DATA_SCALE, c.NULLABLE, c.DATA_DEFAULT, m.COMMENTS
                  FROM ALL_TAB_COLUMNS c LEFT JOIN ALL_COL_COMMENTS m
                    ON m.OWNER=c.OWNER AND m.TABLE_NAME=c.TABLE_NAME AND m.COLUMN_NAME=c.COLUMN_NAME
                 WHERE c.OWNER IN ({owner_sql}) ORDER BY c.OWNER, c.TABLE_NAME, c.COLUMN_ID
            """, binds)
            constraints = rows(cursor, f"""
                SELECT ac.OWNER, ac.CONSTRAINT_NAME, ac.CONSTRAINT_TYPE, ac.TABLE_NAME, acc.COLUMN_NAME, acc.POSITION,
                       ac.R_OWNER, rc.TABLE_NAME R_TABLE_NAME, rcc.COLUMN_NAME R_COLUMN_NAME
                  FROM ALL_CONSTRAINTS ac JOIN ALL_CONS_COLUMNS acc ON acc.OWNER=ac.OWNER AND acc.CONSTRAINT_NAME=ac.CONSTRAINT_NAME
                  LEFT JOIN ALL_CONSTRAINTS rc ON rc.OWNER=ac.R_OWNER AND rc.CONSTRAINT_NAME=ac.R_CONSTRAINT_NAME
                  LEFT JOIN ALL_CONS_COLUMNS rcc ON rcc.OWNER=rc.OWNER AND rcc.CONSTRAINT_NAME=rc.R_CONSTRAINT_NAME AND rcc.POSITION=acc.POSITION
                 WHERE ac.OWNER IN ({owner_sql}) AND ac.CONSTRAINT_TYPE IN ('P','U','R')
                 ORDER BY ac.OWNER, ac.TABLE_NAME, ac.CONSTRAINT_NAME, acc.POSITION
            """, binds)
            indexes = rows(cursor, f"""
                SELECT i.OWNER, i.TABLE_NAME, i.INDEX_NAME, i.UNIQUENESS, c.COLUMN_NAME, c.COLUMN_POSITION
                  FROM ALL_INDEXES i JOIN ALL_IND_COLUMNS c ON c.INDEX_OWNER=i.OWNER AND c.INDEX_NAME=c.INDEX_NAME
                 WHERE i.TABLE_OWNER IN ({owner_sql}) ORDER BY i.OWNER, i.TABLE_NAME, i.INDEX_NAME, c.COLUMN_POSITION
            """, binds)
            view_definitions = rows(cursor, f"SELECT OWNER, VIEW_NAME, TEXT FROM ALL_VIEWS WHERE OWNER IN ({owner_sql}) ORDER BY OWNER, VIEW_NAME", binds)

        payload = {
            "source": {"db_type": "oracle", "endpoint": dsn, "database": identity.get("database_name"), "owners": owners, "read_only": True},
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "identity": identity,
            "tables": tables, "views": views, "columns": columns,
            "constraints": constraints, "indexes": indexes, "view_definitions": view_definitions,
            "summary": {
                "owners": len(owners), "tables": len(tables), "views": len(views), "columns": len(columns),
                "constraint_columns": len(constraints), "index_columns": len(indexes), "source_writes": 0,
            },
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False))
        return 0
    finally:
        cursor.close()
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
