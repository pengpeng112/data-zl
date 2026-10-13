"""关系图谱 API（108 号专项整改版；215 E11 起实现拆至 graph_parts/ 子模块）。

P0/P1 整改要点（与 schemas/graph.py 严格对齐，extra="forbid" 防止字段静默丢弃）：
1. GraphNode.id 使用完整物理键 system_code|source_code|namespace_name|schema_name|table_name；
2. display_id 仅用于展示（SCHEMA.TABLE），不再作为图节点唯一键；
3. 边 source/target 使用完整物理键；边 id 使用稳定 relation_business_key；
4. _table_map_for 不再用 schema.table 作为唯一字典键（跨系统同名表不会相互覆盖）；
5. 邻居查询优先接受 physical_key 或 system/source/schema/table；旧 table 参数仅在唯一匹配时兼容；
6. diagnostics 不再按起止表判断重复，改为统计稳定业务键重复/未解析端点/物理键缺失等。

215 E11 门面约定：本文件保留 router 与全部路由（含 169 P1 聚合分支的
resolver 复用实现，test_graph_overview_fix_169 源码护栏锚定于此）；
端点解析/构建/概览支撑移入 graph_parts/{resolution,builders,overview_support}，
此处 re-import 兼容既有 from app.api.v1.graph import <helper> 用法。
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import require_permission
from ...models.asset import AssetRelation, AssetTable
from ...models.asset_system import AssetDataSource, AssetSourceSchema
from ...models.lineage import AssetViewDependency
from ...schemas.common import ApiResponse
from ...schemas.graph import (
    GraphData,
    GraphEdge,
    GraphFilterOption,
    GraphFilterOptionsData,
    GraphNode,
    GraphOptionItem,
    GraphOptions,
    GraphOverviewData,
    GraphTableSearchItem,
)
from ...services.asset_catalog import (
    load_system_name_map,
    normalize_system_code,
)
from ...services.data_masking import sanitize_text
from .graph_parts.builders import (
    GRAPH_VIEW_MODES,
    SCHEMA_COLORS as SCHEMA_COLORS,
    _build_candidate_edge,
    _build_candidate_stmt,
    _build_edge,
    _build_relation_filter_stmt,
    _candidate_endpoint_key,
    _column_map_for,
    _count_stmt,
    _data_version,
    _enrichment_stats,
    _field_mappings_for,
    _filters_dict,
    _graph_meta,
    _graph_node_for,
    _nodes_and_edges_for_relations,
    _table_full,
    _table_map_by_physical_key as _table_map_by_physical_key,
    _table_scope_names,
    _table_scope_physical,
    _enrich_edge_table_meta as _enrich_edge_table_meta,
    _is_deferred_confidence as _is_deferred_confidence,
    _split_relation_columns as _split_relation_columns,
)
from .graph_parts.overview_support import (
    _apply_asset_filters,
    _field_overview,
    _field_node_id as _field_node_id,
    _object_type_name,
    _overview_id,
    _overview_node,
    _parse_parent_path,
)
from .graph_parts.resolution import (
    _EndpointResolver,
    _aliases_for,
    _candidate_edge_id as _candidate_edge_id,
    _display_id,
    _endpoint_physical_key,
    _physical_key,
    _resolve_endpoint_lenient as _resolve_endpoint_lenient,
    _resolve_neighbor_target,
    _resolve_relation_endpoint,
    _resolve_table_filter as _resolve_table_filter,
    _split_table_name,
    _stable_edge_id as _stable_edge_id,
)

router = APIRouter(
    prefix="/api/v1/graph",
    tags=["graph"],
    dependencies=[Depends(require_permission("asset.graph.view"))],
)

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
                enrichment=_enrichment_stats(nodes),
            ),
        )
    )

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
    if edge.join_condition:
        edge.sql_hash = hashlib.sha256(edge.join_condition.encode("utf-8")).hexdigest()
        edge.sql_snippet = sanitize_text(edge.join_condition, limit=200)
    # 详情响应只暴露脱敏摘要；原始 SQL 不出接口，也不得进入日志。
    edge.join_condition = None
    return ApiResponse(data=edge)

@router.get("/neighbors", response_model=ApiResponse[GraphData], summary="某表邻居图")
def neighbors(
    table: str | None = Query(None, description="旧参数：表名，如 HIS.PAT_VISIT（仅物理唯一时兼容）"),
    physical_key: str | None = Query(None, description="完整物理键 system|source|namespace|schema|table"),
    center_physical_key: str | None = Query(None, description="关系探索中心物理键（physical_key 的明确别名）"),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    schema: str | None = Query(None),
    depth: int = Query(2, ge=1, le=3),
    direction: str = Query("both", pattern="^(in|out|both)$"),
    limit: int = Query(100, ge=1, le=200),
    include: list[str] | None = Query(None, description="客户端已持有的五段物理键，可重复传入"),
    cursor: str | None = Query(None, description="继续加载游标（稳定边偏移量）"),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphData]:
    try:
        offset = max(0, int(cursor or "0"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="cursor 必须是非负整数") from exc
    include_keys = set(include or [])
    if any(len(value.split("|")) != 5 for value in include_keys):
        raise HTTPException(status_code=422, detail="include 必须使用五段物理键")
    target = _resolve_neighbor_target(
        db,
        physical_key=center_physical_key or physical_key,
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
        # asset_relations 是治理关系资产而非业务大表；完整收集命中边，才能返回真实 actual_count。
        # 最终响应仍严格按 limit/cursor 分页，不把全量关系下发给客户端。
        stmt = select(AssetRelation).where(or_(*conds)).order_by(AssetRelation.id)
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
        frontier = next_frontier

    actual_count = len(collected)
    has_more = actual_count > offset + limit
    page_relations = collected[offset:offset + limit]
    nodes, edges, _ = _nodes_and_edges_for_relations(db, page_relations)
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        out_degree[edge.source] += 1
        in_degree[edge.target] += 1
    for node in nodes:
        node.in_degree = in_degree[node.id]
        node.out_degree = out_degree[node.id]
    # 已持有节点不重复下发；连接新节点所需的边仍保留，由客户端按边 ID 去重。
    response_nodes = [node for node in nodes if node.id not in include_keys]
    return ApiResponse(
        data=GraphData(
            nodes=response_nodes,
            edges=edges,
            meta=_graph_meta(
                total_relations=db.scalar(select(func.count()).select_from(AssetRelation)) or 0,
                matched_relations=actual_count,
                returned_relations=len(edges),
                truncated=has_more,
                unresolved_count=0,
                filters={"center_physical_key": target, "depth": depth, "direction": direction, "limit": limit},
                enrichment=_enrichment_stats(nodes),
                center_physical_key=target,
                direction_semantics="all/in/out",
                shown_count=len(response_nodes),
                actual_count=actual_count,
                continuation_cursor=str(offset + limit) if has_more else None,
            ),
        )
    )

@router.get("/overview", response_model=ApiResponse[GraphOverviewData], summary="服务端完整资产概览")
def overview(
    level: str = Query("system", pattern="^(system|source|schema|object|field)$"),
    parent_physical_key: str | None = Query(None),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    schema: str | None = Query(None),
    domain: str | None = Query(None),
    object_type: str | None = Query(None, pattern="^(table|view)$"),
    limit: int = Query(80, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphOverviewData]:
    started = perf_counter()
    p_sys, p_src, p_ns, p_schema, p_table = _parse_parent_path(parent_physical_key)
    system_code, source_code, schema = system_code or p_sys, source_code or p_src, schema or p_schema
    if level == "source" and not system_code:
        raise HTTPException(status_code=422, detail="source 概览必须提供 system_code 或 parent_physical_key")
    if level == "schema" and not system_code:
        raise HTTPException(status_code=422, detail="schema 概览必须提供 system_code 或 parent_physical_key")
    if level == "object" and (not system_code or not schema):
        raise HTTPException(status_code=422, detail="object 概览必须提供 system_code 和 schema")
    if level == "field":
        if not parent_physical_key or not p_sys or not p_src or not p_schema or not p_table:
            raise HTTPException(status_code=422, detail="field 概览必须提供完整表物理键 parent_physical_key")
        return _field_overview(
            db,
            table_physical_key=parent_physical_key,
            system_code=p_sys,
            source_code=p_src,
            namespace_name=p_ns,
            schema_name=p_schema,
            table_name=p_table,
            limit=limit,
            started=started,
        )
    base = _apply_asset_filters(select(AssetTable), system_code=system_code, source_code=source_code, schema_name=schema, domain=domain, object_type=object_type)
    matched_assets = db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    # 169 P5：聚合分支的关系计数口径（真实关系数，非表数；空结果分支的安全默认 0）
    total_relations_filtered = 0
    matched_relations = 0
    if level == "object":
        rows = db.scalars(base.order_by(AssetTable.schema_name, AssetTable.table_name).limit(limit)).all()
        object_candidates: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
        for table in rows:
            key = _physical_key(table.system_code, table.source_code, table.namespace_name, table.schema_name, table.table_name)
            if not key:
                continue
            node = _graph_node_for(key, _display_id(table.schema_name, table.table_name), table.system_code, table.source_code, table.namespace_name, table.schema_name, table.table_name, table)
            node.asset_count, node.child_count, node.object_type, node.technical_name = 1, 1, _object_type_name(table), _table_full(table.schema_name, table.table_name)
            node.category = node.object_type
            nodes.append(node)
            if table.system_code and table.source_code and table.schema_name and table.table_name:
                object_candidates[(table.system_code, table.source_code, table.schema_name, table.table_name)].append(key)

        object_ids = {
            logical_key: candidates[0]
            for logical_key, candidates in object_candidates.items()
            if len(candidates) == 1
        }

        # 对象层展示真实表间关系，上一层 Schema 节点不继续占据画布。
        # 历史关系 namespace 可能为空，因此先按唯一逻辑四元组定位到当前展示节点，
        # 再把边端点替换为资产表的完整物理键，避免同名跨来源串边。
        endpoint_resolver = _EndpointResolver.load(db)
        seen_edge_ids: set[str] = set()
        for relation in db.scalars(select(AssetRelation)).all():
            from_ep = _resolve_relation_endpoint(db, relation, "from", resolver=endpoint_resolver)
            to_ep = _resolve_relation_endpoint(db, relation, "to", resolver=endpoint_resolver)
            f_sys, f_src, _f_ns, f_schema, f_table, f_display = from_ep
            t_sys, t_src, _t_ns, t_schema, t_table, t_display = to_ep
            if not all((f_sys, f_src, f_schema, f_table, t_sys, t_src, t_schema, t_table)):
                continue
            from_key = object_ids.get((f_sys, f_src, f_schema, f_table))
            to_key = object_ids.get((t_sys, t_src, t_schema, t_table))
            if not from_key or not to_key or from_key == to_key:
                continue
            edge = _build_edge(relation, from_key, to_key, f_display, t_display, from_ep, to_ep)
            if edge.id in seen_edge_ids:
                continue
            seen_edge_ids.add(edge.id)
            edges.append(edge)
    else:
        system_names = load_system_name_map(db)
        source_names = {
            row[0]: row[1]
            for row in db.execute(select(AssetDataSource.source_code, AssetDataSource.source_name_cn)).all()
            if row[0]
        }
        schema_names = {
            (row[0], row[1]): row[2]
            for row in db.execute(
                select(AssetSourceSchema.source_code, AssetSourceSchema.schema_name, AssetSourceSchema.schema_name_cn)
            ).all()
            if row[0] and row[1] and row[2]
        }
        ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
        if level == "system":
            raw_rows = db.execute(
                base.with_only_columns(AssetTable.system_code, func.count(AssetTable.id)).group_by(AssetTable.system_code)
            ).all()
            merged: dict[str, int] = {}
            for raw_code, cnt in raw_rows:
                canon = normalize_system_code(raw_code) or (raw_code or "UNKNOWN")
                merged[canon] = merged.get(canon, 0) + int(cnt or 0)
            for canon, cnt in sorted(merged.items(), key=lambda item: (-item[1], item[0])):
                label = system_names.get(canon, canon)
                nodes.append(_overview_node("system", (canon,), label, cnt, path=canon))
        elif level == "source":
            stmt = (
                base.with_only_columns(AssetTable.system_code, AssetTable.source_code, func.count(AssetTable.id).label("asset_count"))
                .group_by(AssetTable.system_code, AssetTable.source_code)
                .order_by(func.count(AssetTable.id).desc())
                .limit(limit)
            )
            for row in db.execute(stmt).all():
                values = (row[0], row[1])
                label = source_names.get(row[1], str(row[1] or "未命名连接"))
                nodes.append(_overview_node("source", values, label, int(row[2] or 0), path="|".join(v or "" for v in values)))
        else:
            schema_stmt = (
                base.with_only_columns(ns_key.label("schema_key"), func.count(AssetTable.id))
                .group_by(ns_key)
                .order_by(func.count(AssetTable.id).desc())
                .limit(limit)
            )
            for row in db.execute(schema_stmt).all():
                schema_name = row[0] or "未命名"
                canon = normalize_system_code(system_code) or system_code
                label = schema_name
                for (_src, sch), cn in schema_names.items():
                    if sch == schema_name and cn:
                        label = cn
                        break
                display = f"{label}（{schema_name}）" if label != schema_name else schema_name
                nodes.append(
                    _overview_node(
                        "schema",
                        (canon, "", schema_name),
                        display,
                        int(row[1] or 0),
                        path=f"{canon}|{schema_name}",
                    )
                )
        if nodes:
            node_ids = {node.id for node in nodes}

            def _level_key(sys_c: str | None, src_c: str | None, sch: str | None) -> str | None:
                canon = normalize_system_code(sys_c) or sys_c
                if level == "system":
                    return _overview_id("system", (canon,)) if canon else None
                if level == "source":
                    return _overview_id("source", (canon, src_c)) if canon and src_c else None
                if not canon or not sch:
                    return None
                return _overview_id("schema", (canon, "", sch))

            rel_stmt = select(AssetRelation)
            if domain:
                rel_stmt = rel_stmt.where(AssetRelation.domain == domain)
            # 169 P1：复用端点解析缓存（与 object 层 1586 行同款）——此前逐条
            # _resolve_relation_endpoint 触发 N+1 全表反查，12702 表规模下 23.5s。
            endpoint_resolver = _EndpointResolver.load(db)
            total_relations_filtered = db.scalar(select(func.count()).select_from(rel_stmt.order_by(None).subquery())) or 0
            pair_counts: dict[tuple[str, str], int] = {}
            matched_relations = 0
            for rel in db.scalars(rel_stmt).all():
                f_sys, f_src, _f_ns, f_sch, _f_tbl, _f_disp = _resolve_relation_endpoint(db, rel, "from", resolver=endpoint_resolver)
                t_sys, t_src, _t_ns, t_sch, _t_tbl, _t_disp = _resolve_relation_endpoint(db, rel, "to", resolver=endpoint_resolver)
                f_id = _level_key(f_sys, f_src, f_sch)
                t_id = _level_key(t_sys, t_src, t_sch)
                if not f_id or not t_id or f_id == t_id:
                    continue
                if f_id not in node_ids or t_id not in node_ids:
                    continue
                pair_counts[(f_id, t_id)] = pair_counts.get((f_id, t_id), 0) + 1
                matched_relations += 1
            for (f_id, t_id), edge_count in sorted(pair_counts.items()):
                edges.append(GraphEdge(
                    id=f"overview-rel:{f_id}->{t_id}",
                    source=f_id,
                    target=t_id,
                    label=f"{edge_count} 条关系",
                    relation_type="formal",
                    relation_layer="aggregated",
                ))
    filters = {"level": level, "system_code": system_code, "source_code": source_code, "schema": schema, "domain": domain, "object_type": object_type, "limit": limit}
    if level == "object":
        meta = _graph_meta(
            db.scalar(select(func.count()).select_from(AssetRelation)) or 0,
            len(edges),
            len(edges),
            matched_assets > len(nodes),
            0,
            filters,
            query_ms=round((perf_counter() - started) * 1000, 2),
            warnings=[] if edges else ["当前表层暂无已治理的表间关系；仍可选择表查看字段图谱"],
        )
    else:
        # 169 P5：total/matched 填真实关系数（此前误填表数 12702，工具栏「总数/命中」误导）；
        # truncated=聚合去重导致的关系数落差（returned < matched），与 object 层口径一致。
        meta = _graph_meta(
            total_relations_filtered,
            matched_relations,
            len(edges),
            matched_relations > len(edges),
            0,
            filters,
            query_ms=round((perf_counter() - started) * 1000, 2),
            warnings=["结果已按层级聚合；继续下钻可查看真实表间关系和字段"],
        )
    meta.returned_nodes = len(nodes)
    meta.estimated_total = matched_assets
    next_level = {"system": "schema", "source": "schema", "schema": "object", "object": "field"}[level]
    return ApiResponse(data=GraphOverviewData(level=level, next_level=next_level, selected_path={k: v for k, v in (("system", system_code), ("source", source_code), ("schema", schema)) if v}, data=GraphData(nodes=nodes, edges=edges, meta=meta)))

@router.get("/filter-options", response_model=ApiResponse[GraphFilterOptionsData], summary="级联图谱筛选项")
def filter_options(
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    schema: str | None = Query(None),
    next_level: str = Query("system", pattern="^(system|source|schema|object)$"),
    db: Session = Depends(get_db),
) -> ApiResponse[GraphFilterOptionsData]:
    if next_level == "source" and not system_code:
        raise HTTPException(status_code=422, detail="source 级联选项需要 system_code")
    if next_level == "schema" and not system_code:
        raise HTTPException(status_code=422, detail="schema 级联选项需要 system_code")
    if next_level == "object" and (not system_code or not schema):
        raise HTTPException(status_code=422, detail="object 级联选项需要 system_code 和 schema")
    base = _apply_asset_filters(select(AssetTable), system_code=system_code, source_code=source_code, schema_name=schema, domain=None, object_type=None)
    field = {"system": AssetTable.system_code, "source": AssetTable.source_code, "schema": AssetTable.schema_name, "object": AssetTable.table_name}[next_level]
    rows = db.execute(base.with_only_columns(field, func.count(AssetTable.id)).group_by(field).order_by(field)).all()
    system_names = load_system_name_map(db)
    source_names = {
        row[0]: row[1]
        for row in db.execute(select(AssetDataSource.source_code, AssetDataSource.source_name_cn).where(AssetDataSource.source_code.isnot(None))).all()
        if row[0]
    }
    domain_rows = db.execute(base.with_only_columns(AssetTable.domain, func.count(AssetTable.id)).where(AssetTable.domain.isnot(None)).group_by(AssetTable.domain).order_by(AssetTable.domain)).all()
    type_rows = db.scalars(base).all()
    type_counts: dict[str, int] = defaultdict(int)
    for table in type_rows:
        type_counts[_object_type_name(table)] += 1
    names = system_names if next_level == "system" else source_names if next_level == "source" else {}
    return ApiResponse(data=GraphFilterOptionsData(
        selected_path={k: v for k, v in (("system", system_code), ("source", source_code), ("schema", schema)) if v},
        next_level=next_level,
        items=[GraphFilterOption(value=str(row[0]), label=names.get(str(row[0]), str(row[0])), count=int(row[1] or 0)) for row in rows if row[0]],
        business_domains=[GraphFilterOption(value=str(row[0]), label=str(row[0]), count=int(row[1] or 0)) for row in domain_rows if row[0]],
        object_types=[GraphFilterOption(value=k, label=k, count=v) for k, v in sorted(type_counts.items())],
    ))

@router.get("/tables/search", response_model=ApiResponse[dict[str, Any]], summary="物理资产搜索")
def table_search(
    q: str = Query(..., min_length=1, max_length=100),
    system_code: str | None = Query(None),
    source_code: str | None = Query(None),
    schema: str | None = Query(None),
    limit: int = Query(30, ge=1, le=30),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=422, detail="q 不能为空")
    stmt = _apply_asset_filters(select(AssetTable).where(or_(AssetTable.table_name.ilike(f"%{keyword}%"), AssetTable.table_name_cn.ilike(f"%{keyword}%"), AssetTable.schema_name.ilike(f"%{keyword}%"), AssetTable.namespace_name.ilike(f"%{keyword}%"))), system_code=system_code, source_code=source_code, schema_name=schema, domain=None, object_type=None)
    rows = db.scalars(stmt.order_by(AssetTable.system_code, AssetTable.source_code, AssetTable.schema_name, AssetTable.table_name).limit(limit * 3)).all()
    logical_counts: dict[tuple[str | None, str | None], int] = defaultdict(int)
    for table in rows:
        logical_counts[(table.schema_name, table.table_name)] += 1
    items: list[GraphTableSearchItem] = []
    seen: set[str] = set()
    for table in rows:
        key = _physical_key(table.system_code, table.source_code, table.namespace_name, table.schema_name, table.table_name)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(GraphTableSearchItem(physical_key=key, display_name=table.table_name_cn or table.table_name or key, technical_name=_table_full(table.schema_name, table.table_name) or key, system_code=table.system_code, source_code=table.source_code, namespace_name=table.namespace_name, schema_name=table.schema_name, table_name=table.table_name, object_type=_object_type_name(table), business_domain=table.domain, column_count=table.column_count, ambiguous=logical_counts[(table.schema_name, table.table_name)] > 1))
        if len(items) >= limit:
            break
    return ApiResponse(data={"items": [item.model_dump() for item in items], "total": len(items), "query": keyword})

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

    system_names = load_system_name_map(db)
    source_names = {
        row[0]: row[1]
        for row in db.execute(
            select(AssetDataSource.source_code, AssetDataSource.source_name_cn)
            .where(AssetDataSource.source_code.isnot(None))
        ).all()
        if row[0]
    }
    def option_items(values: list[Any], names: dict[str, str] | None = None) -> list[GraphOptionItem]:
        return [
            GraphOptionItem(value=value, label=(names or {}).get(value) or value)
            for value in sorted({str(value) for value in values if value})
        ]

    return ApiResponse(
        data=GraphOptions(
            systems=sorted([str(s) for s in systems_rows if s]),
            sources=sorted([str(s) for s in sources_rows if s]),
            schemas=sorted([str(s) for s in schemas_rows if s]),
            domains=sorted([str(d) for d in domains_rows if d]),
            system_options=option_items(systems_rows, system_names),
            source_options=option_items(sources_rows, source_names),
            schema_options=option_items(schemas_rows),
            domain_options=option_items(domains_rows),
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
    # C1：一次性预载 asset_tables 端点索引，替代逐条关系的反查 SQL；
    # 已回填物理字段的关系本来就零查询，缺失字段的关系现在也走内存索引。
    endpoint_resolver = _EndpointResolver.load(db)
    unresolved_samples: list[str] = []
    for r in rows:
        from_key = _endpoint_physical_key(db, r, "from", resolver=endpoint_resolver)
        to_key = _endpoint_physical_key(db, r, "to", resolver=endpoint_resolver)
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

    # 孤儿引用：关系端点表在 asset_tables 中不存在（视图特殊节点除外）；
    # 复用 endpoint_resolver 预载的 (schema, table) 集合，不再单独拉全表实体。
    table_names = endpoint_resolver.schema_table_names
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
