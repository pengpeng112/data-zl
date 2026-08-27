from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_permission
from ...models.lineage import AssetViewDependency
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


@router.post("/sync", summary="144 S5：静态血缘确定性导入（默认 dry-run）", dependencies=[Depends(require_permission("query.create"))])
def sync_static_lineage(
    request: Request,
    dry_run: bool = Query(True, description="默认 dry-run；true 时零写入"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...services.lineage_ingest import sync_lineage_edges

    result = sync_lineage_edges(db, dry_run=dry_run)
    if not dry_run:
        db.commit()
    return ApiResponse(data=result)


@router.get("/impact", summary="精确 object_key 血缘影响分析（typed nodes/edges）")
def impact_analysis(
    object_key: str | None = Query(None, description="138 对象键；表键可由 table 参数代算"),
    table: str | None = Query(None, description="SCHEMA.TABLE；服务端在元数据目录内精确解析，歧义即 422"),
    direction: str = Query("downstream", pattern="^(downstream|upstream|both)$"),
    max_hops: int = Query(3, ge=1, le=5),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...services.lineage_ingest import lineage_impact, table_object_key
    from ...services.object_identity import AmbiguousObjectError
    from ...services.query_validation_service import build_metadata_index

    if not object_key and not table:
        raise HTTPException(status_code=422, detail="需要 object_key 或 table 参数")
    if table and not object_key:
        index = build_metadata_index(db)
        parts = table.split(".")
        if len(parts) == 2:
            key = (parts[0].upper(), parts[1].upper())
            meta = index.get(key)
            if meta is None:
                raise HTTPException(status_code=422, detail=f"表不在元数据目录: {table}")
        else:
            hits = [k for k in index if k[1] == parts[0].upper()]
            if len(hits) != 1:
                raise HTTPException(status_code=422, detail="裸表名歧义或不存在，请提供 SCHEMA.TABLE")
            key = hits[0]
            meta = index[key]
        object_key = table_object_key(meta.get("system_code"), meta.get("source_code"), key[0], key[1])
    try:
        result = lineage_impact(db, object_key=object_key, direction=direction, max_hops=max_hops)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=result)


@router.get("/impact/legacy", summary="旧表影响分析（兼容保留：视图引用 + 业务关系提示）", include_in_schema=False)
def impact_analysis_legacy(
    table: str = Query(..., description="格式: SCHEMA.TABLE, 如 HIS.PAT_VISIT"),
    db: Session = Depends(get_db),
) -> ApiResponse[ImpactResult]:
    from ...models.asset import AssetRelation
    from ...models.candidate import AssetCandidateRelation

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
