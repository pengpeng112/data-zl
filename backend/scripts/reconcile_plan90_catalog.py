"""Plan 90: normalize systems + dry-run/apply catalog reconcile on platform asset schema.

Never touches business source DBs.
Default mode is dry-run. Apply requires --apply --confirmation RECONCILE-PLAN90-CATALOG.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, update

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.asset_system import AssetDataSource, AssetSystem
from app.services.asset_catalog import (
    CANONICAL_SYSTEMS,
    LEGACY_SYSTEM_MAP,
    ensure_canonical_systems,
    normalize_system_code,
)
from app.services.row_presence import CONFIRMED_EMPTY, is_catalog_visible

CONFIRMATION = "RECONCILE-PLAN90-CATALOG"


def plan_system_normalize(db) -> dict:
    ensure_canonical_systems(db)
    changes = []
    sources = db.scalars(select(AssetDataSource)).all()
    for src in sources:
        new_code = normalize_system_code(
            src.system_code,
            source_code=src.source_code,
            source_kind=src.source_kind,
        )
        if new_code != src.system_code and new_code in CANONICAL_SYSTEMS:
            changes.append({
                "entity": "data_source",
                "source_code": src.source_code,
                "old": src.system_code,
                "new": new_code,
            })
    # mark legacy systems
    systems = db.scalars(select(AssetSystem)).all()
    legacy_marks = []
    for sys in systems:
        code = (sys.system_code or "").upper()
        if code in CANONICAL_SYSTEMS:
            continue
        if code in LEGACY_SYSTEM_MAP:
            canon = LEGACY_SYSTEM_MAP[code]
            status = (sys.status or "").lower()
            already = (
                status in {"merged", "deleted"}
                and (sys.canonical_system_code or "").upper() == canon
            )
            if already:
                continue
            # only if no physical sources remain under old code with independent identity
            phys = [
                s for s in sources
                if s.system_code == code
                and (s.source_kind or "physical_connection") == "physical_connection"
            ]
            if not phys:
                legacy_marks.append({
                    "system_code": code,
                    "canonical_system_code": canon,
                    "action": "soft_merge",
                })
    return {
        "source_system_rewrites": changes,
        "legacy_system_marks": legacy_marks,
        "canonical_systems": list(CANONICAL_SYSTEMS),
    }


def apply_system_normalize(db, plan: dict) -> int:
    writes = 0
    ensure_canonical_systems(db)
    for ch in plan["source_system_rewrites"]:
        src = db.scalar(
            select(AssetDataSource).where(AssetDataSource.source_code == ch["source_code"])
        )
        if src and src.system_code != ch["new"]:
            old = src.system_code
            src.system_code = ch["new"]
            # rewrite table/column system_code for this source
            for model in (AssetTable, AssetColumn):
                db.execute(
                    update(model)
                    .where(model.source_code == ch["source_code"], model.system_code == old)
                    .values(system_code=ch["new"])
                )
            writes += 1
    for mark in plan["legacy_system_marks"]:
        row = db.scalar(
            select(AssetSystem).where(AssetSystem.system_code == mark["system_code"])
        )
        if row:
            row.status = "merged"
            row.canonical_system_code = mark["canonical_system_code"]
            writes += 1
    # ensure canonical names if empty only
    for code, name in CANONICAL_SYSTEMS.items():
        row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == code))
        if row and not (row.system_name_cn or "").strip():
            row.system_name_cn = name
            writes += 1
    return writes


def presence_summary(db) -> dict:
    rows = db.execute(
        select(AssetTable.system_code, AssetTable.row_presence_status, func.count())
        .group_by(AssetTable.system_code, AssetTable.row_presence_status)
    ).all()
    by_sys: dict[str, dict[str, int]] = {}
    for sc, st, cnt in rows:
        bucket = by_sys.setdefault(sc or "UNKNOWN", {})
        key = st or "null"
        bucket[key] = int(cnt)
    return by_sys


def mark_relations_for_empty_endpoints(db, dry_run: bool = True) -> dict:
    empty_tables = db.scalars(
        select(AssetTable).where(AssetTable.row_presence_status == CONFIRMED_EMPTY)
    ).all()
    endpoints = set()
    for t in empty_tables:
        ns = t.schema_name or t.namespace_name or ""
        endpoints.add(f"{ns}.{t.table_name}".upper())
        endpoints.add(t.table_name.upper())
    marked = 0
    if not endpoints:
        return {"empty_tables": 0, "relations_marked": 0}
    rels = db.scalars(select(AssetRelation)).all()
    for r in rels:
        ft = (r.from_table or "").upper()
        tt = (r.to_table or "").upper()
        hit = False
        for ep in endpoints:
            if ft == ep or tt == ep or ft.endswith("." + ep) or tt.endswith("." + ep):
                hit = True
                break
        if hit and not r.endpoint_excluded_empty:
            marked += 1
            if not dry_run:
                r.endpoint_excluded_empty = True
    return {"empty_tables": len(empty_tables), "relations_marked": marked}


def catalog_counts(db) -> dict:
    total = db.scalar(select(func.count()).select_from(AssetTable)) or 0
    visible = db.scalar(
        select(func.count()).where(
            (AssetTable.row_presence_status.is_(None))
            | (AssetTable.row_presence_status != CONFIRMED_EMPTY)
        )
    ) or 0
    empty = db.scalar(
        select(func.count()).where(AssetTable.row_presence_status == CONFIRMED_EMPTY)
    ) or 0
    return {"tables_total": int(total), "tables_visible": int(visible), "tables_confirmed_empty": int(empty)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    with SessionLocal() as db:
        plan = plan_system_normalize(db)
        counts = catalog_counts(db)
        presence = presence_summary(db)
        rel_plan = mark_relations_for_empty_endpoints(db, dry_run=True)
        out = {
            "mode": "apply" if args.apply else "dry_run",
            "generated_at": now,
            "plan": plan,
            "catalog_counts": counts,
            "presence_by_system": presence,
            "relation_empty_endpoints": rel_plan,
            "writes": 0,
        }
        if not args.apply:
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
        writes = apply_system_normalize(db, plan)
        rel_applied = mark_relations_for_empty_endpoints(db, dry_run=False)
        db.commit()
        out["writes"] = writes + rel_applied["relations_marked"]
        out["relation_empty_endpoints"] = rel_applied
        out["catalog_counts_after"] = catalog_counts(db)
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
