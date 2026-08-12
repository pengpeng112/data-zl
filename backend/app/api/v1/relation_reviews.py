"""Relation review workflow API — fact table asset_relation_reviews (127 S6)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.asset import AssetRelation, AssetRelationReview
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse
from ...services.relation_review_service import approve_review, reject_review

router = APIRouter(prefix="/api/v1/relation-reviews", tags=["relation-reviews"])


class ReviewActionRequest(BaseModel):
    note: str | None = None


class BatchReviewRequest(BaseModel):
    review_ids: list[int] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = None


def _item(r: AssetRelationReview) -> dict:
    return {
        "id": r.id,
        "relation_scope": r.relation_scope,
        "source_relation_table": r.source_relation_table,
        "source_relation_id": r.source_relation_id,
        "from_system_code": r.from_system_code,
        "from_source_code": r.from_source_code,
        "from_table": r.from_table,
        "from_columns": r.from_columns,
        "to_system_code": r.to_system_code,
        "to_source_code": r.to_source_code,
        "to_table": r.to_table,
        "to_columns": r.to_columns,
        "join_condition": r.join_condition,
        "relation_desc_cn": r.relation_desc_cn,
        "business_logic_cn": r.business_logic_cn,
        "confidence": r.confidence,
        "validation_status": r.validation_status,
        "review_status": r.review_status,
        "reviewer": r.reviewer,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "review_note": r.review_note,
        "source_evidence": r.source_evidence,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/counts", summary="复核状态计数")
def review_counts(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    rows = db.execute(
        select(AssetRelationReview.review_status, func.count(AssetRelationReview.id)).group_by(
            AssetRelationReview.review_status
        )
    ).all()
    counts = { (r[0] or "unknown"): r[1] for r in rows }
    return ApiResponse(
        data={
            "draft": counts.get("draft", 0) + counts.get("pending", 0) + counts.get("reviewing", 0),
            "approved": counts.get("approved", 0),
            "rejected": counts.get("rejected", 0),
            "total": sum(counts.values()),
            "by_status": counts,
        }
    )


@router.get("", summary="关系复核草稿列表")
def list_reviews(
    review_status: str | None = Query(None, description="draft/approved/rejected/reviewing"),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetRelationReview)
    if review_status:
        if review_status in {"draft", "pending"}:
            stmt = stmt.where(
                func.lower(func.coalesce(AssetRelationReview.review_status, "draft")).in_(
                    ["draft", "pending", "reviewing"]
                )
            )
        else:
            stmt = stmt.where(
                func.lower(func.coalesce(AssetRelationReview.review_status, "")) == review_status.lower()
            )
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetRelationReview.from_table.ilike(like) | AssetRelationReview.to_table.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetRelationReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApiResponse(
        data={"total": total, "page": page, "page_size": page_size, "items": [_item(r) for r in rows]}
    )


@router.get("/{review_id}", summary="复核草稿详情")
def get_review(review_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    r = db.get(AssetRelationReview, review_id)
    if not r:
        raise HTTPException(status_code=404, detail="复核草稿不存在")
    data = _item(r)
    if r.source_relation_id:
        rel = db.get(AssetRelation, r.source_relation_id)
        if rel:
            data["linked_relation"] = {
                "id": rel.id,
                "rel_id": rel.rel_id,
                "from_table": rel.from_table,
                "to_table": rel.to_table,
                "relation_layer": rel.relation_layer,
                "validation_status": rel.validation_status,
            }
    return ApiResponse(data=data)


@router.post(
    "/{review_id}/approve",
    summary="批准复核草稿（链接既有 formal，禁止重复提升 candidate）",
    dependencies=[Depends(require_permission("relation:review"))],
)
def approve(
    review_id: int,
    req: ReviewActionRequest | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    r = db.get(AssetRelationReview, review_id)
    if not r:
        raise HTTPException(status_code=404, detail="复核草稿不存在")
    user = "reviewer"
    try:
        if request is not None:
            user = get_current_user(request) or user
    except Exception:
        pass
    result = approve_review(db, r, reviewer=user, note=(req.note if req else None))
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "approve failed")
    db.add(
        GovernAuditLog(
            module="relation_review",
            entity_type="relation_review",
            entity_ref=str(review_id),
            action="approve",
            after_data=result,
            operator=user,
        )
    )
    db.commit()
    return ApiResponse(data=result)


@router.post(
    "/{review_id}/reject",
    summary="拒绝复核草稿（保留证据，不物理删除）",
    dependencies=[Depends(require_permission("relation:review"))],
)
def reject(
    review_id: int,
    req: ReviewActionRequest | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    r = db.get(AssetRelationReview, review_id)
    if not r:
        raise HTTPException(status_code=404, detail="复核草稿不存在")
    user = "reviewer"
    try:
        if request is not None:
            user = get_current_user(request) or user
    except Exception:
        pass
    result = reject_review(db, r, reviewer=user, note=(req.note if req else None))
    db.add(
        GovernAuditLog(
            module="relation_review",
            entity_type="relation_review",
            entity_ref=str(review_id),
            action="reject",
            after_data=result,
            operator=user,
        )
    )
    db.commit()
    return ApiResponse(data=result)


@router.post(
    "/batch",
    summary="批量批准/拒绝",
    dependencies=[Depends(require_permission("relation:review"))],
)
def batch_review(
    req: BatchReviewRequest,
    request: Request = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    user = "reviewer"
    try:
        if request is not None:
            user = get_current_user(request) or user
    except Exception:
        pass
    results = []
    for rid in req.review_ids:
        r = db.get(AssetRelationReview, rid)
        if not r:
            results.append({"review_id": rid, "ok": False, "error": "not_found"})
            continue
        if req.action == "approve":
            results.append(approve_review(db, r, reviewer=user, note=req.note))
        else:
            results.append(reject_review(db, r, reviewer=user, note=req.note))
    db.commit()
    return ApiResponse(data={"results": results, "count": len(results)})


@router.get("/{review_id}/field-mappings", summary="复核草稿字段映射（数组）")
def field_mappings(review_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    r = db.get(AssetRelationReview, review_id)
    if not r:
        raise HTTPException(status_code=404, detail="复核草稿不存在")
    from_cols = [c.strip() for c in (r.from_columns or "").split(",") if c.strip()]
    to_cols = [c.strip() for c in (r.to_columns or "").split(",") if c.strip()]
    items = []
    for i, fc in enumerate(from_cols):
        tc = to_cols[i] if i < len(to_cols) else (to_cols[-1] if to_cols else "")
        items.append(
            {
                "from_table": r.from_table,
                "from_column": fc,
                "to_table": r.to_table,
                "to_column": tc,
                "match_type": "key",
                "note": r.join_condition,
            }
        )
    return ApiResponse(data=items)
