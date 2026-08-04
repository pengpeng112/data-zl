#!/usr/bin/env python3
"""Static validator for HIS_SOURCE Oracle 11g read-only SQL."""
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
LOCKING = re.compile(r"\b(?:FOR\s+UPDATE|FOR\s+SHARE|LOCK\s+TABLE)\b", re.IGNORECASE)
SELECT_INTO = re.compile(r"\bSELECT\b[\s\S]*?\bINTO\b", re.IGNORECASE)
SELECT_STAR = re.compile(r"\bSELECT\s+(?:[A-Za-z_][\w$#]*\.)?\*", re.IGNORECASE)
FETCH_FIRST = re.compile(r"\bFETCH\s+FIRST\b", re.IGNORECASE)
WHERE = re.compile(r"\bWHERE\b", re.IGNORECASE)

LARGE_TABLES = {
    "ORDADM.ORDERS",
    "ORDADM.ORDERS_COSTS",
    "ORDADM.ORDERS_EXECUTE_DETAILS",
    "LAB.LAB_RESULT",
    "INPBILL.INP_BILL_DETAIL",
    "OUTPBILL.OUTP_BILL_ITEMS",
    "PHARMACY.DRUG_DISPENSE_REC",
}


def strip_comments_and_literals(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\r\n]*", " ", sql)
    return re.sub(r"'(?:''|[^'])*'", "''", sql)


def referenced_tables(sql: str) -> set[str]:
    return {
        match.group(1).upper().strip('"')
        for match in re.finditer(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w$#]*\.[A-Za-z_][\w$#]*)", sql, re.IGNORECASE)
    }


def validate(sql: str) -> list[str]:
    errors: list[str] = []
    cleaned = strip_comments_and_literals(sql).strip()
    if not cleaned:
        return ["SQL is empty"]
    first = re.match(r"[A-Za-z]+", cleaned)
    if not first or first.group(0).upper() not in {"SELECT", "WITH"}:
        errors.append("SQL must start with SELECT or a read-only WITH clause")
    if FORBIDDEN.search(cleaned) or LOCKING.search(cleaned) or SELECT_INTO.search(cleaned):
        errors.append("write, DDL, procedural, SELECT INTO, or locking SQL detected")
    if SELECT_STAR.search(cleaned):
        errors.append("SELECT * is not allowed in the delivered projection")
    if FETCH_FIRST.search(cleaned):
        errors.append("Oracle 11g does not support FETCH FIRST; use an outer ROWNUM limit")
    statements = [part for part in cleaned.split(";") if part.strip()]
    if len(statements) != 1:
        errors.append("exactly one SQL statement is allowed")
    protected = referenced_tables(cleaned).intersection(LARGE_TABLES)
    if protected and not WHERE.search(cleaned):
        errors.append("a WHERE clause is required for large table(s): " + ", ".join(sorted(protected)))
    if "LAB.LAB_RESULT" in protected and not re.search(r"\bTEST_NO\b", cleaned, re.IGNORECASE):
        errors.append("LAB.LAB_RESULT must be constrained through TEST_NO")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate HIS_SOURCE Oracle read-only SQL")
    parser.add_argument("sql_file", type=Path)
    args = parser.parse_args()
    errors = validate(args.sql_file.read_text(encoding="utf-8-sig"))
    if errors:
        print("BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: static HIS read-only checks passed; SQL was not executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
