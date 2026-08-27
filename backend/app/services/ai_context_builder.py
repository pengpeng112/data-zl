"""144 S6: unified AI context building + snapshot persistence.

filter_ai_readable is the unconditional first gate for EVERY AI-facing object
list (144 §4.6): ai_readable=False drops; missing flag fails closed (treated
as not readable) until governance backfills the value.

build_context_snapshot assembles the versioned ai-data-context/v1 document
from certified/current platform assets only — never raw SQL unless explicitly
authorized, never patient-level data.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

CONTEXT_SCHEMA_VERSION = "ai-data-context/v1"
DEFAULT_TTL_HOURS = 24
DEFAULT_MAX_OBJECTS = 200


def is_ai_readable(obj: dict[str, Any]) -> bool:
    flag = obj.get("ai_readable")
    if flag is None:
        return False  # fail closed (144 §8.4)
    return bool(flag)


def filter_ai_readable(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [o for o in (objects or []) if is_ai_readable(o)]


def strip_full_sql(entry: dict[str, Any]) -> dict[str, Any]:
    """Default AI view: SQL hash + contract, not full SQL text (144 §4.6)."""
    out = dict(entry)
    sql_text = out.pop("sql_text", None)
    if sql_text is not None:
        out["sql_sha256"] = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
        out["sql_available"] = "full_read_permission_required"
    return out


def build_context_snapshot(
    db,
    *,
    question_summary: str | None = None,
    system_code: str | None = None,
    source_code: str | None = None,
    business_domain: str | None = None,
    max_objects: int = DEFAULT_MAX_OBJECTS,
    include_sql: bool = False,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Assemble + persist one ai-data-context/v1 snapshot; returns the doc."""
    from sqlalchemy import select

    from ..models.ai_collab import AiContextSnapshot
    from ..models.asset import AssetRelation
    from ..models.asset_system import AssetSystem
    from ..models.data_product import AssetDataProduct
    from ..models.lineage import AssetLineageEdge
    from ..models.metric_asset import AssetMetricDefinition, AssetMetricVersion
    from ..models.query_asset import AssetQueryDefinition, AssetQueryVersion

    now = datetime.now(timezone.utc)
    warnings: list[str] = []
    truncated = False

    # objects: tables via definition-scoped catalog queries
    from .query_validation_service import build_metadata_index

    index = build_metadata_index(db)
    objects: list[dict[str, Any]] = []
    for (schema, table), meta in sorted(index.items()):
        if system_code and meta.get("system_code") != system_code:
            continue
        if source_code and meta.get("source_code") != source_code:
            continue
        objects.append(
            {
                "object_key": f"{meta.get('system_code') or ''}|{meta.get('source_code') or ''}||{schema}|{table}|table",
                "schema_name": schema,
                "object_name": table,
                "system_code": meta.get("system_code"),
                "source_code": meta.get("source_code"),
                "ai_readable": True,
            }
        )
        if len(objects) >= max_objects:
            truncated = True
            warnings.append(f"对象列表按 max_objects={max_objects} 截断")
            break

    # relations: formal evidence only, ai-facing subset
    relations = [
        {
            "id": r.id,
            "from_table": r.from_table,
            "to_table": r.to_table,
            "validation_status": r.validation_status,
            "cardinality": r.cardinality,
        }
        for r in db.scalars(
            select(AssetRelation).where(AssetRelation.validation_status.in_(["validated", "A", "A_rechecked"])).limit(200)
        ).all()
    ]

    # queries: current versions only, ai_readable definitions, SQL stripped
    q_defs = {
        d.query_code: d
        for d in db.scalars(select(AssetQueryDefinition)).all()
        if d.ai_readable is not False
    }
    queries = []
    for qv in db.scalars(
        select(AssetQueryVersion).where(AssetQueryVersion.is_active.is_(True))
    ).all():
        d = q_defs.get(qv.query_code)
        if d is None:
            continue  # ai_readable=False filtered unconditionally (144 §4.6)
        if system_code and d.system_code != system_code:
            continue
        if business_domain and (d.business_domain or "") != business_domain:
            continue
        entry = {
            "query_code": qv.query_code,
            "version": qv.version,
            "title": d.title,
            "certification_status": qv.certification_status,
            "dialect": qv.dialect,
            "sql_sha256": qv.sql_sha256,
            "parameter_schema": qv.parameter_schema,
            "semantic_contract": qv.semantic_contract,
            "limitations": qv.limitations,
        }
        if include_sql:
            entry["sql_text"] = qv.sql_text
        queries.append(strip_full_sql(entry) if not include_sql else entry)

    # metrics / products (current only)
    metrics = [
        {
            "metric_code": mv.metric_code,
            "version": mv.version,
            "certification_status": getattr(mv, "certification_status", "legacy_unverified"),
            "calculation_type": getattr(mv, "calculation_type", "ratio"),
        }
        for mv in db.scalars(
            select(AssetMetricVersion).where(AssetMetricVersion.is_active.is_(True)).limit(200)
        ).all()
    ]
    products = [
        {"product_code": p.product_code, "product_type": p.product_type, "enabled": bool(p.enabled)}
        for p in db.scalars(
            select(AssetDataProduct).where(AssetDataProduct.enabled.is_(True)).limit(200)
        ).all()
    ]

    sources = [
        {"system_code": s.system_code, "system_name_cn": s.system_name_cn, "status": s.status}
        for s in db.scalars(select(AssetSystem)).all()
    ]

    # 149 P1c 主注入路径：写 SQL 之前，全量携带该系统 confirmed 值域+陷阱
    # （不依赖列级解析；未裁决冲突记录已被服务层过滤，不进入注入）
    from .value_domain_service import confirmed_domains_for_injection

    value_domains = confirmed_domains_for_injection(db, system_code=system_code)

    doc = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "question_summary": (question_summary or "")[:200] or None,
        "expires_at": (now + timedelta(hours=DEFAULT_TTL_HOURS)).isoformat(),
        "system_code": system_code,
        "source_code": source_code,
        "business_domain": business_domain,
        "source_capabilities": sources,
        "objects": objects,
        "business_relations": relations,
        "lineage_edge_count": db.scalar(
            select(AssetLineageEdge.id).where(AssetLineageEdge.status == "active").limit(1)
        )
        is not None,
        "queries": queries,
        "metrics": metrics,
        "products": products,
        "value_domains": value_domains,
        "value_domain_count": len(value_domains),
        "warnings": warnings,
        "unresolved": [],
        "truncated": truncated,
    }
    manifest_blob = json.dumps(
        {
            "objects": len(objects),
            "relations": len(relations),
            "queries": len(queries),
            "metrics": len(metrics),
            "products": len(products),
            "value_domains": len(value_domains),
        },
        sort_keys=True,
    )
    doc["manifest_hash"] = "sha256:" + hashlib.sha256(manifest_blob.encode("utf-8")).hexdigest()
    doc["object_count"] = len(objects)
    doc["relation_count"] = len(relations)
    doc["query_count"] = len(queries)
    doc["metric_count"] = len(metrics)
    doc["product_count"] = len(products)

    context_id = f"ctx-{now.strftime('%Y%m%dT%H%M%S')}-{hashlib.sha256((manifest_blob + (question_summary or '')).encode('utf-8')).hexdigest()[:10]}"
    doc["context_id"] = context_id
    db.add(
        AiContextSnapshot(
            context_id=context_id,
            schema_version=CONTEXT_SCHEMA_VERSION,
            question_summary=doc["question_summary"],
            generated_at=now,
            expires_at=now + timedelta(hours=DEFAULT_TTL_HOURS),
            manifest_hash=doc["manifest_hash"],
            object_count=len(objects),
            relation_count=len(relations),
            query_count=len(queries),
            metric_count=len(metrics),
            product_count=len(products),
            truncated=truncated,
            snapshot_json=doc,
            created_by=created_by,
        )
    )
    db.flush()
    return doc


def load_context_snapshot(db, context_id: str) -> dict[str, Any] | None:
    from sqlalchemy import select

    from ..models.ai_collab import AiContextSnapshot

    row = db.scalar(
        select(AiContextSnapshot).where(AiContextSnapshot.context_id == context_id)
    )
    if row is None:
        return None
    doc = dict(row.snapshot_json or {})
    doc["context_id"] = row.context_id
    doc["expired"] = bool(row.expires_at and row.expires_at < datetime.now(timezone.utc))
    return doc
