"""Safety checks for controlled ops write templates.

This module is intentionally conservative. It only accepts single-statement,
parameterized INSERT/UPDATE templates targeting asset schema tables.
"""

from __future__ import annotations

import re
from typing import Any

FORBIDDEN_KEYWORDS = {
    "DELETE", "MERGE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE",
    "CALL", "EXEC", "EXECUTE", "BEGIN", "COMMIT", "ROLLBACK", "VACUUM", "COPY",
    "RENAME", "COMMENT", "ANALYZE", "REINDEX", "SAVEPOINT",
}

FORBIDDEN_FUNCTIONS = {
    "dblink", "lo_import", "lo_export", "pg_read_file", "pg_write_file", "pg_ls_dir",
    "pg_stat_file", "pg_sleep", "pg_notify", "http_get", "http_post", "format",
    "set_config",
}

ALLOWED_FUNCTIONS = {"now"}
IGNORED_FUNCTION_LIKE_KEYWORDS = {"values", "into", "set", "where", "update", "insert"}

IDENT = r'[A-Za-z_][\w$]*'
TABLE_RE = rf'{IDENT}(?:\.{IDENT})?'
PARAM_RE = re.compile(r'(?<!:):([A-Za-z_][\w]*)')
FUNCTION_RE = re.compile(r'\b([A-Za-z_][\w$]*)\s*\(', re.IGNORECASE)


def _clean_sql(sql: str) -> str:
    return " ".join((sql or "").strip().split())


def _normalize_table(name: str) -> str:
    return name.strip().strip('"').lower()


def _table_schema(name: str) -> str | None:
    parts = _normalize_table(name).split(".")
    return parts[0] if len(parts) == 2 else None


def _has_forbidden_keyword(sql: str) -> str | None:
    upper = sql.upper()
    for keyword in sorted(FORBIDDEN_KEYWORDS):
        if re.search(rf'\b{keyword}\b', upper):
            return keyword
    return None


def _function_errors(sql: str) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for match in FUNCTION_RE.finditer(sql):
        name = match.group(1).lower()
        if name in seen:
            continue
        seen.add(name)
        if name in IGNORED_FUNCTION_LIKE_KEYWORDS:
            continue
        if match.start(1) > 0 and sql[match.start(1) - 1] == ".":
            continue
        if name in FORBIDDEN_FUNCTIONS:
            errors.append(f"forbidden function: {name}")
        elif name not in ALLOWED_FUNCTIONS:
            errors.append(f"function {name} is not allowed in write templates")
    return errors


def _extract_params(sql: str) -> list[str]:
    return sorted(set(PARAM_RE.findall(sql)))


def _parse_statement(sql: str) -> dict[str, Any] | None:
    cleaned = _clean_sql(sql)
    update_match = re.match(rf'^UPDATE\s+({TABLE_RE})\s+SET\s+(.+)\s+WHERE\s+(.+)$', cleaned, re.IGNORECASE)
    if update_match:
        return {
            "operation": "UPDATE",
            "target_table": update_match.group(1),
            "set_summary": update_match.group(2)[:240],
            "where_summary": update_match.group(3)[:240],
        }
    insert_match = re.match(
        rf'^INSERT\s+INTO\s+({TABLE_RE})\s*\(([^)]*)\)\s+VALUES\s*\((.+)\)$',
        cleaned,
        re.IGNORECASE,
    )
    if insert_match:
        return {
            "operation": "INSERT",
            "target_table": insert_match.group(1),
            "columns_summary": insert_match.group(2)[:240],
            "values_summary": insert_match.group(3)[:240],
            "where_summary": None,
        }
    return None


def validate_writable_sql(
    sql: str,
    allowed_tables: list[str] | tuple[str, ...] | None,
    allowed_ops: list[str] | tuple[str, ...] | None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    cleaned = _clean_sql(sql)
    parsed = _parse_statement(cleaned) if cleaned else None

    if not cleaned:
        errors.append("SQL template is required")
    if ";" in cleaned:
        errors.append("semicolon or multi-statement SQL is not allowed")
    if "--" in sql or "/*" in sql or "*/" in sql:
        errors.append("SQL comments are not allowed in write templates")

    forbidden = _has_forbidden_keyword(cleaned)
    if forbidden:
        errors.append(f"forbidden keyword: {forbidden}")
    errors.extend(_function_errors(cleaned))

    if re.search(r'\bINSERT\b', cleaned, re.IGNORECASE) and re.search(r'\bSELECT\b', cleaned, re.IGNORECASE):
        errors.append("INSERT ... SELECT is not allowed")
    if re.search(r'\bON\s+CONFLICT\b', cleaned, re.IGNORECASE):
        errors.append("ON CONFLICT/UPSERT is not allowed")

    if not parsed:
        errors.append("only single UPDATE ... WHERE or INSERT INTO ... VALUES templates are allowed")
    else:
        operation = parsed["operation"]
        target_table = parsed["target_table"]
        allowed_op_set = {item.upper() for item in (allowed_ops or [])}
        allowed_table_set = {_normalize_table(item) for item in (allowed_tables or [])}
        normalized_target = _normalize_table(target_table)
        if operation not in allowed_op_set:
            errors.append(f"operation {operation} is not in allowed_operations")
        if normalized_target not in allowed_table_set:
            errors.append(f"target table {target_table} is not in allowed_tables")
        if _table_schema(target_table) != "asset":
            errors.append("first phase only allows writes to asset schema tables")
        if operation == "UPDATE":
            where_summary = parsed.get("where_summary") or ""
            if not where_summary:
                errors.append("UPDATE must include WHERE")
            elif ":" not in where_summary:
                errors.append("UPDATE WHERE must use bind parameters")
        if operation == "INSERT" and ":" not in (parsed.get("values_summary") or ""):
            errors.append("INSERT VALUES must use bind parameters")

    param_names = _extract_params(cleaned)
    provided_params = set((params or {}).keys())
    missing_params = [name for name in param_names if name not in provided_params]
    if missing_params:
        errors.append(f"missing bind params: {', '.join(missing_params)}")
    extra_params = sorted(provided_params - set(param_names))
    if extra_params:
        warnings.append(f"unused bind params: {', '.join(extra_params)}")
    if not param_names:
        errors.append("write templates must use bind parameters")

    parsed_summary = None
    if parsed:
        parsed_summary = {
            "operation": parsed["operation"],
            "target_table": _normalize_table(parsed["target_table"]),
            "where_summary": parsed.get("where_summary"),
            "param_names": param_names,
        }

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "parsed_summary": parsed_summary,
    }