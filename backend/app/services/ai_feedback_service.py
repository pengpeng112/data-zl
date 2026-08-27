"""144 S7: AI answer provenance + feedback state machine (144 §4.7/§7.3).

Feedback can only produce candidate revisions and evaluation cases — never a
direct publish of queries/metrics/products/relations.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.ai_accuracy import AssetAiAnswerEvent, AssetAiFeedback

RATINGS = {"correct", "partially_correct", "incorrect", "insufficient_evidence", "ambiguous"}

# fixed error taxonomy (144 §4.7)
ERROR_TYPES = {
    "metadata_stale", "wrong_source", "wrong_field", "join_error", "fanout",
    "filter_error", "time_semantics", "dedup", "numerator", "denominator",
    "formula", "dimension", "parameter", "source_data_quality", "result_stale",
    "permission_or_masking", "performance", "answer_phrasing",
}

# state machine transitions (144 §7.3)
TRANSITIONS = {
    "submitted": {"triaged", "rejected"},
    "triaged": {"accepted", "rejected", "needs_business_confirmation"},
    "accepted": {"revision_draft"},
    "needs_business_confirmation": {"accepted", "rejected"},
    "revision_draft": {"evaluation_running"},
    "evaluation_running": {"resolved", "regression_failed"},
    "regression_failed": {"revision_draft", "resolved"},
}


def _now():
    return datetime.now(timezone.utc)


def _digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def register_answer_event(
    db: Session,
    *,
    question_summary: str,
    caller_id: str = "unknown",
    model_version: str | None = None,
    context_id: str | None = None,
    query_code: str | None = None,
    query_version: int | None = None,
    metric_code: str | None = None,
    metric_version: int | None = None,
    product_code: str | None = None,
    run_id: int | None = None,
    result_digest: str | None = None,
    data_as_of: datetime | None = None,
    answer_text: str | None = None,
) -> dict[str, Any]:
    """Register answer provenance; stores digests, never raw sensitive content."""
    event = AssetAiAnswerEvent(
        question_digest=_digest(question_summary),
        question_summary=(question_summary or "")[:200],
        caller_id=caller_id or "unknown",
        model_version=model_version,
        context_id=context_id,
        query_code=query_code,
        query_version=query_version,
        metric_code=metric_code,
        metric_version=metric_version,
        product_code=product_code,
        run_id=run_id,
        result_digest=result_digest,
        data_as_of=data_as_of,
        answer_digest=_digest(answer_text or ""),
        # metadata only — answer content itself is never persisted (144 §7.2)
        answer_summary=f"chars={len(answer_text or '')}",
    )
    db.add(event)
    db.flush()
    return {"id": event.id, "answer_event_id": event.id, "question_digest": event.question_digest}


def submit_feedback(
    db: Session,
    *,
    answer_event_id: int,
    rating: str,
    error_types: list[str] | None = None,
    comment: str | None = None,
    suggested_revision: str | None = None,
    submitted_by: str | None = None,
) -> dict[str, Any]:
    if rating not in RATINGS:
        raise ValueError(f"rating 必须是 {sorted(RATINGS)}")
    unknown = set(error_types or []) - ERROR_TYPES
    if unknown:
        raise ValueError(f"未知错误类型（固定分类）: {sorted(unknown)}")
    event = db.get(AssetAiAnswerEvent, answer_event_id)
    if event is None:
        raise LookupError(f"answer event 不存在: {answer_event_id}")
    row = AssetAiFeedback(
        answer_event_id=answer_event_id,
        rating=rating,
        error_types=sorted(set(error_types or [])),
        comment=(comment or "")[:500],
        suggested_revision=(suggested_revision or "")[:2000],
        submitted_by=submitted_by,
        status="submitted",
    )
    db.add(row)
    db.flush()
    return {
        "id": row.id,
        "feedback_id": row.id,
        "status": row.status,
        "answer_event_id": answer_event_id,
    }


def review_feedback(
    db: Session,
    *,
    feedback_id: int,
    action: str,
    reviewed_by: str | None = None,
    review_note: str | None = None,
    revision_query_code: str | None = None,
    revision_query_version: int | None = None,
) -> dict[str, Any]:
    row = db.get(AssetAiFeedback, feedback_id)
    if row is None:
        raise LookupError(f"feedback 不存在: {feedback_id}")
    allowed = TRANSITIONS.get(row.status, set())
    if action not in allowed:
        raise ValueError(f"状态 {row.status} 不允许转移到 {action}；允许: {sorted(allowed)}")
    row.status = action
    row.reviewed_by = reviewed_by
    row.reviewed_at = _now()
    if review_note:
        row.review_note = review_note[:500]
    if revision_query_code:
        row.revision_query_code = revision_query_code
        row.revision_query_version = revision_query_version
    if action == "resolved":
        row.resolved_at = _now()
    db.flush()
    return {"feedback_id": row.id, "status": row.status}


def get_feedback_status(db: Session, feedback_id: int) -> dict[str, Any] | None:
    row = db.get(AssetAiFeedback, feedback_id)
    if row is None:
        return None
    return {
        "feedback_id": row.id,
        "answer_event_id": row.answer_event_id,
        "rating": row.rating,
        "error_types": row.error_types,
        "status": row.status,
        "reviewed_by": row.reviewed_by,
        "revision_query_code": row.revision_query_code,
        "revision_query_version": row.revision_query_version,
        "evaluation_case_id": row.evaluation_case_id,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }
