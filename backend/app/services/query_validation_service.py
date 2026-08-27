"""144 S3: orchestrate G1–G3 validation against platform evidence.

Builds the metadata index and relation evidence from the platform catalog
(read-only), runs the pure semantic validator, then persists the validation
report onto the query version and typed evidence onto dependency rows.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.asset import AssetColumn, AssetRelation, AssetTable
from ..models.query_asset import AssetQueryDependency, AssetQueryVersion
from .object_identity import build_object_key
from .query_semantic_validator import build_validation_report, resolve_table
from .sql_ast import (
    PARSER_VERSION,
    SQLParseError,
    UnsupportedDialectError,
    extract_table_dependencies,
)

# relations with these validation statuses count as formal JOIN evidence
FORMAL_STATUSES = {"validated", "A", "A_rechecked", "formal", "active"}

# how fresh a metadata snapshot may be before G1 reports stale (144 §4.4)
SNAPSHOT_STALE_DAYS = 180


def build_metadata_index(db: Session, only_tables: set[tuple[str, str]] | None = None):
    """(schema, table) → {columns, system_code, source_code} from the catalog."""
    stmt = select(AssetTable)
    rows = db.scalars(stmt).all()
    index: dict[tuple[str, str], dict] = {}
    wanted = only_tables or None
    for t in rows:
        if not t.schema_name or not t.table_name:
            continue
        key = (t.schema_name.upper(), t.table_name.upper())
        if wanted and key not in wanted:
            continue
        if key in index:
            # duplicate physical rows would make identity ambiguous
            index[key]["_ambiguous"] = True
            continue
        index[key] = {
            "columns": set(),
            "system_code": t.system_code,
            "source_code": t.source_code,
        }
    col_rows = db.scalars(select(AssetColumn)).all()
    for c in col_rows:
        if not c.schema_name or not c.table_name:
            continue
        key = (c.schema_name.upper(), c.table_name.upper())
        entry = index.get(key)
        if entry is not None and c.column_name:
            entry["columns"].add(c.column_name.upper())
    return index


def build_relation_evidence(db: Session) -> list[dict]:
    rows = db.scalars(select(AssetRelation)).all()
    evidence = []
    for r in rows:
        if not r.from_table or not r.to_table:
            continue
        evidence.append(
            {
                "id": r.id,
                "from_table": r.from_table,
                "from_columns": r.from_columns,
                "to_table": r.to_table,
                "to_columns": r.to_columns,
                "cardinality": r.cardinality,
                "validation_status": r.validation_status or r.confidence,
                "validation_level": r.validation_level,
            }
        )
    return evidence


def snapshot_is_stale(db: Session) -> bool:
    """Newest metadata snapshot older than SNAPSHOT_STALE_DAYS → stale."""
    from datetime import datetime, timedelta, timezone

    from ..models.governance import ApiKey  # noqa: F401  (import ordering safety)
    from ..models.asset import AssetTable

    newest = db.scalar(
        select(AssetTable.updated_at).order_by(AssetTable.updated_at.desc()).limit(1)
    )
    if newest is None:
        return True
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return newest < datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_STALE_DAYS)


def run_query_validation(
    db: Session,
    *,
    query_code: str,
    version: int,
) -> dict[str, Any]:
    """Run G1–G3 validation and persist the report; returns the report."""
    qv = db.scalar(
        select(AssetQueryVersion).where(
            AssetQueryVersion.query_code == query_code,
            AssetQueryVersion.version == version,
        )
    )
    if not qv:
        raise LookupError(f"查询版本不存在: {query_code}@{version}")
    dialect = (qv.dialect or "oracle").lower()
    sql_text = qv.sql_text or ""

    try:
        deps = extract_table_dependencies(sql_text, dialect)
        wanted = set()
        for dep in deps["tables"]:
            parts = dep["name"].split(".")
            if len(parts) >= 2:
                wanted.add((parts[-2].upper(), parts[-1].upper()))
            else:
                wanted.add(("", parts[-1].upper()))  # resolved via bare-name scan
        metadata_index = build_metadata_index(db)
        relations = build_relation_evidence(db)
        report = build_validation_report(
            sql_text,
            dialect,
            metadata_tables=metadata_index,
            relations=relations,
            snapshot_stale=snapshot_is_stale(db),
        )
        unresolved_reason = None
    except (SQLParseError, UnsupportedDialectError) as exc:
        report = {
            "schema_version": "query-validation/v1",
            "overall": "unresolved",
            "layers": [
                {
                    "layer": "G0_parse",
                    "status": "unresolved",
                    "findings": [{"code": "E_SEMANTIC", "message": str(exc)[:300]}],
                }
            ],
            "validation_digest": None,
        }
        unresolved_reason = str(exc)[:500]

    # persist onto the version (never flips lifecycle status — only evidence)
    from datetime import datetime, timezone

    qv.validated_at = datetime.now(timezone.utc)
    qv.parser_version = PARSER_VERSION
    qv.unresolved_reason = unresolved_reason
    if report.get("validation_digest"):
        qv.validation_digest = report["validation_digest"]
    contract = next(
        (l.get("contract") for l in report["layers"] if l.get("layer") == "G3_semantic"),
        None,
    )
    if contract:
        qv.semantic_contract = contract

    # rewrite table dependency rows with physical object keys + resolution
    if unresolved_reason is None:
        existing = db.scalars(
            select(AssetQueryDependency).where(
                AssetQueryDependency.query_version_id == qv.id,
                AssetQueryDependency.dep_type == "table",
            )
        ).all()
        by_name = {
            (d.schema_name or "").upper() + "." + (d.object_name or "").upper(): d
            for d in existing
        }
        for dep in deps["tables"]:
            resolved = resolve_table(metadata_index, dep["name"])
            name_key = dep["name"].upper()
            dep_row = by_name.get(name_key)
            if dep_row is None:
                continue
            if resolved is None:
                dep_row.resolution_status = "unresolved"
                dep_row.object_key = None
                continue
            meta = metadata_index[resolved]
            try:
                dep_row.object_key = build_object_key(
                    system_code=meta.get("system_code") or "",
                    source_code=meta.get("source_code") or "",
                    schema_name=resolved[0],
                    object_name=resolved[1],
                    object_type="table",
                )
            except ValueError:
                dep_row.object_key = None
                dep_row.resolution_status = "unresolved"
                continue
            dep_row.resolution_status = "resolved"
            dep_row.evidence_type = "metadata_snapshot"

    db.flush()
    return report


def certification_gate(certification_status: str | None) -> bool:
    """AI-facing recommendation gate: only certified assets are 'verified'."""
    return (certification_status or "") == "certified"
