"""Idempotent import of HRP offline asset package into platform asset_tables/columns.

Default scope: decided keep list (P0 KEEP_CORE + keep decisions).
Never writes to HRP business source DB.

Usage:
  python scripts/import_hrp_assets.py --dry-run
  python scripts/import_hrp_assets.py --apply --confirmation IMPORT-HRP-ASSETS
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PKG = ROOT / "开发起步包" / "数据资产_HRP源端资产包"

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetTable
from app.models.asset_system import AssetDataSource, AssetSourceSchema, AssetSystem
from app.services.connection_identity import (
    build_connection_identity_key,
    build_database_key,
    build_endpoint_key,
    host_masked_from_target,
)
from app.services.ops_event_log import log_event

CONFIRMATION = "IMPORT-HRP-ASSETS"
SOURCE_CODE = "hrp_10_10_10_23"
SYSTEM_CODE = "HRP"
HRP_HOST = "10.10.10.23"
HRP_PORT = 1521
HRP_SERVICE = "hrpdb"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_keep_tables(pkg: Path, scope: str) -> set[tuple[str, str]]:
    """Return set of (owner, table_name) to import."""
    tables: set[tuple[str, str]] = set()
    if scope == "ods_mirror":
        path = pkg / "hrp_ods_mirror_tables.csv"
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                owner = (row.get("owner") or row.get("schema_name") or "HRP").strip()
                name = (row.get("table_name") or "").strip()
                if name:
                    tables.add((owner, name))
        return tables

    if scope == "core":
        path = pkg / "hrp_tables_core_candidates.csv"
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                owner = (row.get("owner") or "").strip()
                name = (row.get("table_name") or "").strip()
                if name:
                    tables.add((owner, name))
        return tables

    # default: decided keep list
    path = pkg / "hrp_decided_keep_list.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                action = (row.get("suggested_action_code") or "").upper()
                if action and action not in {"KEEP_CORE", "KEEP", "KEEP_REVIEW"}:
                    # still keep rows marked KEEP*
                    if not action.startswith("KEEP"):
                        continue
                owner = (row.get("owner") or "").strip()
                name = (row.get("table_name") or "").strip()
                if name:
                    tables.add((owner, name))
    if not tables and (pkg / "hrp_tables_core_candidates.csv").exists():
        return load_keep_tables(pkg, "core")
    return tables


def load_table_meta(pkg: Path, keep: set[tuple[str, str]]) -> dict[tuple[str, str], dict]:
    meta: dict[tuple[str, str], dict] = {}
    path = pkg / "hrp_source_tables.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            owner = (row.get("owner") or "").strip()
            name = (row.get("table_name") or "").strip()
            key = (owner, name)
            if key not in keep:
                continue
            meta[key] = row
    # if keep tables missing from source tables (ods mirror only), fabricate
    for key in keep:
        if key not in meta:
            meta[key] = {
                "owner": key[0],
                "table_name": key[1],
                "table_comment": "",
                "inferred_domain": "",
                "num_rows_stats": "",
                "include_status": "candidate",
            }
    return meta


def load_columns_for_tables(pkg: Path, keep: set[tuple[str, str]], limit_per_table: int | None = None) -> list[dict]:
    """Stream columns csv; only keep matching tables. Columns file may be huge."""
    # prefer smaller mirror columns if scope was ods_mirror
    candidates = [
        pkg / "hrp_ods_mirror_columns.csv",
        pkg / "hrp_source_columns.csv",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return []
    out: list[dict] = []
    per_table: dict[tuple[str, str], int] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            owner = (row.get("owner") or row.get("schema_name") or row.get("source_owner") or "").strip()
            table = (row.get("table_name") or "").strip()
            col = (row.get("column_name") or "").strip()
            if not table or not col:
                continue
            key = (owner, table)
            if key not in keep and (owner or "HRPSEY656", table) not in keep:
                # try default owner
                alt = ("HRPSEY656", table)
                if alt not in keep:
                    continue
                key = alt
                owner = key[0]
            n = per_table.get(key, 0)
            if limit_per_table is not None and n >= limit_per_table:
                continue
            per_table[key] = n + 1
            row = dict(row)
            row["_owner"] = owner
            row["_table"] = table
            row["_column"] = col
            out.append(row)
    return out


def ensure_hrp_registry(db) -> None:
    sys_row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == SYSTEM_CODE))
    if not sys_row:
        db.add(
            AssetSystem(
                system_code=SYSTEM_CODE,
                system_name_cn="HRP 业务系统",
                system_type="HRP",
                status="active",
                target_host=HRP_HOST,
                system_identity_key=HRP_HOST.lower(),
            )
        )
    else:
        sys_row.status = "active"
        if not sys_row.target_host:
            sys_row.target_host = HRP_HOST
    src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == SOURCE_CODE))
    endpoint = build_endpoint_key("oracle", HRP_HOST, HRP_PORT)
    dbkey = build_database_key("oracle", HRP_HOST, HRP_PORT, HRP_SERVICE, None, "service_name")
    if not src:
        db.add(
            AssetDataSource(
                system_code=SYSTEM_CODE,
                source_code=SOURCE_CODE,
                source_name_cn="HRP 生产库",
                db_type="oracle",
                target_host=HRP_HOST,
                host_masked=host_masked_from_target(HRP_HOST),
                port=HRP_PORT,
                service_mode="service_name",
                service_name=HRP_SERVICE,
                environment="prod",
                collect_mode="metadata_only",
                enabled=True,
                write_policy="readonly",
                endpoint_key=endpoint,
                database_key=dbkey,
                source_kind="physical_connection",
                business_labels=["HRP"],
                metadata_origin="offline_package",
                connection_identity_key=build_connection_identity_key(
                    "oracle", HRP_HOST, HRP_PORT, HRP_SERVICE, None, "service_name"
                ),
            )
        )
    else:
        src.system_code = SYSTEM_CODE
        src.enabled = True
        src.target_host = src.target_host or HRP_HOST
        src.port = src.port or HRP_PORT
        src.service_name = src.service_name or HRP_SERVICE
        src.service_mode = src.service_mode or "service_name"
        src.host_masked = host_masked_from_target(src.target_host)
        src.endpoint_key = endpoint
        src.database_key = dbkey
        src.source_kind = "physical_connection"
        src.business_labels = src.business_labels or ["HRP"]
        src.metadata_origin = src.metadata_origin or "offline_package"
        src.write_policy = "readonly"
    db.flush()


def apply_import(db, table_meta: dict[tuple[str, str], dict], columns: list[dict], meta: dict, operator: str) -> dict:
    ensure_hrp_registry(db)
    upserted_tables = 0
    for (owner, name), row in table_meta.items():
        obj = db.scalar(
            select(AssetTable).where(
                AssetTable.source_code == SOURCE_CODE,
                AssetTable.schema_name == owner,
                AssetTable.table_name == name,
            )
        )
        if not obj:
            # also match by schema+name without source (legacy unique)
            obj = db.scalar(
                select(AssetTable).where(
                    AssetTable.schema_name == owner,
                    AssetTable.table_name == name,
                )
            )
        if not obj:
            obj = AssetTable()
            db.add(obj)
        obj.system_code = SYSTEM_CODE
        obj.source_code = SOURCE_CODE
        obj.namespace_name = owner
        obj.schema_name = owner
        obj.table_name = name
        obj.table_name_cn = (row.get("table_comment") or "").strip() or None
        obj.domain = (row.get("inferred_domain") or row.get("inferred_domain_refined") or "").strip() or None
        obj.row_count_stats = str(row.get("num_rows_stats") or "") or None
        cc = row.get("column_count_in_current_file") or row.get("column_count")
        obj.column_count = int(cc) if str(cc or "").isdigit() else obj.column_count
        obj.include_status = (row.get("include_status") or "candidate").strip()
        obj.source = "HRP offline package"
        obj.note = (row.get("exclude_reason") or "").strip() or None
        upserted_tables += 1
        if upserted_tables % 200 == 0:
            db.flush()

    upserted_cols = 0
    for row in columns:
        owner = row["_owner"]
        table = row["_table"]
        col = row["_column"]
        obj = db.scalar(
            select(AssetColumn).where(
                AssetColumn.source_code == SOURCE_CODE,
                AssetColumn.schema_name == owner,
                AssetColumn.table_name == table,
                AssetColumn.column_name == col,
            )
        )
        if not obj:
            obj = db.scalar(
                select(AssetColumn).where(
                    AssetColumn.schema_name == owner,
                    AssetColumn.table_name == table,
                    AssetColumn.column_name == col,
                )
            )
        if not obj:
            obj = AssetColumn()
            db.add(obj)
        obj.system_code = SYSTEM_CODE
        obj.source_code = SOURCE_CODE
        obj.namespace_name = owner
        obj.schema_name = owner
        obj.table_name = table
        obj.column_name = col
        obj.column_name_cn = (row.get("column_comment") or row.get("column_name_cn") or "").strip() or None
        obj.data_type = (row.get("data_type") or "").strip() or None
        length = row.get("data_length") or row.get("length")
        obj.length = int(length) if str(length or "").isdigit() else None
        obj.nullable = (row.get("nullable") or row.get("null_ok") or "").strip() or None
        upserted_cols += 1
        if upserted_cols % 1000 == 0:
            db.flush()

    # refresh schema stats
    schema_stats = db.execute(
        select(
            AssetTable.schema_name,
            func.count(),
            func.coalesce(func.sum(AssetTable.column_count), 0),
        )
        .where(AssetTable.source_code == SOURCE_CODE)
        .group_by(AssetTable.schema_name)
    ).all()
    for schema_name, tcnt, ccnt in schema_stats:
        row = db.scalar(
            select(AssetSourceSchema).where(
                AssetSourceSchema.source_code == SOURCE_CODE,
                AssetSourceSchema.schema_name == schema_name,
            )
        )
        if not row:
            row = AssetSourceSchema(source_code=SOURCE_CODE, schema_name=schema_name or "")
            db.add(row)
        row.table_count = int(tcnt or 0)
        row.column_count = int(ccnt or 0)
        row.business_labels = ["HRP"]
        row.last_collect_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)

    src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == SOURCE_CODE))
    if src:
        src.last_collect_status = "succeeded"
        src.last_collect_at = datetime.now(timezone.utc)
        src.metadata_origin = "offline_package"

    log_event(
        db,
        module="dict" if False else "asset",
        entity_type="hrp_import",
        entity_ref=SOURCE_CODE,
        action="import_success",
        operator=operator,
        status="succeeded",
        target_source_code=SOURCE_CODE,
        target_database_key=src.database_key if src else None,
        batch_code=meta.get("batch_code"),
        affected_count=upserted_tables,
        summary_masked=f"tables={upserted_tables} columns={upserted_cols}",
        detail={
            "tables_upserted": upserted_tables,
            "columns_upserted": upserted_cols,
            "scope": meta.get("scope"),
            "package_sha": meta.get("package_files"),
        },
    )
    db.commit()
    return {
        "status": "succeeded",
        "tables_upserted": upserted_tables,
        "columns_upserted": upserted_cols,
        "schemas": len(schema_stats),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PKG)
    parser.add_argument("--scope", choices=["keep", "core", "ods_mirror"], default="keep")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--max-columns-per-table", type=int, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--operator", default="script:import_hrp_assets")
    args = parser.parse_args()

    pkg = args.package_dir
    keep = load_keep_tables(pkg, args.scope)
    table_meta = load_table_meta(pkg, keep)
    # for keep/core use source columns; stream only matching
    columns = load_columns_for_tables(pkg, keep, limit_per_table=args.max_columns_per_table)

    package_files = {}
    for name in (
        "hrp_source_catalog.json",
        "hrp_decided_keep_list.csv",
        "hrp_source_tables.csv",
        "hrp_source_columns.csv",
        "hrp_ods_mirror_tables.csv",
        "hrp_ods_mirror_columns.csv",
    ):
        p = pkg / name
        if p.exists():
            package_files[name] = {
                "size": p.stat().st_size,
                "sha256": file_sha256(p) if p.stat().st_size < 50_000_000 else "skipped_large",
            }

    with SessionLocal() as db:
        existing_tables = db.scalar(
            select(func.count()).select_from(AssetTable).where(AssetTable.source_code == SOURCE_CODE)
        ) or 0
        existing_cols = db.scalar(
            select(func.count()).select_from(AssetColumn).where(AssetColumn.source_code == SOURCE_CODE)
        ) or 0

    report = {
        "mode": "apply" if args.apply else "dry_run",
        "scope": args.scope,
        "package_dir": str(pkg),
        "package_files": package_files,
        "keep_tables": len(keep),
        "table_meta_rows": len(table_meta),
        "columns_loaded": len(columns),
        "platform_existing_hrp_tables": int(existing_tables),
        "platform_existing_hrp_columns": int(existing_cols),
        "batch_code": f"hrp-import-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "apply_result": None,
    }

    if args.apply:
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
        with SessionLocal() as db:
            report["apply_result"] = apply_import(
                db, table_meta, columns, report, args.operator
            )
    else:
        report["apply_result"] = {"status": "dry_run", "writes": 0}

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
