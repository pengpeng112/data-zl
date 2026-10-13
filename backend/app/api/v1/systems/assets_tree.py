"""215 E11 自 systems.py 拆出：资产树与来源分类（/api/v1/assets/tree*）。"""
from __future__ import annotations


from fastapi import Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....core.db import get_db
from ....models.asset import AssetTable
from ....models.asset_system import AssetDataSource, AssetSourceSchema
from ....schemas.common import ApiResponse
from ....services.connection_identity import (
    host_masked_from_target,
)
from ....services.asset_catalog import (
    CANONICAL_SYSTEMS,
    classify_for_tree,
    load_system_name_map,
    owner_display_cn,
)
from ._router import router


# Tables with confirmed zero rows must not appear in normal catalog APIs.
_EXCLUDED_PRESENCE = ("confirmed_empty",)

def _classify_asset_source(
    system_code: str | None,
    source_code: str | None,
    source_kind: str | None = None,
    source_name_cn: str | None = None,
    schema_name: str | None = None,
    system_names: dict[str, str] | None = None,
) -> tuple[str, str, str, str]:
    """Return (system_code, system_name_cn, connection_key, connection_label).

    First-level identity is always a canonical business system (or catalog_anomaly).
    DATA_CENTER mirror owners stay nested under DATA_CENTER, never first-level.
    Independent LIS/PACS/Docare/JHEMR/移动护理 are peers, not external_business.
    """
    info = classify_for_tree(
        system_code,
        source_code,
        source_kind=source_kind,
        source_name_cn=source_name_cn,
        schema_name=schema_name,
        system_names=system_names,
    )
    # source_system field re-used as connection grouping key for API compatibility
    conn_key = (source_code or "").lower() or "unknown_connection"
    conn_label = source_name_cn or source_code or "未命名连接"
    if not info["catalog_ok"]:
        return (
            info["system_code"],
            info["system_name_cn"],
            "catalog_anomaly",
            "目录异常",
        )
    return (
        info["system_code"],
        info["system_name_cn"],
        conn_key,
        conn_label,
    )

def _presence_visible_clause():
    """Exclude confirmed_empty from normal catalog; keep unknown/blocked."""
    return (
        (AssetTable.row_presence_status.is_(None))
        | (AssetTable.row_presence_status != "confirmed_empty")
    )

def _table_brief(t: AssetTable) -> dict:
    ns = t.namespace_name or t.schema_name or ""
    return {
        "id": t.id,
        "table_name": t.table_name,
        "table_name_cn": t.table_name_cn,
        "name_cn_source": t.name_cn_source,
        "name_cn_status": t.name_cn_status,
        "column_count": t.column_count,
        "domain": t.domain,
        "owner_hint": (ns or "").upper(),
        "schema_name": ns,
        "source_code": t.source_code,
        "system_code": t.system_code,
        "row_presence_status": getattr(t, "row_presence_status", None),
    }

@router.get(
    "/assets/tree",
    summary="业务系统 → 连接 → schema 树（默认不含表清单，表按需加载）",
)
def assets_tree(
    system_code: str | None = Query(None),
    system_category: str | None = Query(
        None,
        description="兼容旧参数：现按 system_code 过滤；勿再传 external_business 等大类",
    ),
    include_tables: bool = Query(
        False,
        description="true 时内嵌全量表（仅调试/小库）；默认 false 仅返回 schema 计数，表走 /assets/tree/tables",
    ),
    max_tables_per_schema: int = Query(
        0,
        ge=0,
        le=500,
        description="include_tables=true 时每 schema 最多内嵌表数；0 表示不截断",
    ),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    # Load all sources so legacy aliases can always resolve their canonical
    # physical connection; filtering is applied after canonical classification.
    sources = {s.source_code: s for s in db.scalars(select(AssetDataSource)).all()}
    system_names = load_system_name_map(db)
    schema_inventory = {
        (row.source_code, (row.schema_name or "").upper()): row
        for row in db.scalars(select(AssetSourceSchema)).all()
    }

    # 骨架：仅聚合 (source_code, schema) 计数；排除 confirmed_empty
    ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    count_rows = db.execute(
        select(
            AssetTable.source_code,
            AssetTable.system_code,
            ns_key.label("ns"),
            func.count().label("cnt"),
        )
        .where(_presence_visible_clause())
        .group_by(AssetTable.source_code, AssetTable.system_code, ns_key)
    ).all()

    grouped: dict[str, dict[str, int]] = {}
    source_system_hint: dict[str, str] = {}
    for sc, tsys, ns, cnt in count_rows:
        sc_key = sc or "unknown"
        ns_val = ns or ""
        grouped.setdefault(sc_key, {})[ns_val] = grouped.get(sc_key, {}).get(ns_val, 0) + int(cnt)
        if tsys and sc_key not in source_system_hint:
            source_system_hint[sc_key] = tsys

    tables_by_schema: dict[tuple[str, str], list[dict]] = {}
    if include_tables:
        tables = db.scalars(select(AssetTable).where(_presence_visible_clause())).all()
        for t in tables:
            sc = t.source_code or "unknown"
            ns = t.namespace_name or t.schema_name or ""
            key = (sc, ns)
            bucket = tables_by_schema.setdefault(key, [])
            if max_tables_per_schema and len(bucket) >= max_tables_per_schema:
                continue
            bucket.append(_table_brief(t))

    tree = []
    for sc, schema_counts in sorted(grouped.items()):
        ds = sources.get(sc)
        canonical_ds = (
            sources.get(ds.canonical_source_code)
            if ds and ds.source_kind == "legacy_alias" and ds.canonical_source_code
            else None
        )
        display_ds = canonical_ds or ds
        raw_sys = (
            (display_ds.system_code if display_ds else None)
            or source_system_hint.get(sc)
            or "UNKNOWN"
        )
        # sample schema for DATA_CENTER mirror detection
        sample_ns = next(iter(schema_counts.keys()), None)
        physical_source_code = display_ds.source_code if display_ds else sc
        sys_code, sys_name, conn_key, conn_label = _classify_asset_source(
            raw_sys,
            sc,
            display_ds.source_kind if display_ds else (ds.source_kind if ds else None),
            display_ds.source_name_cn if display_ds else (ds.source_name_cn if ds else None),
            schema_name=sample_ns,
            system_names=system_names,
        )
        # connection endpoint display
        endpoint = None
        if display_ds:
            host = display_ds.host_masked or host_masked_from_target(display_ds.target_host) or display_ds.target_host
            port = display_ds.port
            db_or_svc = display_ds.service_name or display_ds.database_name
            if host:
                endpoint = f"{host}:{port or '-'}" + (f" / {db_or_svc}" if db_or_svc else "")
        conn_display = endpoint or conn_label

        # filter: system_category param now accepts system_code (compat)
        filter_code = system_category or system_code
        if filter_code and sys_code != filter_code.upper():
            continue

        node = {
            "source_code": sc,
            "physical_source_code": physical_source_code,
            "source_name_cn": (display_ds.source_name_cn if display_ds else sc),
            "connection_endpoint": endpoint,
            "system_code": sys_code,
            "system_name_cn": system_names.get(sys_code) or sys_name,
            # plan 90: category fields intentionally null for peers (no 大类)
            "system_category": None if sys_code in CANONICAL_SYSTEMS else "catalog_anomaly",
            "system_category_cn": None if sys_code in CANONICAL_SYSTEMS else "目录异常",
            "source_system": conn_key,
            "source_system_cn": conn_display,
            "schemas": [],
            "table_count": sum(schema_counts.values()),
            "tables_embedded": include_tables,
            "empty_catalog_hint": None,
        }
        for ns, cnt in sorted(schema_counts.items()):
            tbls = tables_by_schema.get((sc, ns), []) if include_tables else []
            inventory = schema_inventory.get((sc, (ns or "").upper()))
            owner_cn = (
                (inventory.schema_name_cn if inventory else None)
                or owner_display_cn(ns, parent_system=sys_code)
            )
            node["schemas"].append({
                "namespace": ns,
                "source_code": sc,
                "namespace_name_cn": owner_cn,
                "name_cn_source": inventory.name_cn_source if inventory else None,
                "name_cn_status": inventory.name_cn_status if inventory else None,
                "tables": tbls,
                "table_count": cnt,
                "tables_loaded": include_tables,
            })
        if node["table_count"] == 0:
            node["empty_catalog_hint"] = "当前未发现非空对象"
        tree.append(node)

    # 同一物理连接折叠；Schema 仍保留原 source_code
    consolidated: dict[tuple[str, str], dict] = {}
    for node in tree:
        key = (node["system_code"], node.get("physical_source_code") or node["source_code"])
        current = consolidated.get(key)
        if not current:
            current = {**node, "source_code": key[1], "schemas": [], "table_count": 0}
            consolidated[key] = current
        current["schemas"].extend(node["schemas"])
        current["table_count"] += node["table_count"]
        if current["table_count"] == 0:
            current["empty_catalog_hint"] = "当前未发现非空对象"
        else:
            current["empty_catalog_hint"] = None
    # stable order: canonical systems first
    order = {c: i for i, c in enumerate(CANONICAL_SYSTEMS)}
    result = sorted(
        consolidated.values(),
        key=lambda n: (order.get(n["system_code"], 999), n["system_code"], n["source_code"]),
    )
    return ApiResponse(data=result)

@router.get("/assets/tree/tables", summary="懒加载：某 source+schema 下的表清单（分页）")
def assets_tree_tables(
    source_code: str = Query(..., min_length=1),
    schema_name: str = Query("", description="Owner/schema；空串表示无 namespace"),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    ns = schema_name or ""
    ns_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    stmt = select(AssetTable).where(
        AssetTable.source_code == source_code,
        ns_key == ns,
        _presence_visible_clause(),
    )
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (AssetTable.table_name.ilike(like))
            | (AssetTable.table_name_cn.ilike(like))
            | (AssetTable.domain.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AssetTable.table_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApiResponse(
        data={
            "source_code": source_code,
            "schema_name": ns,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_table_brief(t) for t in rows],
        }
    )

@router.get("/assets/tree/search", summary="按表名/中文名搜索（返回完整路径，限量）")
def assets_tree_search(
    keyword: str = Query(..., min_length=1),
    system_category: str | None = Query(None, description="兼容：按 system_code 过滤"),
    system_code: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    like = f"%{keyword.strip()}%"
    stmt = (
        select(AssetTable)
        .where(
            _presence_visible_clause(),
            (AssetTable.table_name.ilike(like))
            | (AssetTable.table_name_cn.ilike(like)),
        )
        .order_by(AssetTable.schema_name, AssetTable.table_name)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    sources = {
        s.source_code: s
        for s in db.scalars(select(AssetDataSource)).all()
    }
    system_names = load_system_name_map(db)
    filter_code = (system_code or system_category or "").upper() or None
    items = []
    for t in rows:
        sc = t.source_code or "unknown"
        ds = sources.get(sc)
        raw_sys = ds.system_code if ds else (t.system_code or "UNKNOWN")
        ns = t.namespace_name or t.schema_name or ""
        sys_code, sys_name, conn_key, conn_label = _classify_asset_source(
            raw_sys,
            sc,
            ds.source_kind if ds else None,
            ds.source_name_cn if ds else None,
            schema_name=ns,
            system_names=system_names,
        )
        if filter_code and sys_code != filter_code:
            continue
        owner_cn = owner_display_cn(ns, parent_system=sys_code)
        path_parts = [
            system_names.get(sys_code) or sys_name,
            conn_label,
            f"{owner_cn}（{ns}）" if owner_cn and ns else (ns or "-"),
            t.table_name_cn and f"{t.table_name}（{t.table_name_cn}）" or t.table_name,
        ]
        items.append({
            **_table_brief(t),
            "system_code": sys_code,
            "system_name_cn": system_names.get(sys_code) or sys_name,
            "system_category": None if sys_code in CANONICAL_SYSTEMS else "catalog_anomaly",
            "system_category_cn": None if sys_code in CANONICAL_SYSTEMS else "目录异常",
            "source_system": conn_key,
            "source_system_cn": conn_label,
            "source_name_cn": ds.source_name_cn if ds else sc,
            "path": " → ".join(str(p) for p in path_parts if p),
            "namespace_name_cn": owner_cn,
        })
    return ApiResponse(data={"keyword": keyword, "total": len(items), "items": items})


# ── 186 v1.10 P0-18：source registry 受控用途绑定 ──
