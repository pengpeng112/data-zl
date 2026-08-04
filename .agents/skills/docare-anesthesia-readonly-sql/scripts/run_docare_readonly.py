#!/usr/bin/env python3
"""Run a bounded Docare SELECT through the repository Oracle connector."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.db_connectors import OracleConnector, validate_readonly_sql

SENSITIVE = (
    "PATIENT_NAME", "PERSON_NAME", "NAME", "ID_CARD", "ID_NO", "PHONE",
    "MOBILE", "ADDRESS", "CONTACT", "CERT_NO", "PATIENT_ID", "INP_NO",
)
LARGE_TABLES = {
    "MEDSURGERY.MED_CUSTOM_DATA",
    "MEDSURGERY.MED_ANESTHESIA_EVENT_BACK",
    "MEDCOMM.MED_VITAL_SIGN_MERGE",
    "MEDCOMM.MED_LAB_RESULT",
    "MEDSURGERY.MED_QIXIE_QINGDIAN",
    "MEDSURGERY.MED_PATIENT_MONITOR_DATA",
    "MEDSURGERY.MED_APPLICATION_AUDIT_TRAIL",
    "MEDSURGERY.MED_PAT_MONITOR_DATA",
    "MEDSURGERY.MED_ANESTHESIA_EVENT",
}


def load_credential() -> tuple[str, str]:
    user = os.environ.get("APP_DOCARE_USER", "").strip()
    password = os.environ.get("APP_DOCARE_PASSWORD", "")
    combined = os.environ.get("CRED_DOCARE", "")
    if combined and ":" in combined:
        user, password = combined.split(":", 1)
    if not (user and password):
        path = Path(os.environ.get(
            "APP_DOCARE_CREDENTIAL_FILE",
            "/etc/data-asset/credentials/docare_10_10_10_68",
        ))
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if ":" in value:
                user, password = value.split(":", 1)
    if not (user and password):
        raise RuntimeError("Docare read-only credential is not configured through the approved environment")
    return user, password


def build_connector() -> OracleConnector:
    user, password = load_credential()
    mode = os.environ.get("APP_DOCARE_CONNECTION_MODE", "direct").strip().lower()
    if mode not in {"direct", "ssh_jump"}:
        raise RuntimeError("APP_DOCARE_CONNECTION_MODE must be direct or ssh_jump")
    return OracleConnector(
        host=os.environ.get("APP_DOCARE_HOST", "10.10.10.68"),
        port=int(os.environ.get("APP_DOCARE_PORT", "1521")),
        database=os.environ.get("APP_DOCARE_SERVICE", "docare"),
        user=user,
        password=password,
        connection_mode=mode,
        oracle_client_lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"),
        timeout_ms=min(max(int(os.environ.get("APP_DOCARE_QUERY_TIMEOUT_MS", "60000")), 1000), 120000),
        large_tables=list(LARGE_TABLES),
    )


def normalize(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return "<binary>"
    return value


def redact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: "***" if any(marker in str(key).upper() for marker in SENSITIVE) else normalize(value)
        for key, value in row.items()
    }


def safe_error(value: str) -> str:
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<host>", str(value)[:500])
    value = re.sub(r"(?i)(user|password|pwd)\s*=\s*[^\s,;]+", r"\1=<redacted>", value)
    return value[:200]


def export_rows(db: OracleConnector, sql: str, params: dict[str, Any], target: Path, fmt: str, limit: int) -> int:
    if db.connection_mode != "direct":
        raise RuntimeError("50,000-row export requires the internal direct environment")
    target = target.expanduser().resolve()
    if target == REPO_ROOT or REPO_ROOT in target.parents or not target.parent.is_dir():
        raise RuntimeError("export must target an existing directory outside the Git repository")
    conn = db.connect()
    cursor = conn.cursor()
    count = 0
    try:
        conn.call_timeout = db._timeout_ms()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.arraysize = 1000
        cursor.execute(sql, params)
        columns = [item[0] for item in cursor.description]
        with target.open("w", encoding="utf-8-sig" if fmt == "csv" else "utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns) if fmt == "csv" else None
            if writer:
                writer.writeheader()
            while count < limit:
                batch = cursor.fetchmany(min(1000, limit - count))
                if not batch:
                    break
                for values in batch:
                    row = redact(dict(zip(columns, values)))
                    writer.writerow(row) if writer else handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += len(batch)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return count
    finally:
        cursor.close()
        conn.rollback()


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a bounded, read-only Docare query")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test-connection", action="store_true")
    group.add_argument("--sql-file", type=Path)
    parser.add_argument("--params-file", type=Path)
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--export-file", type=Path)
    parser.add_argument("--export-format", choices=("csv", "jsonl"), default="csv")
    parser.add_argument("--export-max-rows", type=int, default=50000)
    args = parser.parse_args()
    if not 1 <= args.max_rows <= 10000:
        raise SystemExit("--max-rows must be between 1 and 10000")
    if not 1 <= args.export_max_rows <= 50000:
        raise SystemExit("--export-max-rows must be between 1 and 50000")

    db: OracleConnector | None = None
    try:
        db = build_connector()
        if args.test_connection:
            ok, message, elapsed = db.test_connectivity()
            print(json.dumps({"ok": ok, "message": safe_error(message), "elapsed_ms": elapsed}, ensure_ascii=False))
            return 0 if ok else 1
        sql = args.sql_file.read_text(encoding="utf-8-sig").strip().rstrip(";").strip()
        sql = validate_readonly_sql(sql, LARGE_TABLES)
        params = json.loads(args.params_file.read_text(encoding="utf-8-sig")) if args.params_file else {}
        if not isinstance(params, dict):
            raise RuntimeError("params file must contain one JSON object")
        if args.export_file:
            count = export_rows(db, sql, params, args.export_file, args.export_format, args.export_max_rows)
            result = {"readonly": True, "business_source_writes": 0, "exported": True, "row_count": count}
        else:
            rows = db.execute_readonly(sql, params=params, max_rows=args.max_rows)
            result = {
                "readonly": True,
                "business_source_writes": 0,
                "row_count": len(rows),
                "rows": [redact(dict(row)) for row in rows],
            }
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": safe_error(str(exc))}, ensure_ascii=False))
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
