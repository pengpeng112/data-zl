"""Backfill from/to_system_code + source_code for plan139/143 review drafts.

Root cause (fixed in plan139_common): review evidence lacked system
attribution, so the 56 four-source drafts (run 142) and 5 OA drafts (run 143)
were inserted with NULL from/to_system_code.  This script derives the
attribution from the endpoint namespace prefix, updates only rows carrying the
plan139/oa batch tags with NULL attribution, and never touches anything else.

Dry-run by default; apply requires --confirm FIX-PLAN139-REVIEW-ATTRIBUTION.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CONFIRM = "FIX-PLAN139-REVIEW-ATTRIBUTION"

PREFIX_MAP = {
    "CORE2DB.": ("CORE2DB", "core2db_mysql_10_10_8_135"),
    "EIS.": ("PHYSICAL_EXAM", "physical_exam_sqlserver_10_10_10_96"),
    "JZCIS.": ("PHYSICAL_EXAM", "physical_exam_sqlserver_10_10_10_96"),
    "ZONEKINGNET.": ("PHYSICAL_EXAM", "physical_exam_sqlserver_10_10_10_96"),
    "PITAYA.": ("PATHOLOGY", "pathology_sqlserver_10_10_9_41"),
    "QPIS.": ("PATHOLOGY", "pathology_sqlserver_10_10_9_41"),
    "TJDATABASE4.": ("OCCUPATIONAL_DISEASE", "occupational_disease_sqlserver_10_10_8_96"),
    "OA.": ("OA", "oa_sqlserver_10_10_10_69"),
}


def _attribute(table: str | None) -> tuple[str, str] | None:
    name = str(table or "").upper()
    for prefix, pair in PREFIX_MAP.items():
        if name.startswith(prefix):
            return pair
    return None


def execute(apply: bool, confirm: str) -> dict:
    if apply and confirm != CONFIRM:
        raise RuntimeError(f"apply requires --confirm {CONFIRM}")
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models.asset import AssetRelationReview

    summary = {"mode": "apply" if apply else "dry_run", "candidates": 0, "updated": 0,
               "skipped_prefix_unknown": 0, "skipped_mismatch": 0, "unchanged": 0, "details": []}
    with SessionLocal() as db:
        rows = db.scalars(
            select(AssetRelationReview).where(
                AssetRelationReview.review_note.contains("plan139_four_sources_"),
                AssetRelationReview.from_system_code.is_(None),
            )
        ).all()
        for row in rows:
            summary["candidates"] += 1
            left = _attribute(row.from_table)
            right = _attribute(row.to_table)
            if left is None or right is None:
                summary["skipped_prefix_unknown"] += 1
                continue
            if left[0] != right[0]:
                summary["skipped_mismatch"] += 1
                continue
            system_code, source_code = left
            if apply:
                row.from_system_code = system_code
                row.to_system_code = system_code
                row.from_source_code = source_code
                row.to_source_code = source_code
                summary["updated"] += 1
            summary["details"].append({"id": row.id, "from": row.from_table, "to": row.to_table,
                                       "system": system_code})
        if apply:
            db.commit()
        else:
            db.rollback()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = execute(args.apply, args.confirm)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
