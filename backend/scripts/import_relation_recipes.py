"""Import view_relation_recipes.json into asset_relation_recipes table.

127 fixes:
- repo root = parents[2] (backend/scripts -> backend -> repo)
- preserve full recipe_json (field_logic/hard_rules/evidence/...)
- map seed status user_confirmed -> approved
- normalize join shape type/condition -> join_type/on
- --dry-run and content_hash idempotent upsert
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal
from app.models.recipe import AssetRelationRecipe
from app.services.recipe_service import (
    canonical_recipe_payload,
    map_seed_status,
    normalize_recipe_joins,
    recipe_hash,
)
from sqlalchemy import select


def recipes_seed_path() -> Path:
    # backend/scripts -> backend -> repo root
    return (
        Path(__file__).resolve().parents[2]
        / "开发起步包"
        / "数据资产_关系图谱"
        / "view_relation_recipes.json"
    )


def import_recipes(*, dry_run: bool = False, only_recipe_ids: set[str] | None = None) -> dict:
    path = recipes_seed_path()
    if not path.exists():
        raise FileNotFoundError(f"seed not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    created = 0
    updated = 0
    skipped = 0
    try:
        for item in data:
            recipe_id = item.get("recipe_id") or item.get("id")
            if not recipe_id:
                skipped += 1
                continue
            if only_recipe_ids and recipe_id not in only_recipe_ids:
                continue

            payload = canonical_recipe_payload(item)
            joins = normalize_recipe_joins(item.get("joins") or [])
            primary_tables = item.get("primary_tables") or []
            status = map_seed_status(item.get("status"))
            # Seed confirmed recipes land as approved, not auto-active
            is_active = False
            content = recipe_hash(payload)
            existing = db.scalar(
                select(AssetRelationRecipe)
                .where(AssetRelationRecipe.recipe_id == recipe_id)
                .order_by(AssetRelationRecipe.version.desc())
            )
            if existing and existing.content_hash == content:
                skipped += 1
                continue

            if dry_run:
                if existing:
                    updated += 1
                else:
                    created += 1
                continue

            if existing and existing.content_hash != content:
                # new version
                next_version = (existing.version or 1) + 1
                db.add(
                    AssetRelationRecipe(
                        recipe_id=recipe_id,
                        version=next_version,
                        recipe_name=item.get("recipe_name") or item.get("recommended_view_name"),
                        status=status,
                        is_active=is_active,
                        domain=item.get("domain"),
                        source_system=item.get("source_system"),
                        recommended_view_name=item.get("recommended_view_name"),
                        description=item.get("description"),
                        business_domain=item.get("business_domain", item.get("domain")),
                        primary_tables=primary_tables,
                        joins=joins,
                        recipe_json=payload,
                        content_hash=content,
                        imported_from="view_relation_recipes.json",
                        ai_readable=False,
                        evidence_summary=item.get("validation_evidence"),
                        risk_summary={
                            "hard_rules": item.get("hard_rules"),
                            "do_not_use_as_primary_join": item.get("do_not_use_as_primary_join"),
                        },
                    )
                )
                updated += 1
            elif existing:
                skipped += 1
            else:
                db.add(
                    AssetRelationRecipe(
                        recipe_id=recipe_id,
                        version=1,
                        recipe_name=item.get("recipe_name") or item.get("recommended_view_name"),
                        status=status,
                        is_active=is_active,
                        domain=item.get("domain"),
                        source_system=item.get("source_system"),
                        recommended_view_name=item.get("recommended_view_name"),
                        description=item.get("description"),
                        business_domain=item.get("business_domain", item.get("domain")),
                        primary_tables=primary_tables,
                        joins=joins,
                        recipe_json=payload,
                        content_hash=content,
                        imported_from="view_relation_recipes.json",
                        ai_readable=False,
                        evidence_summary=item.get("validation_evidence"),
                        risk_summary={
                            "hard_rules": item.get("hard_rules"),
                            "do_not_use_as_primary_join": item.get("do_not_use_as_primary_join"),
                        },
                    )
                )
                created += 1
        if not dry_run:
            db.commit()
        result = {
            "path": str(path),
            "dry_run": dry_run,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total_seed": len(data),
        }
        print(json.dumps(result, ensure_ascii=False))
        return result
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import relation recipes (127)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="*", help="optional recipe_id filter")
    args = parser.parse_args()
    import_recipes(dry_run=args.dry_run, only_recipe_ids=set(args.only) if args.only else None)
