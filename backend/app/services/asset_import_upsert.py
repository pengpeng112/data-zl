"""Idempotent upsert of explored metadata into platform asset schema (plan 90).

Never delete-all-then-insert for a source. Never overwrite human-confirmed names.
Never writes to business source databases.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models.asset import AssetColumn, AssetRelation, AssetTable
from ..models.asset_system import AssetSourceSchema
from .row_presence import (
    CONFIRMED_EMPTY,
    classify_from_stats,
    is_catalog_visible,
    merge_presence,
    should_skip_probe,
)

CONFIRMED_NAME_STATUSES = {"confirmed", "human_confirmed", "manual_confirmed", "admin_confirmed"}


def _is_confirmed_name(status: str | None) -> bool:
    return (status or "").lower() in CONFIRMED_NAME_STATUSES


def pick_chinese_name(
    *,
    existing_cn: str | None,
    existing_status: str | None,
    db_comment: str | None,
    doc_name: str | None = None,
    ai_name: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (name_cn, name_cn_source, name_cn_status). Never overwrite confirmed."""
    if _is_confirmed_name(existing_status) and (existing_cn or "").strip():
        return existing_cn, "human_confirmed", existing_status
    if (db_comment or "").strip():
        return db_comment.strip(), "db_comment", "from_db"
    if (doc_name or "").strip():
        return doc_name.strip(), "confirmed_document", "from_document"
    if (ai_name or "").strip():
        return ai_name.strip(), "ai_suggested", "pending_review"
    if (existing_cn or "").strip():
        return existing_cn, None, existing_status
    return None, None, None


def upsert_tables(
    db: Session,
    *,
    system_code: str,
    source_code: str,
    tables: list[dict[str, Any]],
    now: datetime | None = None,
    skip_confirmed_empty: bool = True,
) -> dict[str, int]:
    """Upsert tables by (source_code, schema, table_name). Returns counters."""
    now = now or datetime.now(timezone.utc)
    writes = inserts = updates = skipped_empty = 0
    for row in tables:
        ns = row.get("namespace") or row.get("schema_name") or ""
        tname = row.get("table") or row.get("table_name")
        if not tname:
            continue
        role = (row.get("role") or row.get("table_role") or "table").lower()
        rows_stats = row.get("rows") if "rows" in row else row.get("row_count_stats")
        comment = row.get("comment")
        doc_name = row.get("table_name_cn") or row.get("doc_name")
        presence_in = row.get("row_presence_status")
        evidence = should_skip_probe(system_code, ns, tname)
        stats_st = classify_from_stats(rows_stats)
        presence = merge_presence(
            current=presence_in,
            stats_status=stats_st,
            evidence_status=evidence,
            probe_status=row.get("probe_status"),
        )
        if skip_confirmed_empty and presence == CONFIRMED_EMPTY:
            skipped_empty += 1
            # still record exclusion marker if already exists
            existing = db.scalar(
                select(AssetTable).where(
                    AssetTable.source_code == source_code,
                    AssetTable.schema_name == ns,
                    AssetTable.table_name == tname,
                )
            )
            if existing:
                existing.row_presence_status = CONFIRMED_EMPTY
                existing.row_presence_checked_at = now
                existing.row_presence_method = row.get("row_presence_method") or "import_gate"
                existing.include_status = "excluded_empty"
                db.execute(
                    delete(AssetColumn).where(
                        AssetColumn.source_code == source_code,
                        AssetColumn.schema_name == ns,
                        AssetColumn.table_name == tname,
                    )
                )
                updates += 1
                writes += 1
            continue

        existing = db.scalar(
            select(AssetTable).where(
                AssetTable.source_code == source_code,
                AssetTable.schema_name == ns,
                AssetTable.table_name == tname,
            )
        )
        name_cn, name_src, name_st = pick_chinese_name(
            existing_cn=existing.table_name_cn if existing else None,
            existing_status=existing.name_cn_status if existing else None,
            db_comment=comment,
            doc_name=doc_name,
            ai_name=row.get("ai_name"),
        )
        if not existing:
            obj = AssetTable(
                system_code=system_code,
                source_code=source_code,
                namespace_name=ns,
                schema_name=ns,
                table_name=tname,
                table_name_cn=name_cn,
                name_cn_source=name_src,
                name_cn_status=name_st,
                table_role=role,
                comment=comment,
                row_count_stats=str(rows_stats) if rows_stats is not None else None,
                domain=row.get("domain") or system_code,
                include_status=row.get("include_status") or "keep",
                confidence=row.get("confidence") or "live_metadata",
                source=row.get("source") or "explored_evidence",
                row_presence_status=presence if is_catalog_visible(presence) or presence else stats_st,
                row_presence_checked_at=now if presence else None,
                row_presence_method=row.get("row_presence_method") or ("evidence" if evidence else "stats"),
            )
            db.add(obj)
            inserts += 1
            writes += 1
        else:
            changed = False
            if existing.system_code != system_code:
                existing.system_code = system_code
                changed = True
            if name_cn and name_cn != existing.table_name_cn and not _is_confirmed_name(existing.name_cn_status):
                existing.table_name_cn = name_cn
                existing.name_cn_source = name_src
                existing.name_cn_status = name_st
                changed = True
            if comment is not None and comment != existing.comment:
                existing.comment = comment
                changed = True
            if rows_stats is not None and str(rows_stats) != (existing.row_count_stats or ""):
                existing.row_count_stats = str(rows_stats)
                changed = True
            if presence and presence != existing.row_presence_status:
                existing.row_presence_status = presence
                existing.row_presence_checked_at = now
                changed = True
            if changed:
                updates += 1
                writes += 1
    return {
        "writes": writes,
        "inserts": inserts,
        "updates": updates,
        "skipped_confirmed_empty": skipped_empty,
        "tables_in": len(tables),
    }


def upsert_columns(
    db: Session,
    *,
    system_code: str,
    source_code: str,
    columns: list[dict[str, Any]],
    excluded_tables: set[tuple[str, str]] | None = None,
) -> dict[str, int]:
    excluded_tables = excluded_tables or set()
    writes = inserts = updates = skipped = 0
    for row in columns:
        ns = row.get("namespace") or row.get("schema_name") or ""
        tname = row.get("table") or row.get("table_name")
        cname = row.get("column") or row.get("column_name")
        if not tname or not cname:
            continue
        if (ns, tname) in excluded_tables:
            skipped += 1
            continue
        # skip columns for confirmed_empty tables
        parent = db.scalar(
            select(AssetTable).where(
                AssetTable.source_code == source_code,
                AssetTable.schema_name == ns,
                AssetTable.table_name == tname,
            )
        )
        if parent and parent.row_presence_status == CONFIRMED_EMPTY:
            skipped += 1
            continue
        existing = db.scalar(
            select(AssetColumn).where(
                AssetColumn.source_code == source_code,
                AssetColumn.schema_name == ns,
                AssetColumn.table_name == tname,
                AssetColumn.column_name == cname,
            )
        )
        comment = row.get("comment")
        name_cn, name_src, name_st = pick_chinese_name(
            existing_cn=existing.column_name_cn if existing else None,
            existing_status=existing.name_cn_status if existing else None,
            db_comment=comment,
            doc_name=row.get("column_name_cn"),
            ai_name=row.get("ai_name"),
        )
        if not existing:
            db.add(
                AssetColumn(
                    system_code=system_code,
                    source_code=source_code,
                    namespace_name=ns,
                    schema_name=ns,
                    table_name=tname,
                    column_id=row.get("ordinal") or row.get("column_id"),
                    column_name=cname,
                    column_name_cn=name_cn,
                    name_cn_source=name_src,
                    name_cn_status=name_st,
                    data_type=row.get("data_type"),
                    length=row.get("length"),
                    nullable=str(row.get("nullable")) if row.get("nullable") is not None else None,
                    comment=comment,
                    review_status=row.get("review_status") or "live_metadata",
                )
            )
            inserts += 1
            writes += 1
        else:
            changed = False
            if existing.system_code != system_code:
                existing.system_code = system_code
                changed = True
            if name_cn and name_cn != existing.column_name_cn and not _is_confirmed_name(existing.name_cn_status):
                existing.column_name_cn = name_cn
                existing.name_cn_source = name_src
                existing.name_cn_status = name_st
                changed = True
            if row.get("data_type") and row.get("data_type") != existing.data_type:
                existing.data_type = row.get("data_type")
                changed = True
            if changed:
                updates += 1
                writes += 1
    return {"writes": writes, "inserts": inserts, "updates": updates, "skipped": skipped}


def upsert_relations(
    db: Session,
    *,
    domain: str,
    relations: list[dict[str, Any]],
    excluded_endpoints: set[str] | None = None,
) -> dict[str, int]:
    """Upsert formal relations by endpoints; mark endpoint_excluded_empty when needed."""
    excluded_endpoints = {e.upper() for e in (excluded_endpoints or set())}
    writes = inserts = updates = marked = 0
    next_id = (db.scalar(select(func.max(AssetRelation.rel_id))) or 0) + 1
    for row in relations:
        ft = row.get("from_table") or ""
        tt = row.get("to_table") or ""
        fc = row.get("from_columns") or ""
        tc = row.get("to_columns") or ""
        jc = row.get("join_condition") or ""
        level = row.get("level") or row.get("validation_level") or "sample_data"
        if not ft or not tt:
            continue
        existing = db.scalar(
            select(AssetRelation).where(
                AssetRelation.domain == domain,
                AssetRelation.from_table == ft,
                AssetRelation.to_table == tt,
                AssetRelation.from_columns == fc,
                AssetRelation.to_columns == tc,
                AssetRelation.join_condition == jc,
            )
        )
        endpoint_excluded = False
        for ep in (ft, tt):
            bare = ep.split(".")[-1].upper() if ep else ""
            full = ep.upper()
            if full in excluded_endpoints or bare in excluded_endpoints:
                endpoint_excluded = True
                break
        if not existing:
            new_rel = AssetRelation(
                rel_id=next_id,
                domain=domain,
                from_table=ft,
                from_columns=fc,
                to_table=tt,
                to_columns=tc,
                join_condition=row.get("join_condition")
                or f"{ft}({fc}) = {tt}({tc})",
                confidence=row.get("confidence"),
                validation_level=level,
                validation_status=row.get("status") or row.get("validation_status"),
                validation_metrics=row.get("metrics"),
                note=row.get("note"),
                endpoint_excluded_empty=endpoint_excluded,
            )
            # 98号 S0：导入新建时同步填充端点四元组、业务键、分层
            from .relation_identity import populate_endpoint_fields
            populate_endpoint_fields(db, new_rel)
            db.add(new_rel)
            next_id += 1
            inserts += 1
            writes += 1
            if endpoint_excluded:
                marked += 1
        else:
            changed = False
            if endpoint_excluded and not existing.endpoint_excluded_empty:
                existing.endpoint_excluded_empty = True
                changed = True
                marked += 1
            for attr, key in [
                ("confidence", "confidence"),
                ("validation_status", "status"),
                ("validation_metrics", "metrics"),
                ("note", "note"),
            ]:
                val = row.get(key)
                if val is not None and getattr(existing, attr) != val:
                    setattr(existing, attr, val)
                    changed = True
            if changed:
                # 98号 S0：更新时刷新端点四元组、业务键、分层与 updated_at
                from .relation_identity import populate_endpoint_fields
                populate_endpoint_fields(db, existing)
                existing.updated_at = datetime.now(timezone.utc)
                updates += 1
                writes += 1
    return {"writes": writes, "inserts": inserts, "updates": updates, "endpoint_excluded_marked": marked}


def rebuild_schema_inventory(
    db: Session,
    *,
    source_code: str,
    labels: list | None = None,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    # count non-empty-catalog tables only
    schema_key = func.coalesce(AssetTable.schema_name, AssetTable.namespace_name, "")
    rows = db.execute(
        select(
            schema_key,
            func.count(),
        )
        .where(
            AssetTable.source_code == source_code,
            (AssetTable.row_presence_status.is_(None))
            | (AssetTable.row_presence_status != CONFIRMED_EMPTY),
        )
        .group_by(schema_key)
    ).all()
    column_schema_key = func.coalesce(AssetColumn.schema_name, AssetColumn.namespace_name, "")
    col_rows = db.execute(
        select(
            column_schema_key,
            func.count(),
        )
        .where(AssetColumn.source_code == source_code)
        .group_by(column_schema_key)
    ).all()
    col_map = {ns: int(c) for ns, c in col_rows}
    seen = set()
    for ns, cnt in rows:
        seen.add(ns)
        inv = db.scalar(
            select(AssetSourceSchema).where(
                AssetSourceSchema.source_code == source_code,
                AssetSourceSchema.schema_name == ns,
            )
        )
        if not inv:
            db.add(
                AssetSourceSchema(
                    source_code=source_code,
                    schema_name=ns,
                    business_labels=labels,
                    table_count=int(cnt),
                    column_count=col_map.get(ns, 0),
                    last_collect_at=now,
                )
            )
        else:
            inv.table_count = int(cnt)
            inv.column_count = col_map.get(ns, 0)
            inv.last_collect_at = now
            if labels and not inv.business_labels:
                inv.business_labels = labels
    return len(seen)
