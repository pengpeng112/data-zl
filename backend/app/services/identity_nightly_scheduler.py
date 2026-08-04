"""Nightly identity sync scheduler per plan 107.

Features:
- Asia/Shanghai timezone cron
- Distributed lock (multi-instance only executes once)
- Misfire handling (grace period)
- Max runtime timeout
- Checkpoint resume (idempotent re-entry)
- Limited retry
- Consecutive failure circuit breaker
- Threshold-based fuses (candidate/new/update/deactivate/ratio)
- Desensitized daily report + alert
- nightly defaults to false until Phase D validation passes
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..core.config import settings

logger = logging.getLogger(__name__)


def register_nightly_job(scheduler) -> None:
    """Register the nightly identity sync job with APScheduler.

    Only registers if identity_nightly_enabled is True (default False).
    Uses CronTrigger with Asia/Shanghai timezone.
    """
    if not settings.identity_nightly_enabled:
        logger.info("Identity nightly sync is disabled (APP_IDENTITY_NIGHTLY_ENABLED=false)")
        return

    if not settings.identity_sync_enabled:
        logger.warning("Identity sync feature is disabled; nightly job not registered")
        return

    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed; nightly identity sync unavailable")
        return

    trigger = CronTrigger.from_crontab(
        settings.identity_nightly_cron,
        timezone=settings.scheduler_timezone,
    )

    scheduler.add_job(
        _run_nightly_wrapper,
        trigger=trigger,
        id="identity_nightly_sync",
        replace_existing=True,
        misfire_grace_time=settings.identity_nightly_misfire_grace_seconds,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "Identity nightly sync registered: cron=%s tz=%s max_runtime=%ds",
        settings.identity_nightly_cron,
        settings.scheduler_timezone,
        settings.identity_nightly_max_runtime_seconds,
    )


def _run_nightly_wrapper() -> None:
    """Wrapper that creates a DB session and runs the nightly pipeline."""
    from ..core.db import SessionLocal
    from ..services.identity_sync_orchestrator import run_nightly_pipeline

    db: Session = SessionLocal()
    try:
        result = run_nightly_pipeline(db, triggered_by="nightly_cron")
        logger.info("Nightly identity sync completed: %s", result.get("status"))
        if result.get("status") == "failed":
            logger.error("Nightly identity sync failed: %s", result.get("error", "unknown"))
    except Exception:
        logger.exception("Nightly identity sync unhandled exception")
    finally:
        db.close()


def get_scheduler_status(db: Session) -> dict[str, Any]:
    """Return current nightly scheduler configuration and status."""
    from ..models.identity_sync import IdentitySchedulerRun, IdentityCircuitBreaker
    from sqlalchemy import select

    last_run = db.scalar(
        select(IdentitySchedulerRun).order_by(IdentitySchedulerRun.created_at.desc())
    )
    cb_cdms = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == "nightly_cdms")
    )
    cb_jhemr = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == "nightly_jhemr")
    )

    return {
        "nightly_enabled": settings.identity_nightly_enabled,
        "identity_sync_enabled": settings.identity_sync_enabled,
        "cron": settings.identity_nightly_cron,
        "timezone": settings.scheduler_timezone,
        "max_runtime_seconds": settings.identity_nightly_max_runtime_seconds,
        "max_retries": settings.identity_nightly_max_retries,
        "misfire_grace_seconds": settings.identity_nightly_misfire_grace_seconds,
        "last_run": {
            "run_id": last_run.run_id if last_run else None,
            "status": last_run.status if last_run else None,
            "started_at": last_run.started_at.isoformat() if last_run and last_run.started_at else None,
            "finished_at": last_run.finished_at.isoformat() if last_run and last_run.finished_at else None,
        } if last_run else None,
        "circuit_breakers": {
            "cdms": {
                "is_open": bool(cb_cdms.is_open) if cb_cdms else False,
                "consecutive_failures": cb_cdms.consecutive_failures if cb_cdms else 0,
            },
            "jhemr": {
                "is_open": bool(cb_jhemr.is_open) if cb_jhemr else False,
                "consecutive_failures": cb_jhemr.consecutive_failures if cb_jhemr else 0,
            },
        },
    }
