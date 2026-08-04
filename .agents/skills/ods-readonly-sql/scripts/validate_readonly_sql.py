#!/usr/bin/env python3
"""Static safety gate for ODS read-only SQL drafts.
This script does not connect to a database and does not execute SQL.
"""

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
LAB_RESULT = re.compile(r"\bHIS\.LAB_RESULT\b", re.IGNORECASE)
TEST_NO = re.compile(r"\bTEST_NO\b", re.IGNORECASE)


def strip_comments_and_literals(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\r\n]*", " ", sql)
    sql = re.sub(r"'(?:''|[^'])*'", "''", sql)
    return sql


def validate(sql: str) -> list[str]:
    errors: list[str] = []
    cleaned = strip_comments_and_literals(sql).strip()
    if not cleaned:
        return ["SQL is empty"]

    first_word = re.match(r"[A-Za-z]+", cleaned)
    if not first_word or first_word.group(0).upper() not in {"SELECT", "WITH"}:
        errors.append("SQL must start with SELECT or a read-only WITH clause")
    if FORBIDDEN.search(cleaned):
        errors.append("DDL/DML or procedural keyword detected")
    if SELECT_STAR.search(cleaned):
        errors.append("SELECT * is not allowed in the delivered projection")
    if FETCH_FIRST.search(cleaned):
        errors.append("Oracle 11g does not support FETCH FIRST; use an outer ROWNUM limit")
    if LAB_RESULT.search(cleaned) and not TEST_NO.search(cleaned):
        errors.append("HIS.LAB_RESULT must be constrained through TEST_NO")

    statements = [part for part in cleaned.split(";") if part.strip()]
    if len(statements) != 1:
        errors.append("Exactly one SQL statement is allowed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an ODS Oracle read-only SQL draft")
    parser.add_argument("sql_file", type=Path)
    args = parser.parse_args()
    sql = args.sql_file.read_text(encoding="utf-8-sig")
    errors = validate(sql)
    if errors:
        print("BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: static read-only checks passed; SQL was not executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
