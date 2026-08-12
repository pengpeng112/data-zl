"""Relation review workflow helpers (127 S6).

asset_relation_reviews is the review fact table; asset_relations remains the
graph formal/candidate asset store. Approve must:
1. alias-normalize ODS HIS.* mirror names vs HIS source owner names
2. dedupe by stable business key / semantic match
3. link existing formal relations instead of promoting candidate copies
4. never auto-approve cross-system draft without evidence
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.asset import AssetRelation, AssetRelationReview
from ..services.relation_identity import (
    populate_endpoint_fields,
    split_qualified_name,
)

# ODS HIS schema mirror table → common HIS source owner prefixes (semantic alias)
_ODS_HIS_OWNER_ALIASES: dict[str, tuple[str, ...]] = {
    "INP_BILL_DETAIL": ("INPBILL", "HIS"),
    "PAT_VISIT": ("MEDREC", "HIS"),
    "PAT_MASTER_INDEX": ("MEDREC", "HIS"),
    "CLINIC_MASTER": ("OUTPADM", "HIS"),
    "LAB_TEST_MASTER": ("LAB", "HIS"),
    "LAB_RESULT": ("LAB", "HIS"),
    "EXAM_MASTER": ("EXAM", "HIS"),
    "EXAM_REPORT": ("EXAM", "HIS"),
    "DIAGNOSIS": ("MEDREC", "HIS"),
    "ORDERS": ("ORDADM", "HIS"),
    "OPERATION_MASTER": ("SURGERY", "HIS"),
}


def alias_qualified_names(qualified: str | None) -> list[str]:
    """Return self + owner-alias variants for semantic endpoint matching."""
    if not qualified:
        return []
    q = qualified.strip()
    names = {q, q.upper()}
    _, schema, table = split_qualified_name(q)
    table_u = (table or "").upper()
    schema_u = (schema or "").upper()
    if table_u in _ODS_HIS_OWNER_ALIASES:
        for owner in _ODS_HIS_OWNER_ALIASES[table_u]:
            names.add(f"{owner}.{table_u}")
            names.add(f"{owner.lower()}.{table_u}")
    if schema_u == "HIS" and table_u:
        for owner in _ODS_HIS_OWNER_ALIASES.get(table_u, ()):
            names.add(f"{owner}.{table_u}")
    # owner form → HIS mirror
    if schema_u in {"INPBILL", "MEDREC", "OUTPADM", "LAB", "EXAM", "ORDADM", "SURGERY"} and table_u:
        names.add(f"HIS.{table_u}")
    return list(names)


def find_matching_relations(
    db: Session,
    *,
    from_table: str,
    to_table: str,
    from_columns: str | None = None,
    to_columns: str | None = None,
) -> list[AssetRelation]:
    """Find relations with same semantic endpoints (alias-aware)."""
    from_aliases = alias_qualified_names(from_table)
    to_aliases = alias_qualified_names(to_table)
    if not from_aliases or not to_aliases:
        return []
    stmt = select(AssetRelation).where(
        or_(*[AssetRelation.from_table.ilike(a) for a in from_aliases]),
        or_(*[AssetRelation.to_table.ilike(a) for a in to_aliases]),
    )
    rows = list(db.scalars(stmt).all())
    # Prefer exact column match when provided
    if from_columns or to_columns:
        fc = (from_columns or "").replace(" ", "").upper()
        tc = (to_columns or "").replace(" ", "").upper()

        def cols_ok(r: AssetRelation) -> bool:
            rfc = (r.from_columns or "").replace(" ", "").upper()
            rtc = (r.to_columns or "").replace(" ", "").upper()
            if fc and fc not in rfc and rfc not in fc:
                return False
            if tc and tc not in rtc and rtc not in tc:
                return False
            return True

        filtered = [r for r in rows if cols_ok(r)]
        if filtered:
            return filtered
    return rows


def pick_formal_link(matches: list[AssetRelation]) -> Optional[AssetRelation]:
    """Prefer existing formal/verified relation over candidate copies."""
    formal = [
        r
        for r in matches
        if (r.relation_layer or "").lower() == "formal"
        or (r.validation_status or "").lower() in {"verified", "approved", "manual_reviewed"}
    ]
    if formal:
        # Prefer owner-named (not HIS.* ODS mirror) when both exist
        def score(r: AssetRelation) -> int:
            s = 0
            ft = (r.from_table or "").upper()
            if not ft.startswith("HIS."):
                s += 2
            if (r.relation_layer or "").lower() == "formal":
                s += 3
            if (r.validation_status or "").lower() == "verified":
                s += 1
            return s

        formal.sort(key=score, reverse=True)
        return formal[0]
    # No formal: return highest-id candidate for link (do not promote)
    if matches:
        return sorted(matches, key=lambda r: r.id or 0, reverse=True)[0]
    return None


def approve_review(
    db: Session,
    review: AssetRelationReview,
    *,
    reviewer: str = "reviewer",
    note: str | None = None,
) -> dict:
    """Approve a draft review: link existing formal/candidate, never duplicate formal."""
    if (review.review_status or "").lower() not in {"draft", "reviewing", "pending", ""}:
        return {
            "ok": False,
            "error": f"cannot approve review in status={review.review_status}",
            "review_id": review.id,
        }

    matches = find_matching_relations(
        db,
        from_table=review.from_table,
        to_table=review.to_table,
        from_columns=review.from_columns,
        to_columns=review.to_columns,
    )
    link = pick_formal_link(matches)
    action = "linked_existing"
    if link is None:
        # Create candidate only if nothing exists; do not auto-create formal
        rel = AssetRelation(
            from_table=review.from_table,
            from_columns=review.from_columns,
            to_table=review.to_table,
            to_columns=review.to_columns,
            join_condition=review.join_condition,
            confidence=review.confidence or "B",
            validation_status="sample_pass",
            relation_layer="candidate",
            note=review.review_note or review.relation_desc_cn,
        )
        populate_endpoint_fields(db, rel)
        db.add(rel)
        db.flush()
        link = rel
        action = "created_candidate"

    layer = (link.relation_layer or "").lower()
    status = (link.validation_status or "").lower()
    if layer == "formal" or status in {"verified", "approved", "manual_reviewed"}:
        action = "linked_formal"
    elif layer == "candidate" or status == "candidate":
        # Explicitly do NOT promote candidate to formal here — avoids 537/538 formal dup
        action = "linked_candidate_no_promote"

    review.source_relation_id = link.id
    review.source_relation_table = "asset_relations"
    review.review_status = "approved"
    review.reviewer = reviewer
    review.reviewed_at = datetime.now(timezone.utc)
    if note:
        review.review_note = (review.review_note or "") + f"\n[approve] {note}"
    elif not review.review_note:
        review.review_note = f"approved: {action}; linked relation id={link.id}"
    db.flush()
    return {
        "ok": True,
        "review_id": review.id,
        "action": action,
        "source_relation_id": link.id,
        "relation_layer": link.relation_layer,
        "validation_status": link.validation_status,
        "from_table": link.from_table,
        "to_table": link.to_table,
    }


def reject_review(
    db: Session,
    review: AssetRelationReview,
    *,
    reviewer: str = "reviewer",
    note: str | None = None,
) -> dict:
    review.review_status = "rejected"
    review.reviewer = reviewer
    review.reviewed_at = datetime.now(timezone.utc)
    if note:
        review.review_note = (review.review_note or "") + f"\n[reject] {note}"
    db.flush()
    return {"ok": True, "review_id": review.id, "review_status": "rejected"}
