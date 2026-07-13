import re
from itertools import zip_longest

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.asset import AssetColumn, AssetRelation, AssetTable
from ...models.candidate import AssetCandidateRelation
from ...models.lineage import AssetViewDependency
from ...schemas.common import ApiResponse
from ...schemas.graph import GraphData, GraphEdge, GraphFieldMapping, GraphNode, GraphOptions

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

GRAPH_VIEW_MODES = [
    {
        "code": "system",
        "label": "系统关系",
        "description": "按 HIS、ODS 等系统大类观察资产关系。",
        "group_by": "system",
        "layout_mode": "grouped",
        "confidence": "A",
        "validation_status": "A_rechecked",
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
    },
    {
        "code": "domain",
        "label": "业务域",
        "description": "按患者、就诊、医嘱、检验、检查、费用、药品等业务域聚合关系。",
        "group_by": "domain",
        "layout_mode": "grouped",
        "confidence": "A",
        "validation_status": "A_rechecked",
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
    },
    {
        "code": "schema",
        "label": "Schema 聚合",
        "description": "按 MEDREC、ORDADM、LAB、EXAM、COMM 等 schema/owner 聚合关系。",
        "group_by": "schema",
        "layout_mode": "grouped",
        "confidence": "A",
        "validation_status": "A_rechecked",
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
    },
    {
        "code": "table",
        "label": "表级图谱",
        "description": "表级关系图谱，展示库/owner 下表与表之间的正式关系。",
        "group_by": "schema",
        "layout_mode": "layered",
        "confidence": "A",
        "validation_status": "A_rechecked",
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
    },
    {
        "code": "lineage",
        "label": "上下游链路",
        "description": "单表上下游链路，围绕指定表展示直接上下游或两跳链路，并支持按边方向过滤。",
        "group_by": "schema",
        "layout_mode": "radial",
        "confidence": "A",
        "validation_status": "A_rechecked",
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": True,
    },
    {
        "code": "deferred",
        "label": "待分析层",
        "description": "D 类跨系统关系和候选关系待分析视图，不进入正式图谱。",
        "group_by": "schema",
        "layout_mode": "layered",
        "confidence": "D",
        "validation_status": None,
        "include_candidates": True,
        "include_dependencies": False,
        "show_review_layer": True,
        "requires_table": False,
    },
    {
        "code": "review",
        "label": "证据复核",
        "description": "展示候选、依赖和 D 类待分析关系。",
        "group_by": "schema",
        "layout_mode": "layered",
        "confidence": None,
        "validation_status": None,
        "include_candidates": True,
        "include_dependencies": True,
        "show_review_layer": True,
        "requires_table": False,
    },
]

SCHEMA_COLORS: dict[str, str] = {
    "HIS": "#409EFF",
    "LIS": "#67C23A",
    "PACS": "#9B59B6",
    "YDHL": "#E6A23C",
    "SM": "#F56C6C",
}


def _table_full(schema_name: str, table_name: str) -> str:
    return f"{schema_name}.{table_name}"

def _table_scope_names(db: Session, system_code: str | None, source_code: str | None) -> set[str] | None:
    if not system_code and not source_code:
        return None
    stmt = select(AssetTable.schema_name, AssetTable.table_name)
    if system_code:
        stmt = stmt.where(AssetTable.system_code == system_code)
    if source_code:
        stmt = stmt.where(AssetTable.source_code == source_code)
    return {_table_full(row.schema_name, row.table_name) for row in db.execute(stmt) if row.schema_name and row.table_name}


def _graph_node_for(full_name: str, table: AssetTable | None) -> GraphNode:
    if table:
        return GraphNode(
            id=full_name,
            label=table.table_name_cn or table.table_name or full_name,
            system_code=table.system_code,
            source_code=table.source_code,
            namespace_name=table.namespace_name,
            schema_name=table.schema_name,
            table_name=table.table_name,
            table_name_cn=table.table_name_cn,
            table_role=table.table_role,
            domain=table.domain,
            business_domain=table.domain,
            column_count=table.column_count,
            source=table.source or table.source_code,
            category=table.schema_name,
            row_count_stats=table.row_count_stats,
            grain=table.grain,
            pk=table.pk,
            confidence=table.confidence,
            include_status=table.include_status,
            review_status=table.review_status,
            note=table.note,
        )
    parts = full_name.split(".", 1)
    schema_name = parts[0] if len(parts) > 1 else "?"
    table_name = parts[1] if len(parts) > 1 else full_name
    return GraphNode(
        id=full_name,
        label=table_name,
        namespace_name=schema_name,
        schema_name=schema_name,
        table_name=table_name,
        category=schema_name,
    )

def _table_map_for(db: Session, table_set: set[str]) -> dict[str, AssetTable]:
    if not table_set:
        return {}
    table_rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.schema_name + "." + AssetTable.table_name).in_(list(table_set))
        )
    ).all()
    return {_table_full(t.schema_name, t.table_name): t for t in table_rows}


def _split_table_name(full_name: str) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    if full_name.startswith("[VIEW] "):
        return "VIEW", full_name.replace("[VIEW] ", "", 1)
    parts = full_name.split(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, full_name


def _edge_side_metadata(full_name: str, table_map: dict[str, AssetTable]) -> dict[str, str | None]:
    table = table_map.get(full_name)
    if table:
        return {
            "system_code": table.system_code,
            "source_code": table.source_code,
            "schema_name": table.schema_name,
            "table_name": table.table_name,
            "table_name_cn": table.table_name_cn,
            "table_role": table.table_role,
            "include_status": table.include_status,
        }
    schema_name, table_name = _split_table_name(full_name)
    return {
        "system_code": None,
        "source_code": None,
        "schema_name": schema_name,
        "table_name": table_name,
        "table_name_cn": None,
        "table_role": None,
        "include_status": None,
    }

def _column_map_for(db: Session, table_set: set[str]) -> dict[tuple[str, str], AssetColumn]:
    if not table_set:
        return {}
    rows = db.scalars(
        select(AssetColumn).where(
            (AssetColumn.schema_name + "." + AssetColumn.table_name).in_(list(table_set))
        )
    ).all()
    return {
        (_table_full(c.schema_name, c.table_name), (c.column_name or "").upper()): c
        for c in rows
        if c.schema_name and c.table_name and c.column_name
    }


def _split_relation_columns(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("，", ",")
    return [item.strip().strip('"') for item in re.split(r"\s*(?:,|\+)\s*", normalized) if item.strip()]


def _field_mappings_for(edge: GraphEdge, column_map: dict[tuple[str, str], AssetColumn]) -> list[GraphFieldMapping]:
    from_columns = _split_relation_columns(edge.from_columns)
    to_columns = _split_relation_columns(edge.to_columns)
    mappings: list[GraphFieldMapping] = []
    for from_col, to_col in zip_longest(from_columns, to_columns):
        from_meta = column_map.get((edge.source, (from_col or "").upper())) if from_col else None
        to_meta = column_map.get((edge.target, (to_col or "").upper())) if to_col else None
        mappings.append(GraphFieldMapping(
            from_column=from_col,
            from_column_name_cn=from_meta.column_name_cn if from_meta else None,
            to_column=to_col,
            to_column_name_cn=to_meta.column_name_cn if to_meta else None,
        ))
    return mappings

def _is_deferred_confidence(confidence: str | None) -> bool:
    return (confidence or "").upper() == "D"


def _enrich_edges(db: Session, edges: list[GraphEdge], table_map: dict[str, AssetTable]) -> list[GraphEdge]:
    column_map = _column_map_for(db, set(table_map.keys()))
    for edge in edges:
        src = _edge_side_metadata(edge.source, table_map)
        tgt = _edge_side_metadata(edge.target, table_map)
        edge.from_system_code = src["system_code"]
        edge.from_source_code = src["source_code"]
        edge.from_schema_name = src["schema_name"]
        edge.from_table_name = src["table_name"]
        edge.from_table_name_cn = src["table_name_cn"]
        edge.from_table_role = src["table_role"]
        edge.from_include_status = src["include_status"]
        edge.to_system_code = tgt["system_code"]
        edge.to_source_code = tgt["source_code"]
        edge.to_schema_name = tgt["schema_name"]
        edge.to_table_name = tgt["table_name"]
        edge.to_table_name_cn = tgt["table_name_cn"]
        edge.to_table_role = tgt["table_role"]
        edge.to_include_status = tgt["include_status"]
        edge.field_mappings = _field_mappings_for(edge, column_map)
    return edges


def _nodes_for_tables(table_set: set[str], table_map: dict[str, AssetTable]) -> list[GraphNode]:
    return [_graph_node_for(full_name, table_map.get(full_name)) for full_name in table_set]

@router.get("", response_model=ApiResponse[GraphData], summary="全局关系图谱")
def graph(
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
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
    scoped_tables = _table_scope_names(db, system_code, source_code)
    if scoped_tables is not None and not scoped_tables:
        return ApiResponse(data=GraphData(nodes=[], edges=[]))

    stmt = select(AssetRelation)
    if schema:
        stmt = stmt.where(
            (AssetRelation.from_table.startswith(f"{schema}."))
            | (AssetRelation.to_table.startswith(f"{schema}."))
        )
    if domain:
        stmt = stmt.where(AssetRelation.domain == domain)
    if scoped_tables is not None:
        stmt = stmt.where(or_(AssetRelation.from_table.in_(scoped_tables), AssetRelation.to_table.in_(scoped_tables)))
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
        is_deferred = _is_deferred_confidence(r.confidence)
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
                business_domain=r.domain,
                confidence=r.confidence,
                validation_level=r.validation_level,
                validation_status=r.validation_status,
                validation_metrics=r.validation_metrics,
                is_deferred=is_deferred,
                deferred_reason=(r.validation_note or r.note) if is_deferred else None,
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
        if scoped_tables is not None:
            cand_stmt = cand_stmt.where(or_(AssetCandidateRelation.from_table.in_(scoped_tables), AssetCandidateRelation.to_table.in_(scoped_tables)))
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
                    business_domain=cr.domain,
                    confidence=cr.confidence,
                    is_deferred=True,
                    deferred_reason=cr.note or cr.source_view or "candidate_relation",
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
        if scoped_tables is not None:
            dep_stmt = dep_stmt.where((AssetViewDependency.referenced_schema + "." + AssetViewDependency.referenced_table).in_(scoped_tables))
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

    table_map = _table_map_for(db, table_set)
    return ApiResponse(data=GraphData(nodes=_nodes_for_tables(table_set, table_map), edges=_enrich_edges(db, edges, table_map)))



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
        is_deferred = _is_deferred_confidence(r.confidence)
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
                business_domain=r.domain,
                confidence=r.confidence,
                validation_level=r.validation_level,
                validation_status=r.validation_status,
                validation_metrics=r.validation_metrics,
                is_deferred=is_deferred,
                deferred_reason=(r.validation_note or r.note) if is_deferred else None,
                note=r.note,
                validation_note=r.validation_note,
            )
        )

    table_map = _table_map_for(db, table_set)
    return ApiResponse(data=GraphData(nodes=_nodes_for_tables(table_set, table_map), edges=_enrich_edges(db, edges, table_map)))



@router.get("/options", response_model=ApiResponse[GraphOptions], summary="图谱筛选项")
def options(db: Session = Depends(get_db)) -> ApiResponse[GraphOptions]:
    systems_rows = db.scalars(
        select(func.distinct(AssetTable.system_code)).where(AssetTable.system_code.isnot(None))
    ).all()
    sources_rows = db.scalars(
        select(func.distinct(AssetTable.source_code)).where(AssetTable.source_code.isnot(None))
    ).all()
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
            systems=sorted([s for s in systems_rows if s]),
            sources=sorted([s for s in sources_rows if s]),
            schemas=sorted([s for s in schemas_rows if s]),
            domains=sorted([d for d in domains_rows if d]),
            validation_statuses=sorted(set([s for s in statuses_rows if s] + ["A_rechecked", "verified"])),
            confidences=sorted([c for c in confidences_rows if c]),
            relation_types=["formal", "candidate", "dependency"],
            view_modes=GRAPH_VIEW_MODES,
        )
    )
