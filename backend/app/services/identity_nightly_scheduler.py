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
from .identity_sync_status import config_fingerprint, normalize_status

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

    # Host cron/systemd is authoritative when declared.  In-process
    # scheduling is blocked rather than running a second writer.
    if settings.identity_scheduler_provider in {"host_cron", "systemd"}:
        logger.error("identity scheduler misconfigured: provider=%s and APScheduler both enabled", settings.identity_scheduler_provider)
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
        result = run_nightly_pipeline(db, triggered_by="nightly_cron", refresh_source=True)
        logger.info("Nightly identity sync completed: %s", result.get("status"))
        if result.get("status") == "failed":
            logger.error("Nightly identity sync failed: %s", result.get("error", "unknown"))
    except Exception:
        logger.exception("Nightly identity sync unhandled exception")
    finally:
        db.close()


def get_scheduler_status(db: Session) -> dict[str, Any]:
    """Return current nightly scheduler configuration and status."""
    from ..models.identity_sync import IdentitySchedulerRun, IdentityCircuitBreaker, IdentitySyncAlert, IdentitySyncSubtask, IdentitySyncWatermark
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
    subtasks = []
    watermarks = []
    if last_run:
        try:
            subtasks = db.scalars(select(IdentitySyncSubtask).where(IdentitySyncSubtask.run_id == last_run.run_id).order_by(IdentitySyncSubtask.subtask_code)).all()
        except Exception:
            subtasks = []
    try:
        watermarks = db.scalars(select(IdentitySyncWatermark).where(IdentitySyncWatermark.source_code == "HIS")).all()
    except Exception:
        watermarks = []

    providers = []
    declared = str(getattr(settings, "identity_scheduler_provider", "disabled") or "disabled")
    if declared != "disabled":
        providers.append(declared)
    if settings.identity_nightly_enabled:
        providers.append("apscheduler")
    provider_set = sorted(set(providers))
    misconfigured = len(provider_set) > 1
    now = datetime.now(timezone.utc)
    last_finished = last_run.finished_at if last_run and last_run.finished_at else None
    if last_finished and last_finished.tzinfo is None:
        last_finished = last_finished.replace(tzinfo=timezone.utc)
    age_hours = (now - last_finished).total_seconds() / 3600 if last_finished else None
    last_status = normalize_status(last_run.status) if last_run else None
    overdue = bool((age_hours is None and bool(provider_set)) or (age_hours is not None and age_hours > settings.identity_scheduler_overdue_hours))
    overall_status = "misconfigured" if misconfigured else ("overdue" if overdue else last_status)
    try:
        alerts = db.scalars(select(IdentitySyncAlert).where(IdentitySyncAlert.status == "open").order_by(IdentitySyncAlert.created_at.desc()).limit(50)).all()
        alert_data = [{"alert_type": a.alert_type, "severity": a.severity, "error_class": a.error_class, "occurrence_count": a.occurrence_count, "run_id": a.run_id, "created_at": a.created_at.isoformat() if a.created_at else None} for a in alerts]
    except Exception:
        alert_data = []
    if misconfigured:
        alert_data.insert(0, {"alert_type": "dual_scheduler", "severity": "error", "error_class": "multiple_providers", "occurrence_count": 1, "run_id": last_run.run_id if last_run else None, "created_at": None})
    if overdue:
        alert_data.insert(0, {"alert_type": "overdue", "severity": "error", "error_class": "heartbeat_stale", "occurrence_count": 1, "run_id": last_run.run_id if last_run else None, "created_at": None})
    for watermark in watermarks:
        if watermark.watermark_status == "stalled":
            alert_data.append({"alert_type": "watermark_stalled", "severity": "warning", "error_class": "watermark_not_advanced", "occurrence_count": 1, "run_id": watermark.candidate_run_id, "created_at": None})

    return {
        "status": overall_status,
        "authoritative_provider": provider_set[0] if len(provider_set) == 1 else ("none" if not provider_set else "multiple"),
        "provider_candidates": provider_set,
        "provider_config_fingerprint": config_fingerprint(declared, settings.identity_nightly_cron, settings.scheduler_timezone, settings.identity_nightly_enabled),
        "provider_heartbeat": last_run.provider_heartbeat_at.isoformat() if last_run and last_run.provider_heartbeat_at else None,
        "overdue": overdue,
        "overdue_hours": round(age_hours, 2) if age_hours is not None else None,
        "alerts": alert_data,
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
            "overall_status": normalize_status(last_run.status) if last_run else None,
            "subtasks": [{"subtask_code": s.subtask_code, "status": normalize_status(s.status), "planned_count": s.planned_count, "succeeded_count": s.succeeded_count, "skipped_count": s.skipped_count, "failed_count": s.failed_count, "error_classes": s.error_classes or {}} for s in subtasks],
        } if last_run else None,
        "watermarks": [{"watermark_key": w.watermark_key, "status": w.watermark_status, "last_create_date": w.last_create_date.isoformat() if w.last_create_date else None, "last_employee_key_present": bool(w.last_emp_no), "candidate_run_id": w.candidate_run_id} for w in watermarks],
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
