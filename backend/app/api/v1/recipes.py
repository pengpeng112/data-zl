"""Versioned relationship recipes; SQL generation is preview-only."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select, Text
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.recipe import AssetRelationRecipe
from ...schemas.common import ApiResponse
from ...schemas.recipe import RecipeCreate, RecipeDraftUpdate, RecipeReview, RecipeSqlGenerateRequest
from ...services.recipe_service import assert_transition, canonical_recipe_payload, generate_select_sql, recipe_hash

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


def _item(row: AssetRelationRecipe) -> dict:
    return {"id": row.id, "recipe_id": row.recipe_id, "version": row.version, "recipe_name": row.recipe_name, "status": row.status, "is_active": row.is_active, "domain": row.domain, "source_system": row.source_system, "recommended_view_name": row.recommended_view_name, "description": row.description, "business_domain": row.business_domain, "primary_tables": row.primary_tables, "joins": row.joins, "recipe_json": row.recipe_json, "ai_readable": row.ai_readable, "content_hash": row.content_hash, "created_by": row.created_by, "updated_by": row.updated_by, "reviewed_by": row.reviewed_by, "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None, "created_at": row.created_at.isoformat() if row.created_at else None, "updated_at": row.updated_at.isoformat() if row.updated_at else None}


@router.get("/ai/context", summary="AI 可读配方上下文")
def ai_context(domain: str | None = Query(None), db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    stmt = select(AssetRelationRecipe).where(AssetRelationRecipe.ai_readable.is_(True), AssetRelationRecipe.status == "active", AssetRelationRecipe.is_active.is_(True))
    if domain: stmt = stmt.where(AssetRelationRecipe.domain == domain)
    return ApiResponse(data=[_item(row) for row in db.scalars(stmt.order_by(AssetRelationRecipe.recipe_id, AssetRelationRecipe.version)).all()])


@router.get("")
def list_recipes(domain: str | None = Query(None), business_domain: str | None = Query(None), status: str | None = Query(None), keyword: str | None = Query(None), page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=200), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    stmt = select(AssetRelationRecipe)
    if domain: stmt = stmt.where(AssetRelationRecipe.domain == domain)
    if business_domain: stmt = stmt.where(AssetRelationRecipe.business_domain == business_domain)
    if status: stmt = stmt.where(AssetRelationRecipe.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(AssetRelationRecipe.recipe_id.ilike(like), AssetRelationRecipe.description.ilike(like), AssetRelationRecipe.recipe_name.ilike(like), AssetRelationRecipe.primary_tables.cast(Text).ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AssetRelationRecipe.recipe_id, AssetRelationRecipe.version.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": [_item(row) for row in rows]})


@router.get("/{recipe_id}/versions")
def list_versions(recipe_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=[_item(row) for row in db.scalars(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id).order_by(AssetRelationRecipe.version.desc())).all()])


@router.get("/{recipe_id}/versions/{version}")
def get_version(recipe_id: str, version: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id, AssetRelationRecipe.version == version))
    if not row: raise HTTPException(status_code=404, detail="配方版本不存在")
    return ApiResponse(data=_item(row))


@router.get("/{recipe_id}")
def get_recipe(recipe_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id, AssetRelationRecipe.is_active.is_(True)).order_by(AssetRelationRecipe.version.desc()))
    if not row: row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id).order_by(AssetRelationRecipe.version.desc()))
    if not row: raise HTTPException(status_code=404, detail="配方不存在")
    return ApiResponse(data=_item(row))


@router.post("", dependencies=[Depends(require_permission("recipe:create"))])
def create_recipe(req: RecipeCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = get_current_user(request)
    if db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == req.recipe_id)):
        raise HTTPException(status_code=409, detail="recipe_id 已存在，请创建新版本")
    payload = req.recipe_json or {"primary_tables": req.primary_tables, "joins": req.joins}
    row = AssetRelationRecipe(recipe_id=req.recipe_id, version=1, recipe_name=req.recipe_name, status="draft", domain=req.domain, source_system=req.source_system, business_domain=req.business_domain, description=req.description, primary_tables=req.primary_tables, joins=req.joins, recipe_json=canonical_recipe_payload(payload), content_hash=recipe_hash(payload), created_by=user, updated_by=user, ai_readable=False)
    db.add(row); db.commit(); db.refresh(row)
    return ApiResponse(data=_item(row))


@router.post("/{recipe_id}/versions", dependencies=[Depends(require_permission("recipe:create"))])
def copy_version(recipe_id: str, request: Request, version: int | None = Query(None), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    user = get_current_user(request)
    source = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id, *( [AssetRelationRecipe.version == version] if version else [] )).order_by(AssetRelationRecipe.version.desc()))
    if not source: raise HTTPException(status_code=404, detail="源配方不存在")
    next_version = (db.scalar(select(func.max(AssetRelationRecipe.version)).where(AssetRelationRecipe.recipe_id == recipe_id)) or 0) + 1
    row = AssetRelationRecipe(recipe_id=recipe_id, version=next_version, parent_version_id=source.id, recipe_name=source.recipe_name, status="draft", domain=source.domain, source_system=source.source_system, business_domain=source.business_domain, description=source.description, primary_tables=source.primary_tables, joins=source.joins, recipe_json=source.recipe_json, content_hash=source.content_hash, created_by=user, updated_by=user, ai_readable=False)
    db.add(row); db.commit(); db.refresh(row)
    return ApiResponse(data=_item(row))


@router.put("/{recipe_id}/versions/{version}", dependencies=[Depends(require_permission("recipe:edit"))])
def update_version(recipe_id: str, version: int, req: RecipeDraftUpdate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id, AssetRelationRecipe.version == version))
    if not row: raise HTTPException(status_code=404, detail="配方版本不存在")
    if row.status != "draft": raise HTTPException(status_code=400, detail="只有 draft 版本可编辑")
    user = get_current_user(request); data = req.model_dump(exclude_unset=True)
    for key, value in data.items(): setattr(row, key, value)
    payload = {**(row.recipe_json or {}), "primary_tables": row.primary_tables or [], "joins": row.joins or []}
    row.recipe_json, row.content_hash, row.updated_by, row.updated_at = canonical_recipe_payload(payload), recipe_hash(payload), user, datetime.now(timezone.utc)
    db.commit(); db.refresh(row)
    return ApiResponse(data=_item(row))


def _transition(recipe_id: str, version: int, target: str, reason: str | None, request: Request, db: Session) -> dict:
    row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id, AssetRelationRecipe.version == version))
    if not row: raise HTTPException(status_code=404, detail="配方版本不存在")
    assert_transition(row.status, target); user = get_current_user(request)
    row.status, row.updated_by = target, user
    row.review_reason = reason
    if target == "active":
        db.query(AssetRelationRecipe).filter(AssetRelationRecipe.recipe_id == recipe_id, AssetRelationRecipe.id != row.id).update({"is_active": False})
        row.is_active, row.ai_readable = True, True
    elif target != "active": row.is_active, row.ai_readable = False, False
    if target in {"approved", "deprecated"}: row.reviewed_by, row.reviewed_at = user, datetime.now(timezone.utc)
    db.commit(); db.refresh(row); return _item(row)


@router.post("/{recipe_id}/versions/{version}/submit", dependencies=[Depends(require_permission("recipe:edit"))])
def submit(recipe_id: str, version: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]: return ApiResponse(data=_transition(recipe_id, version, "submitted", None, request, db))


@router.post("/{recipe_id}/versions/{version}/approve", dependencies=[Depends(require_permission("recipe:review"))])
def approve(recipe_id: str, version: int, req: RecipeReview, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]: return ApiResponse(data=_transition(recipe_id, version, "approved", req.reason, request, db))


@router.post("/{recipe_id}/versions/{version}/reject", dependencies=[Depends(require_permission("recipe:review"))])
def reject(recipe_id: str, version: int, req: RecipeReview, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]: return ApiResponse(data=_transition(recipe_id, version, "draft", req.reason, request, db))


@router.post("/{recipe_id}/versions/{version}/activate", dependencies=[Depends(require_permission("recipe:activate"))])
def activate(recipe_id: str, version: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]: return ApiResponse(data=_transition(recipe_id, version, "active", None, request, db))


@router.post("/{recipe_id}/versions/{version}/deprecate", dependencies=[Depends(require_permission("recipe:activate"))])
def deprecate(recipe_id: str, version: int, req: RecipeReview, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]: return ApiResponse(data=_transition(recipe_id, version, "deprecated", req.reason, request, db))


@router.post("/{recipe_id}/versions/{version}/sql", dependencies=[Depends(require_permission("recipe:sql_generate"))])
def generate_sql(recipe_id: str, version: int, req: RecipeSqlGenerateRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = db.scalar(select(AssetRelationRecipe).where(AssetRelationRecipe.recipe_id == recipe_id, AssetRelationRecipe.version == version))
    if not row: raise HTTPException(status_code=404, detail="配方版本不存在")
    tables = row.primary_tables or []
    if not tables: raise HTTPException(status_code=400, detail="配方没有主表，无法生成 SQL")
    sql = generate_select_sql(tables, row.joins or [])
    return ApiResponse(data={"recipe_id": recipe_id, "version": version, "dialect": req.dialect, "sql": sql, "executed": False})
