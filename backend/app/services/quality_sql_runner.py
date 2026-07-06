"""Read-only quality SQL execution against registered source databases."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import SessionLocal
from ..models.asset_system import AssetDataSource
from ..services.credentials import resolve
from ..services.data_masking import mask_sensitive
from ..services.db_connectors import DB_CONNECTOR_MAP


STAT_TOTAL_KEYS = ("TOTAL_CNT", "TOTAL_COUNT", "TOTAL", "CNT")
STAT_ERROR_KEYS = ("ERROR_CNT", "ERROR_COUNT", "INVALID_CNT", "BAD_CNT")


def _upper_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k).upper(): v for k, v in row.items()}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _extract_stats(rows: list[dict[str, Any]]) -> tuple[int, int] | None:
    if not rows:
        return 0, 0
    first = _upper_row(rows[0])
    total_key = next((k for k in STAT_TOTAL_KEYS if k in first), None)
    error_key = next((k for k in STAT_ERROR_KEYS if k in first), None)
    if total_key and error_key:
        return _as_int(first[total_key]), _as_int(first[error_key])
    if error_key:
        error_cnt = _as_int(first[error_key])
        total_cnt = _as_int(first.get(total_key or "TOTAL_CNT"), error_cnt)
        return total_cnt, error_cnt
    return None


def _build_connector(source: AssetDataSource):
    db_type = (source.db_type or "").lower()
    connector_cls = DB_CONNECTOR_MAP.get(db_type)
    if connector_cls is None:
        raise ValueError(f"unsupported db_type: {source.db_type}")
    user, password = resolve(source.credential_ref)
    database = source.service_name or source.database_name or ""
    return connector_cls(
        host=source.host_masked or "",
        port=source.port or 0,
        database=database,
        user=user or "",
        password=password or "",
        connection_mode=source.connection_mode or "direct",
    )


def execute_quality_sql(
    rule_code: str,
    sql: str,
    source_code: str,
    max_rows: int = 1000,
    sample_limit: int = 20,
    db: Session | None = None,
) -> dict:
    """Execute a read-only quality SQL and return aggregate stats plus masked samples."""
    from ..services.quality_rule_engine import validate_sql_safety

    validation = validate_sql_safety(sql or "")
    if not validation.get("valid"):
        return {
            "rule_code": rule_code,
            "total_cnt": 0,
            "error_cnt": 0,
            "error_rate": 0,
            "sample_data": [],
            "status": "invalid_sql",
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
        }

    owns_session = db is None
    session = db or SessionLocal()
    connector = None
    try:
        source = session.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
        if source is None:
            return {
                "rule_code": rule_code,
                "total_cnt": 0,
                "error_cnt": 0,
                "error_rate": 0,
                "sample_data": [],
                "status": "source_not_found",
                "note": f"source_code not found: {source_code}",
            }

        connector = _build_connector(source)
        rows = connector.execute_readonly(sql, max_rows=max_rows)
        rows = [dict(r) for r in rows]
        stats = _extract_stats(rows)
        if stats is None:
            total_cnt = len(rows)
            error_cnt = len(rows)
        else:
            total_cnt, error_cnt = stats
        error_rate = int(round(error_cnt / total_cnt * 100)) if total_cnt else 0
        samples = [mask_sensitive(row) for row in rows[: max(0, sample_limit)]]
        return {
            "rule_code": rule_code,
            "total_cnt": total_cnt,
            "error_cnt": error_cnt,
            "error_rate": error_rate,
            "sample_data": samples,
            "status": "success",
            "warnings": validation.get("warnings", []),
        }
    except Exception as exc:
        return {
            "rule_code": rule_code,
            "total_cnt": 0,
            "error_cnt": 0,
            "error_rate": 0,
            "sample_data": [],
            "status": "failed",
            "note": str(exc)[:500],
        }
    finally:
        if connector is not None:
            connector.close()
        if owns_session:
            session.close()


def execute_and_collect_findings(
    rule,
    source_code: str,
    max_rows: int = 1000,
    sample_limit: int = 20,
    db: Session | None = None,
) -> list[dict]:
    """Execute SQL and convert non-zero error results to finding dictionaries."""
    result = execute_quality_sql(
        rule.rule_code,
        rule.check_sql or "",
        source_code,
        max_rows,
        sample_limit or 20,
        db=db,
    )
    if result["error_cnt"] == 0:
        return []

    findings = []
    for sample in result.get("sample_data", []) or [{}]:
        findings.append({
            "rule_code": rule.rule_code,
            "target_type": rule.target_type or "table",
            "target_ref": f"{rule.namespace_name or ''}.{rule.target_table or ''}.{rule.target_field or ''}",
            "system_code": rule.system_code,
            "source_code": rule.source_code,
            "namespace_name": rule.namespace_name,
            "table_name": rule.target_table,
            "column_name": rule.target_field,
            "severity": rule.error_level or "minor",
            "status": "open",
            "rectification_status": "open",
            "total_cnt": result["total_cnt"],
            "error_cnt": result["error_cnt"],
            "error_rate": result["error_rate"],
            "sample_data": sample,
            "detail": {
                "sql": rule.check_sql,
                "execution_result": result,
            },
        })
    return findings
