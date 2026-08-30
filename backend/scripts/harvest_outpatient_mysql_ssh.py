"""Harvest 门诊预约 MySQL via nested SSH exec + mysql CLI (root is localhost-only).

Same output shape as harvest_mysql_readonly.py so downstream packaging works.
Credentials only via env: OUTPATIENT_SSH_PASSWORD / OUTPATIENT_DB_PASSWORD.
Read-only: SELECT/SHOW against information_schema only.
"""
import csv
import io as _io
import json
import os
import shlex
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paramiko

JUMP = ("10.10.8.83", 22)
TARGET = "10.10.8.161"
MYSQL = "/usr/bin/mysql"
SYSTEM_DATABASES = ("information_schema", "mysql", "performance_schema", "sys")


def _load_known_hosts(client: paramiko.SSHClient, env_name: str) -> None:
    """Load trusted host keys and fail closed when the host is unknown."""
    client.load_system_host_keys()
    default_file = Path.home() / ".ssh" / "known_hosts"
    configured = os.environ.get(env_name)
    if configured:
        client.load_host_keys(configured)
    elif default_file.exists():
        client.load_host_keys(str(default_file))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())


def _mysql_option_value(value: str) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("MySQL credential values may not contain NUL or newlines")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _mysql_command(option_file: str, sql: str) -> str:
    return " ".join(
        [
            shlex.quote(MYSQL),
            f"--defaults-extra-file={shlex.quote(option_file)}",
            "-N",
            "-B",
            "--raw",
            "-e",
            shlex.quote(sql),
        ]
    )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    ssh_user = os.environ.get("OUTPATIENT_SSH_USER", "root")
    ssh_pass = os.environ["OUTPATIENT_SSH_PASSWORD"]
    db_user = os.environ.get("OUTPATIENT_DB_USER", "root")
    db_pass = os.environ["OUTPATIENT_DB_PASSWORD"]
    output = os.environ.get("OUTPATIENT_OUTPUT", "outpatient_snapshot.json")
    jump_key = os.environ.get(
        "OUTPATIENT_JUMP_KEY_FILE",
        str(Path.home() / ".ssh" / "id_ed25519_ai"),
    )

    jump = paramiko.SSHClient()
    target = paramiko.SSHClient()
    option_file = f"/tmp/data_asset_mysql_{uuid.uuid4().hex}.cnf"
    _load_known_hosts(jump, "OUTPATIENT_JUMP_KNOWN_HOSTS")
    _load_known_hosts(target, "OUTPATIENT_TARGET_KNOWN_HOSTS")

    def mysql_tsv(sql: str) -> list[dict]:
        cmd = _mysql_command(option_file, sql)
        _, stdout, stderr = target.exec_command(cmd, timeout=600)
        text = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace").strip()
        if err:
            raise RuntimeError(f"mysql error: {err[:300]}")
        return [dict(row) for row in csv.DictReader(_io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)]

    try:
        jump.connect(JUMP[0], JUMP[1], username="root", key_filename=jump_key, timeout=15, allow_agent=False, look_for_keys=False)
        transport = jump.get_transport()
        if transport is None:
            raise RuntimeError("SSH jump transport unavailable")
        channel = transport.open_channel("direct-tcpip", (TARGET, 22), ("127.0.0.1", 0))
        target.connect(TARGET, 22, username=ssh_user, password=ssh_pass, sock=channel, timeout=15, allow_agent=False, look_for_keys=False)

        # A unique 0600 option file keeps credentials out of command arguments.
        option_lines = ["[client]", f"user={_mysql_option_value(db_user)}"]
        if os.environ.get("OUTPATIENT_DB_USE_PASSWORD", "1") == "1":
            option_lines.append(f"password={_mysql_option_value(db_pass)}")
        sftp = target.open_sftp()
        try:
            with sftp.file(option_file, "x") as fh:
                # Tighten permissions before any credential bytes are written.
                sftp.chmod(option_file, 0o600)
                fh.write("\n".join(option_lines) + "\n")
        finally:
            sftp.close()

        version = mysql_tsv("SELECT VERSION() v")[0]["v"]
        exclude = ",".join(_sql_literal(d) for d in SYSTEM_DATABASES)
        databases = [r["schema_name"] for r in mysql_tsv(
            f"SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ({exclude}) ORDER BY schema_name")]
        if not databases:
            raise RuntimeError("no non-system MySQL databases are visible to the supplied account")
        db_filter = ",".join(_sql_literal(d) for d in databases)

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
        cleanup_error = None
        if target.get_transport() is not None:
            cleanup_sftp = None
            try:
                cleanup_sftp = target.open_sftp()
                cleanup_sftp.remove(option_file)
            except FileNotFoundError:
                pass
            except Exception as exc:
                cleanup_error = exc
            finally:
                if cleanup_sftp is not None:
                    cleanup_sftp.close()
        target.close()
        jump.close()
        if cleanup_error is not None:
            raise RuntimeError("failed to remove remote temporary MySQL option file") from cleanup_error

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
