"""Identity sync API: HIS -> CDMS / JHEMR nightly auto-sync (plan 107).

Endpoints:
- GET  /api/v1/identity-sync/status          (feature + nightly status)
- GET  /api/v1/identity-sync/nightly/status   (scheduler, circuit breakers, last run)
- POST /api/v1/identity-sync/nightly/trigger  (manual rerun, reuses full pipeline)
- POST /api/v1/identity-sync/validation/trigger (doctor_nurse_dual_target_v1)
- GET  /api/v1/identity-sync/batches          (list batches)
- GET  /api/v1/identity-sync/gates            (pre-execution gate checks)
- POST /api/v1/identity-sync/candidates       (read-only candidate selection)

Removed per plan 107 section 6:
- No arbitrary single-account apply interface
- No client-specified emp_no, SQL, table name, or action parameters
- No confirmation token for nightly batches
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.identity_sync import IdentitySyncBatch
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/identity-sync", tags=["identity-sync"])


def _sync_enabled() -> bool:
    return bool(settings.identity_sync_enabled)


def _require_sync_enabled() -> None:
    if not _sync_enabled():
        raise HTTPException(status_code=403, detail="identity sync is disabled (APP_IDENTITY_SYNC_ENABLED=false)")


@router.get("/status", summary="Identity sync feature and nightly status")
def sync_status(user=Depends(get_current_user)) -> ApiResponse[dict]:
    return ApiResponse(data={
        "enabled": _sync_enabled(),
        "nightly_enabled": settings.identity_nightly_enabled,
        "nightly_cron": settings.identity_nightly_cron,
        "timezone": settings.scheduler_timezone,
        "managed_since": settings.identity_sync_managed_since,
        "jhemr_hospital_no": settings.identity_sync_jhemr_hospital_no,
        "template_version": "jhemr-login-v1",
    })


@router.get("/nightly/status", summary="Nightly scheduler status and circuit breakers")
def nightly_status(user=Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Return current nightly scheduler configuration, last run, and circuit breaker state."""
    _require_sync_enabled()
    from ...services.identity_nightly_scheduler import get_scheduler_status
    result = get_scheduler_status(db)
    return ApiResponse(data=result)


@router.get("/alerts", summary="Queryable identity sync alerts")
def identity_sync_alerts(user=Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[dict[str, Any]]]:
    """Return redacted operational alerts; identities and SQL are never exposed."""
    from sqlalchemy import select
    from ...models.identity_sync import IdentitySyncAlert
    try:
        rows = db.scalars(select(IdentitySyncAlert).order_by(IdentitySyncAlert.created_at.desc()).limit(100)).all()
    except Exception:
        rows = []
    return ApiResponse(data=[{
        "run_id": row.run_id,
        "alert_type": row.alert_type,
        "severity": row.severity,
        "status": row.status,
        "error_class": row.error_class,
        "occurrence_count": row.occurrence_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows])


@router.post("/nightly/trigger", summary="Manual nightly rerun (reuses full pipeline)")
def nightly_trigger(user=Depends(require_permission("identity.sync.trigger")), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Trigger a manual nightly rerun.

    Reuses the same auto-candidate selection, snapshot re-read, HMAC,
    circuit breaker, and idempotency gates as the cron-triggered run.
    No client-specified emp_no, SQL, table, or action parameters accepted.
    """
    _require_sync_enabled()
    from ...services.identity_sync_orchestrator import run_nightly_pipeline
    result = run_nightly_pipeline(db, triggered_by="manual_rerun")
    return ApiResponse(data=result)


@router.post("/validation/trigger", summary="Trigger doctor_nurse_dual_target_v1 validation batch")
def validation_trigger(user=Depends(require_permission("identity.sync.trigger")), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Trigger the fixed validation batch: one doctor + one nurse x two targets.

    Fixed max 2 persons, 4 target actions. No client parameters accepted.
    Returns blocked_no_candidate if no eligible pair exists.
    """
    _require_sync_enabled()
    from ...services.identity_sync_orchestrator import run_validation_batch
    result = run_validation_batch(db)
    return ApiResponse(data=result)


@router.post("/candidates", summary="Read-only candidate selection (no writes)")
def select_candidates(user=Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Select eligible candidates per plan 107 section 4 rules.

    Read-only. Returns masked candidate info only.
    No client-specified filters or parameters.
    """
    _require_sync_enabled()
    from ...services.identity_sync_orchestrator import select_nightly_candidates
    from ...services.identity_hmac import compute_account_fingerprint
    from ...services.identity_sync_status import short_fingerprint
    candidates = select_nightly_candidates(db)
    return ApiResponse(data={
        "total_eligible": len(candidates),
        "candidates": [
            {
                "account_fingerprint": short_fingerprint(compute_account_fingerprint(c["emp_no"], "JHEMR", settings.identity_hmac_key_ref)),
                "classification": c["classification"],
                "dept_count": len(c["dept_codes"]),
                "create_date": c["create_date"],
            }
            for c in candidates[:20]
        ],
        "note": "Full list truncated; only first 20 shown. No emp_no plaintext returned.",
    })


@router.get("/runs", summary="夜间同步运行日志")
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    emp_no: str | None = Query(None, max_length=32),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ApiResponse[dict]:
    from ...services.identity_sync_log import list_sync_runs

    return ApiResponse(data=list_sync_runs(db, page=page, page_size=page_size, status=status, emp_no=emp_no))


@router.get("/runs/{run_id}", summary="单次同步运行详情")
def get_run(run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)) -> ApiResponse[dict]:
    from ...services.identity_sync_log import get_sync_run

    data = get_sync_run(db, run_id)
    if not data:
        raise HTTPException(status_code=404, detail="同步运行记录不存在")
    return ApiResponse(data=data)


@router.get("/batches", summary="List sync batches")
def list_batches(db: Session = Depends(get_db), user=Depends(get_current_user)) -> ApiResponse[list[dict]]:
    from sqlalchemy import select
    batches = db.scalars(
        select(IdentitySyncBatch).order_by(IdentitySyncBatch.created_at.desc()).limit(50)
    ).all()
    return ApiResponse(data=[
        {
            "batch_id": b.batch_id,
            "batch_type": b.batch_type,
            "validation_mode": b.validation_mode,
            "account_fingerprint": b.account_fingerprint[:12] if b.account_fingerprint else None,
            "person_classification": b.person_classification,
            "status": b.status,
            "cdms_status": b.cdms_status,
            "jhemr_status": b.jhemr_status,
            "template_version": b.template_version,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ])


@router.get("/gates", summary="Pre-execution gate check results")
def gate_checks(user=Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Run all pre-execution gates and return pass/fail status."""
    _require_sync_enabled()
    from ...services.identity_sync_orchestrator import run_gate_checks
    result = run_gate_checks(db)
    return ApiResponse(data=result)
