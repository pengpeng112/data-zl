"""Dry-run/apply business system normalization by explicit mapping + target host.

Default is dry-run. Apply requires --apply --confirmation NORMALIZE-BUSINESS-SYSTEMS.
Never writes to business source DBs; only updates platform asset.* tables.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelationReview, AssetTable
from app.models.asset_system import AssetDataSource, AssetSystem
from app.models.governance_base import GovernAuditLog
from app.services.asset_catalog import CANONICAL_SYSTEMS as CANONICAL_SYSTEM_NAMES

# Explicit canonical mapping (plan 75 §4.3)
EXPLICIT_SOURCE_MAP = {
    "his_source_10_10_10_15": "HIS_SOURCE",
    "ods_8_216": "DATA_CENTER",
    "ods_lis": "DATA_CENTER",
    "ods_pacs": "DATA_CENTER",
    "ods_emr": "DATA_CENTER",
    "ods_ydhl": "DATA_CENTER",
    "ods_sm": "DATA_CENTER",
    "hrp_10_10_10_23": "HRP",
}

CANONICAL_SYSTEMS = {
    "HIS_SOURCE": {"system_name_cn": CANONICAL_SYSTEM_NAMES["HIS_SOURCE"], "system_type": "HIS"},
    "HRP": {"system_name_cn": CANONICAL_SYSTEM_NAMES["HRP"], "system_type": "HRP"},
    "DATA_CENTER": {"system_name_cn": CANONICAL_SYSTEM_NAMES["DATA_CENTER"], "system_type": "ODS"},
}

CONFIRMATION = "NORMALIZE-BUSINESS-SYSTEMS"


def _count_refs(db, system_code: str) -> dict:
    return {
        "tables": db.scalar(select(func.count()).where(AssetTable.system_code == system_code)) or 0,
        "columns": db.scalar(select(func.count()).where(AssetColumn.system_code == system_code)) or 0,
        # The legacy asset_relations table only stores qualified table names and
        # has no system_code columns. System-scoped references live in the
        # review/evidence table, so count that model for dry-run conservation.
        "relations_from": db.scalar(
            select(func.count()).where(AssetRelationReview.from_system_code == system_code)
        ) or 0,
        "relations_to": db.scalar(
            select(func.count()).where(AssetRelationReview.to_system_code == system_code)
        ) or 0,
        "sources": db.scalar(select(func.count()).where(AssetDataSource.system_code == system_code)) or 0,
    }


def build_plan(db) -> dict:
    sources = db.scalars(select(AssetDataSource).order_by(AssetDataSource.id)).all()
    mapping = []
    conflicts = []
    missing_host = []

    for source in sources:
        host = (source.target_host or "").strip()
        if not host:
            missing_host.append(source.source_code)
        explicit = EXPLICIT_SOURCE_MAP.get(source.source_code)
        target = explicit
        reason = "explicit_map" if explicit else None
        if not target:
            text_blob = f"{source.system_code} {source.source_code}".lower()
            candidates = set()
            if source.system_code == "DATA_CENTER" or "ods" in text_blob:
                candidates.add("DATA_CENTER")
            if source.system_code == "HRP" or "hrp" in text_blob:
                candidates.add("HRP")
            if source.system_code in {"HIS", "HIS_SOURCE"} or "his" in text_blob:
                candidates.add("HIS_SOURCE")
            if len(candidates) == 1:
                target = next(iter(candidates))
                reason = "heuristic"
            elif len(candidates) > 1:
                # 多候选才是真冲突，必须人工裁定
                conflicts.append({
                    "source_code": source.source_code,
                    "old_system": source.system_code,
                    "target_host": host or None,
                    "candidates": sorted(candidates),
                    "reason": "manual selection required",
                })
            else:
                # 周边独立系统（JHEMR/DOCARE/LIS 等）保留现有 system_code，
                # 不强制并入 HIS/HRP/DATA_CENTER，也不阻塞 apply。
                current = (source.system_code or "").strip()
                if current:
                    target = current
                    reason = "keep_existing_system"
                else:
                    conflicts.append({
                        "source_code": source.source_code,
                        "old_system": source.system_code,
                        "target_host": host or None,
                        "candidates": [],
                        "reason": "missing system_code and no canonical map",
                    })
        mapping.append({
            "source_code": source.source_code,
            "old_system": source.system_code,
            "new_system": target,
            "target_host": host or None,
            "identity_source": reason or "unresolved",
            "will_change": bool(target and target != source.system_code),
        })

    # conservation counts before
    before_systems = {
        row.system_code: _count_refs(db, row.system_code)
        for row in db.scalars(select(AssetSystem)).all()
    }
    before_sources = len(sources)

    return {
        "canonical_systems": list(CANONICAL_SYSTEMS),
        "explicit_map": EXPLICIT_SOURCE_MAP,
        "mapping": mapping,
        "conflicts": conflicts,
        "missing_target_host": missing_host,
        "source_count": before_sources,
        "before_system_refs": before_systems,
        "change_count": sum(1 for m in mapping if m["will_change"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def apply_plan(db, plan: dict, approval_ref: str) -> dict:
    if plan["conflicts"]:
        raise SystemExit("refusing apply: unresolved conflicts")
    if plan["missing_target_host"]:
        # warn but allow if explicit map covers; still record
        pass

    # ensure canonical systems
    for code, meta in CANONICAL_SYSTEMS.items():
        row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == code))
        if not row:
            db.add(AssetSystem(
                system_code=code,
                system_name_cn=meta["system_name_cn"],
                system_type=meta["system_type"],
                status="active",
                system_identity_key=code.lower(),
            ))
        else:
            if (row.status or "").lower() in {"merged", "inactive", "deleted"}:
                row.status = "active"
            row.system_name_cn = row.system_name_cn or meta["system_name_cn"]

    old_systems_touched: set[str] = set()
    for item in plan["mapping"]:
        if not item["new_system"]:
            continue
        src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == item["source_code"]))
        if not src:
            continue
        old = src.system_code
        new = item["new_system"]
        if old != new:
            old_systems_touched.add(old)
            # update source + asset refs
            src.system_code = new
            src.identity_source = item["identity_source"]
            db.execute(
                text("UPDATE asset.asset_tables SET system_code = :new WHERE source_code = :sc"),
                {"new": new, "sc": src.source_code},
            )
            db.execute(
                text("UPDATE asset.asset_columns SET system_code = :new WHERE source_code = :sc"),
                {"new": new, "sc": src.source_code},
            )
            db.execute(
                text(
                    "UPDATE asset.asset_relation_reviews "
                    "SET from_system_code = :new "
                    "WHERE from_source_code = :sc"
                ),
                {"new": new, "sc": src.source_code},
            )
            db.execute(
                text(
                    "UPDATE asset.asset_relation_reviews "
                    "SET to_system_code = :new "
                    "WHERE to_source_code = :sc"
                ),
                {"new": new, "sc": src.source_code},
            )

    # Ensure ORM updates are visible to subsequent COUNT queries.
    db.flush()

    # mark old non-canonical systems as merged
    for old_code in old_systems_touched:
        if old_code in CANONICAL_SYSTEMS:
            continue
        row = db.scalar(select(AssetSystem).where(AssetSystem.system_code == old_code))
        if row:
            remaining = db.scalar(
                select(func.count()).where(AssetDataSource.system_code == old_code)
            ) or 0
            if remaining == 0:
                row.status = "merged"
                row.description_cn = (row.description_cn or "") + f" | merged→canonical approval={approval_ref}"
                row.updated_at = datetime.now(timezone.utc)

    after = {
        code: _count_refs(db, code)
        for code in list(CANONICAL_SYSTEMS) + list(old_systems_touched)
    }
    db.add(GovernAuditLog(
        module="systems",
        entity_type="business_system_normalize",
        entity_ref=approval_ref,
        action="apply",
        operator="script:normalize_business_systems",
        after_data={
            "change_count": plan["change_count"],
            "source_count": plan["source_count"],
            "after_refs": after,
        },
    ))
    db.commit()
    plan["applied"] = True
    plan["after_system_refs"] = after
    plan["approval_ref"] = approval_ref
    return plan


def main():
    parser = argparse.ArgumentParser(description="Normalize business systems (platform DB only)")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", type=str, default="")
    parser.add_argument("--approval-ref", type=str, default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plan = build_plan(db)
        plan["applied"] = False
        if args.apply:
            if args.confirmation != CONFIRMATION:
                raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
            approval = args.approval_ref or f"normalize-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            plan = apply_plan(db, plan, approval)
        text_out = json.dumps(plan, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(text_out, encoding="utf-8")
        print(text_out)
    finally:
        db.close()


if __name__ == "__main__":
    main()
