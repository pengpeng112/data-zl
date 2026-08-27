"""Harvest 门诊预约 MySQL via nested SSH exec + mysql CLI (root is localhost-only).

Same output shape as harvest_mysql_readonly.py so downstream packaging works.
Credentials only via env: OUTPATIENT_SSH_PASSWORD / OUTPATIENT_DB_PASSWORD.
Read-only: SELECT/SHOW against information_schema only.
"""
import csv
import io as _io
import json
import os
import sys
from datetime import datetime, timezone

import paramiko

JUMP = ("10.10.8.83", 22)
JUMP_KEY = r"C:\Users\Administrator\.ssh\id_ed25519_ai"
TARGET = "10.10.8.161"
MYSQL = "/usr/bin/mysql"
SYSTEM_DATABASES = ("information_schema", "mysql", "performance_schema", "sys")


def run_tsv(target, sql: str) -> list[dict]:
    cmd = f"{MYSQL} -N -B --raw -e {json.dumps(sql)}"
    _, stdout, stderr = target.exec_command(cmd, timeout=300)
    text = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace").strip()
    if err:
        raise RuntimeError(f"mysql error: {err[:300]}")
    reader = csv.DictReader(_io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    return [dict(row) for row in reader]


def main() -> int:
    ssh_user = os.environ.get("OUTPATIENT_SSH_USER", "root")
    ssh_pass = os.environ["OUTPATIENT_SSH_PASSWORD"]
    db_user = os.environ.get("OUTPATIENT_DB_USER", "root")
    db_pass = os.environ["OUTPATIENT_DB_PASSWORD"]
    output = os.environ.get("OUTPATIENT_OUTPUT", "outpatient_snapshot.json")

    jump = paramiko.SSHClient()
    jump.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    jump.connect(JUMP[0], JUMP[1], username="root", key_filename=JUMP_KEY, timeout=15, allow_agent=False, look_for_keys=False)
    channel = jump.get_transport().open_channel("direct-tcpip", (TARGET, 22), ("127.0.0.1", 0))
    target = paramiko.SSHClient()
    target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target.connect(TARGET, 22, username=ssh_user, password=ssh_pass, sock=channel, timeout=15, allow_agent=False, look_for_keys=False)
    target.exec_command(f"export MYSQL_PWD={db_pass}")  # env applies per-session below

    def mysql_tsv(sql: str) -> list[dict]:
        cmd = f"if [ -s /tmp/.mpw ]; then MYSQL_PWD=$(cat /tmp/.mpw) {MYSQL} -u{db_user} -N -B --raw -e {json.dumps(sql)}; else {MYSQL} -u{db_user} -N -B --raw -e {json.dumps(sql)}; fi"
        _, stdout, stderr = target.exec_command(cmd, timeout=600)
        text = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace").strip()
        if err:
            raise RuntimeError(f"mysql error: {err[:300]}")
        return [dict(row) for row in csv.DictReader(_io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)]

    # keep the password off the command line: write 0600 temp file once
    sftp = target.open_sftp()
    # empty file => auth_socket passwordless root path
    with sftp.file("/tmp/.mpw", "w") as fh:
        fh.write(db_pass if os.environ.get("OUTPATIENT_DB_USE_PASSWORD", "1") == "1" else "")
    sftp.chmod("/tmp/.mpw", 0o600)

    try:
        version = mysql_tsv("SELECT VERSION() v")[0]["v"]
        exclude = ",".join(f"'{d}'" for d in SYSTEM_DATABASES)
        databases = [r["schema_name"] for r in mysql_tsv(
            f"SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ({exclude}) ORDER BY schema_name")]
        db_filter = ",".join(f"'{d}'" for d in databases)

        tables = mysql_tsv(f"""
            SELECT TABLE_SCHEMA database_name, TABLE_NAME table_name, TABLE_TYPE table_type,
                   IFNULL(ENGINE,'') engine, IFNULL(TABLE_ROWS,'') estimated_rows, IFNULL(TABLE_COMMENT,'') comment
              FROM information_schema.tables WHERE TABLE_SCHEMA IN ({db_filter})
             ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        columns = mysql_tsv(f"""
            SELECT TABLE_SCHEMA database_name, TABLE_NAME table_name, ORDINAL_POSITION ordinal_position,
                   COLUMN_NAME column_name, DATA_TYPE data_type, IFNULL(IS_NULLABLE,'') is_nullable,
                   IFNULL(COLUMN_KEY,'') column_key, IFNULL(EXTRA,'') extra,
                   IFNULL(COLUMN_DEFAULT,'') column_default, IFNULL(COLUMN_COMMENT,'') comment
              FROM information_schema.columns WHERE TABLE_SCHEMA IN ({db_filter})
             ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
        """)
        keys = mysql_tsv(f"""
            SELECT kcu.CONSTRAINT_SCHEMA database_name, kcu.TABLE_NAME table_name,
                   kcu.CONSTRAINT_NAME constraint_name, tc.CONSTRAINT_TYPE constraint_type,
                   kcu.COLUMN_NAME column_name, kcu.ORDINAL_POSITION ordinal_position
              FROM information_schema.key_column_usage kcu
              JOIN information_schema.table_constraints tc
                ON tc.CONSTRAINT_SCHEMA=kcu.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=kcu.CONSTRAINT_NAME
               AND tc.TABLE_NAME=kcu.TABLE_NAME AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY','UNIQUE')
             WHERE kcu.CONSTRAINT_SCHEMA IN ({db_filter})
             ORDER BY kcu.CONSTRAINT_SCHEMA, kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
        """)
        foreign_keys = mysql_tsv(f"""
            SELECT CONSTRAINT_SCHEMA database_name, TABLE_NAME table_name, CONSTRAINT_NAME constraint_name,
                   COLUMN_NAME column_name, ORDINAL_POSITION ordinal_position,
                   IFNULL(REFERENCED_TABLE_SCHEMA,'') referenced_database,
                   IFNULL(REFERENCED_TABLE_NAME,'') referenced_table,
                   IFNULL(REFERENCED_COLUMN_NAME,'') referenced_column
              FROM information_schema.key_column_usage
             WHERE CONSTRAINT_SCHEMA IN ({db_filter}) AND REFERENCED_TABLE_NAME IS NOT NULL
             ORDER BY CONSTRAINT_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
        """)
        indexes = mysql_tsv(f"""
            SELECT TABLE_SCHEMA database_name, TABLE_NAME table_name, INDEX_NAME index_name,
                   IFNULL(NON_UNIQUE,'') non_unique, IFNULL(INDEX_TYPE,'') index_type,
                   COLUMN_NAME column_name, SEQ_IN_INDEX ordinal_position
              FROM information_schema.statistics
             WHERE TABLE_SCHEMA IN ({db_filter})
             ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
        """)
    finally:
        target.exec_command("rm -f /tmp/.mpw")
        target.close()
        jump.close()

    views = [t for t in tables if str(t.get("table_type", "")).upper() == "VIEW"]
    real_tables = [t for t in tables if str(t.get("table_type", "")).upper() != "VIEW"]
    unique_keys = [k for k in keys if k["constraint_type"] == "UNIQUE"]
    primary_keys = [k for k in keys if k["constraint_type"] == "PRIMARY KEY"]

    payload = {
        "source": {"db_type": "mysql", "endpoint": "10.10.8.161:3306@localhost-via-ssh", "read_only": True},
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "database_version": version,
        "databases": databases,
        "tables": real_tables, "views": views, "columns": columns,
        "keys": primary_keys, "unique_keys": unique_keys, "foreign_keys": foreign_keys, "indexes": indexes,
        "routines": [], "triggers": [], "dependencies": [],
        "routine_metadata_status": "SKIPPED_SSH_PATH",
        "errors": [], "source_writes": 0,
        "summary": {
            "databases": len(databases), "tables": len(real_tables), "views": len(views),
            "columns": len(columns), "keys": len(primary_keys), "unique_keys": len(unique_keys),
            "foreign_keys": len(foreign_keys), "indexes": len(indexes), "source_writes": 0,
        },
    }
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
