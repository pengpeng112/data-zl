"""Controlled ops execution service.

Phase 1 intentionally supports platform DB writes only. Business source systems
remain read-only and are not connected from this executor.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.governance_base import GovernAuditLog
from ..models.ops_tool import OpsToolRun, OpsToolTemplate
from .data_masking import mask_sensitive
from .ops_sql_safety import validate_writable_sql


class OpsExecutionError(ValueError):
    pass


def _params(run: OpsToolRun) -> dict[str, Any]:
    return dict(run.input_params_masked or {})


def _write_config(tool: OpsToolTemplate) -> dict[str, Any]:
    input_schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    config = input_schema.get("__ops_write_config__") or {}
    return dict(config) if isinstance(config, dict) else {}


def _allowed_tables(tool: OpsToolTemplate) -> list[str]:
    return list(_write_config(tool).get("allowed_tables") or [])


def _allowed_operations(tool: OpsToolTemplate) -> list[str]:
    return list(_write_config(tool).get("allowed_operations") or [])


def _max_affected_rows(tool: OpsToolTemplate) -> int:
    value = _write_config(tool).get("max_affected_rows", 100)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise OpsExecutionError("max_affected_rows must be an integer")
    if parsed < 1:
        raise OpsExecutionError("max_affected_rows must be greater than 0")
    return min(parsed, 100)


def _write_credential_ref(tool: OpsToolTemplate) -> str:
    return str(_write_config(tool).get("write_credential_ref") or "").strip()


def _parse_credential_payload(payload: str, source: str) -> tuple[str, str]:
    if ":" not in payload:
        raise OpsExecutionError(f"write credential {source} must use <user>:<password> format")
    user, password = payload.split(":", 1)
    if not user.strip() or not password:
        raise OpsExecutionError(f"write credential {source} must include user and password")
    return user.strip(), password


def _resolve_write_credential(tool: OpsToolTemplate) -> tuple[str, str]:
    ref = _write_credential_ref(tool)
    if not ref:
        raise OpsExecutionError("write_credential_ref is required for whitelist_dml formal execution")
    if ref.startswith("env:"):
        env_name = ref[4:].strip()
        if not env_name:
            raise OpsExecutionError("write credential env name is required")
        payload = os.environ.get(env_name)
        if not payload:
            raise OpsExecutionError(f"write credential env is missing: {env_name}")
        return _parse_credential_payload(payload, ref)
    if ref.startswith("file://"):
        file_path = Path(ref[7:])
        if not file_path.exists() or not file_path.is_file():
            raise OpsExecutionError(f"write credential file is missing: {file_path}")
        payload = file_path.read_text(encoding="utf-8").strip()
        return _parse_credential_payload(payload, "file://...")
    raise OpsExecutionError("write_credential_ref must start with env: or file://")


def sql_template_hash(sql: str) -> str:
    normalized = re.sub(r"\s+", " ", (sql or "").strip()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# backward-compatible alias
_sql_template_hash = sql_template_hash


def _ensure_platform_source(tool: OpsToolTemplate) -> None:
    if tool.source_code not in (None, "", "asset", "ASSET_PLATFORM"):
        raise OpsExecutionError("whitelist_dml only supports platform asset source in phase 1")


def _dry_run_preview(db: Session, tool: OpsToolTemplate, params: dict[str, Any]) -> dict[str, Any]:
    dry_run_sql = _write_config(tool).get("dry_run_sql")
    if not dry_run_sql:
        raise OpsExecutionError("dry_run_sql is required for whitelist_dml")
    result = db.execute(text(dry_run_sql), params)
    scalar = result.scalar()
    estimated = int(scalar or 0)
    max_rows = _max_affected_rows(tool)
    return {
        "preview_available": True,
        "estimated_count": estimated,
        "max_affected_rows": max_rows,
        "would_execute": estimated <= max_rows,
        "dry_run_sql_hash": _sql_template_hash(dry_run_sql),
    }


def execute_whitelist_dml(
    tool: OpsToolTemplate,
    run: OpsToolRun,
    db: Session,
    *,
    dry_run: bool = False,
    executed_by: str = "system",
) -> dict[str, Any]:
    if tool.execution_mode != "whitelist_dml":
        raise OpsExecutionError("tool execution_mode is not whitelist_dml")
    _ensure_platform_source(tool)

    params = _params(run)
    sql = tool.sql_or_endpoint_ref or ""
    sql_hash = _sql_template_hash(sql)
    scan = validate_writable_sql(
        sql,
        allowed_tables=_allowed_tables(tool),
        allowed_ops=_allowed_operations(tool),
        params=params,
    )
    if scan.get("parsed_summary"):
        scan["parsed_summary"]["sql_template_hash"] = sql_hash

    if not scan["valid"]:
        if dry_run:
            return {
                "dry_run": True,
                "preview_available": False,
                "estimated_count": None,
                "max_affected_rows": _max_affected_rows(tool),
                "would_execute": False,
                "risk_scan": scan,
                "sql_template_hash": sql_hash,
            }
        run.risk_scan = scan
        raise OpsExecutionError("; ".join(scan["errors"]))

    if dry_run:
        preview = _dry_run_preview(db, tool, params)
        return {"dry_run": True, "risk_scan": scan, "sql_template_hash": sql_hash, **preview}

    write_user, _write_password = _resolve_write_credential(tool)
    preview = _dry_run_preview(db, tool, params)
    run.risk_scan = scan
    if preview["estimated_count"] > preview["max_affected_rows"]:
        raise OpsExecutionError(
            f"estimated_count {preview['estimated_count']} exceeds max_affected_rows {preview['max_affected_rows']}"
        )

    result = db.execute(text(sql), params)
    affected = int(result.rowcount or 0)
    if affected > preview["max_affected_rows"]:
        raise OpsExecutionError(
            f"affected_count {affected} exceeds max_affected_rows {preview['max_affected_rows']}"
        )
    run.affected_count = affected

    db.add(GovernAuditLog(
        module="ops",
        entity_type="ops_tool_run",
        entity_ref=str(run.id),
        action="execute_write",
        operator=executed_by,
        before_data={
            "tool_code": tool.tool_code,
            "target": scan.get("parsed_summary", {}).get("target_table") if scan.get("parsed_summary") else None,
            "dry_run": False,
            "sql_template_hash": sql_hash,
            "dry_run_sql_hash": preview.get("dry_run_sql_hash"),
            "estimated_count": preview["estimated_count"],
            "max_affected_rows": preview["max_affected_rows"],
            "write_user": write_user,
        },
        after_data={
            "affected_count": affected,
            "affected_rows": affected,
            "params_masked": mask_sensitive(params),
            "params_json_masked": mask_sensitive(params),
            "risk_scan": scan,
            "rollback_note_cn": tool.rollback_note_cn,
        },
    ))

    return {
        "result": "whitelist_dml executed",
        "dry_run": False,
        "affected_count": affected,
        "affected_rows": affected,
        "estimated_count": preview["estimated_count"],
        "max_affected_rows": preview["max_affected_rows"],
        "risk_scan": scan,
        "sql_template_hash": sql_hash,
        "dry_run_sql_hash": preview.get("dry_run_sql_hash"),
        "write_user": write_user,
        "rollback_note_cn": tool.rollback_note_cn,
    }