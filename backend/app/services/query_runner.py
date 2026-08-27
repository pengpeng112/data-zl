"""126 P1 + 144 S2: execute active query versions via registered read-only connectors.

144 changes in this module:
- strict bind-parameter contract (params really reach the connector, E_PARAM on mismatch);
- state gate: only active current versions run by default; historical recalc is explicit;
- source policy gate before any connection attempt;
- structural big-table policy via pinned sqlglot AST (regex stays pre-screen only);
- content-addressed result/schema digests + data_as_of provenance;
- sanitized error taxonomy (E_* codes) — raw exception text never enters run rows.
"""
from __future__ import annotations

import hashlib
import logging
import re
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
from ..services.query_parameter_validator import (
    ParameterValidationError,
    build_bind_parameters,
)
from ..services.query_result_digest import compute_result_digest, compute_schema_digest
from ..services.query_source_policy import SourcePolicyError, validate_source_policy
from ..services.sql_ast import (
    SQLParseError,
    UnsupportedDialectError,
    check_big_table_policy,
)

logger = logging.getLogger(__name__)

# parameter names that are always treated as identifiers/sensitive (fail closed)
_SENSITIVE_PARAM_HINTS = (
    "PATIENT_ID", "INP_NO", "OUTPATIENT_NUM", "VISIT_ID", "TEST_NO", "EXAM_NO",
    "ID_CARD", "PHONE", "MOBILE", "NAME", "MRN", "CARD_NO", "PERSON_ID",
)

_DATA_AS_OF_KEYS = ("data_as_of", "DATA_AS_OF", "as_of", "AS_OF")


def _now():
    return datetime.now(timezone.utc)


def ensure_runnable_query_version(
    qv: AssetQueryVersion,
    *,
    recalc: bool = False,
    recalc_reason: str | None = None,
) -> None:
    """State gate (144 §4.2): default execution only for active current versions.

    - blocked/candidate never run (even with recalc);
    - superseded/inactive require explicit recalc=true plus a reason;
    - historical recalc of active-but-superseded lines stays auditable upstream.
    """
    status = getattr(qv, "status", "")
    is_active = bool(getattr(qv, "is_active", False))
    if status == "blocked":
        raise PermissionError("blocked 版本禁止执行")
    if status == "candidate":
        raise PermissionError("candidate 版本禁止执行（须先通过门禁激活）")
    if status == "active" and is_active:
        return
    if recalc:
        if not (recalc_reason or "").strip():
            raise ValueError("历史重算必须提供 recalc_reason（理由/数据窗口）")
        return
    raise PermissionError(
        f"默认仅允许现行 active 版本执行（当前 status={status}, is_active={is_active}）；"
        "历史重算需显式 recalc=true 并记录理由"
    )


def classify_execution_error(exc: Exception) -> dict[str, str]:
    """Map any execution failure to the fixed E_* taxonomy (144 §9).

    The raw message never leaves this process (logged via sanitized logger);
    callers get a code + actionable, secret-free hint only.
    """
    if isinstance(exc, ParameterValidationError):
        code = "E_PARAM"
    elif isinstance(exc, SourcePolicyError):
        code = "E_SOURCE"
    elif isinstance(exc, LookupError):
        code = "E_SOURCE"
    elif isinstance(exc, PermissionError):
        code = "E_SAFETY"
    elif isinstance(exc, ValueError):
        code = "E_PARAM"
    elif isinstance(exc, (SQLParseError, UnsupportedDialectError)):
        code = "E_SEMANTIC"
    else:
        code = "E_INTERNAL"
    hints = {
        "E_PARAM": "参数校验失败：请核对参数 schema 与 SQL bind 名称",
        "E_SOURCE": "数据源不可用或配置不合规：请核对只读连接登记",
        "E_SAFETY": "安全门禁拒绝：请检查 SQL 是否满足只读与大表策略",
        "E_SEMANTIC": "SQL 无法结构化解析（unresolved）：请修正语法后重试",
        "E_INTERNAL": "执行内部错误：请联系管理员以 correlation id 检索受控日志",
    }
    return {"error_code": code, "safe_message": hints[code]}


def _is_sensitive_param(name: str, spec: dict | None) -> bool:
    if spec and spec.get("sensitive"):
        return True
    upper = (name or "").upper()
    return any(hint in upper for hint in _SENSITIVE_PARAM_HINTS)


def safe_parameters_summary(
    parameters: dict | None, parameter_schema: dict | None = None
) -> dict[str, Any]:
    """Masked parameter summary for run rows/audit (144 §4.1/§4.5).

    Sensitive identifiers are stored only as SHA-256; non-sensitive values stay
    readable for reproducibility.
    """
    props = (parameter_schema or {}).get("properties") or {}
    out: dict[str, Any] = {}
    for key, value in (parameters or {}).items():
        spec = props.get(key)
        if _is_sensitive_param(key, spec):
            blob = str(value)
            out[f"{key}_hash"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        else:
            out[key] = value
    return out


def extract_data_as_of(rows: list[dict], columns: list[str]) -> tuple[datetime | None, str]:
    """Derive data_as_of from query output convention; unknown when absent."""
    colmap = {str(c).lower(): c for c in (columns or [])}
    for key in _DATA_AS_OF_KEYS:
        actual = colmap.get(key.lower())
        if actual and rows:
            raw = rows[0].get(actual)
            if isinstance(raw, datetime):
                return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc), "query_output"
            if isinstance(raw, str):
                try:
                    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc), "query_output"
                except ValueError:
                    continue
    return None, "unknown"


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
    recalc: bool = False,
    recalc_reason: str | None = None,
    skip_ast_gate: bool = False,
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

    # 144 S2 state gate (replaces the bare blocked-only check)
    ensure_runnable_query_version(qv, recalc=recalc, recalc_reason=recalc_reason)

    src = source_code or None
    # Prefer definition source if not provided
    if not src:
        from ..models.query_asset import AssetQueryDefinition

        d = db.get(AssetQueryDefinition, qv.query_id)
        src = d.source_code if d else None
    if not src:
        raise ValueError("执行需要 source_code（登记的只读连接）")

    dialect = (qv.dialect or "oracle").lower()
    sql_text = qv.sql_text or ""

    # regex pre-screen stays, but is no longer the final evidence
    safety = validate_sql_safety(sql_text, db_type=dialect)
    if not safety.get("valid"):
        raise PermissionError("SQL 安全门禁失败: " + "; ".join(safety.get("errors") or []))

    # 144 S2: structural big-table policy via pinned AST (fail-closed)
    if not skip_ast_gate:
        ast_check = check_big_table_policy(sql_text, dialect)
        if not ast_check["ok"]:
            raise PermissionError(
                "SQL 大表策略未通过（AST 结构化校验）: " + "; ".join(ast_check["violations"])
            )

    # 144 S2: bind-parameter contract — unknown/missing/unused all blocked here
    bind_params = build_bind_parameters(
        sql_text, qv.parameter_schema or None, parameters or {}, dialect
    )

    correlation_id = str(uuid.uuid4())[:12]
    summary_params = safe_parameters_summary(parameters or {}, qv.parameter_schema or None)
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
        sql_sha256=qv.sql_sha256 or sql_sha256(sql_text),
        triggered_by=triggered_by,
        session_key=session_key,
        correlation_id=correlation_id,
        warnings=safety.get("warnings") or [],
    )
    db.add(run)
    db.flush()

    t0 = time.perf_counter()
    try:
        from ..services.quality_sql_runner import _extract_stats  # type: ignore

        from ..models.asset_system import AssetDataSource
        from ..services.quality_sql_runner import _build_connector
        from ..services.data_masking import mask_sensitive

        source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == src))
        if source is None:
            raise LookupError(f"source_code 不存在: {src}")

        # 144 S2: source policy gate (disabled / non-readonly / misconfigured)
        validate_source_policy(source)

        connector = _build_connector(source)
        try:
            # 144 S2 fix: parameters actually reach the connector now (144 §4.1)
            rows = connector.execute_readonly(
                sql_text, params=bind_params, max_rows=max_rows
            )
            rows = [dict(r) for r in rows]
        finally:
            connector.close()

        # A4：连接器带回 max_rows+1 探针行。truncated 必须是严格大于——
        # 恰好 max_rows 行不算截断；探针行丢弃，样本/统计/digest 只覆盖 max_rows 内。
        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]

        samples = [mask_sensitive(r) for r in rows[: max(0, sample_limit)]]
        stats = _extract_stats(rows)
        row_count = int(stats[0]) if stats else len(rows)
        duration_ms = int((time.perf_counter() - t0) * 1000)

        columns = sorted({k for r in rows for k in r.keys()}) if rows else []
        result_digest = compute_result_digest(columns, rows)
        schema_digest = compute_schema_digest(columns)
        data_as_of, data_as_of_source = extract_data_as_of(rows, columns)

        run.status = "success"
        run.finished_at = _now()
        run.duration_ms = duration_ms
        run.row_count = row_count
        run.truncated = truncated
        run.result_hash = result_hash({"n": row_count, "sample_n": len(samples)})
        run.result_digest = result_digest
        run.schema_digest = schema_digest
        run.data_as_of = data_as_of
        run.data_as_of_source = data_as_of_source
        run.safe_parameters_summary = summary_params

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
                    "result_digest": result_digest,
                    "data_as_of_source": data_as_of_source,
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
            "result_digest": result_digest,
            "schema_digest": schema_digest,
            "data_as_of": data_as_of.isoformat() if data_as_of else None,
            "data_as_of_source": data_as_of_source,
            "correlation_id": correlation_id,
            "sample": samples,
            "warnings": run.warnings,
        }
    except Exception as exc:
        # 144 S2: sanitized failure — raw exception text only goes to the
        # controlled log; run rows/API carry the E_* taxonomy only.
        classified = classify_execution_error(exc)
        logger.error(
            "query run failed code=%s version=%s correlation_id=%s class=%s detail=%s",
            qv.query_code,
            qv.version,
            correlation_id,
            type(exc).__name__,
            str(exc)[:300],
        )
        run.status = "failed"
        run.finished_at = _now()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        run.error_class = classified["error_code"]
        run.error_message = classified["safe_message"]
        db.add(
            GovernAuditLog(
                module="query_asset",
                entity_type="query_run",
                entity_ref=str(run.id),
                action="run_failed",
                after_data={
                    "query_code": qv.query_code,
                    "error_code": classified["error_code"],
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
            "error_class": classified["error_code"],
            "error_message": classified["safe_message"],
            "correlation_id": correlation_id,
        }
