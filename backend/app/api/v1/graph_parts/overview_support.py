"""215 E11 自 graph.py 拆出：overview（服务端资产概览）支撑函数。"""
from __future__ import annotations

from time import perf_counter

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....models.asset import AssetColumn, AssetRelation, AssetTable
from ....schemas.common import ApiResponse
from ....schemas.graph import GraphData, GraphEdge, GraphOverviewData, GraphNode
from ....services.asset_catalog import system_code_filter_values
from .resolution import _display_id
from .builders import (
    _enrichment_stats,
    _graph_meta,
    _graph_node_for,
    _object_type,
    _split_relation_columns,
    _table_map_by_physical_key,
)

def _parse_parent_path(value: str | None) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    if not value:
        return None, None, None, None, None
    parts = value.split("|")
    if len(parts) != 5:
        raise HTTPException(status_code=422, detail="parent_physical_key 格式应为 system|source|namespace|schema|table")
    return tuple(parts)  # type: ignore[return-value]

def _object_type_name(table: AssetTable) -> str:
    return _object_type(table)

def _apply_asset_filters(stmt, *, system_code: str | None, source_code: str | None, schema_name: str | None, domain: str | None, object_type: str | None):
    if system_code:
        codes = system_code_filter_values(system_code)
        stmt = stmt.where(AssetTable.system_code.in_(codes or [system_code]))
    if source_code:
        stmt = stmt.where(AssetTable.source_code == source_code)
    if schema_name:
        ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
        stmt = stmt.where(ns_key == schema_name)
    if domain:
        stmt = stmt.where(AssetTable.domain == domain)
    if object_type == "view":
        stmt = stmt.where(or_(AssetTable.table_role.ilike("%view%"), AssetTable.table_role.ilike("%视图%"), AssetTable.table_name.ilike("V\\_%", escape="\\")))
    elif object_type == "table":
        stmt = stmt.where(~or_(AssetTable.table_role.ilike("%view%"), AssetTable.table_role.ilike("%视图%"), AssetTable.table_name.ilike("V\\_%", escape="\\")))
    return stmt

def _overview_id(level: str, values: tuple[str | None, ...]) -> str:
    return "overview|" + level + "|" + "|".join(value or "" for value in values)

def _overview_node(
    level: str,
    values: tuple[str | None, ...],
    label: str,
    count: int,
    *,
    path: str | None = None,
) -> GraphNode:
    system_code = values[0] if values else None
    source_code = values[1] if len(values) > 1 else None
    schema_name = values[2] if len(values) > 2 else None
    return GraphNode(
        id=_overview_id(level, values),
        physical_key=_overview_id(level, values),
        display_id=label,
        label=label,
        system_code=system_code,
        source_code=source_code,
        schema_name=schema_name,
        table_name=values[3] if len(values) > 3 else None,
        technical_name=label,
        object_type="aggregate",
        category=level,
        asset_count=count,
        child_count=count,
        path=path,
        is_aggregate=True,
    )

def _field_node_id(table_physical_key: str, column_name: str) -> str:
    return f"field|{table_physical_key}|{column_name}"

def _field_overview(
    db: Session,
    *,
    table_physical_key: str,
    system_code: str,
    source_code: str,
    namespace_name: str | None,
    schema_name: str,
    table_name: str,
    limit: int,
    started: float,
) -> ApiResponse[GraphOverviewData]:
    """按完整物理键返回一张表及其字段节点，不跨来源拼接同名字段。"""
    endpoint = (system_code, source_code, namespace_name, schema_name, table_name)
    table = _table_map_by_physical_key(db, {endpoint}).get(table_physical_key)
    if table is None:
        raise HTTPException(status_code=404, detail="字段概览的中心表不存在或物理键不唯一")

    column_base = select(AssetColumn).where(
        AssetColumn.system_code == system_code,
        AssetColumn.source_code == source_code,
        AssetColumn.schema_name == schema_name,
        AssetColumn.table_name == table_name,
    )
    if namespace_name:
        exact_stmt = column_base.where(AssetColumn.namespace_name == namespace_name)
        exact_count = db.scalar(select(func.count()).select_from(exact_stmt.order_by(None).subquery())) or 0
        if exact_count:
            column_base = exact_stmt
        else:
            column_base = column_base.where(or_(
                AssetColumn.namespace_name.is_(None),
                AssetColumn.namespace_name == "",
                AssetColumn.namespace_name == schema_name,
            ))
    else:
        column_base = column_base.where(or_(
            AssetColumn.namespace_name.is_(None),
            AssetColumn.namespace_name == "",
            AssetColumn.namespace_name == schema_name,
        ))

    matched_columns = db.scalar(
        select(func.count()).select_from(column_base.order_by(None).subquery())
    ) or 0
    columns = db.scalars(
        column_base.order_by(AssetColumn.column_id, AssetColumn.column_name).limit(limit)
    ).all()

    relation_columns: set[str] = set()
    from_match = (
        (AssetRelation.from_system_code == system_code)
        & (AssetRelation.from_source_code == source_code)
        & (AssetRelation.from_schema_name == schema_name)
        & (AssetRelation.from_table_name == table_name)
    )
    to_match = (
        (AssetRelation.to_system_code == system_code)
        & (AssetRelation.to_source_code == source_code)
        & (AssetRelation.to_schema_name == schema_name)
        & (AssetRelation.to_table_name == table_name)
    )
    for relation in db.scalars(select(AssetRelation).where(or_(from_match, to_match))).all():
        if (
            relation.from_system_code == system_code
            and relation.from_source_code == source_code
            and relation.from_schema_name == schema_name
            and relation.from_table_name == table_name
        ):
            relation_columns.update(item.upper() for item in _split_relation_columns(relation.from_columns))
        if (
            relation.to_system_code == system_code
            and relation.to_source_code == source_code
            and relation.to_schema_name == schema_name
            and relation.to_table_name == table_name
        ):
            relation_columns.update(item.upper() for item in _split_relation_columns(relation.to_columns))

    primary_columns = {item.upper() for item in _split_relation_columns(table.pk)}
    center = _graph_node_for(
        table_physical_key,
        _display_id(schema_name, table_name),
        system_code,
        source_code,
        namespace_name,
        schema_name,
        table_name,
        table,
    )
    center.category = "table"
    center.path = table_physical_key
    center.asset_count = matched_columns
    center.child_count = matched_columns

    nodes: list[GraphNode] = [center]
    edges: list[GraphEdge] = []
    for column in columns:
        column_name = column.column_name or f"COLUMN_{column.column_id or len(nodes)}"
        field_id = _field_node_id(table_physical_key, column_name)
        upper_name = column_name.upper()
        is_primary = upper_name in primary_columns
        is_relation = upper_name in relation_columns
        nodes.append(GraphNode(
            id=field_id,
            physical_key=field_id,
            display_id=column_name,
            label=column.column_name_cn or column_name,
            system_code=system_code,
            source_code=source_code,
            namespace_name=column.namespace_name or namespace_name,
            schema_name=schema_name,
            table_name=table_name,
            category="field",
            object_type="column",
            technical_name=f"{schema_name}.{table_name}.{column_name}",
            metadata_match="exact" if (column.namespace_name or "") == (namespace_name or "") else "namespace_compatible",
            path=table_physical_key,
            column_name=column_name,
            column_name_cn=column.column_name_cn,
            data_type=column.data_type,
            nullable=column.nullable,
            is_primary_key=is_primary,
            is_relation_key=is_relation,
        ))
        edge_label = "主键字段" if is_primary else "关联字段" if is_relation else "包含字段"
        edges.append(GraphEdge(
            id=f"overview-field:{table_physical_key}->{field_id}",
            source=table_physical_key,
            target=field_id,
            label=edge_label,
            relation_type="hierarchy",
            relation_layer="hierarchy",
        ))

    truncated = matched_columns > len(columns)
    warnings = []
    if truncated:
        warnings.append(f"字段共 {matched_columns} 个，当前展示前 {len(columns)} 个；请在表详情查看完整字段清单")
    meta = _graph_meta(
        total_relations=len(edges),
        matched_relations=matched_columns,
        returned_relations=len(edges),
        truncated=truncated,
        unresolved_count=0,
        filters={"level": "field", "parent_physical_key": table_physical_key, "limit": limit},
        query_ms=round((perf_counter() - started) * 1000, 2),
        enrichment=_enrichment_stats(nodes),
        warnings=warnings,
        center_physical_key=table_physical_key,
        direction_semantics="contains",
    )
    meta.returned_nodes = len(nodes)
    meta.estimated_total = matched_columns
    return ApiResponse(data=GraphOverviewData(
        level="field",
        next_level=None,
        selected_path={
            "system": system_code,
            "source": source_code,
            "schema": schema_name,
            "object": table_name,
        },
        data=GraphData(nodes=nodes, edges=edges, meta=meta),
    ))
