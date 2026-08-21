"""134 号 · 取数 SQL 关系摄取：写入 asset_relation_reviews draft。

历史 SQL 只作证据。本脚本只登记复核草稿，不批准、不写正式 relationships。
按 from_table + to_table + join_condition 防重。

用法:
    python -m scripts.import_query_sql_relation_reviews --dry-run
    python -m scripts.import_query_sql_relation_reviews
    python -m scripts.import_query_sql_relation_reviews --json path/to.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.asset import AssetRelationReview

DEFAULT_JSON = REPO_DIR / "开发起步包" / "134_取数SQL关系摄取候选.json"
EVIDENCE_PREFIX = "134 取数SQL关系摄取"


def load_payload(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    reviews = data.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise SystemExit(f"no reviews in {path}")
    return reviews


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", dest="json_path", default=str(DEFAULT_JSON))
    args = parser.parse_args()
    payload = load_payload(Path(args.json_path))
    db = SessionLocal()
    summary = {
        "inserted": 0,
        "updated": 0,
        "skipped_existing": [],
        "ids": [],
        "dry_run": args.dry_run,
        "source": args.json_path,
    }
    try:
        next_id = (db.scalar(select(func.max(AssetRelationReview.id))) or 0) + 1
        for rel in payload:
            files = "; ".join(rel.get("source_files") or [])
            evidence = f"{EVIDENCE_PREFIX} {rel['key']}; n={rel.get('evidence_count', 0)}; {files}"
            replace_id = rel.get("replace_review_id")
            target = None
            if replace_id is not None:
                target = db.get(AssetRelationReview, int(replace_id))
                if target is None:
                    raise SystemExit(f"{rel['key']} replace_review_id={replace_id} not found")
            else:
                target = db.scalar(
                    select(AssetRelationReview).where(
                        AssetRelationReview.from_table == rel["from_table"],
                        AssetRelationReview.to_table == rel["to_table"],
                        AssetRelationReview.join_condition == rel["join_condition"],
                    )
                )
                if target is not None:
                    summary["skipped_existing"].append(
                        f"{rel['key']} (id={target.id}, status={target.review_status})"
                    )
                    continue
            if replace_id is not None:
                if not args.dry_run:
                    target.from_system_code = rel["from_system_code"]
                    target.from_source_code = rel["from_source_code"]
                    target.from_table = rel["from_table"]
                    target.from_columns = rel["from_columns"]
                    target.to_system_code = rel["to_system_code"]
                    target.to_source_code = rel["to_source_code"]
                    target.to_table = rel["to_table"]
                    target.to_columns = rel["to_columns"]
                    target.join_condition = rel["join_condition"]
                    target.relation_desc_cn = rel["desc"]
                    target.business_logic_cn = rel.get("logic")
                    target.confidence = rel["confidence"]
                    target.validation_status = "pending"
                    target.review_status = "draft"
                    target.source_evidence = evidence[:2000]
                summary["updated"] += 1
                summary["ids"].append({"key": rel["key"], "id": int(replace_id), "action": "update"})
                continue
            if not args.dry_run:
                rec = AssetRelationReview(
                    id=next_id,
                    relation_scope="formal",
                    from_system_code=rel["from_system_code"],
                    from_source_code=rel["from_source_code"],
                    from_table=rel["from_table"],
                    from_columns=rel["from_columns"],
                    to_system_code=rel["to_system_code"],
                    to_source_code=rel["to_source_code"],
                    to_table=rel["to_table"],
                    to_columns=rel["to_columns"],
                    join_condition=rel["join_condition"],
                    relation_desc_cn=rel["desc"],
                    business_logic_cn=rel.get("logic"),
                    confidence=rel["confidence"],
                    validation_status="pending",
                    review_status="draft",
                    source_evidence=evidence[:2000],
                )
                db.add(rec)
                summary["ids"].append({"key": rel["key"], "id": next_id, "action": "insert"})
                next_id += 1
            else:
                summary["ids"].append({"key": rel["key"], "id": "dry-run", "action": "insert"})
            summary["inserted"] += 1
        if not args.dry_run:
            db.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as exc:
        db.rollback()
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
