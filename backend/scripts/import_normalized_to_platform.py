"""Import normalized package tables/columns into platform asset_* (platform PG only).

Usage on server (inside container or with APP_DB_URL):
  PYTHONPATH=/app python scripts/import_normalized_to_platform.py --csv-dir /path/to/数据资产_ODS_HIS归一优化包

Default: skip if asset_tables already has many rows unless --force.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

# allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.services.relation_identity import populate_endpoint_fields
from app.models.asset_system import AssetDataSource, AssetSystem
from app.services.asset_catalog import CANONICAL_SYSTEMS


def _ensure_system_source(db, system_code: str, system_name: str, system_type: str, source_code: str, source_name: str, host: str, service: str):
    sys_row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    if not sys_row:
        db.add(
            AssetSystem(
                system_code=system_code,
                system_name_cn=CANONICAL_SYSTEMS.get(system_code, system_name),
                system_type=system_type,
                status="active",
            )
        )
    src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if not src:
        db.add(
            AssetDataSource(
                system_code=system_code,
                source_code=source_code,
                source_name_cn=source_name,
                db_type="oracle",
                host_masked=host,
                port=1521,
                service_name=service,
                environment="prod",
                collect_mode="metadata_only",
                enabled=True,
            )
        )
    elif source_code.startswith("ods_") and src.system_code != "DATA_CENTER":
        # ODS 镜像连接始终属于数据中心；重跑导入时也要纠偏历史一级系统归属。
        src.system_code = "DATA_CENTER"
    db.flush()


def import_tables(db, tables_csv: Path, force: bool) -> dict:
    existing = db.scalar(select(func.count()).select_from(AssetTable)) or 0
    if existing > 200 and not force:
        return {"skipped": True, "reason": f"asset_tables already has {existing} rows (use --force)"}

    if force and existing:
        # only clear tables/columns from normalized import sources to avoid wiping unrelated
        pass

    t_count = 0
    with tables_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cat = (row.get("system_category") or "").strip()
            source_system = (row.get("source_system") or "").strip()
            schema = (row.get("schema_name") or "").strip()
            table = (row.get("table_name") or "").strip()
            if not table:
                continue
            # map category to platform system/source
            if cat == "his_source":
                system_code, source_code = "HIS_SOURCE", "his_source_10_10_10_15"
            elif cat == "hrp_source":
                system_code, source_code = "HRP", "hrp_10_10_10_23"
            else:
                system_code = "DATA_CENTER"
                # peripheral logical sources if known
                zone = source_system or "ods_his"
                zone_to_source = {
                    "ods_lis": "ods_lis",
                    "ods_pacs": "ods_pacs",
                    "ods_emr": "ods_emr",
                    "ods_ydhl": "ods_ydhl",
                    "ods_sm": "ods_sm",
                    "ods_his": "ods_8_216",
                    "ods_cda": "ods_8_216",
                    "ods_other": "ods_8_216",
                }
                source_code = zone_to_source.get(zone, "ods_8_216")

            # unique is (schema_name, table_name) on platform — not source-scoped
            obj = db.scalar(
                select(AssetTable).where(
                    AssetTable.schema_name == schema,
                    AssetTable.table_name == table,
                )
            )
            if obj and not force:
                continue
            if not obj:
                obj = AssetTable()
                db.add(obj)
            obj.system_code = system_code
            obj.source_code = source_code
            obj.namespace_name = schema
            obj.schema_name = schema
            obj.table_name = table
            obj.table_name_cn = (row.get("table_name_cn") or "").strip() or None
            obj.table_role = (row.get("table_role") or "").strip() or None
            obj.domain = (row.get("business_domain") or "").strip() or None
            obj.column_count = int(row["column_count"]) if (row.get("column_count") or "").isdigit() else 0
            obj.pk = (row.get("pk") or "").strip() or None
            obj.include_status = (row.get("include_status") or "candidate").strip()
            obj.note = (row.get("note") or "").strip() or None
            obj.source = (row.get("source_system_cn") or row.get("source") or "").strip() or None
            t_count += 1
            if t_count % 500 == 0:
                db.flush()
    db.commit()
    return {"skipped": False, "tables_upserted": t_count}


def import_columns(db, columns_csv: Path, limit: int | None) -> dict:
    if not columns_csv.exists():
        return {"columns_upserted": 0, "note": "columns csv missing"}
    existing = db.scalar(select(func.count()).select_from(AssetColumn)) or 0
    if existing > 5000 and limit is None:
        # still import but only for tables missing columns
        pass
    c_count = 0
    with columns_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if limit is not None and c_count >= limit:
                break
            schema = (row.get("schema_name") or row.get("source_owner") or "").strip()
            table = (row.get("table_name") or "").strip()
            col = (row.get("column_name") or "").strip()
            if not table or not col:
                continue
            cat = (row.get("system_category") or "").strip()
            source_system = (row.get("source_system") or "").strip()
            if cat == "his_source":
                system_code, source_code = "HIS_SOURCE", "his_source_10_10_10_15"
            else:
                system_code = "DATA_CENTER"
                zone_to_source = {
                    "ods_lis": "ods_lis",
                    "ods_pacs": "ods_pacs",
                    "ods_emr": "ods_emr",
                    "ods_ydhl": "ods_ydhl",
                    "ods_sm": "ods_sm",
                }
                source_code = zone_to_source.get(source_system, "ods_8_216")

            exists = db.scalar(
                select(AssetColumn.id).where(
                    AssetColumn.schema_name == schema,
                    AssetColumn.table_name == table,
                    AssetColumn.column_name == col,
                )
            )
            if exists:
                # still refresh source routing when force-like reimport of missing only
                continue
            db.add(
                AssetColumn(
                    system_code=system_code,
                    source_code=source_code,
                    namespace_name=schema,
                    schema_name=schema,
                    table_name=table,
                    column_id=int(row["column_id"]) if (row.get("column_id") or "").isdigit() else 0,
                    column_name=col,
                    column_name_cn=(row.get("column_name_cn") or "").strip() or None,
                    data_type=(row.get("data_type") or "").strip() or None,
                    length=int(row["length"]) if (row.get("length") or "").isdigit() else None,
                    nullable=(row.get("nullable") or "").strip() or None,
                    comment=(row.get("comment") or "").strip() or None,
                    is_sensitive=False,
                )
            )
            c_count += 1
            if c_count % 1000 == 0:
                db.flush()
    db.commit()
    return {"columns_upserted": c_count}


def import_relations(db, rel_csv: Path) -> dict:
    if not rel_csv.exists():
        return {"relations_upserted": 0}
    existing = db.scalar(select(func.count()).select_from(AssetRelation)) or 0
    if existing > 20:
        return {"relations_upserted": 0, "skipped": True, "existing": existing}
    n = 0
    with rel_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ft = (row.get("from_table") or row.get("left_table") or "").strip()
            tt = (row.get("to_table") or row.get("right_table") or "").strip()
            if not ft or not tt:
                continue
            # expect schema.table or just table
            def split(full: str):
                if "." in full:
                    a, b = full.split(".", 1)
                    return a, b
                return "", full

            _fs, fn = split(ft)
            _ts, tn = split(tt)
            conf = (row.get("confidence") or row.get("validation_level") or "").strip() or None
            _rel = AssetRelation(
                    from_table=fn if not _fs else f"{_fs}.{fn}",
                    to_table=tn if not _ts else f"{_ts}.{tn}",
                    from_columns=(row.get("from_columns") or row.get("left_columns") or "").strip() or None,
                    to_columns=(row.get("to_columns") or row.get("right_columns") or "").strip() or None,
                    join_condition=(row.get("join_condition") or "").strip() or None,
                    confidence=conf,
                    validation_level=conf,
                    validation_status=(row.get("validation_status") or "").strip() or None,
                    note=(row.get("note") or "").strip() or None,
                )
            populate_endpoint_fields(db, _rel)
            db.add(_rel)
            n += 1
    db.commit()
    return {"relations_upserted": n}


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--csv-dir",
        default=str(
            Path(__file__).resolve().parents[2]
            / "开发起步包"
            / "数据资产_ODS_HIS归一优化包"
        ),
    )
    p.add_argument("--force", action="store_true")
    p.add_argument("--columns-limit", type=int, default=50000, help="cap columns import size")
    p.add_argument("--skip-columns", action="store_true")
    args = p.parse_args()
    d = Path(args.csv_dir)
    tables_csv = d / "normalized_tables.csv"
    columns_csv = d / "normalized_columns.csv"
    rel_csv = d / "normalized_relationships.csv"
    if not tables_csv.exists():
        raise SystemExit(f"missing {tables_csv}")

    db = SessionLocal()
    try:
        _ensure_system_source(
            db, "DATA_CENTER", CANONICAL_SYSTEMS["DATA_CENTER"], "ODS", "ods_8_216", "数据中心 ODS", "10.10.8.216", "orcl"
        )
        _ensure_system_source(
            db, "HIS_SOURCE", CANONICAL_SYSTEMS["HIS_SOURCE"], "HIS", "his_source_10_10_10_15", "HIS业务库", "10.10.10.15", "his"
        )
        # ODS owner mirrors are physical connections under DATA_CENTER, never
        # first-level business systems. Keep each connection code/name intact.
        for source_code, owner in (("ods_lis", "LIS"), ("ods_pacs", "PACS"), ("ods_emr", "EMR"), ("ods_ydhl", "YDHL"), ("ods_sm", "SM")):
            _ensure_system_source(
                db, "DATA_CENTER", CANONICAL_SYSTEMS["DATA_CENTER"], "ODS",
                source_code, f"ODS.{owner}", "10.10.8.216", "orcl"
            )
        db.commit()

        out = {
            "tables": import_tables(db, tables_csv, args.force),
            "relations": import_relations(db, rel_csv),
        }
        if not args.skip_columns:
            out["columns"] = import_columns(db, columns_csv, args.columns_limit)
        final_t = db.scalar(select(func.count()).select_from(AssetTable)) or 0
        final_c = db.scalar(select(func.count()).select_from(AssetColumn)) or 0
        final_r = db.scalar(select(func.count()).select_from(AssetRelation)) or 0
        out["totals"] = {"tables": final_t, "columns": final_c, "relations": final_r}
        print(out)
    finally:
        db.close()


if __name__ == "__main__":
    main()
