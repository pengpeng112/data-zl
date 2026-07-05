from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.db import get_db
from ...models.dict_general import (
    DictCategory,
    DictItemMapping,
    DictStandardItem,
    DictSystemItem,
    DictVersion,
)
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/dictionaries", tags=["dictionaries"])


# ── Categories ──

class CategoryUpsert(BaseModel):
    category_code: str
    category_name_cn: str
    standard_system: str | None = None
    description_cn: str | None = None
    enabled: bool = True


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(DictCategory).order_by(DictCategory.category_code)).all()
    return ApiResponse(data=[
        {"id": r.id, "category_code": r.category_code, "category_name_cn": r.category_name_cn,
         "standard_system": r.standard_system, "enabled": r.enabled}
        for r in rows
    ])


@router.put("/categories")
def upsert_category(req: CategoryUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictCategory).where(DictCategory.category_code == req.category_code))
    if existing:
        existing.category_name_cn = req.category_name_cn
        existing.standard_system = req.standard_system
        existing.description_cn = req.description_cn
        existing.enabled = req.enabled
        existing.updated_at = datetime.now(timezone.utc)
        c = existing
    else:
        c = DictCategory(**req.model_dump())
        db.add(c)
    db.commit()
    db.refresh(c)
    return ApiResponse(data={"id": c.id, "category_code": c.category_code})


# ── Standard Items ──

class StandardItemUpsert(BaseModel):
    category_code: str
    standard_code: str
    standard_name_cn: str
    standard_name_en: str | None = None
    parent_code: str | None = None
    pinyin_code: str | None = None
    wubi_code: str | None = None
    status: str | None = "active"
    effective_from: str | None = None
    effective_to: str | None = None
    description_cn: str | None = None
    extra: dict | None = None


@router.get("/standard-items")
def list_standard_items(
    category_code: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictStandardItem)
    if category_code:
        stmt = stmt.where(DictStandardItem.category_code == category_code)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            DictStandardItem.standard_name_cn.ilike(like)
            | DictStandardItem.standard_code.ilike(like)
            | DictStandardItem.standard_name_en.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(DictStandardItem.category_code, DictStandardItem.standard_code).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {"id": r.id, "category_code": r.category_code, "standard_code": r.standard_code,
         "standard_name_cn": r.standard_name_cn, "status": r.status}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.put("/standard-items")
def upsert_standard_item(req: StandardItemUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictStandardItem).where(
        DictStandardItem.category_code == req.category_code,
        DictStandardItem.standard_code == req.standard_code,
    ))
    if existing:
        for k, v in req.model_dump().items():
            if k != "extra":
                setattr(existing, k, v)
        existing.extra = req.extra
        item = existing
    else:
        item = DictStandardItem(**req.model_dump())
        db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data={"id": item.id})


# ── System Items ──

@router.get("/system-items")
def list_system_items(
    category_code: str | None = Query(None),
    system_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(DictSystemItem)
    if category_code:
        stmt = stmt.where(DictSystemItem.category_code == category_code)
    if system_code:
        stmt = stmt.where(DictSystemItem.system_code == system_code)
    rows = db.scalars(stmt.order_by(DictSystemItem.system_code, DictSystemItem.system_item_code)).all()
    return ApiResponse(data=[
        {"id": r.id, "category_code": r.category_code, "system_code": r.system_code,
         "system_item_code": r.system_item_code, "system_item_name_cn": r.system_item_name_cn,
         "source_table": r.source_table, "raw_status": r.raw_status}
        for r in rows
    ])


class SystemItemImport(BaseModel):
    category_code: str
    system_code: str
    items: list[dict]


@router.post("/import")
def import_system_items(req: SystemItemImport, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    count = 0
    for item in req.items:
        existing = db.scalar(select(DictSystemItem).where(
            DictSystemItem.category_code == req.category_code,
            DictSystemItem.system_code == req.system_code,
            DictSystemItem.system_item_code == item.get("system_item_code", ""),
        ))
        if existing:
            existing.system_item_name_cn = item.get("system_item_name_cn", "")
            existing.last_sync_at = datetime.now(timezone.utc)
        else:
            db.add(DictSystemItem(
                category_code=req.category_code,
                system_code=req.system_code,
                system_item_code=item.get("system_item_code", ""),
                system_item_name_cn=item.get("system_item_name_cn", ""),
                source_table=item.get("source_table"),
                source_key_column=item.get("source_key_column"),
                source_name_column=item.get("source_name_column"),
                last_sync_at=datetime.now(timezone.utc),
            ))
        count += 1
    db.commit()
    return ApiResponse(data={"imported": count})


# ── Item Mappings ──

class ItemMappingUpsert(BaseModel):
    category_code: str
    standard_code: str | None = None
    system_code: str
    system_item_code: str
    mapping_type: str | None = "manual"
    confidence: str | None = None


@router.get("/mappings")
def list_item_mappings(
    category_code: str | None = Query(None),
    review_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictItemMapping)
    if category_code:
        stmt = stmt.where(DictItemMapping.category_code == category_code)
    if review_status:
        stmt = stmt.where(DictItemMapping.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(DictItemMapping.category_code).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {"id": r.id, "category_code": r.category_code, "standard_code": r.standard_code,
         "system_code": r.system_code, "system_item_code": r.system_item_code,
         "mapping_type": r.mapping_type, "confidence": r.confidence, "review_status": r.review_status}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.put("/mappings")
def upsert_item_mapping(req: ItemMappingUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    m = DictItemMapping(
        category_code=req.category_code, standard_code=req.standard_code,
        system_code=req.system_code, system_item_code=req.system_item_code,
        mapping_type=req.mapping_type or "manual", confidence=req.confidence,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return ApiResponse(data={"id": m.id})


# ── Versions ──

class VersionCreate(BaseModel):
    category_code: str
    version_no: str
    version_name_cn: str | None = None
    note: str | None = None


@router.get("/versions")
def list_versions(
    category_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(DictVersion)
    if category_code:
        stmt = stmt.where(DictVersion.category_code == category_code)
    rows = db.scalars(stmt.order_by(DictVersion.category_code, DictVersion.publish_status, DictVersion.version_no.desc())).all()
    return ApiResponse(data=[
        {"id": r.id, "category_code": r.category_code, "version_no": r.version_no,
         "version_name_cn": r.version_name_cn, "publish_status": r.publish_status,
         "published_by": r.published_by, "published_at": r.published_at.isoformat() if r.published_at else None}
        for r in rows
    ])


@router.put("/versions")
def upsert_version(req: VersionCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictVersion).where(
        DictVersion.category_code == req.category_code,
        DictVersion.version_no == req.version_no,
    ))
    if existing:
        existing.version_name_cn = req.version_name_cn
        existing.note = req.note
        v = existing
    else:
        v = DictVersion(**req.model_dump())
        db.add(v)
    db.commit()
    db.refresh(v)
    return ApiResponse(data={"id": v.id, "version_no": v.version_no})
