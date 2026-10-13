"""215 E11 自 systems.py 拆出：系统/数据源共享序列化、连接元数据校验与审计写。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ....models.asset_system import AssetDataSource
from ....models.governance_base import GovernAuditLog
from ....services import credential_store
from ....services.connection_identity import (
    ODS_ALIAS_SOURCES,
    build_connection_identity_key,
    build_database_key,
    build_endpoint_key,
    default_port,
    host_masked_from_target,
    validate_connection_fields,
)


def _source_public(r: AssetDataSource) -> dict:
    kind = getattr(r, "source_kind", None) or "physical_connection"
    return {
        "id": r.id,
        "system_code": r.system_code,
        "source_code": r.source_code,
        "source_name_cn": r.source_name_cn,
        "db_type": r.db_type,
        "db_type_label": {
            "oracle": "Oracle",
            "mysql": "MySQL",
            "sqlserver": "SQL Server",
            "vastbase": "海量数据库（Vastbase）",
            "postgresql": "PostgreSQL",
        }.get((r.db_type or "").lower(), r.db_type),
        "environment": r.environment,
        "target_host": r.target_host,
        "host_masked": r.host_masked,
        "port": r.port,
        "service_mode": r.service_mode,
        "service_name": r.service_name,
        "database_name": r.database_name,
        "default_schema": r.default_schema,
        "display_order": r.display_order or 0,
        "connection_mode": r.connection_mode,
        "collect_mode": r.collect_mode,
        "write_policy": r.write_policy or "readonly",
        "connection_options": r.connection_options,
        "enabled": r.enabled,
        "last_check_status": r.last_check_status,
        "last_check_at": r.last_check_at.isoformat() if r.last_check_at else None,
        "credential_configured": bool(r.credential_ref) or credential_store.status(r.source_code) == "configured",
        "credential_status": r.credential_status,
        "credential_username_masked": r.credential_username_masked,
        "credential_updated_at": r.credential_updated_at.isoformat() if r.credential_updated_at else None,
        "credential_updated_by": r.credential_updated_by,
        "write_credential_configured": bool(r.write_credential_ref)
        or credential_store.status(r.source_code, writable=True) == "configured",
        "write_credential_status": (
            "configured"
            if (bool(r.write_credential_ref) or credential_store.status(r.source_code, writable=True) == "configured")
            else "unconfigured"
        ),
        "write_username_masked": (
            (r.connection_options or {}).get("write_username_masked")
            if isinstance(r.connection_options, dict)
            else None
        ),
        "connection_identity_key": r.connection_identity_key,
        "endpoint_key": getattr(r, "endpoint_key", None),
        "database_key": getattr(r, "database_key", None),
        "source_kind": kind,
        "canonical_source_code": getattr(r, "canonical_source_code", None),
        "business_labels": getattr(r, "business_labels", None) or [],
        "metadata_origin": getattr(r, "metadata_origin", None),
        "last_test_status": getattr(r, "last_test_status", None) or r.last_check_status,
        "last_test_at": (
            r.last_test_at.isoformat()
            if getattr(r, "last_test_at", None)
            else (r.last_check_at.isoformat() if r.last_check_at else None)
        ),
        "last_test_latency_ms": getattr(r, "last_test_latency_ms", None),
        "last_test_error_code": getattr(r, "last_test_error_code", None),
        "last_test_error_masked": getattr(r, "last_test_error_masked", None),
        "last_collect_status": getattr(r, "last_collect_status", None),
        "last_collect_at": r.last_collect_at.isoformat() if getattr(r, "last_collect_at", None) else None,
        "is_writeable": (r.write_policy or "readonly") in {"platform_controlled", "medical_dict_push"},
        "supports_medical_dict_push": (r.write_policy or "readonly") == "medical_dict_push"
        and (
            bool(r.write_credential_ref)
            or credential_store.status(r.source_code, writable=True) == "configured"
        ),
        "is_legacy_alias": kind == "legacy_alias",
        # never expose credential_ref or password
    }

def _apply_connection_meta(ds: AssetDataSource, payload: dict[str, Any], system_code: str) -> list[str]:
    data = {
        "db_type": payload.get("db_type") or ds.db_type,
        "target_host": payload.get("target_host") if payload.get("target_host") is not None else ds.target_host,
        "port": payload.get("port") if payload.get("port") is not None else ds.port,
        "service_mode": payload.get("service_mode") if payload.get("service_mode") is not None else ds.service_mode,
        "service_name": payload.get("service_name") if payload.get("service_name") is not None else ds.service_name,
        "database_name": payload.get("database_name") if payload.get("database_name") is not None else ds.database_name,
        "write_policy": payload.get("write_policy") or ds.write_policy or "readonly",
        "system_code": system_code,
    }
    if data["port"] is None and data["db_type"]:
        data["port"] = default_port(data["db_type"])
    errors = validate_connection_fields(data)
    if errors:
        return errors
    ds.db_type = (data["db_type"] or "").lower()
    ds.target_host = data["target_host"]
    ds.port = int(data["port"])
    ds.service_mode = data.get("service_mode")
    ds.service_name = data.get("service_name")
    ds.database_name = data.get("database_name")
    ds.write_policy = data["write_policy"]
    ds.host_masked = host_masked_from_target(ds.target_host) or ds.host_masked
    ds.connection_identity_key = build_connection_identity_key(
        ds.db_type, ds.target_host, ds.port, ds.service_name, ds.database_name, ds.service_mode
    )
    ds.endpoint_key = build_endpoint_key(ds.db_type, ds.target_host, ds.port)
    ds.database_key = build_database_key(
        ds.db_type, ds.target_host, ds.port, ds.service_name, ds.database_name, ds.service_mode
    )
    alias = ODS_ALIAS_SOURCES.get(ds.source_code)
    if alias:
        ds.source_kind = "legacy_alias"
        ds.canonical_source_code = alias["canonical"]
        ds.business_labels = alias["labels"]
    elif not getattr(ds, "source_kind", None):
        ds.source_kind = "physical_connection"
    return []

def _audit(db: Session, *, action: str, operator: str, entity_ref: str, before=None, after=None, reason=None):
    db.add(GovernAuditLog(
        module="systems",
        entity_type="asset_data_source",
        entity_ref=entity_ref,
        action=action,
        operator=operator,
        before_data=before,
        after_data=after,
        reason=reason,
    ))
