"""126 P1: execute active/validated query versions via registered read-only connectors."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.governance_base import GovernAuditLog
from ..models.query_asset import AssetQueryResult, AssetQueryRun, AssetQueryVersion
from ..services.query_fingerprint import parameters_hash, result_hash, sql_sha256
from ..services.quality_rule_engine import validate_sql_safety
from ..services.quality_sql_runner import execute_quality_sql


def _now():
    return datetime.now(timezone.utc)


def run_query_version(
    db: Session,
    *,
    query_version_id: int | None = None,
    query_code: str | None = None,
    version: int | None = None,
    source_code: str | None = None,
    parameters: dict | None = None,
    result_storage: str = "none",
    max_rows: int = 1000,
    sample_limit: int = 20,
    triggered_by: str | None = None,
    session_key: str | None = None,
) -> dict[str, Any]:
    """Run a fixed query version. Parameters do not create a new version."""
    result_storage = (result_storage or "none").lower()
    if result_storage not in {"none", "summary", "file_ref"}:
        raise ValueError("result_storage 必须是 none|summary|file_ref")

    qv: AssetQueryVersion | None = None
    if query_version_id:
        qv = db.get(AssetQueryVersion, query_version_id)
    elif query_code:
        stmt = select(AssetQueryVersion).where(AssetQueryVersion.query_code == query_code)
        if version is not None:
            stmt = stmt.where(AssetQueryVersion.version == version)
        else:
            stmt = stmt.where(AssetQueryVersion.is_active.is_(True))
        qv = db.scalar(stmt.order_by(AssetQueryVersion.version.desc()))
    if not qv:
        raise LookupError("查询版本不存在")
    if qv.status == "blocked":
        raise PermissionError("blocked 版本禁止执行")

    src = source_code or None
    # Prefer definition source if not provided
    if not src:
        from ..models.query_asset import AssetQueryDefinition

        d = db.get(AssetQueryDefinition, qv.query_id)
        src = d.source_code if d else None
    if not src:
        raise ValueError("执行需要 source_code（登记的只读连接）")

    safety = validate_sql_safety(qv.sql_text or "", db_type=(qv.dialect or "oracle").lower())
    if not safety.get("valid"):
        raise PermissionError("SQL 安全门禁失败: " + "; ".join(safety.get("errors") or []))

    correlation_id = str(uuid.uuid4())[:12]
    run = AssetQueryRun(
        query_version_id=qv.id,
        query_code=qv.query_code,
        version=qv.version,
        source_code=src,
        dialect=qv.dialect,
        parameters=parameters or {},
        parameters_hash=parameters_hash(parameters),
        status="running",
        started_at=_now(),
        result_storage=result_storage,
        sql_sha256=qv.sql_sha256 or sql_sha256(qv.sql_text),
        triggered_by=triggered_by,
        session_key=session_key,
        correlation_id=correlation_id,
        warnings=safety.get("warnings") or [],
    )
    db.add(run)
    db.flush()

    t0 = time.perf_counter()
    try:
        # Reuse quality SQL runner (readonly + masking + stats extract best-effort)
        # For general SELECT we accept rows; if no TOTAL_CNT treat as row listing.
        from ..services.quality_sql_runner import _extract_stats  # type: ignore

        # Direct connector path via execute_quality_sql may mark rule_error for multi-row —
        # use lower-level connector when stats contract not met.
        from ..models.asset_system import AssetDataSource
        from ..services.quality_sql_runner import _build_connector
        from ..services.data_masking import mask_sensitive

        source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == src))
        if source is None:
            raise LookupError(f"source_code 不存在: {src}")

        connector = _build_connector(source)
        try:
            rows = connector.execute_readonly(qv.sql_text, max_rows=max_rows)
            rows = [dict(r) for r in rows]
        finally:
            connector.close()

        samples = [mask_sensitive(r) for r in rows[: max(0, sample_limit)]]
        stats = _extract_stats(rows)
        row_count = int(stats[0]) if stats else len(rows)
        truncated = len(rows) >= max_rows
        duration_ms = int((time.perf_counter() - t0) * 1000)

        run.status = "success"
        run.finished_at = _now()
        run.duration_ms = duration_ms
        run.row_count = row_count
        run.truncated = truncated
        run.result_hash = result_hash({"n": row_count, "sample_n": len(samples)})

        result_row = None
        if result_storage == "summary":
            summary = {
                "row_count": row_count,
                "truncated": truncated,
                "sample": samples[: min(5, len(samples))],
                "note": "default summary only; no patient detail store",
            }
            result_row = AssetQueryResult(
                run_id=run.id,
                storage="summary",
                summary_json=summary,
                sensitivity="aggregate",
                truncated=truncated,
            )
            db.add(result_row)
        elif result_storage == "file_ref":
            # P1: record intent only; no large file store
            result_row = AssetQueryResult(
                run_id=run.id,
                storage="file_ref",
                file_ref=None,
                sensitivity="aggregate",
                truncated=truncated,
            )
            db.add(result_row)

        db.add(
            GovernAuditLog(
                module="query_asset",
                entity_type="query_run",
                entity_ref=str(run.id),
                action="run",
                after_data={
                    "query_code": qv.query_code,
                    "version": qv.version,
                    "status": "success",
                    "row_count": row_count,
                    "result_storage": result_storage,
                    "correlation_id": correlation_id,
                },
                operator=triggered_by,
            )
        )
        db.flush()
        return {
            "run_id": run.id,
            "query_code": qv.query_code,
            "version": qv.version,
            "status": "success",
            "row_count": row_count,
            "truncated": truncated,
            "duration_ms": duration_ms,
            "result_storage": result_storage,
            "result_hash": run.result_hash,
            "correlation_id": correlation_id,
            "sample": samples,
            "warnings": run.warnings,
        }
    except Exception as exc:
        run.status = "failed"
        run.finished_at = _now()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        run.error_class = type(exc).__name__
        run.error_message = str(exc)[:500]
        db.add(
            GovernAuditLog(
                module="query_asset",
                entity_type="query_run",
                entity_ref=str(run.id),
                action="run_failed",
                after_data={
                    "query_code": qv.query_code,
                    "error_class": run.error_class,
                    "correlation_id": correlation_id,
                },
                operator=triggered_by,
            )
        )
        db.flush()
        return {
            "run_id": run.id,
            "query_code": qv.query_code,
            "version": qv.version,
            "status": "failed",
            "error_class": run.error_class,
            "error_message": run.error_message,
            "correlation_id": correlation_id,
        }
