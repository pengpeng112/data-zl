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
AI_SQL_MAX_TABLES = 20
AI_SQL_MAX_RELATIONS = 40
AI_SQL_MAX_PAYLOAD_BYTES = 24 * 1024
# 平台关系资产的现行审核动作落 ``verified``，早期导入资产还会保留
# ``sample_verified`` / ``manual_reviewed``；144 初版只接受查询版本风格的
# validated/A/A_rechecked，导致生产关系在 AI SQL 上下文中被误排除。
# relation_layer=formal 仍是第一道门，候选/依赖/同步映射不会因状态兼容而进入。
FORMAL_RELATION_STATUSES = {
    "validated", "a", "a_rechecked", "formal", "active",
    "verified", "approved", "manual_reviewed", "sample_verified",
    "user_confirmed", "user_confirmed_mapping", "user_confirmed_parallel_sources",
}


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
            "from_columns": r.from_columns,
            "to_columns": r.to_columns,
            "join_condition": r.join_condition,
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


def _table_pair(value: str | None, schema_name: str | None = None, table_name: str | None = None) -> tuple[str, str] | None:
    if schema_name and table_name:
        return schema_name.upper(), table_name.upper()
    parts = [part.strip().upper() for part in (value or "").split(".") if part.strip()]
    return (parts[-2], parts[-1]) if len(parts) >= 2 else None


def _column_list(value: str | None) -> list[str]:
    return [part.strip().upper() for part in (value or "").replace("+", ",").split(",") if part.strip()]


def build_ai_sql_context(
    db,
    *,
    system_code: str,
    selected_tables: list[str],
    max_tables: int = AI_SQL_MAX_TABLES,
    max_relations: int = AI_SQL_MAX_RELATIONS,
    max_payload_bytes: int = AI_SQL_MAX_PAYLOAD_BYTES,
) -> dict[str, Any]:
    """Build a bounded, non-persisted SQL-authoring context from formal evidence only."""
    from sqlalchemy import select
    from ..models.asset import AssetRelation
    from .query_validation_service import build_metadata_index
    from .value_domain_service import confirmed_domains_for_injection

    wanted = {_table_pair(value) for value in selected_tables}
    wanted.discard(None)
    if not wanted:
        raise ValueError("at least one schema.table must be selected")
    index = build_metadata_index(db)
    eligible: list[tuple[Any, tuple[str, str], tuple[str, str], list[str], list[str]]] = []
    for relation in db.scalars(select(AssetRelation)).all():
        if (relation.validation_status or "").lower() not in FORMAL_RELATION_STATUSES:
            continue
        if (relation.relation_layer or "formal").lower() != "formal":
            continue
        if relation.from_system_code and relation.from_system_code != system_code:
            continue
        if relation.to_system_code and relation.to_system_code != system_code:
            continue
        left = _table_pair(relation.from_table, relation.from_schema_name, relation.from_table_name)
        right = _table_pair(relation.to_table, relation.to_schema_name, relation.to_table_name)
        from_columns, to_columns = _column_list(relation.from_columns), _column_list(relation.to_columns)
        if not left or not right or not relation.join_condition or not from_columns or len(from_columns) != len(to_columns):
            continue
        left_meta, right_meta = index.get(left), index.get(right)
        if not left_meta or not right_meta:
            continue
        if left_meta.get("system_code") != system_code or right_meta.get("system_code") != system_code:
            continue
        if not set(from_columns).issubset(left_meta["columns"]) or not set(to_columns).issubset(right_meta["columns"]):
            continue
        visit_key = {"PATIENT_ID", "VISIT_ID"}
        if (visit_key & set(from_columns)) and not visit_key.issubset(from_columns):
            continue
        if (visit_key & set(to_columns)) and not visit_key.issubset(to_columns):
            continue
        eligible.append((relation, left, right, from_columns, to_columns))

    closure = set(wanted)
    for _, left, right, _, _ in eligible:
        if left in wanted:
            closure.add(right)
        if right in wanted:
            closure.add(left)
    ordered_tables = sorted(wanted) + sorted(closure - wanted)
    ordered_tables = ordered_tables[:max_tables]
    allowed = set(ordered_tables)
    relations = []
    for relation, left, right, from_columns, to_columns in eligible:
        if left not in allowed or right not in allowed:
            continue
        relations.append({
            "id": relation.id,
            "from_table": ".".join(left), "from_columns": from_columns,
            "to_table": ".".join(right), "to_columns": to_columns,
            "join_condition": relation.join_condition,
            "cardinality": relation.cardinality,
            "validation_status": relation.validation_status,
        })
        if len(relations) >= max_relations:
            break
    domains = [row for row in confirmed_domains_for_injection(db, system_code=system_code)
               if ((row.get("schema_name") or "").upper(), (row.get("table_name") or "").upper()) in allowed]
    result = {
        "dialect": "oracle", "system_code": system_code,
        "tables": [{"schema_name": pair[0], "table_name": pair[1], "columns": sorted(index[pair]["columns"])} for pair in ordered_tables if pair in index],
        "relations": relations, "value_domains": domains,
        "limits": {"tables": max_tables, "relations": max_relations, "payload_bytes": max_payload_bytes},
        "truncated": len(closure) > max_tables or len(eligible) > max_relations,
    }
    def payload_size() -> int:
        return len(json.dumps(result, ensure_ascii=False).encode("utf-8"))

    # 先删低优先级值域，再压缩非 JOIN 字段；正式 JOIN 证据最后才裁剪。
    # 旧实现只截一次最后一张表后直接 break，仍可能返回超限 payload，随后被
    # HospitalLlmClient 以 payload_too_large 拒绝。
    while payload_size() > max_payload_bytes:
        result["truncated"] = True
        if result["value_domains"]:
            result["value_domains"].pop()
            continue

        required_by_table: dict[str, set[str]] = {}
        for relation in result["relations"]:
            required_by_table.setdefault(relation["from_table"], set()).update(relation["from_columns"])
            required_by_table.setdefault(relation["to_table"], set()).update(relation["to_columns"])
        reducible = None
        for table in sorted(result["tables"], key=lambda row: len(row["columns"]), reverse=True):
            table_key = f"{table['schema_name']}.{table['table_name']}"
            required = required_by_table.get(table_key, set())
            minimum = max(20, len(required))
            if len(table["columns"]) > minimum:
                reducible = (table, required, minimum)
                break
        if reducible:
            table, required, minimum = reducible
            optional = [column for column in table["columns"] if column not in required]
            table["columns"] = sorted(required) + optional[: max(0, minimum - len(required))]
        elif len(result["relations"]) > 1:
            result["relations"].pop()
        else:
            raise ValueError("AI SQL context cannot fit the configured payload budget")
    result["payload_bytes"] = payload_size()
    return result


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
