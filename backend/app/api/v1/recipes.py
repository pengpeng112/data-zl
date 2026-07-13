"""Relationship recipe & view formula library - read-only first phase."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, or_, Text
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.recipe import AssetRelationRecipe
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


@router.get("", summary="配方列表（按业务域/表名/视图名/状态检索）")
def list_recipes(
    domain: str | None = Query(None),
    business_domain: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    ai_readable: bool | None = Query(None, description="true=仅返回 AI 可读配方"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetRelationRecipe)
    if domain:
        stmt = stmt.where(AssetRelationRecipe.domain == domain)
    if business_domain:
        stmt = stmt.where(AssetRelationRecipe.business_domain == business_domain)
    if status:
        stmt = stmt.where(AssetRelationRecipe.status == status)
    if ai_readable:
        stmt = stmt.where(AssetRelationRecipe.ai_readable == True)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(
            AssetRelationRecipe.recipe_id.ilike(like),
            AssetRelationRecipe.description.ilike(like),
            AssetRelationRecipe.recommended_view_name.ilike(like),
            AssetRelationRecipe.primary_tables.cast(Text).ilike(like),
        ))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetRelationRecipe.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "recipe_id": r.recipe_id, "status": r.status,
            "domain": r.domain, "source_system": r.source_system,
            "recommended_view_name": r.recommended_view_name,
            "description": r.description, "business_domain": r.business_domain,
            "primary_tables": r.primary_tables, "joins": r.joins,
            "ai_readable": r.ai_readable,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/{recipe_id}", summary="配方详情")
def get_recipe(
    recipe_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    r = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id))
    if not r:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="配方不存在")
    return ApiResponse(data={
        "id": r.id, "recipe_id": r.recipe_id, "status": r.status,
        "domain": r.domain, "source_system": r.source_system,
        "recommended_view_name": r.recommended_view_name,
        "description": r.description, "business_domain": r.business_domain,
        "primary_tables": r.primary_tables, "joins": r.joins,
        "ai_readable": r.ai_readable,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    })


@router.get("/ai/context", summary="AI 可读的配方上下文（仅 formal/user_confirmed/verified）")
def ai_context(
    domain: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(AssetRelationRecipe).where(
        AssetRelationRecipe.ai_readable == True,
        AssetRelationRecipe.status.in_(["formal", "user_confirmed", "verified"]),
    )
    if domain:
        stmt = stmt.where(AssetRelationRecipe.domain == domain)
    rows = db.scalars(stmt.order_by(AssetRelationRecipe.domain, AssetRelationRecipe.recipe_id)).all()
    return ApiResponse(data=[
        {
            "recipe_id": r.recipe_id, "status": r.status, "domain": r.domain,
            "recommended_view_name": r.recommended_view_name,
            "description": r.description,
            "primary_tables": r.primary_tables, "joins": r.joins,
        }
        for r in rows
    ])
