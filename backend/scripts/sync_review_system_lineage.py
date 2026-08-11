"""Apply user-confirmed review-system lineage to the platform catalog only.

This script reads local metadata snapshots.  It never connects to, or writes to,
any business source database.  Apply mode only changes asset.asset_* metadata.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetRelation, AssetTable
from app.services.relation_identity import populate_endpoint_fields

DOMAIN = "REVIEW_SYSTEM_LINEAGE"
CONFIRMATION = "SYNC-REVIEW-SYSTEM-LINEAGE"
PERIOD_MTL = "[review_source_period:before_2025]"
PERIOD_JHEMR = "[review_source_period:from_2025]"


def _find_snapshot(pattern: str) -> Path:
    matches = sorted((REPO_DIR / "开发起步包").glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one snapshot for {pattern}, found {len(matches)}")
    return matches[0]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dc_names(snapshot: dict, schema: str) -> set[str]:
    item = snapshot["schemas"][schema]
    return {str(name).upper() for name in item.get("tables", {})} | {
        str(name).upper() for name in item.get("views", {})
    }


def build_plan(data_center: Path, docare: Path) -> dict:
    dc = _load(data_center)
    doc = _load(docare)
    sm_names = _dc_names(dc, "SM")
    docare_names = {
        str(row["table_name"]).upper() for row in doc.get("tables", []) + doc.get("views", [])
    }
    synchronized = sorted(sm_names & docare_names)

    relations = [
        {
            "from_table": "HRP.EMR_HOS_PRACTITIONER",
            "to_table": "V1.3.EMR_HOS_PRACTITIONER_INFORMATION",
            "join_condition": "physical view maps to logical standard dataset",
            "validation_status": "user_confirmed_mapping",
            "note": "Keep the physical short name; do not rename or modify the HRP source view.",
        }
    ]
    for suffix in ("", "_ITEM", "_ALLERGY", "_IMAGE"):
        relations.append(
            {
                "from_table": f"rmcloudlis7.dbo.V_EMR_INSPECTION{suffix}",
                "to_table": f"ODS.V_EMR_INSPECTION{suffix}_TEST",
                "join_condition": "parallel implementations retained for separate review",
                "validation_status": "user_confirmed_parallel_sources",
                "note": "Both implementations are parsed after LIS replacement; this is not a row-level join or reporting-source selection.",
            }
        )
    for name in synchronized:
        relations.append(
            {
                "from_table": f"DOCARE.{name}",
                "to_table": f"SM.{name}",
                "join_condition": "same-name object synchronized from Docare to data-center SM",
                "validation_status": "user_confirmed_sync",
                "note": "SM is a synchronized subset; Docare is the more complete source. Same-name identity does not imply a business foreign key.",
            }
        )
    return {
        "relations": relations,
        "summary": {
            "hrp_logical_mappings": 1,
            "lis_parallel_pairs": 4,
            "docare_objects": len(docare_names),
            "sm_objects": len(sm_names),
            "docare_sm_same_name_sync": len(synchronized),
            "mtl_jhemr_policy": "MTL before 2025; JHEMR from 2025 onward",
            "source_writes": 0,
        },
    }


def _append_period(note: str | None, marker: str) -> str:
    value = note or ""
    if marker in value:
        return value
    return f"{value}; {marker}".strip("; ")


def apply_plan(db, plan: dict) -> dict:
    db.execute(delete(AssetRelation).where(AssetRelation.domain == DOMAIN))
    next_rel_id = (db.scalar(select(func.max(AssetRelation.rel_id))) or 0) + 1
    for offset, row in enumerate(plan["relations"]):
        _rel = AssetRelation(
                rel_id=next_rel_id + offset,
                domain=DOMAIN,
                from_table=row["from_table"],
                from_columns="",
                to_table=row["to_table"],
                to_columns="",
                join_condition=row["join_condition"],
                confidence="A",
                validation_level="user_confirmed_2026_07_15",
                validation_status=row["validation_status"],
                note=row["note"],
            )
        populate_endpoint_fields(db, _rel)
        db.add(_rel)

    mtl_rows = db.scalars(select(AssetTable).where(AssetTable.schema_name == "MTL")).all()
    jhemr_rows = db.scalars(
        select(AssetTable).where(
            (func.lower(AssetTable.source_code).like("%jhemr%"))
            | (func.lower(AssetTable.system_code).like("%jhemr%"))
        )
    ).all()
    for row in mtl_rows:
        row.note = _append_period(row.note, PERIOD_MTL)
    for row in jhemr_rows:
        row.note = _append_period(row.note, PERIOD_JHEMR)
    return {
        "relations": len(plan["relations"]),
        "mtl_assets_marked": len(mtl_rows),
        "jhemr_assets_marked": len(jhemr_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-center-snapshot", type=Path)
    parser.add_argument("--docare-snapshot", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    data_center = args.data_center_snapshot or _find_snapshot("08_*快照.json")
    docare = args.docare_snapshot or _find_snapshot("80_*快照.json")
    plan = build_plan(data_center, docare)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "writes": 0, **plan["summary"]}, ensure_ascii=False, indent=2))
        return
    if args.confirmation != CONFIRMATION:
        raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
    with SessionLocal() as db:
        applied = apply_plan(db, plan)
        db.commit()
    print(json.dumps({"mode": "apply", "status": "succeeded", **applied, "source_writes": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
