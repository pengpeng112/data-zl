"""Persistence helpers for plan 122 run/subtask/action facts and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.identity_sync import IdentitySchedulerRun, IdentitySyncAction, IdentitySyncAlert, IdentitySyncSubtask
from .identity_sync_status import aggregate_overall_status, normalize_status, redacted_summary


class AuditWriteError(RuntimeError):
    """Raised when the task cannot prove its action/run audit was persisted."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_subtask(db: Session, *, run_id: str, subtask_code: str, target_system: str | None = None, **values: Any) -> IdentitySyncSubtask:
    try:
        row = db.scalar(select(IdentitySyncSubtask).where(
            IdentitySyncSubtask.run_id == run_id,
            IdentitySyncSubtask.subtask_code == subtask_code,
        ))
        if row is None:
            row = IdentitySyncSubtask(
                run_id=run_id,
                subtask_code=subtask_code,
                target_system=target_system,
                started_at=_now(),
            )
            db.add(row)
        if target_system:
            row.target_system = target_system
        for key, value in values.items():
            if hasattr(row, key):
                setattr(row, key, value)
        if values.get("status") in {"success", "partial_success", "failed", "skipped", "misconfigured", "overdue"} and "finished_at" not in values:
            row.finished_at = _now()
        db.commit()
        return row
    except Exception as exc:
        db.rollback()
        raise AuditWriteError(f"subtask_audit_write:{type(exc).__name__}") from exc


def create_action(db: Session | None, *, run_id: str, fingerprint: str, target_system: str = "JHEMR") -> IdentitySyncAction | None:
    """Create a planned signature action before any target write."""
    if db is None:
        return None
    try:
        row = IdentitySyncAction(
            batch_id=f"{run_id}:jhemr-signature:{fingerprint[:16]}",
            action_seq=1,
            target_system=target_system,
            action_type="signature_sync",
            target_table="jhemr.users_pic",
            account_fingerprint=fingerprint,
            params_summary={"run_id": run_id, "subtask": "jhemr_signature_sync"},
            subtask_code="jhemr_signature_sync",
            status="planned",
        )
        db.add(row)
        db.commit()
        return row
    except Exception as exc:
        db.rollback()
        raise AuditWriteError(f"action_audit_write:{type(exc).__name__}") from exc


def finish_action(db: Session | None, row: IdentitySyncAction | None, *, status: str, rows_affected: int = 0, error_class: str | None = None, error_code: str | None = None, reason_code: str | None = None) -> None:
    if db is None or row is None:
        return
    try:
        row.status = status
        row.rows_affected = rows_affected
        row.error_class = error_class
        row.error_code_masked = error_code
        row.reason_code = reason_code
        row.executed_at = _now()
        # No free-form exception text and no target parameters are persisted.
        row.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        raise AuditWriteError(f"action_audit_write:{type(exc).__name__}") from exc


def record_alert(db: Session | None, *, run_id: str | None, alert_type: str, severity: str = "warning", error_class: str | None = None, count: int = 1, detail: dict[str, Any] | None = None) -> None:
    if db is None:
        return
    try:
        db.add(IdentitySyncAlert(
            run_id=run_id,
            alert_type=alert_type,
            severity=severity,
            error_class=error_class,
            occurrence_count=count,
            detail=redacted_summary(detail),
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise AuditWriteError(f"alert_write:{type(exc).__name__}") from exc


def finalize_run(db: Session | None, *, run_id: str | None, main_result: dict[str, Any], signature_result: dict[str, Any]) -> str:
    """Write the combined fact and return the only supported overall status."""
    overall = aggregate_overall_status(main_result.get("status"), signature_result.get("status"), signature_required=True, lock_reason=main_result.get("reason"))
    if db is None or not run_id:
        return overall
    try:
        run = db.scalar(select(IdentitySchedulerRun).where(IdentitySchedulerRun.run_id == run_id))
        if run is None:
            raise AuditWriteError("run_audit_missing")
        run.status = overall
        run.failed_count = int(run.failed_count or 0) + int(signature_result.get("failed") or 0)
        run.skipped_count = int(run.skipped_count or 0) + int(signature_result.get("skipped_existing") or 0) + int(signature_result.get("skipped_no_user") or 0)
        run.report_summary = redacted_summary({
            "main_account_sync": main_result,
            "jhemr_signature_sync": signature_result,
            "overall_status": overall,
        })
        run.last_error_class = next(iter((signature_result.get("error_classes") or {}).keys()), None)
        db.commit()
        if overall in {"partial_success", "failed", "misconfigured", "overdue"}:
            try:
                record_alert(db, run_id=run_id, alert_type=overall, severity="error", error_class=run.last_error_class, count=int(signature_result.get("failed") or 1), detail={"status": overall})
            except AuditWriteError:
                # Alert-channel failure must not rewrite the authoritative run
                # status; operators can query the original run fact.
                pass
        planned = int(signature_result.get("planned_count") or 0)
        processed = int(signature_result.get("inserted") or 0) + int(signature_result.get("skipped_existing") or 0) + int(signature_result.get("skipped_no_user") or 0) + int(signature_result.get("failed") or 0)
        if planned and planned != processed:
            try:
                record_alert(db, run_id=run_id, alert_type="action_audit_nonconservation", severity="error", error_class="count_mismatch", count=abs(planned - processed), detail={"planned": planned, "processed": processed})
            except AuditWriteError:
                pass
        if "target_readback" in (signature_result.get("error_classes") or {}):
            try:
                record_alert(db, run_id=run_id, alert_type="target_readback_mismatch", severity="error", error_class="target_readback", count=sum((signature_result.get("error_classes") or {}).get("target_readback", {}).values()), detail={"status": overall})
            except AuditWriteError:
                pass
        return overall
    except AuditWriteError:
        raise
    except Exception as exc:
        db.rollback()
        raise AuditWriteError(f"run_audit_write:{type(exc).__name__}") from exc
