"""Compare platform live metadata (column snapshots) vs 08 数据中心元数据快照.

Read-only on platform PG + local/remote 08 JSON. Does not touch Oracle business DBs.

Usage (inside API container or with APP_DB_URL):
  PYTHONPATH=/app python scripts/diff_live_snapshot_vs_08.py \\
    --snapshot-json /tmp/08_数据中心元数据快照.json \\
    --source-code ods_8_216 \\
    --out /tmp/l10_diff_live_vs_08.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.models.governance import MetadataSnapshot
from app.models.metadata_change import AssetMetadataColumnSnapshot


def load_08_tables(path: Path) -> set[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tables: set[tuple[str, str]] = set()
    if not isinstance(data, dict):
        return tables

    # 08 shape: {schemas: {OWNER: {tables: {TABLE: {...}}}}}
    schemas = data.get("schemas")
    if isinstance(schemas, dict):
        for schema, body in schemas.items():
            if not isinstance(body, dict):
                continue
            tmap = body.get("tables")
            if isinstance(tmap, dict):
                for tname in tmap.keys():
                    if tname:
                        tables.add((str(schema).upper(), str(tname).upper()))
            elif isinstance(tmap, list):
                for t in tmap:
                    if isinstance(t, str):
                        tables.add((str(schema).upper(), t.upper()))
                    elif isinstance(t, dict):
                        name = (t.get("table_name") or t.get("name") or "").strip().upper()
                        if name:
                            tables.add((str(schema).upper(), name))
        if tables:
            return tables

    if "tables" in data and isinstance(data["tables"], list):
        for t in data["tables"]:
            if not isinstance(t, dict):
                continue
            schema = (t.get("schema_name") or t.get("owner") or t.get("schema") or "").strip().upper()
            name = (t.get("table_name") or t.get("name") or "").strip().upper()
            if schema and name:
                tables.add((schema, name))
    return tables


def live_tables_from_column_snapshots(db, source_code: str | None) -> set[tuple[str, str]]:
    # latest snapshot id for source
    stmt = select(MetadataSnapshot).order_by(MetadataSnapshot.id.desc())
    if source_code:
        stmt = stmt.where(MetadataSnapshot.source_code == source_code)
    snap = db.scalars(stmt.limit(1)).first()
    if not snap:
        return set()
    q = (
        select(
            AssetMetadataColumnSnapshot.namespace_name,
            AssetMetadataColumnSnapshot.table_name,
        )
        .where(AssetMetadataColumnSnapshot.snapshot_id == snap.id)
        .distinct()
    )
    rows = db.execute(q).all()
    out = set()
    for ns, tn in rows:
        if ns and tn:
            out.add((str(ns).upper(), str(tn).upper()))
    return out, snap.id, snap.source_code, snap.table_count


def live_tables_from_asset_tables(db, system_code: str | None = "DATA_CENTER") -> set[tuple[str, str]]:
    sql = "select upper(schema_name), upper(table_name) from asset.asset_tables"
    params = {}
    if system_code:
        sql += " where system_code = :sc"
        params["sc"] = system_code
    rows = db.execute(text(sql), params).all()
    return {(r[0], r[1]) for r in rows if r[0] and r[1]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot-json", required=True)
    p.add_argument("--source-code", default="ods_8_216")
    p.add_argument("--out", default="")
    p.add_argument("--use-asset-tables", action="store_true", help="fallback compare against asset_tables")
    args = p.parse_args()
    path = Path(args.snapshot_json)
    if not path.exists():
        raise SystemExit(f"missing {path}")

    base_08 = load_08_tables(path)
    db = SessionLocal()
    try:
        live_meta = live_tables_from_column_snapshots(db, args.source_code)
        if isinstance(live_meta, tuple):
            live, snap_id, snap_src, snap_tc = live_meta
        else:
            live, snap_id, snap_src, snap_tc = set(), None, None, None
        if (not live) and args.use_asset_tables:
            live = live_tables_from_asset_tables(db, "DATA_CENTER")
            snap_id = None
            snap_src = "asset_tables"
        only_08 = sorted(base_08 - live)
        only_live = sorted(live - base_08)
        report = {
            "source_code_filter": args.source_code,
            "snapshot_file": str(path),
            "live_snapshot_id": snap_id,
            "live_source_code": snap_src,
            "live_snapshot_table_count_field": snap_tc,
            "count_08": len(base_08),
            "count_live": len(live),
            "only_in_08_count": len(only_08),
            "only_in_live_count": len(only_live),
            "only_in_08_sample": [f"{a}.{b}" for a, b in only_08[:80]],
            "only_in_live_sample": [f"{a}.{b}" for a, b in only_live[:80]],
            "schema_counts_08": dict(Counter(a for a, _ in base_08).most_common()),
            "schema_counts_live": dict(Counter(a for a, _ in live).most_common()),
            "note": "表名大小写已 upper；仅表级对比，不含字段级。源库零写。",
        }
        text_out = json.dumps(report, ensure_ascii=False, indent=2)
        print(text_out[:4000])
        if args.out:
            Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("wrote", args.out)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
