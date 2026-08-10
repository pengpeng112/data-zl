"""Dict sync outbox worker (112 A1/A5).

Durable per-target dispatch. Replaces approval-time synchronous writes with
a lease-based queue so a crash mid-dispatch is replayable after restart.

Design notes (112 A2):
- Enqueue happens in the same transaction as approval (audit + outbox commit
  together) so an approved plan is never lost.
- One event per target system per plan (business_key = plan:<id>:<target>).
  Idempotent: re-enqueue of the same key just resets a stale event, it does
  not duplicate work.
- Lease: claim does SELECT ... FOR UPDATE SKIP LOCKED, marks leased, sets
  lease_expires_at = now + LEASE_SECONDS. Restart recovery re-opens expired
  leases as pending (replay).
- Attempts bounded by max_attempts; exceeding -> dead_letter.
- Retry backoff: base * 2^(attempt-1), capped.

The DB-touching functions are kept thin so the retry/backoff/dead-letter
decisions are pure functions (unit-testable without a database).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models.dict_sync_outbox import DictSyncOutboxEvent

logger = logging.getLogger(__name__)

LEASE_SECONDS = 300
MAX_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 10
MAX_RETRY_DELAY_SECONDS = 3600

EVENT_CATEGORY_DICT_PUSH = "dict_push"
EVENT_CATEGORY_IDENTITY_BATCH = "identity_batch"

STATUS_PENDING = "pending"
STATUS_LEASED = "leased"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_DEAD_LETTER = "dead_letter"


def business_key_for_plan(plan_id: int, target_system: str) -> str:
    return f"plan:{plan_id}:{target_system}"


def business_key_for_batch(batch_id: str, target_system: str) -> str:
    return f"batch:{batch_id}:{target_system}"


# ---------------------------------------------------------------------------
# Pure policy helpers (no DB; directly unit-testable)
# ---------------------------------------------------------------------------

def retry_after_seconds(attempt: int, *, base: int = BASE_RETRY_DELAY_SECONDS, cap: int = MAX_RETRY_DELAY_SECONDS) -> int:
    """Exponential backoff for the NEXT retry after a failed attempt."""
    delay = base * (2 ** max(0, attempt - 1))
    return min(delay, cap)


def should_dead_letter(attempt: int, max_attempts: int = MAX_ATTEMPTS) -> bool:
    """True when the next retry would exceed max_attempts."""
    return attempt >= max_attempts


def classify_event(event: dict[str, Any], handler_result: dict[str, Any]) -> tuple[str, str | None]:
    """Decide next status/error for an event after one execution pass.

    Pure decision helper, kept out of the DB layer for testability.
    """
    attempt = int(event.get("attempt") or 0)
    max_attempts = int(event.get("max_attempts") or MAX_ATTEMPTS)
    ok = bool(handler_result.get("ok"))
    if ok:
        return STATUS_SUCCEEDED, None
    error = str(handler_result.get("error") or "unknown error")[:400]
    if should_dead_letter(attempt, max_attempts):
        return STATUS_DEAD_LETTER, error
    return STATUS_FAILED, error


# ---------------------------------------------------------------------------
# Enqueue (same transaction as approval)
# ---------------------------------------------------------------------------

def enqueue_plan_dispatch(db: Session, plan_id: int, plan_hash: str, target_systems: list[str]) -> list[DictSyncOutboxEvent]:
    """Create one durable event per target system. Caller commits."""
    events: list[DictSyncOutboxEvent] = []
    for target in target_systems:
        existing = db.scalar(
            select(DictSyncOutboxEvent).where(
                DictSyncOutboxEvent.business_key == business_key_for_plan(plan_id, target)
            )
        )
        if existing is not None:
            # Idempotent re-enqueue: reset a stuck event (never duplicate).
            if existing.status in {STATUS_SUCCEEDED}:
                continue
            existing.status = STATUS_PENDING
            existing.attempt = 0
            existing.next_retry_at = None
            existing.lease_expires_at = None
            existing.lease_holder = None
            existing.last_error_masked = None
            existing.plan_hash = plan_hash
            events.append(existing)
            continue
        event = DictSyncOutboxEvent(
            business_key=business_key_for_plan(plan_id, target),
            category=EVENT_CATEGORY_DICT_PUSH,
            target_system=target,
            event_type="plan_approve",
            plan_id=plan_id,
            plan_hash=plan_hash,
            status=STATUS_PENDING,
            attempt=0,
            max_attempts=MAX_ATTEMPTS,
        )
        db.add(event)
        events.append(event)
    return events


def enqueue_batch_dispatch(
    db: Session,
    batch_id: str,
    target_systems: list[str],
    *,
    payload: dict[str, Any] | None = None,
) -> list[DictSyncOutboxEvent]:
    """Create one durable event per target for an identity batch."""
    events: list[DictSyncOutboxEvent] = []
    for target in target_systems:
        existing = db.scalar(
            select(DictSyncOutboxEvent).where(
                DictSyncOutboxEvent.business_key == business_key_for_batch(batch_id, target)
            )
        )
        if existing is not None:
            if existing.status in {STATUS_SUCCEEDED}:
                continue
            existing.status = STATUS_PENDING
            existing.attempt = 0
            existing.next_retry_at = None
            existing.lease_expires_at = None
            existing.lease_holder = None
            existing.last_error_masked = None
            events.append(existing)
            continue
        event = DictSyncOutboxEvent(
            business_key=business_key_for_batch(batch_id, target),
            category=EVENT_CATEGORY_IDENTITY_BATCH,
            target_system=target,
            event_type="identity_batch",
            batch_id=batch_id,
            payload=payload,
            status=STATUS_PENDING,
            attempt=0,
            max_attempts=MAX_ATTEMPTS,
        )
        db.add(event)
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Claim + execute (lease-based, crash recoverable)
# ---------------------------------------------------------------------------

def claim_ready_events(
    db: Session,
    holder: str,
    *,
    batch_size: int = 10,
    now: datetime | None = None,
    categories: list[str] | None = None,
) -> list[DictSyncOutboxEvent]:
    """Lease up to batch_size pending (or due-for-retry) events.

    SELECT ... FOR UPDATE SKIP LOCKED so concurrent workers never double-claim.
    """
    now = now or datetime.now(timezone.utc)
    stmt = (
        select(DictSyncOutboxEvent)
        .where(
            DictSyncOutboxEvent.status.in_([STATUS_PENDING, STATUS_FAILED]),
            DictSyncOutboxEvent.lease_expires_at.is_(None),
        )
        .where(
            (DictSyncOutboxEvent.next_retry_at.is_(None))
            | (DictSyncOutboxEvent.next_retry_at <= now)
        )
        .order_by(DictSyncOutboxEvent.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    if categories:
        stmt = stmt.where(DictSyncOutboxEvent.category.in_(categories))
    events = list(db.scalars(stmt).all())
    for ev in events:
        ev.status = STATUS_LEASED
        ev.attempt = (ev.attempt or 0) + 1
        ev.lease_holder = holder
        ev.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        ev.next_retry_at = None
    db.flush()
    return events


def release_lease(db: Session, event: DictSyncOutboxEvent) -> None:
    """Release a lease without executing (e.g. process is shutting down)."""
    event.status = STATUS_PENDING
    event.lease_expires_at = None
    event.lease_holder = None
    db.flush()


def settle_event(
    db: Session,
    event: DictSyncOutboxEvent,
    handler_result: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    """Record one execution pass result using pure classification helpers."""
    now = now or datetime.now(timezone.utc)
    status, error = classify_event(event.to_dict(), handler_result)
    event.status = status
    event.lease_expires_at = None
    event.lease_holder = None
    if error is not None:
        event.last_error_masked = error
    if status == STATUS_FAILED:
        event.next_retry_at = now + timedelta(seconds=retry_after_seconds(event.attempt or 0))
    db.flush()
    return status


def reset_expired_leases(db: Session, *, now: datetime | None = None) -> int:
    """Restart recovery: any leased event past its lease is re-opened."""
    now = now or datetime.now(timezone.utc)
    result = db.execute(
        update(DictSyncOutboxEvent)
        .where(
            DictSyncOutboxEvent.status == STATUS_LEASED,
            DictSyncOutboxEvent.lease_expires_at.is_not(None),
            DictSyncOutboxEvent.lease_expires_at < now,
        )
        .values(status=STATUS_PENDING, lease_expires_at=None, lease_holder=None)
    )
    return int(result.rowcount or 0)


def run_worker_once(
    db: Session,
    holder: str,
    handler: Callable[[DictSyncOutboxEvent], dict[str, Any]],
    *,
    batch_size: int = 10,
    now: datetime | None = None,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """One worker pass: recover stale leases, claim a batch, dispatch each.

    Returns summary counts. handler is expected to be idempotent per event.
    """
    now = now or datetime.now(timezone.utc)
    recovered = reset_expired_leases(db, now=now)
    claimed = claim_ready_events(
        db,
        holder,
        batch_size=batch_size,
        now=now,
        categories=categories,
    )
    db.commit()

    summary = {
        "recovered": recovered,
        "claimed": len(claimed),
        "succeeded": 0,
        "failed": 0,
        "dead_letter": 0,
    }
    for ev in claimed:
        try:
            result = handler(ev)
        except Exception as exc:  # never leak internals into queue state
            result = {"ok": False, "error": f"handler_failed_{type(exc).__name__}"}
        status = settle_event(db, ev, result, now=now)
        if status == STATUS_SUCCEEDED:
            summary["succeeded"] += 1
        elif status == STATUS_DEAD_LETTER:
            summary["dead_letter"] += 1
        else:
            summary["failed"] += 1
        db.commit()
    return summary


def dispatch_dict_event(db: Session, event: DictSyncOutboxEvent) -> dict[str, Any]:
    """Controlled handler for one dictionary outbox event.

    Reloads all authoritative state from the platform DB and rechecks the
    immutable plan hash at the worker boundary. The event payload never
    supplies SQL, a connection string, or a source code.
    """
    from fastapi import HTTPException
    from ..core.config import settings
    from ..models.dict_medical_push import DictMedicalPushPlan
    from .dict_medical_push import verify_plan_integrity
    from .dict_sync_executor import dispatch_target

    if event.category != EVENT_CATEGORY_DICT_PUSH or event.event_type != "plan_approve":
        return {"ok": False, "error": "unsupported_outbox_event"}
    plan = db.get(DictMedicalPushPlan, event.plan_id)
    if plan is None or plan.status != "approved":
        return {"ok": False, "error": "plan_not_approved"}
    if not event.plan_hash or event.plan_hash != plan.content_hash or not verify_plan_integrity(db, plan):
        return {"ok": False, "error": "plan_hash_mismatch"}
    if event.target_system not in (plan.target_systems or []):
        return {"ok": False, "error": "target_not_in_plan"}
    try:
        result = dispatch_target(
            db, plan, event.target_system,
            his_source_code=settings.dict_medical_his_source_code,
            jhemr_source_code=settings.dict_medical_jhemr_source_code,
            operator="dict-sync-worker",
            hospital_no=settings.dict_medical_push_default_hospital_no,
        )
    except HTTPException as exc:
        return {"ok": False, "error": f"dispatch_rejected_{exc.status_code}"}
    except Exception as exc:
        return {"ok": False, "error": f"dispatch_failed_{type(exc).__name__}"}
    return {"ok": result.get("status") == "succeeded", "error": None if result.get("status") == "succeeded" else result.get("status")}
