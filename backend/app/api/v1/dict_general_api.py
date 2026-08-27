from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.dict_general import (
    DictCategory,
    DictItemMapping,
    DictStandardItem,
    DictSystemItem,
    DictVersion,
)
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/dictionaries", tags=["dictionaries"])

MAX_IMPORT_ITEMS = 1000
MAX_IMPORT_ERRORS = 20


def _audit(db: Session, *, action: str, entity_ref: str, operator: str, after: dict | None = None) -> None:
    db.add(GovernAuditLog(
        module="dict_general",
        entity_type="dictionary",
        entity_ref=entity_ref,
        action=action,
        operator=operator,
        after_data=after or {},
    ))


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Categories ──

class CategoryUpsert(BaseModel):
    category_code: str = Field(..., min_length=1, max_length=100)
    category_name_cn: str = Field(..., min_length=1, max_length=200)
    standard_system: str | None = None
    description_cn: str | None = None
    enabled: bool = True


@router.get("/categories", dependencies=[Depends(require_permission("dict.general.view"))])
def list_categories(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(select(DictCategory).order_by(DictCategory.category_code)).all()
    return ApiResponse(data=[
        {"id": r.id, "category_code": r.category_code, "category_name_cn": r.category_name_cn,
         "standard_system": r.standard_system, "enabled": r.enabled}
        for r in rows
    ])


@router.put("/categories", dependencies=[Depends(require_permission("dict.general.edit"))])
def upsert_category(req: CategoryUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    existing = db.scalar(select(DictCategory).where(DictCategory.category_code == req.category_code))
    if existing:
        existing.category_name_cn = req.category_name_cn
        existing.standard_system = req.standard_system
        existing.description_cn = req.description_cn
        existing.enabled = req.enabled
        existing.updated_at = _now()
        c = existing
    else:
        c = DictCategory(**req.model_dump())
        db.add(c)
    db.flush()
    _audit(db, action="upsert_category", entity_ref=req.category_code, operator=operator,
           after={"category_name_cn": req.category_name_cn, "enabled": req.enabled})
    _commit(db)
    db.refresh(c)
    return ApiResponse(data={"id": c.id, "category_code": c.category_code})


# ── Standard Items ──

class StandardItemUpsert(BaseModel):
    category_code: str = Field(..., min_length=1, max_length=100)
    standard_code: str = Field(..., min_length=1, max_length=200)
    standard_name_cn: str = Field(..., min_length=1, max_length=500)
    standard_name_en: str | None = None
    parent_code: str | None = None
    pinyin_code: str | None = None
    wubi_code: str | None = None
    status: str | None = "active"
    effective_from: str | None = None
    effective_to: str | None = None
    description_cn: str | None = None
    extra: dict | None = None


@router.get("/standard-items", dependencies=[Depends(require_permission("dict.general.view"))])
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


@router.put("/standard-items", dependencies=[Depends(require_permission("dict.general.edit"))])
def upsert_standard_item(req: StandardItemUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    if not db.scalar(select(DictCategory).where(DictCategory.category_code == req.category_code)):
        raise HTTPException(status_code=400, detail="category_code not found")
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
    db.flush()
    _audit(db, action="upsert_standard_item", entity_ref=f"{req.category_code}:{req.standard_code}", operator=operator)
    _commit(db)
    db.refresh(item)
    return ApiResponse(data={"id": item.id})


# ── System Items ──

@router.get("/system-items", dependencies=[Depends(require_permission("dict.general.view"))])
def list_system_items(
    category_code: str | None = Query(None),
    system_code: str | None = Query(None),
    keyword: str | None = Query(None),
    enabled: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictSystemItem)
    if category_code:
        stmt = stmt.where(DictSystemItem.category_code == category_code)
    if system_code:
        stmt = stmt.where(DictSystemItem.system_code == system_code)
    if enabled is not None:
        stmt = stmt.where(DictSystemItem.enabled.is_(enabled))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            DictSystemItem.system_item_code.ilike(like)
            | DictSystemItem.system_item_name_cn.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictSystemItem.system_code, DictSystemItem.system_item_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "category_code": r.category_code, "system_code": r.system_code,
         "system_item_code": r.system_item_code, "system_item_name_cn": r.system_item_name_cn,
         "source_table": r.source_table, "raw_status": r.raw_status, "enabled": r.enabled,
         "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class SystemItemUpsert(BaseModel):
    category_code: str = Field(..., min_length=1, max_length=100)
    system_code: str = Field(..., min_length=1, max_length=100)
    system_item_code: str = Field(..., min_length=1, max_length=200)
    system_item_name_cn: str = Field(..., min_length=1, max_length=500)
    source_table: str | None = None
    source_key_column: str | None = None
    source_name_column: str | None = None
    enabled: bool = True


@router.put("/system-items", dependencies=[Depends(require_permission("dict.general.edit"))])
def upsert_system_item(req: SystemItemUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    if not db.scalar(select(DictCategory).where(DictCategory.category_code == req.category_code)):
        raise HTTPException(status_code=400, detail="category_code not found")
    existing = db.scalar(select(DictSystemItem).where(
        DictSystemItem.category_code == req.category_code,
        DictSystemItem.system_code == req.system_code,
        DictSystemItem.system_item_code == req.system_item_code,
    ))
    created = existing is None
    if existing:
        existing.system_item_name_cn = req.system_item_name_cn
        existing.source_table = req.source_table
        existing.source_key_column = req.source_key_column
        existing.source_name_column = req.source_name_column
        existing.enabled = req.enabled
        existing.last_sync_at = _now()
        row = existing
    else:
        row = DictSystemItem(
            category_code=req.category_code,
            system_code=req.system_code,
            system_item_code=req.system_item_code,
            system_item_name_cn=req.system_item_name_cn,
            source_table=req.source_table,
            source_key_column=req.source_key_column,
            source_name_column=req.source_name_column,
            enabled=req.enabled,
            last_sync_at=_now(),
        )
        db.add(row)
    db.flush()
    _audit(db, action="upsert_system_item",
           entity_ref=f"{req.category_code}:{req.system_code}:{req.system_item_code}",
           operator=operator, after={"enabled": req.enabled})
    _commit(db)
    db.refresh(row)
    return ApiResponse(data={"id": row.id, "created": created})


class SystemItemEnabled(BaseModel):
    enabled: bool


@router.patch("/system-items/{item_id}/enabled", dependencies=[Depends(require_permission("dict.general.edit"))])
def set_system_item_enabled(item_id: int, req: SystemItemEnabled, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    row = db.get(DictSystemItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="system item not found")
    row.enabled = req.enabled
    row.last_sync_at = _now()
    db.flush()
    _audit(db, action="toggle_system_item",
           entity_ref=f"{row.category_code}:{row.system_code}:{row.system_item_code}",
           operator=operator, after={"enabled": req.enabled})
    _commit(db)
    db.refresh(row)
    return ApiResponse(data={"id": row.id, "enabled": row.enabled})


# ── Import ──

class SystemItemImport(BaseModel):
    category_code: str = Field(..., min_length=1, max_length=100)
    system_code: str = Field(..., min_length=1, max_length=100)
    items: list[dict]
    dry_run: bool = False


def _validate_import(db: Session, req: SystemItemImport) -> tuple[list[dict], list[dict], int]:
    """Returns (valid_items, capped_errors, total_rejected)."""
    errors: list[dict] = []
    rejected = 0
    seen_codes: set[str] = set()
    valid: list[dict] = []

    category = db.scalar(select(DictCategory).where(DictCategory.category_code == req.category_code))
    if not category:
        raise HTTPException(status_code=400, detail="category_code not found")
    if not category.enabled:
        raise HTTPException(status_code=400, detail="category is disabled")
    if not req.items:
        raise HTTPException(status_code=400, detail="items must not be empty")
    if len(req.items) > MAX_IMPORT_ITEMS:
        raise HTTPException(status_code=400, detail=f"items exceed limit {MAX_IMPORT_ITEMS}")

    for index, item in enumerate(req.items):
        code = str(item.get("system_item_code") or "").strip()
        name = str(item.get("system_item_name_cn") or "").strip()

        def fail(reason: str) -> None:
            nonlocal rejected
            rejected += 1
            if len(errors) < MAX_IMPORT_ERRORS:
                errors.append({"index": index, "system_item_code": code[:200], "reason": reason})

        if not code or len(code) > 200:
            fail("system_item_code required (1-200 chars)")
            continue
        if not name or len(name) > 500:
            fail("system_item_name_cn required (1-500 chars)")
            continue
        if code in seen_codes:
            fail("duplicate system_item_code in payload")
            continue
        seen_codes.add(code)
        valid.append({
            "system_item_code": code,
            "system_item_name_cn": name,
            "source_table": item.get("source_table"),
            "source_key_column": item.get("source_key_column"),
            "source_name_column": item.get("source_name_column"),
        })
    return valid, errors, rejected


@router.post("/import", dependencies=[Depends(require_permission("dict.general.import"))])
def import_system_items(req: SystemItemImport, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    valid, errors, rejected = _validate_import(db, req)

    created = updated = 0
    for item in valid:
        existing = db.scalar(select(DictSystemItem).where(
            DictSystemItem.category_code == req.category_code,
            DictSystemItem.system_code == req.system_code,
            DictSystemItem.system_item_code == item["system_item_code"],
        ))
        if existing:
            existing.system_item_name_cn = item["system_item_name_cn"]
            existing.source_table = item["source_table"]
            existing.last_sync_at = _now()
            updated += 1
        else:
            db.add(DictSystemItem(
                category_code=req.category_code,
                system_code=req.system_code,
                system_item_code=item["system_item_code"],
                system_item_name_cn=item["system_item_name_cn"],
                source_table=item["source_table"],
                source_key_column=item["source_key_column"],
                source_name_column=item["source_name_column"],
                enabled=True,
                last_sync_at=_now(),
            ))
            created += 1

    if req.dry_run:
        db.rollback()
        return ApiResponse(data={
            "dry_run": True, "created": created, "updated": updated,
            "rejected": rejected, "errors": errors,
        })

    db.flush()
    _audit(db, action="import_system_items",
           entity_ref=f"{req.category_code}:{req.system_code}", operator=operator,
           after={"created": created, "updated": updated, "rejected": rejected})
    _commit(db)
    return ApiResponse(data={
        "dry_run": False, "created": created, "updated": updated,
        "rejected": rejected, "errors": errors,
    })


# ── Item Mappings ──

class ItemMappingUpsert(BaseModel):
    category_code: str = Field(..., min_length=1, max_length=100)
    standard_code: str | None = None
    system_code: str = Field(..., min_length=1, max_length=100)
    system_item_code: str = Field(..., min_length=1, max_length=200)
    mapping_type: str | None = "manual"
    confidence: str | None = None


@router.get("/mappings", dependencies=[Depends(require_permission("dict.general.view"))])
def list_item_mappings(
    category_code: str | None = Query(None),
    system_code: str | None = Query(None),
    review_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictItemMapping)
    if category_code:
        stmt = stmt.where(DictItemMapping.category_code == category_code)
    if system_code:
        stmt = stmt.where(DictItemMapping.system_code == system_code)
    if review_status:
        stmt = stmt.where(DictItemMapping.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictItemMapping.category_code, DictItemMapping.system_code, DictItemMapping.system_item_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "category_code": r.category_code, "standard_code": r.standard_code,
         "system_code": r.system_code, "system_item_code": r.system_item_code,
         "mapping_type": r.mapping_type, "confidence": r.confidence, "review_status": r.review_status}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.put("/mappings", dependencies=[Depends(require_permission("dict.general.edit"))])
def upsert_item_mapping(req: ItemMappingUpsert, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
    existing = db.scalar(select(DictItemMapping).where(
        DictItemMapping.category_code == req.category_code,
        DictItemMapping.system_code == req.system_code,
        DictItemMapping.system_item_code == req.system_item_code,
        DictItemMapping.mapping_type == (req.mapping_type or "manual"),
    ))
    if existing:
        existing.standard_code = req.standard_code
        existing.confidence = req.confidence
        m = existing
    else:
        m = DictItemMapping(
            category_code=req.category_code, standard_code=req.standard_code,
            system_code=req.system_code, system_item_code=req.system_item_code,
            mapping_type=req.mapping_type or "manual", confidence=req.confidence,
        )
        db.add(m)
    db.flush()
    _audit(db, action="upsert_item_mapping",
           entity_ref=f"{req.category_code}:{req.system_code}:{req.system_item_code}", operator=operator)
    _commit(db)
    db.refresh(m)
    return ApiResponse(data={"id": m.id})


# ── Versions ──

class VersionCreate(BaseModel):
    category_code: str = Field(..., min_length=1, max_length=100)
    version_no: str = Field(..., min_length=1, max_length=100)
    version_name_cn: str | None = None
    note: str | None = None


@router.get("/versions", dependencies=[Depends(require_permission("dict.general.view"))])
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


@router.put("/versions", dependencies=[Depends(require_permission("dict.general.edit"))])
def upsert_version(req: VersionCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    operator = get_current_user(request)
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
    db.flush()
    _audit(db, action="upsert_version", entity_ref=f"{req.category_code}:{req.version_no}", operator=operator)
    _commit(db)
    db.refresh(v)
    return ApiResponse(data={"id": v.id, "version_no": v.version_no})
