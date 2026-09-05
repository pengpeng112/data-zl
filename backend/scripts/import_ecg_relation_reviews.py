"""Import validated ECG relation candidates into relation-review drafts.

The 155 snapshot contains seven internal C-grade candidates and two deferred
cross-system D-grade candidates.  Only candidates whose endpoint tables and
columns exist in platform metadata are imported.  Nothing is promoted to the
formal relation layer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal  # noqa: E402
from app.models.asset import AssetColumn, AssetRelation, AssetRelationReview, AssetTable  # noqa: E402

DEFAULT_JSON = REPO_DIR / "开发起步包" / "155_ECG元数据导入与关系候选_结果.json"
EVIDENCE = "155 ECG metadata snapshot 2026-08-27; candidate-only; no declared FK"


def _table_name(value: str) -> str:
    return value.split(".")[-1]


def _condition(item: dict) -> str:
    pairs = zip(item["from_columns"], item["to_columns"], strict=True)
    return " AND ".join(
        f"{item['from_table']}.{left} = {item['to_table']}.{right}"
        for left, right in pairs
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    args = parser.parse_args()
    payload = json.loads(Path(args.json).read_text(encoding="utf-8"))

    db = SessionLocal()
    summary = {"dry_run": args.dry_run, "inserted": 0, "existing": 0, "blocked": []}
    try:
        next_id = (db.scalar(select(func.max(AssetRelationReview.id))) or 0) + 1
        for item in payload["candidates"]:
            source_code = item["source_code"]
            missing: list[str] = []
            for side in ("from", "to"):
                table_name = _table_name(item[f"{side}_table"])
                table = db.scalar(
                    select(AssetTable).where(
                        AssetTable.source_code == source_code,
                        AssetTable.table_name == table_name,
                    )
                )
                if table is None:
                    missing.append(f"{side}_table:{item[f'{side}_table']}")
                    continue
                for column_name in item[f"{side}_columns"]:
                    exists = db.scalar(
                        select(AssetColumn.id).where(
                            AssetColumn.source_code == source_code,
                            AssetColumn.table_name == table_name,
                            AssetColumn.column_name == column_name,
                        )
                    )
                    if exists is None:
                        missing.append(f"{side}_column:{table_name}.{column_name}")
            if missing:
                summary["blocked"].append({"edge": item["join_condition"], "reason": missing})
                continue

            condition = _condition(item)
            formal = db.scalar(
                select(AssetRelation.rel_id).where(
                    AssetRelation.from_table == item["from_table"],
                    AssetRelation.to_table == item["to_table"],
                    AssetRelation.join_condition == condition,
                )
            )
            review = db.scalar(
                select(AssetRelationReview.id).where(
                    AssetRelationReview.from_table == item["from_table"],
                    AssetRelationReview.to_table == item["to_table"],
                    AssetRelationReview.join_condition == condition,
                )
            )
            if formal is not None or review is not None:
                summary["existing"] += 1
                continue

            if not args.dry_run:
                db.add(
                    AssetRelationReview(
                        id=next_id,
                        relation_scope="formal",
                        from_system_code="ECG",
                        from_source_code=source_code,
                        from_table=item["from_table"],
                        from_columns="+".join(item["from_columns"]),
                        to_system_code="ECG",
                        to_source_code=source_code,
                        to_table=item["to_table"],
                        to_columns="+".join(item["to_columns"]),
                        join_condition=condition,
                        relation_desc_cn=item["join_condition"],
                        business_logic_cn=item.get("qualifiers") or None,
                        confidence=item["confidence"],
                        validation_status="pending",
                        review_status="draft",
                        source_evidence=f"{EVIDENCE}; {item.get('warnings', '')}"[:2000],
                    )
                )
                next_id += 1
            summary["inserted"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
