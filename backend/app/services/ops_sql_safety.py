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
            where_norm = re.sub(r"\s+", "", where_summary.upper())
            # reject tautology / always-true predicates
            if where_norm in {"1=1", "TRUE", "(1=1)", "1=1AND1=1"} or re.fullmatch(r"\(?1\s*=\s*1\)?", where_summary.strip(), re.I):
                errors.append("tautology WHERE is not allowed")
            if re.search(r"\bOR\s+1\s*=\s*1\b", where_summary, re.I):
                errors.append("tautology WHERE is not allowed")
            if re.search(r"\bWHERE\s+TRUE\b", f"WHERE {where_summary}", re.I) and ":" not in where_summary:
                errors.append("tautology WHERE is not allowed")
        if operation == "INSERT" and ":" not in (parsed.get("values_summary") or ""):
            errors.append("INSERT VALUES must use bind parameters")
        # no CTE / subquery hints for write templates
        if re.search(r"\bWITH\b", cleaned, re.I):
            errors.append("CTE/WITH is not allowed in write templates")
        if re.search(r"\bRETURNING\b", cleaned, re.I):
            errors.append("RETURNING is not allowed in write templates")

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


def validate_dry_run_sql(
    dml_sql: str,
    dry_run_sql: str,
    allowed_tables: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Ensure dry-run is SELECT count(*) against the same table/WHERE params as DML."""
    errors: list[str] = []
    cleaned_dml = _clean_sql(dml_sql)
    parsed_dml = _parse_statement(cleaned_dml) if cleaned_dml else None
    tables = list(allowed_tables or [])
    if parsed_dml and _normalize_table(parsed_dml["target_table"]) not in {_normalize_table(t) for t in tables}:
        tables.append(parsed_dml["target_table"])
    dml = validate_writable_sql(
        dml_sql,
        allowed_tables=tables,
        allowed_ops=["INSERT", "UPDATE"],
        params={name: 1 for name in _extract_params(cleaned_dml)},
    )
    cleaned = _clean_sql(dry_run_sql)
    if not cleaned:
        errors.append("dry_run_sql is required")
    if ";" in cleaned:
        errors.append("dry_run_sql must be a single statement")
    if "--" in (dry_run_sql or "") or "/*" in (dry_run_sql or ""):
        errors.append("dry_run_sql comments are not allowed")
    count_match = re.match(
        rf'^SELECT\s+COUNT\s*\(\s*\*\s*\)\s+FROM\s+({TABLE_RE})(?:\s+WHERE\s+(.+))?$',
        cleaned,
        re.IGNORECASE,
    )
    if not count_match:
        errors.append("dry_run_sql must be SELECT count(*) FROM asset.<table> [WHERE ...]")
    else:
        target = _normalize_table(count_match.group(1))
        if _table_schema(count_match.group(1)) != "asset":
            errors.append("dry_run_sql target must be asset schema")
        if dml.get("parsed_summary"):
            dml_target = dml["parsed_summary"]["target_table"]
            if target != dml_target:
                errors.append(f"dry_run table {target} != dml table {dml_target}")
            dml_params = set(dml["parsed_summary"].get("param_names") or [])
            dry_params = set(_extract_params(cleaned))
            # for UPDATE, WHERE params should match dry-run WHERE params
            if dml["parsed_summary"]["operation"] == "UPDATE":
                dml_where_params = set(_extract_params(dml["parsed_summary"].get("where_summary") or ""))
                if dry_params != dml_where_params:
                    errors.append("dry_run WHERE params must match UPDATE WHERE params")
            elif dry_params - dml_params:
                errors.append("dry_run has params not present in DML")
    return {
        "valid": not errors and dml.get("valid", False),
        "errors": errors + (dml.get("errors") or []),
        "dml_summary": dml.get("parsed_summary"),
    }