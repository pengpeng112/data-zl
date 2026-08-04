#!/usr/bin/env python3
"""Execute a bounded ODS SELECT through the repository OracleConnector."""

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
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.db_connectors import OracleConnector, validate_readonly_sql


SENSITIVE_MARKERS = (
    "PATIENT_NAME", "PERSON_NAME", "NAME_PHONETIC", "NEXT_OF_KIN", "ID_CARD",
    "ID_NO", "IDENTITY", "PHONE", "MOBILE", "ADDRESS", "HOME_ADDR",
    "CONTACT_NAME", "CONTACT_PHONE", "CERT_NO", "SOCIAL_NO", "PATIENT_ID",
    "PATIENT_NO", "INP_NO", "OUTPATIENT_NO",
)


def load_credential() -> tuple[str, str]:
    user = os.environ.get("APP_ODS_USER", "").strip()
    password = os.environ.get("APP_ODS_PASSWORD", "")
    combined = os.environ.get("CRED_ODS_8_216", "") or os.environ.get("CRED_ODS", "")
    if combined and ":" in combined:
        user, password = combined.split(":", 1)
    if not (user and password):
        credential_file = Path(os.environ.get(
            "APP_ODS_CREDENTIAL_FILE",
            "/etc/data-asset/credentials/ods_8_216",
        ))
        if credential_file.is_file():
            value = credential_file.read_text(encoding="utf-8").strip()
            if ":" in value:
                user, password = value.split(":", 1)
    if not (user and password):
        raise RuntimeError("ODS read-only credential is not configured through the approved environment")
    return user.strip(), password


def normalize(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return "<binary>"
    return value


def redact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: "***" if any(marker in str(key).upper() for marker in SENSITIVE_MARKERS) else normalize(value)
        for key, value in row.items()
    }


def sanitize_error(value: str) -> str:
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<host>", str(value)[:500])
    value = re.sub(r"(?i)(user|password|pwd)\s*=\s*[^\s,;]+", r"\1=<redacted>", value)
    return value[:200]


def build_connector() -> OracleConnector:
    user, password = load_credential()
    mode = os.environ.get("APP_ODS_CONNECTION_MODE", "direct").strip().lower()
    if mode not in {"direct", "ssh_jump"}:
        raise RuntimeError("APP_ODS_CONNECTION_MODE must be direct or ssh_jump")
    return OracleConnector(
        host=os.environ.get("APP_ODS_HOST", "10.10.8.216"),
        port=int(os.environ.get("APP_ODS_PORT", "1521")),
        database=os.environ.get("APP_ODS_SERVICE", "orcl"),
        user=user,
        password=password,
        connection_mode=mode,
        oracle_client_lib_dir=os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle"),
        timeout_ms=min(max(int(os.environ.get("APP_ODS_QUERY_TIMEOUT_MS", "60000")), 1000), 120000),
        large_tables=[
            "HIS.LAB_RESULT", "HIS.INP_BILL_DETAIL", "HIS.ORDERS",
            "HIS.OUTP_BILL_ITEMS",
        ],
    )


def export_readonly(
    connector: OracleConnector,
    sql: str,
    params: dict[str, Any],
    output: Path,
    output_format: str,
    max_rows: int,
) -> int:
    if connector.connection_mode != "direct":
        raise RuntimeError("50,000-row export must run in the internal direct environment, not through ssh_jump")
    resolved = output.expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise RuntimeError("export file must be outside the Git repository")
    if not resolved.parent.is_dir():
        raise RuntimeError("export parent directory does not exist")
    conn = connector.connect()
    cursor = conn.cursor()
    count = 0
    try:
        conn.call_timeout = connector._timeout_ms()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.arraysize = 1000
        cursor.execute(sql, params)
        columns = [item[0] for item in cursor.description]
        with resolved.open("w", encoding="utf-8-sig" if output_format == "csv" else "utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns) if output_format == "csv" else None
            if writer:
                writer.writeheader()
            while count < max_rows:
                batch = cursor.fetchmany(min(1000, max_rows - count))
                if not batch:
                    break
                for values in batch:
                    row = redact_row(dict(zip(columns, values)))
                    if writer:
                        writer.writerow(row)
                    else:
                        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                count += len(batch)
        try:
            os.chmod(resolved, 0o600)
        except OSError:
            pass
        return count
    finally:
        cursor.close()
        conn.rollback()


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a bounded, read-only DATA_CENTER query")
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

    connector: OracleConnector | None = None
    try:
        connector = build_connector()
        if args.test_connection:
            ok, message, elapsed_ms = connector.test_connectivity()
            print(json.dumps({"ok": ok, "message": sanitize_error(message), "elapsed_ms": elapsed_ms}, ensure_ascii=False))
            return 0 if ok else 1
        sql = args.sql_file.read_text(encoding="utf-8-sig").strip().rstrip(";").strip()
        sql = validate_readonly_sql(sql, set(connector.extra.get("large_tables") or []))
        params = {}
        if args.params_file:
            params = json.loads(args.params_file.read_text(encoding="utf-8-sig"))
            if not isinstance(params, dict):
                raise RuntimeError("params file must contain one JSON object")
        if args.export_file:
            count = export_readonly(
                connector, sql, params, args.export_file, args.export_format, args.export_max_rows,
            )
            print(json.dumps({
                "executed": True,
                "readonly": True,
                "business_source_writes": 0,
                "exported": True,
                "export_file": str(args.export_file.expanduser().resolve()),
                "export_format": args.export_format,
                "row_count": count,
                "truncated_possible": count >= args.export_max_rows,
            }, ensure_ascii=False))
            return 0
        rows = connector.execute_readonly(sql, params=params, max_rows=args.max_rows)
        safe_rows = [redact_row(dict(row)) for row in rows]
        print(json.dumps({
            "executed": True,
            "readonly": True,
            "business_source_writes": 0,
            "row_count": len(safe_rows),
            "truncated_possible": len(safe_rows) >= args.max_rows,
            "rows": safe_rows,
        }, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": sanitize_error(str(exc))}, ensure_ascii=False))
        return 1
    finally:
        if connector is not None:
            connector.close()


if __name__ == "__main__":
    sys.exit(main())
