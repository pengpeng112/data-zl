#!/usr/bin/env python3
"""Run a bounded mobile-nursing SELECT through the repository connector."""

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
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.db_connectors import OracleConnector, validate_readonly_sql

SENSITIVE = (
    "PATIENT_NAME", "PERSON_NAME", "NURSE_NAME", "ID_CARD", "ID_NO", "PHONE",
    "MOBILE", "ADDRESS", "CONTACT", "CERT_NO", "PATIENT_ID", "PATIENT_UID",
    "PAT_INDEX_NO", "MRN", "INP_NO",
)
LARGE_TABLES = {
    "LUNA_MCS_SDSEY.MCS_DOC_FORM_RECORDS",
    "LUNA_MCS_SDSEY.MCS_ASSESS_FORM_RECORD",
    "LUNA_MCS_SDSEY.MCS_ORDER_SCHEDULE_PROCESS",
    "LUNA_MCS_SDSEY.MCS_ORDER_SCHEDULE",
    "LUNA_MCS_SDSEY.MCS_PATROL_INFO",
    "LUNA_MCS_SDSEY.MCS_DOC_FORM_OPERATION_LOG",
    "LUNA_MCS_SDSEY.MCS_VITAL_INFO",
    "LUNA_MCS_SDSEY.MCS_DOC_FORM",
}


def credential() -> tuple[str, str]:
    user = os.environ.get("APP_MOBILE_NURSING_USER", "").strip()
    password = os.environ.get("APP_MOBILE_NURSING_PASSWORD", "")
    combined = os.environ.get("CRED_MOBILE_NURSING", "")
    if combined and ":" in combined:
        user, password = combined.split(":", 1)
    if not (user and password):
        path = Path(os.environ.get(
            "APP_MOBILE_NURSING_CREDENTIAL_FILE",
            "/etc/data-asset/credentials/mobile_nursing_10_10_10_125",
        ))
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if ":" in value:
                user, password = value.split(":", 1)
    if not (user and password):
        raise RuntimeError("mobile-nursing read-only credential is not configured")
    return user, password


def connector() -> OracleConnector:
    user, password = credential()
    mode = os.environ.get("APP_MOBILE_NURSING_CONNECTION_MODE", "direct").lower()
    if mode not in {"direct", "ssh_jump"}:
        raise RuntimeError("connection mode must be direct or ssh_jump")
    return OracleConnector(
        host=os.environ.get("APP_MOBILE_NURSING_HOST", "10.10.10.125"),
        port=int(os.environ.get("APP_MOBILE_NURSING_PORT", "1521")),
        database=os.environ.get("APP_MOBILE_NURSING_SERVICE", "ewell"),
        user=user,
        password=password,
        connection_mode=mode,
        oracle_client_lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"),
        timeout_ms=min(max(int(os.environ.get("APP_MOBILE_NURSING_TIMEOUT_MS", "60000")), 1000), 120000),
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


def redact(columns: list[str], values: tuple[Any, ...]) -> dict[str, Any]:
    return {
        key: "***" if any(mark in key.upper() for mark in SENSITIVE) else normalize(value)
        for key, value in zip(columns, values)
    }


def safe_error(value: str) -> str:
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<host>", str(value)[:500])
    return re.sub(r"(?i)(user|password|pwd)\s*=\s*[^\s,;]+", r"\1=<redacted>", value)[:200]


def export(connector_: OracleConnector, sql: str, params: dict[str, Any], path: Path, fmt: str, limit: int) -> int:
    if connector_.connection_mode != "direct":
        raise RuntimeError("export requires the internal direct environment")
    target = path.expanduser().resolve()
    if target == REPO_ROOT or REPO_ROOT in target.parents or not target.parent.is_dir():
        raise RuntimeError("export must target an existing directory outside the Git repository")
    conn = connector_.connect()
    cur = conn.cursor()
    count = 0
    try:
        conn.call_timeout = connector_._timeout_ms()
        cur.execute("SET TRANSACTION READ ONLY")
        cur.arraysize = 1000
        cur.execute(sql, params)
        columns = [item[0] for item in cur.description]
        with target.open("w", encoding="utf-8-sig" if fmt == "csv" else "utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns) if fmt == "csv" else None
            if writer:
                writer.writeheader()
            while count < limit:
                rows = cur.fetchmany(min(1000, limit - count))
                if not rows:
                    break
                for values in rows:
                    row = redact(columns, values)
                    writer.writerow(row) if writer else handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += len(rows)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return count
    finally:
        cur.close()
        conn.rollback()


def main() -> int:
    parser = argparse.ArgumentParser()
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
        db = connector()
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
            count = export(db, sql, params, args.export_file, args.export_format, args.export_max_rows)
            result = {"readonly": True, "business_source_writes": 0, "row_count": count, "exported": True}
        else:
            rows = db.execute_readonly(sql, params=params, max_rows=args.max_rows)
            columns = list(rows[0].keys()) if rows else []
            result = {
                "readonly": True, "business_source_writes": 0, "row_count": len(rows),
                "rows": [redact(columns, tuple(row.values())) for row in rows],
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
