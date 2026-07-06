from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.asset import AssetColumn, AssetRelation, AssetTable
from ...models.candidate import AssetCandidateRelation
from ...models.lineage import AssetViewDependency
from ...schemas.common import ApiResponse
from ...schemas.graph import GraphData, GraphEdge, GraphNode, GraphOptions

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


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


def _display_name(table: str, requested: str | None = None) -> str:
    if requested and table == LEGACY_TABLE_ALIASES.get(requested):
        return requested
    return table

SCHEMA_COLORS: dict[str, str] = {
    "HIS": "#409EFF",
    "LIS": "#67C23A",
    "PACS": "#9B59B6",
    "YDHL": "#E6A23C",
    "SM": "#F56C6C",
}


def _table_full(schema_name: str, table_name: str) -> str:
    return f"{schema_name}.{table_name}"


@router.get("", response_model=ApiResponse[GraphData], summary="全局关系图谱")
def graph(
    schema: str | None = Query(None),
    domain: str | None = Query(None),
    validation_status: str | None = Query(None),
    confidence: str | None = Query(None),
    keyword: str | None = Query(None),
    include_candidates: bool = Query(False),
    include_dependencies: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphData]:
    table_set: set[str] = set()
    edges: list[GraphEdge] = []

    stmt = select(AssetRelation)
    if schema:
        stmt = stmt.where(
            (AssetRelation.from_table.startswith(f"{schema}."))
            | (AssetRelation.to_table.startswith(f"{schema}."))
        )
    if domain:
        stmt = stmt.where(AssetRelation.domain == domain)
    if validation_status:
        stmt = stmt.where(AssetRelation.validation_status == validation_status)
    if confidence:
        stmt = stmt.where(AssetRelation.confidence == confidence)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetRelation.from_table.ilike(like) | AssetRelation.to_table.ilike(like)
        )
    stmt = stmt.limit(limit)
    rows = db.scalars(stmt).all()

    for r in rows:
        src = r.from_table or ""
        tgt = r.to_table or ""
        table_set.add(src)
        table_set.add(tgt)
        edges.append(
            GraphEdge(
                id=f"formal:{src}->{tgt}#{r.rel_id}",
                source=src,
                target=tgt,
                label=r.from_columns + "->" + r.to_columns if r.from_columns and r.to_columns else (r.join_condition or ""),
                relation_type="formal",
                rel_id=r.rel_id,
                join_condition=r.join_condition,
                from_columns=r.from_columns,
                to_columns=r.to_columns,
                cardinality=r.cardinality,
                confidence=r.confidence,
                validation_level=r.validation_level,
                validation_status=r.validation_status,
                validation_metrics=r.validation_metrics,
                note=r.note,
                validation_note=r.validation_note,
            )
        )

    if include_candidates and len(edges) < limit:
        cand_stmt = select(AssetCandidateRelation).where(
            AssetCandidateRelation.status == "candidate"
        )
        if keyword:
            like = f"%{keyword}%"
            cand_stmt = cand_stmt.where(
                AssetCandidateRelation.from_table.ilike(like)
                | AssetCandidateRelation.to_table.ilike(like)
            )
        if schema:
            cand_stmt = cand_stmt.where(
                (AssetCandidateRelation.from_table.startswith(f"{schema}."))
                | (AssetCandidateRelation.to_table.startswith(f"{schema}."))
            )
        cand_stmt = cand_stmt.limit(limit - len(edges))
        cand_rows = db.scalars(cand_stmt).all()
        for cr in cand_rows:
            src = cr.from_table or ""
            tgt = cr.to_table or ""
            table_set.add(src)
            table_set.add(tgt)
            edges.append(
                GraphEdge(
                    id=f"candidate:{src}->{tgt}#{cr.id}",
                    source=src,
                    target=tgt,
                    label=cr.from_columns + "->" + cr.to_columns if cr.from_columns and cr.to_columns else (cr.join_condition or ""),
                    relation_type="candidate",
                    rel_id=cr.id,
                    join_condition=cr.join_condition,
                    from_columns=cr.from_columns,
                    to_columns=cr.to_columns,
                    confidence=cr.confidence,
                    note=cr.source_view,
                )
            )

    if include_dependencies and len(edges) < limit:
        dep_stmt = select(AssetViewDependency).where(AssetViewDependency.view_name.isnot(None))
        if keyword:
            like = f"%{keyword}%"
            dep_stmt = dep_stmt.where(
                AssetViewDependency.referenced_table.ilike(like)
                | AssetViewDependency.view_name.ilike(like)
            )
        if schema:
            dep_stmt = dep_stmt.where(AssetViewDependency.referenced_schema == schema.upper())
        dep_stmt = dep_stmt.limit(limit - len(edges))
        dep_rows = db.scalars(dep_stmt).all()
        for dep in dep_rows:
            src = _table_full(dep.referenced_schema, dep.referenced_table)
            tgt = f"[VIEW] {dep.view_name}"
            table_set.add(src)
            table_set.add(tgt)
            edges.append(
                GraphEdge(
                    id=f"dependency:{src}->{dep.view_name}#{dep.id}",
                    source=src,
                    target=tgt,
                    label="view depends",
                    relation_type="dependency",
                    validation_note=dep.view_name,
                )
            )

    table_rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.schema_name + "." + AssetTable.table_name).in_(list(table_set))
        )
    ).all()
    table_map: dict[str, AssetTable] = {_table_full(t.schema_name, t.table_name): t for t in table_rows}

    nodes: list[GraphNode] = []
    for full_name in table_set:
        t = table_map.get(full_name)
        if t:
            nodes.append(
                GraphNode(
                    id=full_name,
                    label=t.table_name or full_name,
                    schema_name=t.schema_name,
                    table_name=t.table_name,
                    domain=t.domain,
                    column_count=t.column_count,
                    source=t.source,
                    category=t.schema_name,
                )
            )
        else:
            parts = full_name.split(".", 1)
            sch = parts[0] if len(parts) > 1 else "?"
            tbl = parts[1] if len(parts) > 1 else full_name
            nodes.append(
                GraphNode(
                    id=full_name,
                    label=tbl,
                    schema_name=sch,
                    table_name=tbl,
                    category=sch,
                )
            )

    return ApiResponse(data=GraphData(nodes=nodes, edges=edges))


@router.get("/neighbors", response_model=ApiResponse[GraphData], summary="某表邻居图")
def neighbors(
    table: str = Query(..., description="表名，如 HIS.PAT_VISIT"),
    depth: int = Query(1, ge=1, le=2),
    direction: str = Query("both", pattern="^(in|out|both)$"),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphData]:
    collected_edges: list[AssetRelation] = []
    seen: set[int] = set()
    current_tables: set[str] = _aliases_for(table)

    for _ in range(depth):
        if not current_tables:
            break
        conds = []
        if direction in ("out", "both"):
            conds.append(AssetRelation.from_table.in_(current_tables))
        if direction in ("in", "both"):
            conds.append(AssetRelation.to_table.in_(current_tables))
        if not conds:
            break
        from sqlalchemy import or_
        stmt = select(AssetRelation).where(or_(*conds)).limit(limit)
        rows = db.scalars(stmt).all()
        next_tables: set[str] = set()
        for r in rows:
            if r.id in seen:
                continue
            seen.add(r.id)
            collected_edges.append(r)
            src = r.from_table or ""
            tgt = r.to_table or ""
            if src not in current_tables:
                next_tables.add(src)
            if tgt not in current_tables:
                next_tables.add(tgt)
            if len(collected_edges) >= limit:
                break
        current_tables = next_tables
        if len(collected_edges) >= limit:
            break

    table_set: set[str] = set()
    edges: list[GraphEdge] = []
    for r in collected_edges:
        src = r.from_table or ""
        tgt = r.to_table or ""
        src_display = _display_name(src, table)
        tgt_display = _display_name(tgt, table)
        table_set.add(src_display)
        table_set.add(tgt_display)
        edges.append(
            GraphEdge(
                id=f"{src_display}->{tgt_display}#{r.rel_id}",
                source=src_display,
                target=tgt_display,
                label=r.from_columns + "->" + r.to_columns if r.from_columns and r.to_columns else (r.join_condition or ""),
                relation_type="formal",
                rel_id=r.rel_id,
                join_condition=r.join_condition,
                from_columns=r.from_columns,
                to_columns=r.to_columns,
                cardinality=r.cardinality,
                confidence=r.confidence,
                validation_level=r.validation_level,
                validation_status=r.validation_status,
                validation_metrics=r.validation_metrics,
                note=r.note,
                validation_note=r.validation_note,
            )
        )

    if table_set:
        table_rows = db.scalars(
            select(AssetTable).where(
                (AssetTable.schema_name + "." + AssetTable.table_name).in_(list(table_set))
            )
        ).all()
        table_map: dict[str, AssetTable] = {_table_full(t.schema_name, t.table_name): t for t in table_rows}
    else:
        table_map = {}

    nodes: list[GraphNode] = []
    for full_name in table_set:
        t = table_map.get(full_name)
        if t:
            nodes.append(
                GraphNode(
                    id=full_name,
                    label=t.table_name or full_name,
                    schema_name=t.schema_name,
                    table_name=t.table_name,
                    domain=t.domain,
                    column_count=t.column_count,
                    source=t.source,
                    category=t.schema_name,
                )
            )
        else:
            parts = full_name.split(".", 1)
            sch = parts[0] if len(parts) > 1 else "?"
            tbl = parts[1] if len(parts) > 1 else full_name
            nodes.append(
                GraphNode(
                    id=full_name,
                    label=tbl,
                    schema_name=sch,
                    table_name=tbl,
                    category=sch,
                )
            )

    return ApiResponse(data=GraphData(nodes=nodes, edges=edges))


@router.get("/options", response_model=ApiResponse[GraphOptions], summary="图谱筛选项")
def options(db: Session = Depends(get_db)) -> ApiResponse[GraphOptions]:
    schemas_rows = db.scalars(
        select(func.distinct(AssetTable.schema_name)).where(AssetTable.schema_name.isnot(None))
    ).all()
    domains_rows = db.scalars(
        select(func.distinct(AssetTable.domain)).where(AssetTable.domain.isnot(None))
    ).all()
    statuses_rows = db.scalars(
        select(func.distinct(AssetRelation.validation_status)).where(
            AssetRelation.validation_status.isnot(None)
        )
    ).all()
    confidences_rows = db.scalars(
        select(func.distinct(AssetRelation.confidence)).where(
            AssetRelation.confidence.isnot(None)
        )
    ).all()

    return ApiResponse(
        data=GraphOptions(
            schemas=sorted([s for s in schemas_rows if s]),
            domains=sorted([d for d in domains_rows if d]),
            validation_statuses=sorted(set([s for s in statuses_rows if s] + ["verified"])),
            confidences=sorted([c for c in confidences_rows if c]),
            relation_types=["formal", "candidate", "dependency"],
        )
    )
