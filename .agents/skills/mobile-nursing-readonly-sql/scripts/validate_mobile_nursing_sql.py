#!/usr/bin/env python3
"""Static gate for mobile-nursing Oracle read-only SQL; never connects."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORBIDDEN = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|"
    r"COMMENT|RENAME|CALL|EXEC(?:UTE)?|BEGIN|DECLARE|COMMIT|ROLLBACK|LOCK)\b",
    re.IGNORECASE,
)
SELECT_STAR = re.compile(r"\bSELECT\s+(?:[A-Za-z_][\w$#]*\.)?\*", re.IGNORECASE)
FETCH_FIRST = re.compile(r"\bFETCH\s+FIRST\b", re.IGNORECASE)
LARGE_TABLE = re.compile(
    r"\b(?:LUNA_MCS_SDSEY\.)?(?:MCS_DOC_FORM_RECORDS|MCS_ASSESS_FORM_RECORD|"
    r"MCS_ORDER_SCHEDULE_PROCESS|MCS_ORDER_SCHEDULE|MCS_PATROL_INFO|"
    r"MCS_DOC_FORM_OPERATION_LOG|MCS_VITAL_INFO|MCS_DOC_FORM)\b",
    re.IGNORECASE,
)
BOUNDARY = re.compile(
    r"\b(?:PATIENT_UID|FORM_ID|TEMPLATE_CODE|WARD_CODE|RECORD_TIME|PLAN_TIME|"
    r"CREATED_DATE|ROWNUM)\b",
    re.IGNORECASE,
)


def clean(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\r\n]*", " ", sql)
    return re.sub(r"'(?:''|[^'])*'", "''", sql)


def validate(sql: str) -> list[str]:
    text = clean(sql).strip()
    errors: list[str] = []
    first = re.match(r"[A-Za-z]+", text)
    if not first or first.group(0).upper() not in {"SELECT", "WITH"}:
        errors.append("SQL must start with SELECT or a read-only WITH clause")
    if FORBIDDEN.search(text):
        errors.append("DDL/DML, transaction, lock, or procedural keyword detected")
    if SELECT_STAR.search(text):
        errors.append("SELECT * is not allowed")
    if FETCH_FIRST.search(text):
        errors.append("Oracle 11g requires an outer ROWNUM limit")
    if LARGE_TABLE.search(text) and not BOUNDARY.search(text):
        errors.append("mobile-nursing large table requires a patient, form, ward, time, or ROWNUM boundary")
    if len([part for part in text.split(";") if part.strip()]) != 1:
        errors.append("Exactly one SQL statement is allowed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sql_file", type=Path)
    args = parser.parse_args()
    errors = validate(args.sql_file.read_text(encoding="utf-8-sig"))
    if errors:
        print("BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: static read-only checks passed; SQL was not executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
