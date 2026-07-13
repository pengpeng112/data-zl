"""Import view_relation_recipes.json into asset_relation_recipes table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal
from app.models.recipe import AssetRelationRecipe
from sqlalchemy import select


def import_recipes() -> int:
    recipes_path = (
        Path(__file__).resolve().parents[3] / "开发起步包" / "数据资产_关系图谱" / "view_relation_recipes.json"
    )
    with open(recipes_path, encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    count = 0
    try:
        for item in data:
            recipe_id = item["recipe_id"]
            existing = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id))
            if existing:
                existing.status = item.get("status", "candidate")
                existing.domain = item.get("domain")
                existing.source_system = item.get("source_system")
                existing.recommended_view_name = item.get("recommended_view_name")
                existing.description = item.get("description")
                existing.business_domain = item.get("business_domain", item.get("domain"))
                existing.primary_tables = item.get("primary_tables", [])
                existing.joins = item.get("joins", [])
                existing.imported_from = "view_relation_recipes.json"
            else:
                db.add(AssetRelationRecipe(
                    recipe_id=recipe_id,
                    status=item.get("status", "candidate"),
                    domain=item.get("domain"),
                    source_system=item.get("source_system"),
                    recommended_view_name=item.get("recommended_view_name"),
                    description=item.get("description"),
                    business_domain=item.get("business_domain", item.get("domain")),
                    primary_tables=item.get("primary_tables", []),
                    joins=item.get("joins", []),
                    imported_from="view_relation_recipes.json",
                ))
            count += 1
        db.commit()
        print(f"Imported {count} recipes from view_relation_recipes.json")
    finally:
        db.close()
    return count


if __name__ == "__main__":
    import_recipes()
