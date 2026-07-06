from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...models.asset import AssetRelation
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/relations", tags=["relations"])
LEGACY_TABLE_ALIASES = {
    "HIS.PAT_VISIT": "MEDREC.PAT_VISIT",
    "HIS.PAT_MASTER_INDEX": "MEDREC.PAT_MASTER_INDEX",
}
CANONICAL_TO_LEGACY = {v: k for k, v in LEGACY_TABLE_ALIASES.items()}


def _aliases_for(table: str) -> set[str]:
    names = {table}
    if table in LEGACY_TABLE_ALIASES:
        names.add(LEGACY_TABLE_ALIASES[table])
    if table in CANONICAL_TO_LEGACY:
        names.add(CANONICAL_TO_LEGACY[table])
    return names


def _load_edges(db: Session) -> dict[str, list[tuple[str, dict]]]:
    edges: dict[str, list[tuple[str, dict]]] = {}
    for r in db.scalars(select(AssetRelation)):
        meta = {
            "rel_id": r.rel_id,
            "join_condition": r.join_condition,
            "cardinality": r.cardinality,
            "confidence": r.confidence,
            "validation_level": r.validation_level,
            "validation_status": r.validation_status,
            "validation_metrics": r.validation_metrics,
            "note": r.note,
            "validation_note": r.validation_note,
            "from_columns": r.from_columns,
            "to_columns": r.to_columns,
        }
        src = r.from_table or ""
        tgt = r.to_table or ""
        for src_name in _aliases_for(src):
            for tgt_name in _aliases_for(tgt):
                edges.setdefault(src_name, []).append((tgt_name, meta))
    return edges


@router.get("/path", summary="两表之间的关联路径（BFS 最短跳数）")
def relation_path(
    frm: str = Query(..., alias="from"),
    to: str = Query(..., alias="to"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    if frm == to:
        return ApiResponse(
            data={"from": frm, "to": to, "path": [frm], "hops": []}
        )
    edges = _load_edges(db)
    q = deque([frm])
    prev: dict[str, tuple[str, dict] | None] = {frm: None}
    while q:
        cur = q.popleft()
        for nxt, meta in edges.get(cur, []):
            if nxt in prev:
                continue
            prev[nxt] = (cur, meta)
            if nxt == to:
                hops_rev: list[dict] = []
                node: str = to
                while prev[node] is not None:
                    pc, pm = prev[node]
                    hops_rev.append({"from": pc, "to": node, **pm})
                    node = pc
                hops_rev.reverse()
                path = [h["from"] for h in hops_rev] + [to]
                return ApiResponse(
                    data={"from": frm, "to": to, "path": path, "hops": hops_rev}
                )
            q.append(nxt)
    return ApiResponse(
        code=404,
        message="未找到关联路径",
        data={"from": frm, "to": to, "path": None, "hops": []},
    )


# ──────────────────────────────────────────────
# P9 关系复核工作台 API
# ──────────────────────────────────────────────

class RelationUpdate(BaseModel):
    join_condition: str | None = None
    cardinality: str | None = None
    confidence: str | None = None
    note: str | None = None
    validation_note: str | None = None
    review_status: str | None = Field(None, description="draft/reviewing/approved/rejected")


@router.get("/list", summary="关系列表（复核工作台）")
def list_relations(
    review_status: str | None = Query(None),
    confidence: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetRelation)
    if review_status:
        stmt = stmt.where(AssetRelation.validation_status == review_status)
    if confidence:
        stmt = stmt.where(AssetRelation.confidence == confidence)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetRelation.from_table.ilike(like) | AssetRelation.to_table.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetRelation.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "rel_id": r.rel_id,
            "from_table": r.from_table, "to_table": r.to_table,
            "from_columns": r.from_columns, "to_columns": r.to_columns,
            "join_condition": r.join_condition, "cardinality": r.cardinality,
            "confidence": r.confidence,
            "validation_level": r.validation_level,
            "validation_status": r.validation_status,
            "validation_metrics": r.validation_metrics,
            "note": r.note, "validation_note": r.validation_note,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.patch("/{relation_id}", summary="编辑关系（P9 复核工作台）")
def update_relation(relation_id: int, req: RelationUpdate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    r = db.get(AssetRelation, relation_id)
    if not r:
        raise HTTPException(status_code=404)
    before = {
        "join_condition": r.join_condition, "cardinality": r.cardinality,
        "confidence": r.confidence, "note": r.note,
        "validation_status": r.validation_status, "validation_note": r.validation_note,
    }
    changes = {}
    for key in ("join_condition", "cardinality", "confidence", "note", "validation_note"):
        val = getattr(req, key)
        if val is not None:
            setattr(r, key, val)
            changes[key] = val
    if req.review_status is not None:
        r.validation_status = req.review_status
        changes["validation_status"] = req.review_status
    db.commit()
    audit = GovernAuditLog(
        module="asset", entity_type="relation", entity_ref=str(r.rel_id or r.id),
        action="update", before_data=before, after_data=changes,
        operator="reviewer",
    )
    db.add(audit)
    db.commit()
    return ApiResponse(data={
        "id": r.id, "rel_id": r.rel_id,
        "validation_status": r.validation_status,
        "updated": list(changes.keys()),
    })


@router.patch("/{relation_id}/review", summary="审核关系（通过/拒绝）")
def review_relation(
    relation_id: int,
    action: str = Query(..., description="approve / reject"),
    note: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    r = db.get(AssetRelation, relation_id)
    if not r:
        raise HTTPException(status_code=404)
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")
    before_status = r.validation_status
    r.validation_status = "verified" if action == "approve" else "rejected"
    r.validation_note = note
    db.commit()
    audit = GovernAuditLog(
        module="asset", entity_type="relation", entity_ref=str(r.rel_id or r.id),
        action=action,
        before_data={"validation_status": before_status},
        after_data={"validation_status": r.validation_status, "note": note},
        operator="reviewer",
    )
    db.add(audit)
    db.commit()
    return ApiResponse(data={"id": r.id, "validation_status": r.validation_status})


@router.get("/field-mappings", summary="字段映射列表")
def list_field_mappings(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetRelation).where(
        AssetRelation.from_columns.isnot(None), AssetRelation.to_columns.isnot(None)
    )
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetRelation.from_table.ilike(like) | AssetRelation.to_table.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetRelation.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "rel_id": r.rel_id,
            "from_full": f"{r.from_table}({r.from_columns})",
            "to_full": f"{r.to_table}({r.to_columns})",
            "join_condition": r.join_condition,
            "confidence": r.confidence,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})
