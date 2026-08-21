"""Harvest compile-valid HIS_SOURCE Oracle views without source writes.

The script resolves the already registered readonly HIS_SOURCE connection from
the platform database.  It never accepts a password on the command line and it
only executes bounded data-dictionary SELECT statements through OracleConnector.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_SOURCE_CODE = "his_source_10_10_10_15"
OWNER_RE = re.compile(r"^[A-Z][A-Z0-9_$#]*$")
MAX_VIEW_DEFINITION_LENGTH = 1_000_000
SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd|token|access_token)\s*[:=]\s*(['\"]?)[^\s,'\")]+"),
    re.compile(r"(?i)(://[^:/@\s]+:)[^@/\s]+(@)"),
    re.compile(r"(?i)([?&](?:password|pwd|token|access_token)=)[^&'\"\s]+"),
)
SQL_STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")
SENSITIVE_NUMERIC_LITERAL_RE = re.compile(
    r"(?i)(\b(?:patient_id|visit_id|inp_no|outpatient_num|outpatient_no|exam_no|test_no|"
    r"mrn|id_no|id_card|identity_no|card_no)\b\s*(?:=|<>|!=|IN\s*\()\s*)\d{4,}"
)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "read"):
        value = value.read()
    return str(value)


def _mask_secrets(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(://"):
            text = pattern.sub(r"\1***\2", text)
        elif "[?&]" in pattern.pattern:
            text = pattern.sub(r"\1***", text)
        else:
            text = pattern.sub(lambda m: f"{m.group(1)}=***", text)
    return text


def sanitize_text(value: Any) -> str | None:
    """Sanitize and bound diagnostics; view SQL uses the dedicated sanitizer."""
    text = _as_text(value)
    return None if text is None else _mask_secrets(text)[:1000]


def sanitize_view_definition(value: Any) -> str | None:
    """Preserve relation structure while removing literals and bounding CLOBs."""
    text = _as_text(value)
    if text is None:
        return None
    text = _mask_secrets(text)
    text = SQL_STRING_LITERAL_RE.sub("'***'", text)
    text = SENSITIVE_NUMERIC_LITERAL_RE.sub(r"\g<1>0", text)
    return text[:MAX_VIEW_DEFINITION_LENGTH]


def normalize(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return value.hex()
    if hasattr(value, "read"):
        return _as_text(value)
    return value


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{str(key).lower(): normalize(value) for key, value in row.items()} for row in rows]


def validate_owners(values: list[str]) -> list[str]:
    owners = sorted({value.strip().upper() for value in values if value.strip()})
    invalid = [owner for owner in owners if not OWNER_RE.fullmatch(owner)]
    if invalid:
        raise ValueError(f"invalid owner identifiers: {', '.join(invalid)}")
    if not owners:
        raise ValueError("no HIS owners selected")
    return owners


def quoted(values: list[str]) -> str:
    return ",".join(f"'{value}'" for value in values)


def _registered_owners(db: Any, source_code: str) -> list[str]:
    from sqlalchemy import select

    from app.models.asset import AssetTable

    rows = db.scalars(
        select(AssetTable.schema_name)
        .where(AssetTable.source_code == source_code)
        .distinct()
        .order_by(AssetTable.schema_name)
    ).all()
    return validate_owners([value for value in rows if value])


def _connector(db: Any, source_code: str) -> tuple[Any, Any]:
    from sqlalchemy import select

    from app.models.asset_system import AssetDataSource
    from app.services.credentials import resolve
    from app.services.db_connectors import DB_CONNECTOR_MAP

    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise RuntimeError(f"platform source not found: {source_code}")
    policy = (source.write_policy or "").lower()
    has_separate_write_credential = bool(
        source.credential_ref
        and source.write_credential_ref
        and source.credential_ref != source.write_credential_ref
    )
    if policy != "readonly" and not (
        policy == "medical_dict_push" and has_separate_write_credential
    ):
        raise RuntimeError("HIS source does not have a dedicated readonly credential")
    user, password = resolve(source.credential_ref)
    if not user or not password:
        raise RuntimeError("HIS readonly credential is not configured")
    connector_cls = DB_CONNECTOR_MAP.get((source.db_type or "").lower())
    if connector_cls is None:
        raise RuntimeError(f"unsupported source type: {source.db_type}")
    connector = connector_cls(
        host=source.target_host or source.host_masked,
        port=source.port or 1521,
        database=source.service_name or source.database_name,
        user=user,
        password=password,
        connection_mode=source.connection_mode or "direct",
        **(source.connection_options or {}),
    )
    return connector, source


def collect(source_code: str, owners_override: list[str] | None = None) -> dict[str, Any]:
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        registered_owners = _registered_owners(db, source_code)
        owners = validate_owners(owners_override) if owners_override else registered_owners
        unregistered = sorted(set(owners) - set(registered_owners))
        if unregistered:
            raise RuntimeError(f"owner override is outside registered HIS assets: {', '.join(unregistered)}")
        connector, source = _connector(db, source_code)
        owner_sql = quoted(owners)
        try:
            objects = normalize_rows(
                connector.execute_readonly(
                    "SELECT owner,object_name view_name,status,created,last_ddl_time "
                    "FROM all_objects WHERE object_type='VIEW' "
                    f"AND owner IN ({owner_sql}) ORDER BY owner,object_name",
                    max_rows=10000,
                )
            )
            columns = normalize_rows(
                connector.execute_readonly(
                    "SELECT owner,table_name view_name,column_id,column_name,data_type,"
                    "data_length,data_precision,data_scale,nullable "
                    "FROM all_tab_columns "
                    f"WHERE owner IN ({owner_sql}) AND table_name IN "
                    "(SELECT object_name FROM all_objects WHERE object_type='VIEW' AND status='VALID' "
                    f"AND owner IN ({owner_sql})) ORDER BY owner,table_name,column_id",
                    max_rows=10000,
                )
            )
            dependencies = normalize_rows(
                connector.execute_readonly(
                    "SELECT owner,name view_name,referenced_owner,referenced_name,"
                    "referenced_type,dependency_type FROM all_dependencies "
                    f"WHERE owner IN ({owner_sql}) AND type='VIEW' "
                    "AND referenced_type IN ('TABLE','VIEW','SYNONYM') "
                    "ORDER BY owner,name,referenced_owner,referenced_name",
                    max_rows=10000,
                )
            )
            errors = normalize_rows(
                connector.execute_readonly(
                    "SELECT owner,name view_name,sequence,line,position,text "
                    f"FROM all_errors WHERE owner IN ({owner_sql}) AND type='VIEW' "
                    "ORDER BY owner,name,sequence",
                    max_rows=10000,
                )
            )
            for row in errors:
                row["text"] = sanitize_text(row.get("text"))
            definitions = normalize_rows(
                connector.execute_readonly(
                    "SELECT owner,view_name,text FROM all_views "
                    f"WHERE owner IN ({owner_sql}) ORDER BY owner,view_name",
                    max_rows=10000,
                )
            )
        finally:
            connector.close()

    status_by_view = {
        (row["owner"], row["view_name"]): row.get("status") for row in objects
    }
    definition_rows = []
    sanitization_count = 0
    truncated_count = 0
    for row in definitions:
        raw = row.get("text")
        raw_text = _as_text(raw)
        clean = sanitize_view_definition(raw)
        if clean != raw_text:
            sanitization_count += 1
        definition_truncated = bool(raw_text is not None and len(raw_text) > MAX_VIEW_DEFINITION_LENGTH)
        if definition_truncated:
            truncated_count += 1
        definition_rows.append(
            {
                "owner": row.get("owner"),
                "view_name": row.get("view_name"),
                "status": status_by_view.get((row.get("owner"), row.get("view_name"))),
                "text": clean,
                "definition_truncated": definition_truncated,
                "source_sql_sha256": hashlib.sha256((clean or "").encode("utf-8")).hexdigest(),
            }
        )

    valid_count = sum(1 for row in objects if row.get("status") == "VALID")
    invalid_count = sum(1 for row in objects if row.get("status") != "VALID")
    payload = {
        "source": {
            "system_code": source.system_code,
            "source_code": source_code,
            "db_type": source.db_type,
            "database_name": source.service_name or source.database_name,
            "write_policy": source.write_policy,
            "readonly_credential_separate_from_write": bool(
                source.credential_ref
                and source.write_credential_ref
                and source.credential_ref != source.write_credential_ref
            ),
            "owners": owners,
        },
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "objects": objects,
        "columns": columns,
        "dependencies": dependencies,
        "errors": errors,
        "view_definitions": definition_rows,
        "runtime_probes": [],
        "summary": {
            "owners": len(owners),
            "views": len(objects),
            "valid_views": valid_count,
            "invalid_views": invalid_count,
            "columns": len(columns),
            "dependencies": len(dependencies),
            "compile_errors": len(errors),
            "definitions": len(definition_rows),
            "sanitized_definitions": sanitization_count,
            "truncated_definitions": truncated_count,
            "runtime_probe_policy": "skipped_by_default_to_avoid_unbounded_view_execution",
            "source_writes": 0,
        },
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-code", required=True, help=f"Registered source code (expected {DEFAULT_SOURCE_CODE})")
    parser.add_argument("--owners", default="", help="Comma-separated Owner allowlist; default uses platform assets")
    args = parser.parse_args()
    owners = [value for value in args.owners.split(",") if value.strip()] or None
    payload = collect(args.source_code, owners)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=normalize), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
