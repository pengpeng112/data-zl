from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.candidate import AssetCandidateRelation
from ...models.asset import AssetRelation
from ...schemas.candidate import CandidateRelationItem, CandidatePromoteRequest, CandidateRejectRequest
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.get("", summary="查询候选关系列表")
def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = Query(None, pattern="^(candidate|promoted|rejected)$"),
    keyword: str | None = Query(None),
    source_view: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetCandidateRelation)
    if status:
        stmt = stmt.where(AssetCandidateRelation.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetCandidateRelation.from_table.ilike(like)
            | AssetCandidateRelation.to_table.ilike(like)
        )
    if source_view:
        stmt = stmt.where(AssetCandidateRelation.source_view.ilike(f"%{source_view}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    rows = db.scalars(
        stmt.order_by(AssetCandidateRelation.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [CandidateRelationItem.model_validate(r) for r in rows]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.post("/{candidate_id}/promote", summary="候选关系提升为正式关系")
def promote_candidate(
    candidate_id: int,
    req: CandidatePromoteRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    candidate = db.get(AssetCandidateRelation, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="候选关系不存在")

    existing = db.scalars(
        select(AssetRelation).where(
            AssetRelation.from_table == candidate.from_table,
            AssetRelation.to_table == candidate.to_table,
            AssetRelation.from_columns == candidate.from_columns,
            AssetRelation.to_columns == candidate.to_columns,
        ).limit(1)
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail=f"同级正式关系已存在 rel_id={existing.rel_id}")

    max_rel = db.scalar(select(func.max(AssetRelation.rel_id))) or 0
    new_rel = AssetRelation(
        rel_id=max_rel + 1,
        domain=req.domain or "",
        from_table=candidate.from_table,
        from_columns=candidate.from_columns,
        to_table=candidate.to_table,
        to_columns=candidate.to_columns,
        join_condition=candidate.join_condition,
        cardinality=req.cardinality or "",
        confidence="manual_promoted",
        validation_level="manual",
        validation_status="manual_reviewed",
        note=f"由候选关系提升（候选ID={candidate_id}）；审核人={req.reviewer or '?'}；{req.note or ''}",
        validation_note=f"来源: {candidate.source_view or candidate.source_file or 'unknown'}",
    )

    candidate.status = "promoted"
    candidate.reviewed_by = req.reviewer
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.note = req.note

    db.add(new_rel)
    db.commit()

    return ApiResponse(
        data={
            "promoted_to_rel_id": new_rel.rel_id,
            "candidate_id": candidate.id,
            "from": candidate.from_table,
            "to": candidate.to_table,
        }
    )


@router.post("/{candidate_id}/reject", summary="拒绝候选关系")
def reject_candidate(
    candidate_id: int,
    req: CandidateRejectRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    candidate = db.get(AssetCandidateRelation, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="候选关系不存在")

    candidate.status = "rejected"
    candidate.reviewed_by = req.reviewer
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.note = req.note
    db.commit()

    return ApiResponse(
        data={
            "candidate_id": candidate.id,
            "status": "rejected",
            "from": candidate.from_table,
            "to": candidate.to_table,
        }
    )
