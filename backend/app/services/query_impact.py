"""126 P3: impact analysis — table/column changes → query/metric versions."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.metric_asset import AssetMetricVersion
from ..models.query_asset import AssetQueryDependency, AssetQueryVersion
from ..services.query_gate import extract_table_refs


def find_queries_by_table(
    db: Session,
    *,
    table_name: str,
    schema_name: str | None = None,
    active_only: bool = False,
) -> list[dict]:
    table_u = (table_name or "").upper().strip()
    schema_u = (schema_name or "").upper().strip() if schema_name else None
    if not table_u:
        return []

    # Prefer dependency rows; also scan sql_text for safety
    dep_q = select(AssetQueryDependency).where(
        AssetQueryDependency.dep_type == "table",
        AssetQueryDependency.object_name.ilike(table_u),
    )
    if schema_u:
        dep_q = dep_q.where(
            or_(
                AssetQueryDependency.schema_name.ilike(schema_u),
                AssetQueryDependency.schema_name.is_(None),
            )
        )
    deps = db.scalars(dep_q).all()
    version_ids = {d.query_version_id for d in deps}

    # Fallback / augment: LIKE on sql
    like_pat = f"%{table_u}%"
    sql_versions = db.scalars(
        select(AssetQueryVersion).where(AssetQueryVersion.sql_text.ilike(like_pat))
    ).all()
    for v in sql_versions:
        version_ids.add(v.id)

    if not version_ids:
        return []

    stmt = select(AssetQueryVersion).where(AssetQueryVersion.id.in_(version_ids))
    if active_only:
        stmt = stmt.where(AssetQueryVersion.is_active.is_(True))
    versions = db.scalars(stmt.order_by(AssetQueryVersion.query_code, AssetQueryVersion.version.desc())).all()

    out = []
    for v in versions:
        refs = extract_table_refs(v.sql_text or "")
        matched = [r for r in refs if r.endswith("." + table_u) or r == table_u or table_u in r]
        if schema_u:
            matched = [r for r in matched if r.startswith(schema_u + ".") or r == table_u]
        out.append(
            {
                "query_code": v.query_code,
                "version": v.version,
                "status": v.status,
                "is_active": v.is_active,
                "sql_sha256": v.sql_sha256,
                "matched_tables": matched or refs,
            }
        )
    return out


def find_metrics_by_query(db: Session, query_code: str) -> list[dict]:
    rows = db.scalars(
        select(AssetMetricVersion).where(
            or_(
                AssetMetricVersion.query_code == query_code,
                AssetMetricVersion.numerator_query_code == query_code,
                AssetMetricVersion.denominator_query_code == query_code,
            )
        )
    ).all()
    return [
        {
            "metric_code": r.metric_code,
            "version": r.version,
            "status": r.status,
            "is_active": r.is_active,
            "query_code": r.query_code,
            "numerator_query_code": r.numerator_query_code,
            "denominator_query_code": r.denominator_query_code,
        }
        for r in rows
    ]


def impact_for_table(
    db: Session,
    *,
    table_name: str,
    schema_name: str | None = None,
    active_only: bool = False,
) -> dict:
    queries = find_queries_by_table(
        db, table_name=table_name, schema_name=schema_name, active_only=active_only
    )
    metrics = []
    seen = set()
    for q in queries:
        for m in find_metrics_by_query(db, q["query_code"]):
            key = (m["metric_code"], m["version"])
            if key in seen:
                continue
            seen.add(key)
            if active_only and not m["is_active"]:
                continue
            metrics.append(m)
    return {
        "table": table_name,
        "schema": schema_name,
        "query_count": len(queries),
        "metric_count": len(metrics),
        "queries": queries,
        "metrics": metrics,
    }
