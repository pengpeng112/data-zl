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


# ---------------------------------------------------------------------------
# 186 Q2：分页列表 + 所有者/审核范围检查（§4.4 契约）
# ---------------------------------------------------------------------------

FEEDBACK_STATUSES = set(TRANSITIONS.keys()) | {"resolved"}

MAX_PAGE_SIZE = 100


def _feedback_list_item(row: AssetAiFeedback, event: AssetAiAnswerEvent | None) -> dict[str, Any]:
    return {
        "feedback_id": row.id,
        "answer_event_id": row.answer_event_id,
        "status": row.status,
        "rating": row.rating,
        "error_types": row.error_types or [],
        "submitted_at": row.submitted_at.isoformat() if getattr(row, "submitted_at", None) else None,
        "query_code": event.query_code if event else None,
        "query_version": event.query_version if event else None,
        "metric_code": event.metric_code if event else None,
        "metric_version": event.metric_version if event else None,
        "product_code": event.product_code if event else None,
        "run_id": event.run_id if event else None,
        "result_digest": event.result_digest if event else None,
        # §4.4：question_summary/comment 等长文本在详情按权限获取，列表不带
        # 审核者视角才返回稳定提交者标识；mine 列表对本人无额外价值
        "submitted_by": row.submitted_by,
    }


def list_feedback(
    db: Session,
    *,
    current_user: str | None,
    has_review_permission: bool,
    scope: str = "mine",
    status: str | None = None,
    query_code: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """§4.4：scope=mine 仅本人历史（legacy 空 submitted_by 不归属任何人）；
    scope=queue 需要 feedback:review。submitted_at DESC NULLS LAST, id DESC
    稳定分页（186 v1.10 P1-12/T60，与文档契约一致）。"""
    from sqlalchemy import func

    if scope not in {"mine", "queue"}:
        raise ValueError("scope 必须是 mine 或 queue")
    if scope == "mine" and not current_user:
        # 未认证身份不可能有“我的”历史——空结果而非伪造
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    if scope == "queue" and not has_review_permission:
        raise PermissionError("queue 需要 feedback:review 权限")

    stmt = select(AssetAiFeedback)
    if scope == "mine":
        stmt = stmt.where(AssetAiFeedback.submitted_by == current_user)
    if status is not None:
        if status not in FEEDBACK_STATUSES:
            raise ValueError(f"未知 status: {status}")
        stmt = stmt.where(AssetAiFeedback.status == status)
    if query_code:
        stmt = stmt.join(
            AssetAiAnswerEvent,
            AssetAiFeedback.answer_event_id == AssetAiAnswerEvent.id,
        ).where(AssetAiAnswerEvent.query_code == query_code)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # 186 v1.10 P1-12/T60：submitted_at DESC NULLS LAST, id DESC 稳定排序。
    # NULL（历史缺时间）排末尾；相同 submitted_at 按 id 降序保证跨页不重不漏。
    # nullslast() 在 PG 原生支持，SQLite 3.30+ 亦支持（SQLAlchemy 1.4+ 通用）。
    rows = db.scalars(
        stmt.order_by(
            AssetAiFeedback.submitted_at.desc().nullslast(),
            AssetAiFeedback.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    events = {
        e.id: e
        for e in db.scalars(
            select(AssetAiAnswerEvent).where(
                AssetAiAnswerEvent.id.in_([r.answer_event_id for r in rows])
            )
        ).all()
    } if rows else {}
    items = [_feedback_list_item(r, events.get(r.answer_event_id)) for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def feedback_readable_by(
    row: AssetAiFeedback,
    *,
    current_user: str | None,
    has_review_permission: bool,
) -> bool:
    """单条读取范围：本人提交，或持 feedback:review（审核队列语义）。
    旧记录 submitted_by 为空 → 不归属任何普通提交者，仅审核可读。"""
    if has_review_permission:
        return True
    if current_user and row.submitted_by:
        return row.submitted_by == current_user
    return False
