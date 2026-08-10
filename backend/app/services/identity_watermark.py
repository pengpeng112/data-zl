"""Independent composite watermarks for account and signature streams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.identity_sync import IdentitySyncWatermark
from .identity_sync_status import tie_breaker_after


@dataclass(frozen=True)
class Watermark:
    create_date: datetime | None
    employee_key: str | None
    run_id: str | None = None
    seed_required: bool = False


def get_watermark(db: Session, *, source_code: str, watermark_key: str) -> Watermark:
    row = db.scalar(select(IdentitySyncWatermark).where(
        IdentitySyncWatermark.source_code == source_code,
        IdentitySyncWatermark.watermark_key == watermark_key,
    ))
    if row is None or row.last_create_date is None:
        # Initial seed is intentionally a dry-run decision.  No row is
        # inserted here, so a failed or unapproved seed cannot move a cursor.
        return Watermark(None, None, seed_required=True)
    value = row.last_create_date
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return Watermark(value, row.last_emp_no, row.last_run_at.isoformat() if row.last_run_at else None)


def window_start(watermark: Watermark, *, lookback_hours: int | None = None) -> datetime | None:
    if watermark.create_date is None:
        return None
    return watermark.create_date - timedelta(hours=max(0, int(lookback_hours if lookback_hours is not None else settings.identity_sync_lookback_hours)))


def select_after_watermark(create_date: datetime | None, employee_key: str | None, watermark: Watermark, *, lookback_hours: int | None = None) -> bool:
    if watermark.create_date is None:
        return False
    start = window_start(watermark, lookback_hours=lookback_hours)
    if create_date is None or start is None:
        return False
    if create_date > start:
        return True
    return tie_breaker_after(create_date, employee_key, watermark.create_date, watermark.employee_key)


def max_watermark(items: Iterable[tuple[datetime | None, str | None]]) -> Watermark:
    best: tuple[datetime, str] | None = None
    for create_date, employee_key in items:
        if create_date is None:
            continue
        value = create_date if create_date.tzinfo else create_date.replace(tzinfo=timezone.utc)
        key = str(employee_key or "")
        if best is None or (value, key) > best:
            best = (value, key)
    return Watermark(best[0], best[1]) if best else Watermark(None, None, seed_required=True)


def advance_watermark(db: Session, *, source_code: str, watermark_key: str, candidate: Watermark, run_id: str, success: bool, dry_run: bool = False, commit: bool = True) -> None:
    """Commit only a successful, non-dry-run candidate; failures do not move it."""
    if dry_run or not success or candidate.create_date is None:
        return
    row = db.scalar(select(IdentitySyncWatermark).where(
        IdentitySyncWatermark.source_code == source_code,
        IdentitySyncWatermark.watermark_key == watermark_key,
    ))
    if row is None:
        row = IdentitySyncWatermark(source_code=source_code, watermark_key=watermark_key)
        db.add(row)
    row.last_create_date = candidate.create_date
    row.last_emp_no = candidate.employee_key
    row.last_run_at = datetime.now(timezone.utc)
    row.rows_collected = int(row.rows_collected or 0) + 1
    row.candidate_create_date = candidate.create_date
    row.candidate_emp_no = candidate.employee_key
    row.candidate_run_id = run_id
    row.watermark_status = "committed"
    if commit:
        db.commit()


def initial_seed_dry_run(items: Iterable[tuple[datetime | None, str | None]]) -> dict[str, Any]:
    candidate = max_watermark(items)
    return {
        "status": "dry_run",
        "seed_required": candidate.seed_required,
        "candidate_create_date": candidate.create_date.isoformat() if candidate.create_date else None,
        "candidate_employee_key_present": bool(candidate.employee_key),
        "writes": 0,
    }
