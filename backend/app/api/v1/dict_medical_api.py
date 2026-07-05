from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.db import get_db
from ...models.dict_medical import (
    DictMedicalCodeItem,
    DictMedicalCodeMapping,
    DictMedicalCodeSet,
    DictMedicalSyncDiff,
)
from ...models.governance_base import GovernChangeRequest
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/dict-medical", tags=["dict-medical"])


@router.get("/code-sets", summary="诊断/手术三套编码体系列表")
def list_code_sets(
    category_code: str | None = Query(None, description="diagnosis/operation"),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(DictMedicalCodeSet)
    if category_code:
        stmt = stmt.where(DictMedicalCodeSet.category_code == category_code)
    rows = db.scalars(stmt.order_by(DictMedicalCodeSet.category_code, DictMedicalCodeSet.code_set_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "code_set_code": r.code_set_code,
            "code_set_name_cn": r.code_set_name_cn,
            "code_set_type": r.code_set_type,
            "category_code": r.category_code,
            "standard_system": r.standard_system,
            "enabled": r.enabled,
        }
        for r in rows
    ])


@router.get("/code-sets/{code_set_code}/items", summary="编码项列表")
def list_items(
    code_set_code: str,
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code == code_set_code)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            DictMedicalCodeItem.item_name_cn.ilike(like)
            | DictMedicalCodeItem.item_code.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalCodeItem.item_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "item_code": r.item_code, "item_name_cn": r.item_name_cn,
         "item_name_alias": r.item_name_alias, "status": r.status}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/mappings", summary="编码对照关系列表")
def list_mappings(
    category_code: str | None = Query(None),
    review_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalCodeMapping)
    if category_code:
        stmt = stmt.where(DictMedicalCodeMapping.category_code == category_code)
    if review_status:
        stmt = stmt.where(DictMedicalCodeMapping.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalCodeMapping.category_code, DictMedicalCodeMapping.from_code_set)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "category_code": r.category_code,
            "from_code_set": r.from_code_set, "from_item_code": r.from_item_code,
            "to_code_set": r.to_code_set, "to_item_code": r.to_item_code,
            "mapping_type": r.mapping_type, "mapping_cardinality": r.mapping_cardinality,
            "confidence": r.confidence, "review_status": r.review_status,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class MappingUpsert(BaseModel):
    category_code: str
    from_code_set: str
    from_item_code: str
    to_code_set: str
    to_item_code: str
    mapping_type: str | None = "manual"
    mapping_cardinality: str | None = None
    confidence: str | None = "unknown"


@router.put("/mappings", summary="新增/更新诊断手术编码对照关系")
def upsert_mapping(req: MappingUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == req.category_code,
        DictMedicalCodeMapping.from_code_set == req.from_code_set,
        DictMedicalCodeMapping.from_item_code == req.from_item_code,
        DictMedicalCodeMapping.to_code_set == req.to_code_set,
        DictMedicalCodeMapping.to_item_code == req.to_item_code,
    ))
    if existing:
        existing.mapping_type = req.mapping_type
        existing.mapping_cardinality = req.mapping_cardinality
        existing.confidence = req.confidence
        existing.updated_at = datetime.now(timezone.utc)
        m = existing
    else:
        m = DictMedicalCodeMapping(
            category_code=req.category_code,
            from_code_set=req.from_code_set, from_item_code=req.from_item_code,
            to_code_set=req.to_code_set, to_item_code=req.to_item_code,
            mapping_type=req.mapping_type or "manual",
            mapping_cardinality=req.mapping_cardinality,
            confidence=req.confidence or "unknown",
        )
        db.add(m)
    db.commit()
    db.refresh(m)
    return ApiResponse(data={"id": m.id})


@router.get("/sync-diffs", summary="HIS/EMR 诊断手术字典同步差异")
def list_medical_diffs(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalSyncDiff)
    if status:
        stmt = stmt.where(DictMedicalSyncDiff.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalSyncDiff.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "category_code": r.category_code, "target_system": r.target_system,
         "diff_type": r.diff_type, "code_set_code": r.code_set_code,
         "item_code": r.item_code, "status": r.status, "severity": r.severity}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class CodeSetUpsert(BaseModel):
    category_code: str
    code_set_code: str
    code_set_type: str
    code_set_name_cn: str
    standard_system: str | None = None
    version_no: str | None = None
    source_system: str | None = None
    enabled: bool = True


@router.put("/code-sets", summary="新增/更新诊断手术编码体系")
def upsert_code_set(req: CodeSetUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictMedicalCodeSet).where(
        DictMedicalCodeSet.code_set_code == req.code_set_code
    ))
    if existing:
        existing.category_code = req.category_code
        existing.code_set_type = req.code_set_type
        existing.code_set_name_cn = req.code_set_name_cn
        existing.standard_system = req.standard_system
        existing.version_no = req.version_no
        existing.source_system = req.source_system
        existing.enabled = req.enabled
        existing.updated_at = datetime.now(timezone.utc)
        cs = existing
    else:
        cs = DictMedicalCodeSet(
            category_code=req.category_code,
            code_set_code=req.code_set_code,
            code_set_type=req.code_set_type,
            code_set_name_cn=req.code_set_name_cn,
            standard_system=req.standard_system,
            version_no=req.version_no,
            source_system=req.source_system,
            enabled=req.enabled,
        )
        db.add(cs)
    db.commit()
    db.refresh(cs)
    return ApiResponse(data={"id": cs.id, "code_set_code": cs.code_set_code})


class CodeItemUpsert(BaseModel):
    code_set_code: str
    item_code: str
    item_name_cn: str
    item_name_alias: str | None = None
    category_code: str
    parent_code: str | None = None
    status: str | None = "active"


@router.put("/items", summary="新增/更新编码项")
def upsert_code_item(req: CodeItemUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == req.code_set_code,
        DictMedicalCodeItem.item_code == req.item_code,
    ))
    if existing:
        existing.item_name_cn = req.item_name_cn
        existing.item_name_alias = req.item_name_alias
        existing.category_code = req.category_code
        existing.parent_code = req.parent_code
        existing.status = req.status or "active"
        item = existing
    else:
        item = DictMedicalCodeItem(
            code_set_code=req.code_set_code,
            item_code=req.item_code,
            item_name_cn=req.item_name_cn,
            item_name_alias=req.item_name_alias,
            category_code=req.category_code,
            parent_code=req.parent_code,
            status=req.status or "active",
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data={"id": item.id, "code_set_code": item.code_set_code, "item_code": item.item_code})


class DictCRCreate(BaseModel):
    entity_type: str
    entity_ref: str | None = None
    request_type: str
    request_payload: dict | None = None
    requested_by: str | None = None


@router.post("/change-requests", summary="创建字典变更请求")
def create_dict_cr(req: DictCRCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    cr = GovernChangeRequest(
        module="dict",
        entity_type=req.entity_type,
        entity_ref=req.entity_ref,
        request_type=req.request_type,
        request_payload=req.request_payload,
        requested_by=req.requested_by,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.get("/change-requests", summary="字典变更请求列表")
def list_dict_crs(
    approval_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernChangeRequest).where(GovernChangeRequest.module == "dict")
    if approval_status:
        stmt = stmt.where(GovernChangeRequest.approval_status == approval_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernChangeRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_ref": r.entity_ref,
            "request_type": r.request_type, "approval_status": r.approval_status,
            "requested_by": r.requested_by, "approved_by": r.approved_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class ApproveBody(BaseModel):
    approved_by: str
    note: str | None = None


@router.patch("/change-requests/{cr_id}/approve", summary="审批字典变更请求")
def approve_dict_cr(cr_id: int, req: ApproveBody, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if cr.module != "dict":
        raise HTTPException(status_code=400, detail="非字典变更请求")
    if req.approved_by == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    cr.approval_status = "approved"
    cr.approved_by = req.approved_by
    cr.note = req.note
    cr.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.post("/change-requests/{cr_id}/execute", summary="执行字典变更请求")
def execute_dict_cr(cr_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if cr.approval_status != "approved":
        raise HTTPException(status_code=400, detail="仅已审批通过的请求可执行")
    cr.approval_status = "executed"
    cr.executed_by = cr.approved_by
    cr.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status, "executed": True})


@router.get("/versions", summary="编码体系版本列表")
def list_versions(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(DictMedicalCodeSet).order_by(DictMedicalCodeSet.category_code, DictMedicalCodeSet.code_set_code)
    ).all()
    return ApiResponse(data=[
        {
            "id": r.id, "code_set_code": r.code_set_code,
            "code_set_name_cn": r.code_set_name_cn,
            "category_code": r.category_code,
            "version_no": r.version_no,
            "source_system": r.source_system,
        }
        for r in rows
    ])
