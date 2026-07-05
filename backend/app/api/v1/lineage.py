from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.lineage import AssetViewDependency
from ...models.candidate import AssetCandidateRelation
from ...models.asset import AssetRelation
from ...schemas.common import ApiResponse
from ...schemas.lineage import ImpactResult, ViewDependencyItem

router = APIRouter(prefix="/api/v1/lineage", tags=["lineage"])


def _table_full(schema_name: str | None, table_name: str | None) -> str:
    if not schema_name:
        return table_name or ""
    return f"{schema_name}.{table_name}"


@router.get("/views", summary="查询 ODS 视图依赖")
def view_dependencies(
    view: str | None = Query(None),
    referenced_table: str | None = Query(None),
    schema: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AssetViewDependency)
    if view:
        stmt = stmt.where(AssetViewDependency.view_name.ilike(f"%{view}%"))
    if referenced_table:
        stmt = stmt.where(AssetViewDependency.referenced_table.ilike(f"%{referenced_table}%"))
    if schema:
        stmt = stmt.where(AssetViewDependency.referenced_schema == schema.upper())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    rows = db.scalars(
        stmt.order_by(AssetViewDependency.view_name, AssetViewDependency.referenced_table)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [ViewDependencyItem.model_validate(r) for r in rows]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/impact", summary="表影响分析：某表被哪些视图引用，关联哪些关系")
def impact_analysis(
    table: str = Query(..., description="格式: SCHEMA.TABLE, 如 HIS.PAT_VISIT"),
    db: Session = Depends(get_db),
) -> ApiResponse[ImpactResult]:
    parts = table.split(".", 1)
    if len(parts) == 2:
        schema, tbl = parts[0].upper(), parts[1].upper()
    else:
        schema, tbl = None, parts[0].upper()

    view_q = select(func.distinct(AssetViewDependency.view_name))
    if schema:
        view_q = view_q.where(
            AssetViewDependency.referenced_schema == schema,
            AssetViewDependency.referenced_table == tbl,
        )
    else:
        view_q = view_q.where(AssetViewDependency.referenced_table == tbl)
    referencing_views = [row for (row,) in db.execute(view_q).all()]

    rel_q = select(AssetRelation.rel_id, AssetRelation.from_table, AssetRelation.to_table).where(
        (AssetRelation.from_table.ilike(f"%{tbl}%")) | (AssetRelation.to_table.ilike(f"%{tbl}%"))
    )
    rel_rows = db.execute(rel_q).all()
    dependent_relations = [f"{r.from_table} -> {r.to_table}" for r in rel_rows]

    candidate_q = select(func.count()).select_from(AssetCandidateRelation).where(
        (AssetCandidateRelation.from_table.ilike(f"%{tbl}%"))
        | (AssetCandidateRelation.to_table.ilike(f"%{tbl}%"))
    ).where(AssetCandidateRelation.status == "candidate")
    total_candidates = db.scalar(candidate_q) or 0

    result = ImpactResult(
        table=table,
        referencing_views=referencing_views,
        dependent_relations=dependent_relations,
        total_views=len(referencing_views),
        total_relations=len(dependent_relations) + total_candidates,
    )
    return ApiResponse(data=result)
