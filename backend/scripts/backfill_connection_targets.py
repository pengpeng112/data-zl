"""Backfill target_host/endpoint_key/database_key for data sources.

Default dry-run. Does not invent passwords. Known mappings from plan 75/76.

  python scripts/backfill_connection_targets.py --dry-run
  python scripts/backfill_connection_targets.py --apply --confirmation BACKFILL-CONNECTION-TARGETS
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset_system import AssetDataSource
from app.services.connection_identity import (
    ODS_ALIAS_SOURCES,
    build_connection_identity_key,
    build_database_key,
    build_endpoint_key,
    host_masked_from_target,
)

CONFIRMATION = "BACKFILL-CONNECTION-TARGETS"

# Explicit production mappings (plan 76). Only fill when target_host empty.
KNOWN_TARGETS = {
    "ods_8_216": {"target_host": "10.10.8.216", "port": 1521, "service_name": "orcl", "service_mode": "service_name", "db_type": "oracle"},
    "ods_lis": {"target_host": "10.10.8.216", "port": 1521, "service_name": "orcl", "service_mode": "service_name", "db_type": "oracle"},
    "ods_pacs": {"target_host": "10.10.8.216", "port": 1521, "service_name": "orcl", "service_mode": "service_name", "db_type": "oracle"},
    "ods_emr": {"target_host": "10.10.8.216", "port": 1521, "service_name": "orcl", "service_mode": "service_name", "db_type": "oracle"},
    "ods_ydhl": {"target_host": "10.10.8.216", "port": 1521, "service_name": "orcl", "service_mode": "service_name", "db_type": "oracle"},
    "ods_sm": {"target_host": "10.10.8.216", "port": 1521, "service_name": "orcl", "service_mode": "service_name", "db_type": "oracle"},
    "his_source_10_10_10_15": {"target_host": "10.10.10.15", "port": 1521, "service_name": "his", "service_mode": "service_name", "db_type": "oracle"},
    "hrp_10_10_10_23": {"target_host": "10.10.10.23", "port": 1521, "service_name": "hrpdb", "service_mode": "service_name", "db_type": "oracle"},
}


def row_connection_identity_key(source_code: str, source_kind: str, physical_identity: str) -> str:
    """Keep aliases unique while preserving their shared physical database key."""
    return f"alias:{source_code}:{physical_identity}" if source_kind == "legacy_alias" else physical_identity


def build_plan(db) -> dict:
    rows = db.scalars(select(AssetDataSource).order_by(AssetDataSource.id)).all()
    changes = []
    for r in rows:
        known = KNOWN_TARGETS.get(r.source_code, {})
        new_host = r.target_host or known.get("target_host")
        # try parse host_masked only if it looks like full IP (legacy stored real host)
        if not new_host and r.host_masked and r.host_masked.count(".") == 3 and "*" not in r.host_masked:
            new_host = r.host_masked
        new_port = r.port or known.get("port")
        new_service = r.service_name or known.get("service_name")
        new_db = r.database_name
        new_mode = r.service_mode or known.get("service_mode")
        new_type = (r.db_type or known.get("db_type") or "oracle").lower()
        endpoint = build_endpoint_key(new_type, new_host, new_port) if new_host else None
        dbkey = (
            build_database_key(new_type, new_host, new_port, new_service, new_db, new_mode)
            if new_host
            else None
        )
        alias = ODS_ALIAS_SOURCES.get(r.source_code)
        item = {
            "source_code": r.source_code,
            "old_target_host": r.target_host,
            "new_target_host": new_host,
            "old_port": r.port,
            "new_port": new_port,
            "service_name": new_service,
            "endpoint_key": endpoint,
            "database_key": dbkey,
            "source_kind": "legacy_alias" if alias else (r.source_kind or "physical_connection"),
            "canonical_source_code": alias["canonical"] if alias else r.canonical_source_code,
            "business_labels": alias["labels"] if alias else r.business_labels,
            "will_change": bool(
                (new_host and new_host != r.target_host)
                or (endpoint and endpoint != r.endpoint_key)
                or (dbkey and dbkey != r.database_key)
                or (alias and r.source_kind != "legacy_alias")
            ),
            "missing_target": not bool(new_host),
        }
        changes.append(item)

    # detect duplicate database_keys among physical connections
    by_key: dict[str, list[str]] = {}
    for c in changes:
        if c["database_key"] and c["source_kind"] != "legacy_alias":
            by_key.setdefault(c["database_key"], []).append(c["source_code"])
    duplicates = {k: v for k, v in by_key.items() if len(v) > 1}

    return {
        "changes": changes,
        "change_count": sum(1 for c in changes if c["will_change"]),
        "missing_target_host": [c["source_code"] for c in changes if c["missing_target"]],
        "duplicate_physical_database_keys": duplicates,
    }


def apply_plan(db, plan: dict) -> None:
    for item in plan["changes"]:
        if not item["will_change"] and not item.get("endpoint_key"):
            continue
        row = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == item["source_code"]))
        if not row:
            continue
        if item["new_target_host"]:
            row.target_host = item["new_target_host"]
            row.host_masked = host_masked_from_target(item["new_target_host"])
        if item["new_port"]:
            row.port = item["new_port"]
        if item.get("service_name"):
            row.service_name = item["service_name"]
        row.endpoint_key = item["endpoint_key"]
        row.database_key = item["database_key"]
        row.source_kind = item["source_kind"]
        row.canonical_source_code = item.get("canonical_source_code")
        if item.get("business_labels"):
            row.business_labels = item["business_labels"]
        if row.target_host:
            physical_identity = build_connection_identity_key(
                row.db_type,
                row.target_host,
                row.port,
                row.service_name,
                row.database_name,
                row.service_mode,
            )
            # connection_identity_key is a legacy unique column. Historical
            # aliases intentionally share endpoint_key/database_key with the
            # canonical physical connection, but must keep their own stable
            # row identity to satisfy that constraint.
            row.connection_identity_key = row_connection_identity_key(
                row.source_code, item["source_kind"], physical_identity
            )
    db.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        plan = build_plan(db)
        plan["applied"] = False
        if args.apply:
            if args.confirmation != CONFIRMATION:
                raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
            apply_plan(db, plan)
            plan["applied"] = True
        text = json.dumps(plan, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(text)
    finally:
        db.close()


if __name__ == "__main__":
    main()
