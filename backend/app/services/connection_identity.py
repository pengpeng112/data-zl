"""Connection identity helpers and db_type field validation."""

from __future__ import annotations

from typing import Any

ALLOWED_DB_TYPES = {
    "oracle": {"default_port": 1521, "service_modes": {"service_name", "sid"}},
    "mysql": {"default_port": 3306, "service_modes": {"database"}},
    "sqlserver": {"default_port": 1433, "service_modes": {"database"}},
    "vastbase": {"default_port": 5432, "service_modes": {"database"}},
    "postgresql": {"default_port": 5432, "service_modes": {"database"}},
}

BUSINESS_SOURCE_SYSTEMS = {
    "HIS",
    "HIS_SOURCE",
    "HRP",
    "DATA_CENTER",
    "LIS",
    "PACS",
    "EMR",
    "MOBILE_NURSING",
    "YDHL",
    "SM",
}


def default_port(db_type: str | None) -> int:
    meta = ALLOWED_DB_TYPES.get((db_type or "").lower())
    return int(meta["default_port"]) if meta else 1521


def normalize_host(host: str | None) -> str:
    return (host or "").strip().lower() or "unknown-host"


def build_endpoint_key(db_type: str | None, target_host: str | None, port: int | None) -> str:
    db = (db_type or "").strip().lower() or "unknown"
    host = normalize_host(target_host)
    p = int(port or default_port(db))
    return f"{db}://{host}:{p}"


def build_database_key(
    db_type: str | None,
    target_host: str | None,
    port: int | None,
    service_name: str | None,
    database_name: str | None,
    service_mode: str | None = None,
) -> str:
    endpoint = build_endpoint_key(db_type, target_host, port)
    db = (db_type or "").strip().lower() or "unknown"
    mode = (service_mode or "").strip().lower()
    if db == "oracle":
        mode = mode or ("service_name" if service_name else "sid")
        svc = (service_name or database_name or "").strip().lower()
        return f"{endpoint}/{mode}/{svc}"
    mode = mode or "database"
    dbname = (database_name or service_name or "").strip().lower()
    return f"{endpoint}/{mode}/{dbname}"


def build_connection_identity_key(
    db_type: str | None,
    target_host: str | None,
    port: int | None,
    service_name: str | None,
    database_name: str | None,
    service_mode: str | None = None,
) -> str:
    """Legacy identity key; prefer database_key for physical uniqueness."""
    db = (db_type or "").strip().lower() or "unknown"
    host = normalize_host(target_host)
    p = str(port or default_port(db))
    mode = (service_mode or "").strip().lower()
    if db == "oracle":
        svc = (service_name or database_name or "").strip().lower()
        mode = mode or ("service_name" if service_name else "sid")
        return f"{db}:{host}:{p}:{mode}:{svc}"
    dbname = (database_name or service_name or "").strip().lower()
    return f"{db}:{host}:{p}:database:{dbname}"


# Known ODS alias sources that share one physical Oracle instance.
ODS_ALIAS_SOURCES = {
    "ods_lis": {"canonical": "ods_8_216", "labels": ["LIS", "检验"]},
    "ods_pacs": {"canonical": "ods_8_216", "labels": ["PACS", "影像"]},
    "ods_emr": {"canonical": "ods_8_216", "labels": ["EMR", "病历"]},
    "ods_ydhl": {"canonical": "ods_8_216", "labels": ["YDHL", "移动护理"]},
    "ods_sm": {"canonical": "ods_8_216", "labels": ["SM", "手麻"]},
}


def apply_keys_to_payload(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "endpoint_key": build_endpoint_key(
            payload.get("db_type"), payload.get("target_host"), payload.get("port")
        ),
        "database_key": build_database_key(
            payload.get("db_type"),
            payload.get("target_host"),
            payload.get("port"),
            payload.get("service_name"),
            payload.get("database_name"),
            payload.get("service_mode"),
        ),
    }


def validate_connection_fields(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    db_type = (payload.get("db_type") or "").strip().lower()
    if db_type not in ALLOWED_DB_TYPES:
        errors.append("db_type must be one of oracle/mysql/sqlserver/vastbase/postgresql")
        return errors

    host = (payload.get("target_host") or "").strip()
    if not host:
        errors.append("target_host is required")

    port = payload.get("port")
    if port is None:
        errors.append("port is required")
    else:
        try:
            port_i = int(port)
            if port_i < 1 or port_i > 65535:
                errors.append("port must be between 1 and 65535")
        except (TypeError, ValueError):
            errors.append("port must be an integer")

    service_mode = (payload.get("service_mode") or "").strip().lower()
    service_name = (payload.get("service_name") or "").strip()
    database_name = (payload.get("database_name") or "").strip()
    allowed_modes = ALLOWED_DB_TYPES[db_type]["service_modes"]

    if db_type == "oracle":
        if not service_mode:
            service_mode = "service_name" if service_name else "sid"
        if service_mode not in allowed_modes:
            errors.append("oracle service_mode must be service_name or sid")
        if service_mode == "service_name" and not service_name:
            errors.append("oracle service_name is required when service_mode=service_name")
        if service_mode == "sid" and not (service_name or database_name):
            errors.append("oracle SID is required when service_mode=sid")
    else:
        if service_mode and service_mode not in allowed_modes:
            errors.append(f"{db_type} service_mode must be database")
        if not database_name:
            errors.append(f"{db_type} requires database_name")

    write_policy = (payload.get("write_policy") or "readonly").strip().lower()
    system_code = (payload.get("system_code") or "").strip().upper()
    if write_policy not in {"readonly", "platform_controlled"}:
        errors.append("write_policy must be readonly or platform_controlled")
    if write_policy == "platform_controlled" and system_code not in {"ASSET_PLATFORM", "PLATFORM"}:
        errors.append("write_policy=platform_controlled is only allowed for ASSET_PLATFORM")
    if system_code in BUSINESS_SOURCE_SYSTEMS and write_policy != "readonly":
        errors.append("business source connections must use write_policy=readonly")

    return errors


def host_masked_from_target(target_host: str | None) -> str | None:
    if not target_host:
        return None
    parts = target_host.strip().split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.*.*"
    if len(target_host) <= 4:
        return target_host[0] + "***"
    return target_host[:2] + "***" + target_host[-1]
