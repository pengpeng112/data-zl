"""关系图谱 API（108 号专项整改版）。

P0/P1 整改要点（与 schemas/graph.py 严格对齐，extra="forbid" 防止字段静默丢弃）：
1. GraphNode.id 使用完整物理键 system_code|source_code|namespace_name|schema_name|table_name；
2. display_id 仅用于展示（SCHEMA.TABLE），不再作为图节点唯一键；
3. 边 source/target 使用完整物理键；边 id 使用稳定 relation_business_key；
4. _table_map_for 不再用 schema.table 作为唯一字典键（跨系统同名表不会相互覆盖）；
5. 邻居查询优先接受 physical_key 或 system/source/schema/table；旧 table 参数仅在唯一匹配时兼容；
6. diagnostics 不再按起止表判断重复，改为统计稳定业务键重复/未解析端点/物理键缺失等。
"""
from __future__ import annotations

import hashlib
import re
from itertools import zip_longest
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...models.asset import AssetColumn, AssetRelation, AssetTable
from ...models.candidate import AssetCandidateRelation
from ...models.lineage import AssetViewDependency
from ...schemas.common import ApiResponse
from ...schemas.graph import (
    GraphData,
    GraphEdge,
    GraphFieldMapping,
    GraphMeta,
    GraphNode,
    GraphOptions,
)
from ...services.relation_identity import resolve_endpoint, split_qualified_name

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

# 旧前端曾经把 HIS.PAT_VISIT 映射到 MEDREC.PAT_VISIT；保留仅用于旧 table 参数兼容。
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


def _physical_key(
    system_code: str | None,
    source_code: str | None,
    namespace_name: str | None,
    schema_name: str | None,
    table_name: str | None,
) -> str | None:
    """完整物理键 = system_code|source_code|namespace_name|schema_name|table_name。

    108号 §3.1：缺少 system/source/schema/table 的关系不能进入正式图层，不得退化成空前缀物理键。
    """
    if not system_code or not source_code or not schema_name or not table_name:
        return None
    return "|".join([
        system_code,
        source_code,
        namespace_name or "",
        schema_name,
        table_name,
    ])


def _display_id(schema_name: str | None, table_name: str | None) -> str | None:
    if schema_name and table_name:
        return f"{schema_name}.{table_name}"
    return table_name or schema_name or None


def _split_table_name(full_name: str) -> tuple[str | None, str | None, str | None]:
    """把 'SCHEMA.TABLE' 或 'NS.SCHEMA.TABLE' 拆成 (namespace, schema, table)。

    兼容 [VIEW] 前缀（依赖图专用）。
    """
    if not full_name:
        return None, None, None
    if full_name.startswith("[VIEW] "):
        return None, "VIEW", full_name.replace("[VIEW] ", "", 1)
    ns, schema, table = split_qualified_name(full_name)
    return ns, schema, table


def _resolve_endpoint_lenient(
    db: Session,
    schema_name: str | None,
    table_name: str | None,
) -> tuple[str | None, str | None]:
    """宽松物理来源反查：按 (schema, table) 收集 (system, source) 唯一 pair。

    与共享 resolve_endpoint 的区别：不限定 namespace 是否 NULL/""，兼容
    namespace_name=schema 的历史回填数据与 2 段式表名。多命中不猜（返回 None）。
    """
    if not schema_name or not table_name:
        return None, None
    rows = db.execute(
        select(AssetTable.system_code, AssetTable.source_code).where(
            AssetTable.schema_name == schema_name,
            AssetTable.table_name == table_name,
        )
    ).all()
    pairs = {(r[0], r[1]) for r in rows if r[0] and r[1]}
    if len(pairs) == 1:
        return next(iter(pairs))
    return None, None


def _resolve_relation_endpoint(
    db: Session,
    r: AssetRelation,
    side: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """从一条 AssetRelation 提取端点的五元组 + 展示名。

    返回 (system, source, namespace, schema, table, display_id)。
    优先使用已回填的物理字段；缺失时回退到 from_table/to_table 文本拆分；
    仍未解析出 system/source 时按 asset_tables 唯一物理匹配反查（多命中不猜，返回 None）。
    """
    if side == "from":
        sys_c = r.from_system_code
        src_c = r.from_source_code
        ns = r.from_namespace_name
        schema = r.from_schema_name
        table = r.from_table_name
        raw = r.from_table
    else:
        sys_c = r.to_system_code
        src_c = r.to_source_code
        ns = r.to_namespace_name
        schema = r.to_schema_name
        table = r.to_table_name
        raw = r.to_table
    if not sys_c or not src_c or not schema or not table:
        # 物理字段缺失时尝试从文本拆分（namespace/schema/table）
        if raw:
            ns2, schema2, table2 = _split_table_name(raw)
            ns = ns or ns2
            schema = schema or schema2
            table = table or table2
    if (not sys_c or not src_c) and schema and table:
        # 按 (namespace, schema, table) 唯一反查 system/source；多命中不猜（返回 None）。
        # 先精确（含 namespace），再宽松（仅 schema+table 唯一 pair）。
        sys_c, src_c = resolve_endpoint(db, ns, schema, table)
        if sys_c is None or src_c is None:
            sys_c, src_c = _resolve_endpoint_lenient(db, schema, table)
    display = _display_id(schema, table)
    return sys_c, src_c, ns, schema, table, display


def _endpoint_physical_key(db: Session, r: AssetRelation, side: str) -> str | None:
    sys_c, src_c, ns, schema, table, _ = _resolve_relation_endpoint(db, r, side)
    return _physical_key(sys_c, src_c, ns, schema, table)


def _stable_edge_id(
    r: AssetRelation,
    from_key: str | None,
    to_key: str | None,
) -> str:
    """稳定边 ID = relation_business_key；缺失时用 rel:{db_id}（可反查，不随环境漂移）。

    数据库自增 id 只作为 db_id 属性保留，不作为跨环境永久身份（108号 §3.2）。
    对已回填业务键的正式关系，返回业务键；未回填的旧行退化为 rel:{id}。
    """
    if r.relation_business_key:
        return r.relation_business_key
    return f"rel:{r.id}"


def _candidate_edge_id(cr: AssetCandidateRelation) -> str:
    raw = "|".join([
        cr.from_table or "", cr.from_columns or "",
        cr.to_table or "", cr.to_columns or "",
        cr.join_condition or "", cr.source_view or "",
    ]).lower()
    return f"candidate:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


GRAPH_VIEW_MODES = [
    {
        "code": "system",
        "label": "系统关系",
        "description": "按 HIS、ODS 等系统大类观察资产关系。",
        "group_by": "system",
        "layout_mode": "grouped",
        "confidence": "A",
        "validation_status": None,
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
        "validation_status": None,
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
        "validation_status": None,
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
        "validation_status": None,
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
        "validation_status": None,
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


def _table_full(schema_name: str | None, table_name: str | None) -> str | None:
    if not schema_name or not table_name:
        return None
    return f"{schema_name}.{table_name}"


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
    for t in rows:
        key = _physical_key(t.system_code, t.source_code, t.namespace_name, t.schema_name, t.table_name)
        if key:
            result[key] = t
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
        if from_key not in node_meta:
            node_meta[from_key] = from_ep
        if to_key not in node_meta:
            node_meta[to_key] = to_ep
        edges.append(_build_edge(r, from_key, to_key, f_disp, t_disp, from_ep, to_ep))

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
    )


def _data_version() -> str:
    """数据版本：构建时环境注入或退化为 build_id（不连接数据库的确定性值）。"""
    return settings.git_sha or settings.build_id


def _filters_dict(**kwargs) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None and v is not False}


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
    """应用关系过滤条件（供全局/邻居共用）。系统/数据源范围优先按关系物理端点字段过滤。"""
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


def _resolve_table_filter(db: Session, table: str) -> list[tuple[str, str, str, str]]:
    """把旧 table=SCHEMA.TABLE 参数解析为物理端点 (system, source, schema, table)。

    多命中返回多条，调用方决定 409 或空图；禁止随机选择（108号 P1-05）。
    """
    candidates: set[tuple[str, str, str, str]] = set()
    names = _aliases_for(table)
    rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.schema_name + "." + AssetTable.table_name).in_(list(names))
        )
    ).all()
    for t in rows:
        if t.system_code and t.source_code and t.schema_name and t.table_name:
            candidates.add((t.system_code, t.source_code, t.schema_name, t.table_name))
    return sorted(candidates)


def _resolve_neighbor_target(
    db: Session,
    *,
    physical_key: str | None,
    system_code: str | None,
    source_code: str | None,
    schema: str | None,
    table: str | None,
) -> str:
    """邻居查询目标：优先物理键或 system/source/schema/table；旧 table 参数唯一兼容。"""
    if physical_key:
        return physical_key
    if system_code and source_code and schema and table:
        key = _physical_key(system_code, source_code, None, schema, table)
        if not key:
            raise HTTPException(status_code=422, detail="system/source/schema/table 不能为空")
        return key
    if table:
        matches = _resolve_table_filter(db, table)
        if not matches:
            raise HTTPException(status_code=404, detail=f"未找到表 {table} 的物理端点")
        if len(matches) > 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"表 {table} 存在多个物理来源，请指定 system_code/source_code/schema/table 或 physical_key",
                    "candidates": [
                        {
                            "physical_key": _physical_key(m[0], m[1], None, m[2], m[3]),
                            "system_code": m[0],
                            "source_code": m[1],
                            "schema_name": m[2],
                            "table_name": m[3],
                        }
                        for m in matches
                    ],
                },
            )
        m = matches[0]
        key = _physical_key(m[0], m[1], None, m[2], m[3])
        return key or ""
    raise HTTPException(status_code=422, detail="必须提供 physical_key 或 system/source/schema/table，或唯一 table")


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
    limit: int = Query(120, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphData]:
    scoped_tables = _table_scope_names(db, system_code, source_code)
    scoped_physical = _table_scope_physical(db, system_code, source_code)
    filters = _filters_dict(
        system_code=system_code, source_code=source_code, schema=schema,
        domain=domain, validation_status=validation_status, confidence=confidence,
        keyword=keyword, include_candidates=include_candidates,
        include_dependencies=include_dependencies, limit=limit,
    )
    total_relations = db.scalar(select(func.count()).select_from(AssetRelation)) or 0
    if scoped_tables is not None and not scoped_tables:
        return ApiResponse(
            data=GraphData(
                nodes=[],
                edges=[],
                meta=_graph_meta(total_relations, 0, 0, False, 0, filters),
            )
        )

    stmt = _build_relation_filter_stmt(
        select(AssetRelation),
        schema=schema,
        domain=domain,
        scoped_tables=scoped_tables,
        scoped_physical=scoped_physical,
        validation_status=validation_status,
        confidence=confidence,
        keyword=keyword,
    )
    matched = db.scalar(_count_stmt(stmt)) or 0
    rows = db.scalars(
        stmt.order_by(AssetRelation.id).limit(limit)
    ).all()
    nodes, edges, unresolved = _nodes_and_edges_for_relations(db, rows)
    truncated = matched > len(rows)
    unresolved_set = set(unresolved)

    if include_candidates and len(edges) < limit:
        cand_stmt = _build_candidate_stmt(
            schema=schema,
            scoped_tables=scoped_tables,
            keyword=keyword,
        )
        cand_rows = db.scalars(cand_stmt.limit(limit - len(edges))).all()
        for cr in cand_rows:
            from_key = _candidate_endpoint_key(db, cr.from_table)
            to_key = _candidate_endpoint_key(db, cr.to_table)
            if not from_key or not to_key:
                continue
            edges.append(_build_candidate_edge(cr, from_key, to_key, cr.from_table, cr.to_table))

    if include_dependencies and len(edges) < limit:
        dep_rows = db.scalars(
            select(AssetViewDependency).where(AssetViewDependency.view_name.isnot(None))
            .order_by(AssetViewDependency.id).limit(limit - len(edges))
        ).all()
        for dep in dep_rows:
            from_disp = _table_full(dep.referenced_schema, dep.referenced_table) or dep.referenced_table
            view_key = f"[VIEW] {dep.view_name}"
            from_key = _physical_key(None, None, None, dep.referenced_schema, dep.referenced_table)
            edges.append(GraphEdge(
                id=f"dependency:{dep.view_name}#{dep.id}",
                source=from_key or from_disp,
                target=view_key,
                display_source=from_disp,
                display_target=view_key,
                label="view depends",
                relation_type="dependency",
                relation_layer="dependency",
                rel_id=dep.id,
                validation_note=dep.view_name,
            ))

    # 补充候选/依赖边涉及的节点
    existing_ids = {n.id for n in nodes}
    for edge in edges:
        if edge.relation_type in ("candidate", "dependency"):
            for key, disp in ((edge.source, edge.display_source), (edge.target, edge.display_target)):
                if key in existing_ids or not disp:
                    continue
                parts = key.split("|")
                if len(parts) == 5:
                    nodes.append(GraphNode(
                        id=key,
                        physical_key=key if key and not key.startswith("[VIEW] ") else None,
                        display_id=disp,
                        label=parts[4] or disp,
                        schema_name=parts[3],
                        table_name=parts[4],
                        category=parts[3],
                    ))
                else:
                    nodes.append(GraphNode(
                        id=key,
                        physical_key=None,
                        display_id=disp,
                        label=disp,
                        schema_name=parts[3] if len(parts) > 3 else None,
                        table_name=parts[4] if len(parts) > 4 else disp,
                        category=parts[3] if len(parts) > 3 else None,
                    ))
                existing_ids.add(key)

    return ApiResponse(
        data=GraphData(
            nodes=nodes,
            edges=edges,
            meta=_graph_meta(
                total_relations,
                matched,
                len(edges),
                truncated,
                len(unresolved_set),
                filters,
            ),
        )
    )


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


@router.get("/edges/{edge_id}", response_model=ApiResponse[GraphEdge], summary="单条边证据详情")
def edge_detail(
    edge_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[GraphEdge]:
    """边证据详情：按需加载字段映射与验证指标（P1-04 摘要/详情分离）。"""
    row = db.scalar(select(AssetRelation).where(AssetRelation.relation_business_key == edge_id))
    if not row and edge_id.isdigit():
        row = db.get(AssetRelation, int(edge_id))
    if not row and edge_id.startswith("rel:"):
        try:
            row = db.get(AssetRelation, int(edge_id[4:]))
        except ValueError:
            row = None
    if not row:
        raise HTTPException(status_code=404, detail="边不存在")
    from_key = _endpoint_physical_key(db, row, "from")
    to_key = _endpoint_physical_key(db, row, "to")
    edge = _build_edge(
        row, from_key, to_key,
        _resolve_relation_endpoint(db, row, "from")[5],
        _resolve_relation_endpoint(db, row, "to")[5],
    )
    column_map = _column_map_for(db, {k for k in (from_key, to_key) if k})
    from_schema, from_table = row.from_schema_name, row.from_table_name
    to_schema, to_table = row.to_schema_name, row.to_table_name
    if not from_table:
        _, from_schema, from_table = _split_table_name(row.from_table or "")
    if not to_table:
        _, to_schema, to_table = _split_table_name(row.to_table or "")
    edge.field_mappings = _field_mappings_for(
        db, from_schema, from_table, to_schema, to_table,
        edge.from_columns, edge.to_columns, column_map,
    )
    return ApiResponse(data=edge)


@router.get("/neighbors", response_model=ApiResponse[GraphData], summary="某表邻居图")
def neighbors(
    table: str | None = Query(None, description="旧参数：表名，如 HIS.PAT_VISIT（仅物理唯一时兼容）"),
    physical_key: str | None = Query(None, description="完整物理键 system|source|namespace|schema|table"),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    schema: str | None = Query(None),
    depth: int = Query(1, ge=1, le=2),
    direction: str = Query("both", pattern="^(in|out|both)$"),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphData]:
    target = _resolve_neighbor_target(
        db,
        physical_key=physical_key,
        system_code=system_code,
        source_code=source_code,
        schema=schema,
        table=table,
    )
    if not target:
        raise HTTPException(status_code=404, detail="未找到目标物理端点")

    target_parts = target.split("|")
    if len(target_parts) != 5:
        raise HTTPException(status_code=422, detail="physical_key 格式应为 system|source|namespace|schema|table")
    t_sys, t_src, _t_ns, t_schema, t_tbl = target_parts
    t_display = _display_id(t_schema, t_tbl)
    target_texts = _aliases_for(t_display) if t_display else set()

    collected: list[AssetRelation] = []
    seen: set[int] = set()
    # 边界集合：物理四元组 (system, source, schema, table)
    frontier: set[tuple[str, str, str, str]] = {(t_sys, t_src, t_schema, t_tbl)}

    def _node_texts(node: tuple[str, str, str, str]) -> set[str]:
        """物理节点对应的展示文本集合（含 legacy alias）。"""
        display = _display_id(node[2], node[3])
        return _aliases_for(display) if display else set()

    for _ in range(depth):
        if not frontier:
            break
        conds = []
        frontier_texts: set[str] = set()
        for node in frontier:
            frontier_texts |= _node_texts(node)
            if direction in ("out", "both"):
                conds.append(
                    (AssetRelation.from_system_code == node[0])
                    & (AssetRelation.from_source_code == node[1])
                    & (AssetRelation.from_schema_name == node[2])
                    & (AssetRelation.from_table_name == node[3])
                )
            if direction in ("in", "both"):
                conds.append(
                    (AssetRelation.to_system_code == node[0])
                    & (AssetRelation.to_source_code == node[1])
                    & (AssetRelation.to_schema_name == node[2])
                    & (AssetRelation.to_table_name == node[3])
                )
        if frontier_texts:
            if direction in ("out", "both"):
                conds.append(AssetRelation.from_table.in_(frontier_texts))
            if direction in ("in", "both"):
                conds.append(AssetRelation.to_table.in_(frontier_texts))
        if not conds:
            break
        stmt = select(AssetRelation).where(or_(*conds)).order_by(AssetRelation.id).limit(limit)
        rows = db.scalars(stmt).all()
        next_frontier: set[tuple[str, str, str, str]] = set()
        for r in rows:
            if r.id in seen:
                continue
            seen.add(r.id)
            collected.append(r)
            for side in ("from", "to"):
                f_sys2, f_src2, _f_ns, f_schema2, f_tbl2, _disp = _resolve_relation_endpoint(db, r, side)
                if f_sys2 and f_src2 and f_schema2 and f_tbl2 and (f_sys2, f_src2, f_schema2, f_tbl2) not in frontier:
                    next_frontier.add((f_sys2, f_src2, f_schema2, f_tbl2))
            if len(collected) >= limit:
                break
        frontier = next_frontier
        if len(collected) >= limit:
            break

    nodes, edges, _ = _nodes_and_edges_for_relations(db, collected)
    return ApiResponse(
        data=GraphData(
            nodes=nodes,
            edges=edges,
            meta=_graph_meta(
                total_relations=db.scalar(select(func.count()).select_from(AssetRelation)) or 0,
                matched_relations=len(collected),
                returned_relations=len(edges),
                truncated=len(collected) > limit,
                unresolved_count=0,
                filters={"physical_key": target, "depth": depth, "direction": direction, "limit": limit},
            ),
        )
    )


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
            validation_statuses=sorted({s for s in statuses_rows if s}),
            confidences=sorted([c for c in confidences_rows if c]),
            relation_types=["formal", "candidate", "dependency"],
            view_modes=GRAPH_VIEW_MODES,
            default_mode="table",
            backend_build_id=settings.build_id,
        )
    )


@router.get("/diagnostics", summary="关系图谱数据诊断（108号重构口径）")
def diagnostics(db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """108号 §六：统计总表数/总关系数/层级/状态/置信度/物理键缺失/未解析端点/
    稳定业务键重复/孤儿引用/数据版本/后端 build ID。

    合法同端点多边不视为不健康；只有真正重复业务键、未解析端点才降低健康度。
    """
    total_tables = db.scalar(select(func.count()).select_from(AssetTable)) or 0
    total_relations = db.scalar(select(func.count()).select_from(AssetRelation)) or 0

    layer_rows = db.execute(
        select(AssetRelation.relation_layer, func.count()).group_by(AssetRelation.relation_layer)
    ).all()
    layer_dist = {r[0] or "unset": r[1] for r in layer_rows}

    status_rows = db.execute(
        select(AssetRelation.validation_status, func.count()).group_by(AssetRelation.validation_status)
    ).all()
    status_dist = {r[0] or "unset": r[1] for r in status_rows}
    conf_rows = db.execute(
        select(AssetRelation.confidence, func.count()).group_by(AssetRelation.confidence)
    ).all()
    conf_dist = {r[0] or "unset": r[1] for r in conf_rows}

    missing_physical = db.scalar(
        select(func.count()).select_from(AssetRelation).where(
            (AssetRelation.from_system_code.is_(None))
            | (AssetRelation.from_source_code.is_(None))
            | (AssetRelation.from_schema_name.is_(None))
            | (AssetRelation.from_table_name.is_(None))
            | (AssetRelation.to_system_code.is_(None))
            | (AssetRelation.to_source_code.is_(None))
            | (AssetRelation.to_schema_name.is_(None))
            | (AssetRelation.to_table_name.is_(None))
        )
    ) or 0

    unresolved_count = 0
    rows = db.scalars(select(AssetRelation)).all()
    unresolved_samples: list[str] = []
    for r in rows:
        from_key = _endpoint_physical_key(db, r, "from")
        to_key = _endpoint_physical_key(db, r, "to")
        if not from_key or not to_key:
            unresolved_count += 1
            if len(unresolved_samples) < 5:
                unresolved_samples.append(
                    f"{r.from_table} -> {r.to_table} (from_complete={bool(from_key)}, to_complete={bool(to_key)})"
                )

    business_key_dups = db.scalar(
        select(func.count()).select_from(
            select(AssetRelation.relation_business_key).where(
                AssetRelation.relation_business_key.isnot(None)
            ).group_by(
                AssetRelation.relation_business_key
            ).having(func.count() > 1).subquery()
        )
    ) or 0

    # 孤儿引用：关系端点表在 asset_tables 中不存在（视图特殊节点除外）
    table_names = {
        f"{t.schema_name}.{t.table_name}"
        for t in db.scalars(select(AssetTable)).all()
        if t.schema_name and t.table_name
    }
    orphan_names: set[str] = set()
    for r in rows:
        for name in (r.from_table, r.to_table):
            if not name or name.startswith("[VIEW] "):
                continue
            if name not in table_names:
                orphan_names.add(name)
    orphan_count = len(orphan_names)

    warnings: list[str] = []
    healthy = True
    if total_relations == 0:
        warnings.append("当前没有关系数据")
        healthy = False
    if total_tables == 0:
        warnings.append("资产表目录为空")
        healthy = False
    if unresolved_count:
        warnings.append(f"存在 {unresolved_count} 条关系端点未解析为完整物理键（不会进入正式图层）")
        healthy = False
    if missing_physical:
        warnings.append(f"存在 {missing_physical} 条关系缺少物理端点字段（system/source/schema/table）")
        healthy = False
    if business_key_dups:
        warnings.append(f"存在 {business_key_dups} 组稳定业务键重复，需要治理")
        healthy = False

    # 同端点多关系组（信息项，不是错误）
    same_endpoint_groups = db.scalar(
        select(func.count()).select_from(
            select(AssetRelation.from_table, AssetRelation.to_table).group_by(
                AssetRelation.from_table, AssetRelation.to_table
            ).having(func.count() > 1).subquery()
        )
    ) or 0

    return ApiResponse(data={
        "table_count": total_tables,
        "relation_count": total_relations,
        "layer_distribution": layer_dist,
        "validation_status_distribution": status_dist,
        "confidence_distribution": conf_dist,
        "missing_physical_endpoints": missing_physical,
        "unresolved_endpoints": unresolved_count,
        "unresolved_samples": unresolved_samples,
        "duplicate_business_keys": business_key_dups,
        "same_endpoint_multi_edges": same_endpoint_groups,
        "orphan_references": orphan_count,
        "orphan_samples": sorted(list(orphan_names))[:5],
        "warnings": warnings,
        "healthy": healthy,
        "data_version": _data_version(),
        "backend_build_id": settings.build_id,
    })
