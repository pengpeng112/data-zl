"""144 S5 / 138 first-phase: deterministic static lineage ingestion.

Builds lineage edges ONLY from deterministic evidence:
- view → table reads_from (asset_view_dependencies, parsed DDL evidence)
- query version → table reads_from (asset_query_dependencies, resolved object_key)
- query → metric calculates (metric version query refs, exact versions)
- query/metric → product publishes (product pin/active refs)

Business JOIN relations (asset_relations) are NEVER a lineage source (A19).
Every edge is idempotent by edge_key; sync returns created/updated/unchanged
and an unresolved list instead of guessing (no ILIKE fallbacks anywhere).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.lineage import AssetLineageEdge, AssetViewDependency
from ..models.metric_asset import AssetMetricVersion
from ..models.query_asset import AssetQueryDependency, AssetQueryVersion
from ..models.data_product import AssetDataProduct

INGEST_VERSION = "lineage-ingest/v1"


def _now():
    return datetime.now(timezone.utc)


def _edge_key(from_key: str, to_key: str, edge_type: str, process_key: str | None, logic_version: str) -> str:
    blob = "|".join([from_key, to_key, edge_type, process_key or "", logic_version])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def table_object_key(system_code, source_code, schema_name, table_name) -> str:
    from .object_identity import build_object_key

    return build_object_key(
        system_code=system_code or "",
        source_code=source_code or "",
        schema_name=schema_name,
        object_name=table_name,
        object_type="table",
    )


def query_object_key(query_code: str, version: int) -> str:
    return f"query|{query_code}|{version}"


def metric_object_key(metric_code: str, version: int) -> str:
    return f"metric|{metric_code}|{version}"


def product_object_key(product_code: str) -> str:
    return f"product|{product_code}"


def collect_lineage_edges(db: Session, *, metadata_index=None) -> tuple[list[dict], list[dict]]:
    """Return (edges, unresolved). Pure read of platform evidence."""
    from .query_validation_service import build_metadata_index

    edges: list[dict] = []
    unresolved: list[dict] = []
    index = metadata_index if metadata_index is not None else build_metadata_index(db)

    # 1) view → table reads_from
    for dep in db.scalars(select(AssetViewDependency)).all():
        schema = (dep.referenced_schema or "").upper() or None
        table = (dep.referenced_table or "").upper()
        key = (schema, table) if schema else None
        meta = index.get(key) if key else None
        if meta is None:
            # bare-name unique resolution only; ambiguous/unknown → unresolved
            hits = [k for k in index if k[1] == table]
            if len(hits) == 1:
                meta = index[hits[0]]
                key = hits[0]
        if meta is None:
            unresolved.append(
                {"kind": "view_dependency", "object": f"{dep.view_name} → {dep.referenced_schema}.{dep.referenced_table}",
                 "reason": "表不在元数据目录或同名歧义"}
            )
            continue
        edges.append(
            {
                "from_object_key": table_object_key(meta.get("system_code"), meta.get("source_code"), key[0], key[1]),
                "to_object_key": f"view|{dep.view_name}",
                "from_object_type": "table",
                "to_object_type": "view",
                "edge_type": "reads_from",
                "evidence_type": "view_ddl_dependency",
                "evidence_ref": f"asset_view_dependencies:{dep.id}",
                "granularity": "table",
                "process_key": None,
            }
        )

    # 2) query version → table reads_from (resolved dependency object_keys only)
    qv_by_id = {qv.id: qv for qv in db.scalars(select(AssetQueryVersion)).all()}
    for dep in db.scalars(select(AssetQueryDependency)).all():
        if dep.dep_type != "table":
            continue
        qv = qv_by_id.get(dep.query_version_id)
        if qv is None or not dep.object_key:
            unresolved.append(
                {"kind": "query_dependency", "object": f"dep:{dep.id}",
                 "reason": "依赖未解析（无 object_key）或版本缺失"}
            )
            continue
        edges.append(
            {
                "from_object_key": dep.object_key,
                "to_object_key": query_object_key(qv.query_code, qv.version),
                "from_object_type": "table",
                "to_object_type": "query",
                "edge_type": "reads_from",
                "evidence_type": "query_dependency_resolved",
                "evidence_ref": f"asset_query_dependencies:{dep.id}",
                "granularity": "table",
                "process_key": None,
            }
        )

    # 3) query → metric calculates (exact version refs)
    for mv in db.scalars(select(AssetMetricVersion)).all():
        refs = [
            (mv.query_code, mv.query_version),
            (mv.numerator_query_code, mv.numerator_query_version),
            (mv.denominator_query_code, mv.denominator_query_version),
        ]
        target = metric_object_key(mv.metric_code, mv.version)
        for code, ver in refs:
            if not code or ver is None:
                continue
            edges.append(
                {
                    "from_object_key": query_object_key(code, ver),
                    "to_object_key": target,
                    "from_object_type": "query",
                    "to_object_type": "metric",
                    "edge_type": "calculates",
                    "evidence_type": "metric_version_ref",
                    "evidence_ref": f"asset_metric_versions:{mv.id}",
                    "granularity": "table",
                    "process_key": None,
                }
            )

    # 4) query/metric → product publishes
    for p in db.scalars(select(AssetDataProduct)).all():
        if not p.enabled:
            continue
        target = product_object_key(p.product_code)
        if p.product_type == "query" and p.query_code:
            ver = p.pin_version
            if ver is None:
                qv = db.scalar(
                    select(AssetQueryVersion).where(
                        AssetQueryVersion.query_code == p.query_code,
                        AssetQueryVersion.is_active.is_(True),
                    )
                )
                ver = qv.version if qv else None
            if ver is None:
                unresolved.append(
                    {"kind": "product_ref", "object": p.product_code, "reason": "查询产品无可发布版本"}
                )
                continue
            edges.append(
                {
                    "from_object_key": query_object_key(p.query_code, ver),
                    "to_object_key": target,
                    "from_object_type": "query",
                    "to_object_type": "product",
                    "edge_type": "publishes",
                    "evidence_type": "product_pin" if p.pin_version else "product_active_ref",
                    "evidence_ref": f"asset_data_products:{p.id}",
                    "granularity": "table",
                    "process_key": None,
                }
            )
        elif p.product_type == "metric" and p.metric_code:
            mv = db.scalar(
                select(AssetMetricVersion).where(
                    AssetMetricVersion.metric_code == p.metric_code,
                    AssetMetricVersion.is_active.is_(True),
                )
            )
            if mv is None:
                unresolved.append(
                    {"kind": "product_ref", "object": p.product_code, "reason": "指标产品无 active 版本"}
                )
                continue
            edges.append(
                {
                    "from_object_key": metric_object_key(p.metric_code, mv.version),
                    "to_object_key": target,
                    "from_object_type": "metric",
                    "to_object_type": "product",
                    "edge_type": "publishes",
                    "evidence_type": "product_active_ref",
                    "evidence_ref": f"asset_data_products:{p.id}",
                    "granularity": "table",
                    "process_key": None,
                }
            )
    return edges, unresolved


def sync_lineage_edges(db: Session, *, dry_run: bool = False, batch_id: str | None = None) -> dict[str, Any]:
    """Idempotent upsert by edge_key; returns counts and unresolved list."""
    edges, unresolved = collect_lineage_edges(db)
    batch = batch_id or f"lineage-{_now().strftime('%Y%m%dT%H%M%SZ')}"
    created = updated = unchanged = 0
    existing_keys = {
        e.edge_key: e for e in db.scalars(select(AssetLineageEdge)).all()
    }
    seen: set[str] = set()
    for edge in edges:
        key = _edge_key(
            edge["from_object_key"], edge["to_object_key"], edge["edge_type"],
            edge.get("process_key"), "1",
        )
        if key in seen:
            continue
        seen.add(key)
        row = existing_keys.get(key)
        if row is None:
            created += 1
            if not dry_run:
                db.add(
                    AssetLineageEdge(
                        edge_key=key,
                        from_object_key=edge["from_object_key"],
                        to_object_key=edge["to_object_key"],
                        from_object_type=edge["from_object_type"],
                        to_object_type=edge["to_object_type"],
                        edge_type=edge["edge_type"],
                        granularity=edge.get("granularity") or "table",
                        process_key=edge.get("process_key"),
                        evidence_type=edge.get("evidence_type"),
                        evidence_ref=edge.get("evidence_ref"),
                        parser_version=INGEST_VERSION,
                        logic_version="1",
                        observed_at=_now(),
                        batch_id=batch,
                        status="active",
                    )
                )
        else:
            if row.status in {"active", "stale"}:
                updated_or_same = row.observed_at is None
                if not dry_run:
                    row.observed_at = _now()
                    row.batch_id = batch
                    row.status = "active"
                if updated_or_same:
                    updated += 1
                else:
                    unchanged += 1
    if not dry_run:
        db.flush()
    return {
        "dry_run": dry_run,
        "batch_id": batch,
        "collected": len(edges),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "unresolved": unresolved[:200],
        "unresolved_count": len(unresolved),
        "ingest_version": INGEST_VERSION,
    }


def lineage_impact(db: Session, *, object_key: str, direction: str = "downstream", max_hops: int = 3) -> dict:
    """Precise impact traversal over lineage edges (typed nodes/edges only)."""
    if direction not in {"downstream", "upstream", "both"}:
        raise ValueError("direction 必须是 downstream|upstream|both")
    rows = db.scalars(select(AssetLineageEdge).where(AssetLineageEdge.status == "active")).all()
    forward = {r.from_object_key: [] for r in rows}
    backward = {r.to_object_key: [] for r in rows}
    for r in rows:
        forward.setdefault(r.from_object_key, []).append(r)
        backward.setdefault(r.to_object_key, []).append(r)

    def walk(start: str, graph: dict, next_attr: str) -> tuple[set[str], list[dict]]:
        visited: set[str] = set()
        edges_out: list[dict] = []
        frontier = [(start, 0)]
        while frontier:
            node, depth = frontier.pop()
            if node in visited or depth > max_hops:
                continue
            visited.add(node)
            for edge in graph.get(node, []):
                edges_out.append(
                    {
                        "from": edge.from_object_key,
                        "to": edge.to_object_key,
                        "edge_type": edge.edge_type,
                        "from_type": edge.from_object_type,
                        "to_type": edge.to_object_type,
                        "hops": depth + 1,
                    }
                )
                frontier.append((getattr(edge, next_attr), depth + 1))
        visited.discard(start)
        return visited, edges_out

    down_nodes, down_edges = (
        walk(object_key, forward, "to_object_key")
        if direction in {"downstream", "both"}
        else (set(), [])
    )
    up_nodes, up_edges = (
        walk(object_key, backward, "from_object_key")
        if direction in {"upstream", "both"}
        else (set(), [])
    )
    return {
        "object_key": object_key,
        "direction": direction,
        "downstream_nodes": sorted(down_nodes),
        "upstream_nodes": sorted(up_nodes),
        "downstream_edges": down_edges,
        "upstream_edges": up_edges,
        "total_edges": len(down_edges) + len(up_edges),
    }
