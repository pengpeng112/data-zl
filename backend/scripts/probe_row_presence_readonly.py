"""Probe table row presence with bounded read-only SELECT statements.

Business databases are never modified. Default is dry-run; apply only writes
status and cleanup metadata in the platform asset schema.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.asset_system import AssetDataSource
from app.services.credentials import resolve
from app.services.db_connectors import DB_CONNECTOR_MAP
from app.services.row_presence import (
    BLOCKED, CIRCUIT_BREAKER_TIMEOUTS, CONFIRMED_EMPTY, NON_EMPTY_EVIDENCE,
    NON_EMPTY_STATS, UNKNOWN, classify_from_stats, now_utc, probe_one,
    should_skip_probe,
)
from app.services.asset_import_upsert import rebuild_schema_inventory

CONFIRMATION = "APPLY-ROW-PRESENCE-READONLY"


def connector_for(source: AssetDataSource):
    cls = DB_CONNECTOR_MAP.get((source.db_type or "").lower())
    if cls is None:
        raise ValueError("unsupported_db_type")
    if (source.write_policy or "readonly") != "readonly":
        raise ValueError("source_not_readonly")
    user, password = resolve(source.credential_ref)
    opts = dict(source.connection_options or {})
    opts["timeout_ms"] = 5000
    return cls(
        host=source.target_host or source.host_masked or "",
        port=source.port or 0,
        database=source.service_name or source.database_name or "",
        user=user or "", password=password or "",
        connection_mode=source.connection_mode or "direct", **opts,
    )


def run(db, source_codes: set[str], apply: bool, max_objects: int) -> dict:
    sources = db.scalars(select(AssetDataSource).where(
        AssetDataSource.enabled.is_(True),
        AssetDataSource.source_kind == "physical_connection",
    )).all()
    if source_codes:
        sources = [s for s in sources if s.source_code in source_codes]
    summary = {}
    total_updates = 0
    for source in sources:
        counts = defaultdict(int)
        alias_codes = db.scalars(select(AssetDataSource.source_code).where(
            AssetDataSource.source_kind == "legacy_alias",
            AssetDataSource.canonical_source_code == source.source_code,
        )).all()
        table_source_codes = [source.source_code, *alias_codes]
        tables = db.scalars(select(AssetTable).where(
            AssetTable.source_code.in_(table_source_codes)
        ).order_by(AssetTable.source_code, AssetTable.schema_name, AssetTable.table_name)).all()
        if max_objects:
            tables = tables[:max_objects]
        try:
            connector = connector_for(source)
        except Exception as exc:
            summary[source.source_code] = {"blocked_source": type(exc).__name__, "objects": len(tables)}
            continue
        consecutive_timeouts = 0
        try:
            for table in tables:
                evidence = should_skip_probe(table.system_code, table.schema_name, table.table_name)
                stats = classify_from_stats(table.row_count_stats)
                if evidence:
                    result = {"status": evidence, "method": "known_evidence", "error_code": None}
                elif stats:
                    result = {"status": stats, "method": "metadata_stats_positive", "error_code": None}
                elif (table.table_role or "table").lower() == "view":
                    result = {"status": UNKNOWN, "method": "view_not_whitelisted", "error_code": None}
                elif consecutive_timeouts >= CIRCUIT_BREAKER_TIMEOUTS:
                    result = {"status": BLOCKED, "method": "circuit_breaker", "error_code": "SOURCE_TIMEOUT_BREAKER"}
                else:
                    result = probe_one(
                        connector.execute_readonly,
                        db_type=source.db_type or "",
                        schema=table.schema_name or table.namespace_name or source.default_schema or "",
                        table=table.table_name,
                        database=source.database_name,
                    )
                    if result["status"] == UNKNOWN and "TIMEOUT" in (result.get("error_code") or ""):
                        consecutive_timeouts += 1
                    else:
                        consecutive_timeouts = 0
                counts[result["status"]] += 1
                if apply and table.row_presence_status != result["status"]:
                    table.row_presence_status = result["status"]
                    table.row_presence_checked_at = now_utc()
                    table.row_presence_method = result["method"]
                    table.row_presence_error_code = result.get("error_code")
                    if result["status"] == CONFIRMED_EMPTY:
                        table.include_status = "excluded_empty"
                        db.execute(delete(AssetColumn).where(
                            AssetColumn.source_code == table.source_code,
                            AssetColumn.schema_name == table.schema_name,
                            AssetColumn.table_name == table.table_name,
                        ))
                    total_updates += 1
        finally:
            connector.close()
        summary[source.source_code] = {**dict(counts), "asset_source_codes": table_source_codes}
    if apply:
        # Preserve relation audit rows; mark endpoints instead of deleting them.
        empties = db.scalars(select(AssetTable).where(
            AssetTable.row_presence_status == CONFIRMED_EMPTY
        )).all()
        endpoint_names = {f"{t.schema_name or t.namespace_name}.{t.table_name}".upper() for t in empties}
        for rel in db.scalars(select(AssetRelation)).all():
            if (rel.from_table or "").upper() in endpoint_names or (rel.to_table or "").upper() in endpoint_names:
                rel.endpoint_excluded_empty = True
        for source in sources:
            alias_codes = db.scalars(select(AssetDataSource.source_code).where(
                AssetDataSource.source_kind == "legacy_alias",
                AssetDataSource.canonical_source_code == source.source_code,
            )).all()
            for source_code in [source.source_code, *alias_codes]:
                rebuild_schema_inventory(db, source_code=source_code, labels=source.business_labels)
        db.commit()
    else:
        db.rollback()
    return {"mode": "apply" if apply else "dry_run", "business_source_writes": 0,
            "platform_updates": total_updates if apply else 0, "sources": summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-codes", default="")
    parser.add_argument("--max-objects", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    if args.apply and args.confirmation != CONFIRMATION:
        raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
    with SessionLocal() as db:
        out = run(db, {x.strip() for x in args.source_codes.split(",") if x.strip()}, args.apply, args.max_objects)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
