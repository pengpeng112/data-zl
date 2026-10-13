"""215 E11 自 graph.py 拆出：节点/边构建、过滤与聚合元信息。

GraphNode.id 使用完整物理键；边 id 使用稳定 relation_business_key（108号 §3.2）。
"""
from __future__ import annotations

import re
from collections import defaultdict
from itertools import zip_longest
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....core.config import settings
from ....models.asset import AssetColumn, AssetRelation, AssetTable
from ....models.candidate import AssetCandidateRelation
from ....schemas.graph import (
    GraphEdge,
    GraphFieldMapping,
    GraphMeta,
    GraphNode,
)
from .resolution import (
    _candidate_edge_id,
    _physical_key,
    _resolve_relation_endpoint,
    _resolve_table_filter,
    _split_table_name,
    _stable_edge_id,
)

GRAPH_VIEW_MODES = [
    {
        "code": "overview",
        "label": "资产概览",
        "description": "按业务系统、数据连接、Schema/Owner 和对象层级浏览完整资产规模。",
        "group_by": "system",
        "layout_mode": "grouped",
        "confidence": None,
        "validation_status": None,
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
    },
    {
        "code": "path",
        "label": "路径查询",
        "description": "选择两张表，按方向和跳数上限查找最短关联路径（146 E1）。",
        "group_by": "schema",
        "layout_mode": "layered",
        "confidence": None,
        "validation_status": None,
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
    },
    {
        "code": "explore",
        "label": "关系探索",
        "description": "先选择唯一中心资产，再按方向和 1/2 跳展开关系。",
        "group_by": "schema",
        "layout_mode": "force",
        "confidence": None,
        "validation_status": None,
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": True,
        "requires_table": True,
    },
    {
        "code": "review",
        "label": "证据审核",
        "description": "按置信度、验证状态和证据来源查看正式、候选、冲突及延后关系。",
        "group_by": "schema",
        "layout_mode": "grouped",
        "confidence": None,
        "validation_status": None,
        "include_candidates": True,
        "include_dependencies": True,
        "show_review_layer": True,
        "requires_table": False,
    },
    {
        "code": "table",
        "label": "表级图谱（兼容）",
        "description": "旧版表级图谱接口兼容模式；前端不作为任务入口展示。",
        "group_by": "schema",
        "layout_mode": "layered",
        "confidence": "A",
        "validation_status": None,
        "include_candidates": False,
        "include_dependencies": False,
        "show_review_layer": False,
        "requires_table": False,
        "deprecated": True,
    },
]

SCHEMA_COLORS: dict[str, str] = {
    "HIS": "#409EFF",
    "LIS": "#67C23A",
    "PACS": "#9B59B6",
    "YDHL": "#E6A23C",
    "SM": "#F56C6C",
}

def _table_full(schema_name: str | None, table_name: str | None) -> str | None:
    if not schema_name or not table_name:
        return None
    return f"{schema_name}.{table_name}"


def _object_type(table: AssetTable | None, table_name: str | None = None) -> str:
    """统一对象类型，避免前端把表、视图都画成同一类。"""
    role = (table.table_role if table else "") or ""
    name = (table.table_name if table else table_name) or ""
    lowered = f"{role} {name}".lower()
    return "view" if "view" in lowered or "视图" in role or name.upper().startswith("V_") else "table"

def _table_scope_names(
    db: Session,
    system_code: str | None,
    source_code: str | None,
) -> list[tuple[str, str]] | None:
    """返回 (schema_name, table_name) 集合；未过滤时返回 None。"""
    if not system_code and not source_code:
        return None
    stmt = select(AssetTable.schema_name, AssetTable.table_name)
    if system_code:
        stmt = stmt.where(AssetTable.system_code == system_code)
    if source_code:
        stmt = stmt.where(AssetTable.source_code == source_code)
    rows = db.execute(stmt).all()
    return [(row.schema_name, row.table_name) for row in rows if row.schema_name and row.table_name]


def _table_scope_physical(db: Session, system_code: str | None, source_code: str | None) -> set[tuple[str, str]] | None:
    """按物理端点字段返回 (system_code, source_code) 集合；未过滤时返回 None。"""
    if not system_code and not source_code:
        return None
    stmt = select(AssetTable.system_code, AssetTable.source_code)
    if system_code:
        stmt = stmt.where(AssetTable.system_code == system_code)
    if source_code:
        stmt = stmt.where(AssetTable.source_code == source_code)
    rows = db.execute(stmt).all()
    result = set()
    for row in rows:
        if row[0] and row[1]:
            result.add((row[0], row[1]))
    return result or None

def _graph_node_for(
    physical_key: str,
    display_id: str | None,
    system_code: str | None,
    source_code: str | None,
    namespace_name: str | None,
    schema_name: str | None,
    table_name: str | None,
    table: AssetTable | None,
) -> GraphNode:
    """构建节点：id 使用完整物理键，display_id 仅用于展示。"""
    source = source_code
    if table and table.source:
        source = table.source
    elif table and table.source_code:
        source = table.source_code
    return GraphNode(
        id=physical_key,
        physical_key=physical_key,
        display_id=display_id,
        label=(table.table_name_cn or table.table_name) if table else (table_name or display_id or physical_key),
        system_code=system_code,
        source_code=source_code,
        namespace_name=namespace_name,
        schema_name=schema_name,
        table_name=table_name,
        table_name_cn=table.table_name_cn if table else None,
        table_role=table.table_role if table else None,
        domain=table.domain if table else None,
        business_domain=table.domain if table else None,
        column_count=table.column_count if table else None,
        source=source,
        category=schema_name or namespace_name,
        row_count_stats=table.row_count_stats if table else None,
        grain=table.grain if table else None,
        pk=table.pk if table else None,
        confidence=table.confidence if table else None,
        include_status=table.include_status if table else None,
        review_status=table.review_status if table else None,
        note=table.note if table else None,
        object_type=_object_type(table, table_name),
        technical_name=_table_full(schema_name, table_name),
        metadata_match=(
            "exact"
            if table and (table.namespace_name or "") == (namespace_name or "")
            else "namespace_compatible"
            if table
            else "unresolved"
        ),
    )

def _table_map_by_physical_key(
    db: Session,
    endpoints: set[tuple[str | None, str | None, str | None, str | None, str | None]],
) -> dict[str, AssetTable]:
    """按物理键 (system, source, namespace, schema, table) 反查 AssetTable。

    108号 P1-01：不再用 schema.table 作为唯一字典键，避免跨系统同名表覆盖。
    namespace 匹配采用宽松口径（NULL/""/==schema 均可），兼容历史回填差异。
    """
    if not endpoints:
        return {}
    conds = []
    for sys_c, src_c, ns, schema, table in endpoints:
        if not sys_c or not src_c or not schema or not table:
            continue
        if ns:
            ns_cond = (
                AssetTable.namespace_name == ns
            )
        else:
            ns_cond = (
                (AssetTable.namespace_name.is_(None))
                | (AssetTable.namespace_name == "")
                | (AssetTable.namespace_name == schema)
            )
        conds.append(
            (AssetTable.system_code == sys_c)
            & (AssetTable.source_code == src_c)
            & ns_cond
            & (AssetTable.schema_name == schema)
            & (AssetTable.table_name == table)
        )
    if not conds:
        return {}
    rows = db.scalars(select(AssetTable).where(or_(*conds))).all()
    result: dict[str, AssetTable] = {}
    logical_candidates: dict[tuple[str, str, str, str], list[AssetTable]] = defaultdict(list)
    for t in rows:
        key = _physical_key(t.system_code, t.source_code, t.namespace_name, t.schema_name, t.table_name)
        if key:
            result[key] = t
        if t.system_code and t.source_code and t.schema_name and t.table_name:
            logical_candidates[(t.system_code, t.source_code, t.schema_name, t.table_name)].append(t)

    # 关系 namespace 为空而资产 namespace=schema 是当前生产的主要历史差异。
    # 只在四元组唯一时把兼容资产映射到关系端点键；多候选保持未富化，避免误配。
    for sys_c, src_c, ns, schema, table in endpoints:
        endpoint_key = _physical_key(sys_c, src_c, ns, schema, table)
        if not endpoint_key or endpoint_key in result or not schema or not table:
            continue
        candidates = logical_candidates.get((sys_c, src_c, schema, table), [])
        if ns in (None, "", schema) and len(candidates) == 1:
            result[endpoint_key] = candidates[0]
    return result

def _column_map_for(
    db: Session,
    table_keys: set[str],
) -> dict[tuple[str, str, str], AssetColumn]:
    """按 (schema, table, column) 索引字段，避免跨系统同名表串字段。"""
    if not table_keys:
        return {}
    names: set[tuple[str | None, str | None]] = set()
    for key in table_keys:
        parts = key.split("|")
        if len(parts) == 5:
            names.add((parts[3], parts[4]))
    full_names = [f"{s}.{t}" for s, t in names if s and t]
    if not full_names:
        return {}
    rows = db.scalars(
        select(AssetColumn).where(
            (AssetColumn.schema_name + "." + AssetColumn.table_name).in_(full_names)
        )
    ).all()
    return {
        (c.schema_name, c.table_name, (c.column_name or "").upper()): c
        for c in rows
        if c.schema_name and c.table_name and c.column_name
    }

def _split_relation_columns(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("，", ",")
    return [
        item.strip().strip('"')
        for item in re.split(r"\s*(?:,|\+|\|)\s*", normalized)
        if item.strip()
    ]

def _field_mappings_for(
    db: Session,
    from_schema: str | None,
    from_table: str | None,
    to_schema: str | None,
    to_table: str | None,
    from_columns: str | None,
    to_columns: str | None,
    column_map: dict[tuple[str, str, str], AssetColumn],
) -> list[GraphFieldMapping]:
    """字段映射只在边详情（证据）时计算，全局图不预载（P1-04 摘要/详情分离）。"""
    from_cols = _split_relation_columns(from_columns)
    to_cols = _split_relation_columns(to_columns)
    mappings: list[GraphFieldMapping] = []
    for from_col, to_col in zip_longest(from_cols, to_cols):
        from_meta = (
            column_map.get((from_schema, from_table, (from_col or "").upper())) if from_col else None
        )
        to_meta = (
            column_map.get((to_schema, to_table, (to_col or "").upper())) if to_col else None
        )
        mappings.append(GraphFieldMapping(
            from_column=from_col,
            from_column_name_cn=from_meta.column_name_cn if from_meta else None,
            to_column=to_col,
            to_column_name_cn=to_meta.column_name_cn if to_meta else None,
        ))
    return mappings

def _is_deferred_confidence(confidence: str | None) -> bool:
    return (confidence or "").upper() == "D"

def _build_edge(
    r: AssetRelation,
    from_key: str | None,
    to_key: str | None,
    from_display: str | None,
    to_display: str | None,
    from_ep: tuple[str | None, str | None, str | None, str | None, str | None, str | None] | None = None,
    to_ep: tuple[str | None, str | None, str | None, str | None, str | None, str | None] | None = None,
) -> GraphEdge:
    is_deferred = _is_deferred_confidence(r.confidence)
    f_sys, f_src, f_ns, f_schema, f_tbl, f_disp = from_ep if from_ep else (r.from_system_code, r.from_source_code, r.from_namespace_name, r.from_schema_name, r.from_table_name, from_display)
    t_sys, t_src, t_ns, t_schema, t_tbl, t_disp = to_ep if to_ep else (r.to_system_code, r.to_source_code, r.to_namespace_name, r.to_schema_name, r.to_table_name, to_display)
    return GraphEdge(
        id=_stable_edge_id(r, from_key, to_key),
        source=from_key or r.from_table or "",
        target=to_key or r.to_table or "",
        display_source=from_display or f_disp or r.from_table,
        display_target=to_display or t_disp or r.to_table,
        from_system_code=f_sys,
        from_source_code=f_src,
        from_schema_name=f_schema,
        from_table_name=f_tbl,
        to_system_code=t_sys,
        to_source_code=t_src,
        to_schema_name=t_schema,
        to_table_name=t_tbl,
        label=r.from_columns + "->" + r.to_columns if r.from_columns and r.to_columns else (r.join_condition or ""),
        relation_type="formal",
        relation_layer=r.relation_layer,
        db_id=r.id,
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

def _build_candidate_edge(
    cr: AssetCandidateRelation,
    from_key: str,
    to_key: str,
    from_display: str,
    to_display: str,
) -> GraphEdge:
    return GraphEdge(
        id=_candidate_edge_id(cr),
        source=from_key,
        target=to_key,
        display_source=from_display,
        display_target=to_display,
        label=cr.from_columns + "->" + cr.to_columns if cr.from_columns and cr.to_columns else (cr.join_condition or ""),
        relation_type="candidate",
        relation_layer="candidate",
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

def _enrich_edge_table_meta(
    edges: list[GraphEdge],
    table_map: dict[str, AssetTable],
) -> list[GraphEdge]:
    """从 AssetTable 元数据补齐边端点的中文名/角色/纳入状态（旧版由 _enrich_edges 提供）。"""
    for edge in edges:
        from_table = table_map.get(edge.source)
        to_table = table_map.get(edge.target)
        if from_table:
            edge.from_table_name_cn = from_table.table_name_cn
            edge.from_table_role = from_table.table_role
            edge.from_include_status = from_table.include_status
        if to_table:
            edge.to_table_name_cn = to_table.table_name_cn
            edge.to_table_role = to_table.table_role
            edge.to_include_status = to_table.include_status
    return edges

def _build_candidate_edge(
    cr: AssetCandidateRelation,
    from_key: str,
    to_key: str,
    from_display: str,
    to_display: str,
) -> GraphEdge:
    return GraphEdge(
        id=_candidate_edge_id(cr),
        source=from_key,
        target=to_key,
        display_source=from_display,
        display_target=to_display,
        label=cr.from_columns + "->" + cr.to_columns if cr.from_columns and cr.to_columns else (cr.join_condition or ""),
        relation_type="candidate",
        relation_layer="candidate",
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

def _nodes_and_edges_for_relations(
    db: Session,
    rows: list[AssetRelation],
    with_details: bool = False,
) -> tuple[list[GraphNode], list[GraphEdge], list[tuple[int, str]]]:
    """把关系行构建成物理节点与边。

    返回 (nodes, edges, unresolved)。unresolved 为 (关系id, 原因)。
    """
    node_meta: dict[str, tuple[str | None, str | None, str | None, str | None, str | None, str | None]] = {}
    edges: list[GraphEdge] = []
    unresolved: list[tuple[int, str]] = []
    _seen_edge_ids: set[str] = set()

    for r in rows:
        from_ep = _resolve_relation_endpoint(db, r, "from")
        to_ep = _resolve_relation_endpoint(db, r, "to")
        f_sys, f_src, f_ns, f_schema, f_tbl, f_disp = from_ep
        t_sys, t_src, t_ns, t_schema, t_tbl, t_disp = to_ep
        from_key = _physical_key(f_sys, f_src, f_ns, f_schema, f_tbl)
        to_key = _physical_key(t_sys, t_src, t_ns, t_schema, t_tbl)
        if not from_key:
            unresolved.append((r.id, "from_endpoint_incomplete"))
        if not to_key:
            unresolved.append((r.id, "to_endpoint_incomplete"))
        if not from_key or not to_key:
            continue
        # 过滤自环边（from==to）：G6 布局/连线对自环边处理异常，会导致 .split 报错
        if from_key == to_key:
            unresolved.append((r.id, "self_loop_skipped"))
            continue
        if from_key not in node_meta:
            node_meta[from_key] = from_ep
        if to_key not in node_meta:
            node_meta[to_key] = to_ep
        edge = _build_edge(r, from_key, to_key, f_disp, t_disp, from_ep, to_ep)
        # 边 ID 去重：同 ID 的边只保留第一条，避免 G6 addEdge 抛 "Edge already exists"
        if edge.id not in _seen_edge_ids:
            edges.append(edge)
            _seen_edge_ids.add(edge.id)
        else:
            unresolved.append((r.id, "duplicate_edge_id_skipped"))

    endpoints = {(v[0], v[1], v[2], v[3], v[4]) for v in node_meta.values()}
    table_map = _table_map_by_physical_key(db, endpoints)
    nodes = [
        _graph_node_for(
            key, meta[5], meta[0], meta[1], meta[2], meta[3], meta[4],
            table_map.get(key),
        )
        for key, meta in node_meta.items()
    ]
    edges = _enrich_edge_table_meta(edges, table_map)

    if with_details:
        column_map = _column_map_for(db, set(node_meta.keys()))
        for edge in edges:
            edge.field_mappings = _field_mappings_for(
                db, edge.from_schema_name, edge.from_table_name,
                edge.to_schema_name, edge.to_table_name,
                edge.from_columns, edge.to_columns, column_map,
            )
    return nodes, edges, unresolved

def _graph_meta(
    total_relations: int,
    matched_relations: int,
    returned_relations: int,
    truncated: bool,
    unresolved_count: int,
    filters: dict[str, Any],
    *,
    query_ms: float | None = None,
    enrichment: dict[str, int] | None = None,
    warnings: list[str] | None = None,
    center_physical_key: str | None = None,
    direction_semantics: str | None = None,
    shown_count: int | None = None,
    actual_count: int | None = None,
    continuation_cursor: str | None = None,
) -> GraphMeta:
    return GraphMeta(
        total_relations=total_relations,
        matched_relations=matched_relations,
        returned_relations=returned_relations,
        truncated=truncated,
        unresolved_endpoints=unresolved_count,
        filters=filters,
        data_version=_data_version(),
        backend_build_id=settings.build_id,
        query_ms=query_ms,
        matched_total=matched_relations,
        returned_nodes=None,
        enrichment=enrichment or {},
        warnings=warnings or [],
        center_physical_key=center_physical_key,
        direction_semantics=direction_semantics,
        shown_count=shown_count,
        actual_count=actual_count,
        continuation_cursor=continuation_cursor,
    )

def _data_version() -> str:
    """数据版本：构建时环境注入或退化为 build_id（不连接数据库的确定性值）。"""
    return settings.git_sha or settings.build_id

def _filters_dict(**kwargs) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None and v is not False}

def _enrichment_stats(nodes: list[GraphNode]) -> dict[str, int]:
    stats: dict[str, int] = defaultdict(int)
    for node in nodes:
        stats[node.metadata_match or "unresolved"] += 1
    return dict(stats)

def _build_relation_filter_stmt(
    stmt,
    *,
    schema: str | None,
    domain: str | None,
    scoped_tables: list[tuple[str, str]] | None,
    scoped_physical: set[tuple[str, str]] | None,
    validation_status: str | None,
    confidence: str | None,
    keyword: str | None,
):
    """应用关系过滤条件（供全局/邻居共用）。业务系统/数据连接范围优先按关系物理端点字段过滤。"""
    if scoped_physical:
        scope_conds = []
        for sys_c, src_c in scoped_physical:
            scope_conds.append(
                (AssetRelation.from_system_code == sys_c)
                & (AssetRelation.from_source_code == src_c)
            )
            scope_conds.append(
                (AssetRelation.to_system_code == sys_c)
                & (AssetRelation.to_source_code == src_c)
            )
        if scope_conds:
            stmt = stmt.where(or_(*scope_conds))
    elif scoped_tables is not None:
        names = {f"{s}.{t}" for s, t in scoped_tables}
        stmt = stmt.where(
            or_(AssetRelation.from_table.in_(names), AssetRelation.to_table.in_(names))
        )
    if schema:
        stmt = stmt.where(
            (AssetRelation.from_schema_name == schema)
            | (AssetRelation.to_schema_name == schema)
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
    return stmt

def _count_stmt(stmt):
    return select(func.count()).select_from(stmt.order_by(None).subquery())

def _build_candidate_stmt(*, schema, scoped_tables, keyword):
    stmt = select(AssetCandidateRelation).where(AssetCandidateRelation.status == "candidate")
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            AssetCandidateRelation.from_table.ilike(like)
            | AssetCandidateRelation.to_table.ilike(like)
        )
    if schema:
        stmt = stmt.where(
            (AssetCandidateRelation.from_table.startswith(f"{schema}."))
            | (AssetCandidateRelation.to_table.startswith(f"{schema}."))
        )
    if scoped_tables is not None:
        names = {f"{s}.{t}" for s, t in scoped_tables}
        stmt = stmt.where(or_(AssetCandidateRelation.from_table.in_(names), AssetCandidateRelation.to_table.in_(names)))
    return stmt

def _candidate_endpoint_key(db: Session, table: str) -> str | None:
    """候选关系端点：优先 asset_tables 唯一物理匹配；多/零命中返回 None。"""
    ns, _schema, _table_name = _split_table_name(table)
    matches = _resolve_table_filter(db, table)
    if len(matches) == 1:
        m = matches[0]
        return _physical_key(m[0], m[1], ns, m[2], m[3])
    return None
