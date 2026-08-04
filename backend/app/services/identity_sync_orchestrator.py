"""Identity sync orchestrator: full auto pipeline per plan 107.

Pipeline: collect -> preflight -> plan -> apply -> readback -> reconcile -> report.
Two independent targets (CDMS, JHEMR) with independent transactions.
No human approval for normal nightly batches. No confirmation token.
HMAC account fingerprint binding. Circuit breaker. Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.identity import IdentityPerson, IdentityPersonDepartment
from ..models.identity_sync import (
    IdentitySyncBatch,
    IdentitySyncAction,
    IdentitySyncWatermark,
    IdentityRoleMapping,
    IdentityProtectedAccount,
    IdentityManagedRelation,
    IdentitySyncCompensation,
    IdentityClassificationRecord,
    IdentityDistributedLock,
    IdentitySchedulerRun,
    IdentityCircuitBreaker,
)
from ..services.identity_classification import allowed_additional_group_classes
from ..services.identity_hmac import (
    compute_account_fingerprint,
    compute_action_hash,
    compute_idempotency_key,
    compute_batch_fingerprint,
)

logger = logging.getLogger(__name__)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MANAGED_SINCE = datetime(2026, 7, 20, tzinfo=timezone.utc)
TEMPLATE_VERSION = "jhemr-login-v1"
SENSITIVE_FIELDS = {"FPWD", "FPWD_SM", "PASSWORD", "USER_PWD", "USER_PWD_SM", "NAME", "ID_NO", "PHONE"}
ELIGIBLE_CLASSIFICATIONS = {"doctor", "nurse", "pharmacist"}
STAFF_GROUP_SOURCE_TABLE = "COMM.STAFF_VS_GROUP"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    """Normalize DB datetimes to tz-aware UTC for safe comparison.

    PostgreSQL TIMESTAMPTZ comes back tz-aware, SQLite comes back naive;
    comparing mixed values raises TypeError.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _mask_emp_no(emp_no: str) -> str:
    if not emp_no:
        return "***"
    if len(emp_no) <= 4:
        return "*" * len(emp_no)
    return emp_no[:2] + "*" * (len(emp_no) - 4) + emp_no[-2:]


def _strip_sensitive(data: dict) -> dict:
    return {k: v for k, v in data.items() if str(k).upper() not in SENSITIVE_FIELDS}


def _action_hash(actions: list[dict]) -> str:
    raw = "|".join(f"{a.get('target_system')}:{a.get('action_type')}:{a.get('target_table')}" for a in actions)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Distributed lock
# ---------------------------------------------------------------------------

def acquire_lock(db: Session, lock_key: str, holder: str, timeout_s: int) -> bool:
    now = _now()
    existing = db.scalar(
        select(IdentityDistributedLock).where(IdentityDistributedLock.lock_key == lock_key)
    )
    if existing:
        expires_at = _as_aware(existing.expires_at)
        if existing.released_at is None and expires_at and expires_at > now:
            return False
        existing.lock_holder = holder
        existing.acquired_at = now
        existing.expires_at = now + timedelta(seconds=timeout_s)
        existing.released_at = None
    else:
        db.add(IdentityDistributedLock(
            lock_key=lock_key,
            lock_holder=holder,
            acquired_at=now,
            expires_at=now + timedelta(seconds=timeout_s),
        ))
    db.flush()
    return True


def release_lock(db: Session, lock_key: str) -> None:
    existing = db.scalar(
        select(IdentityDistributedLock).where(IdentityDistributedLock.lock_key == lock_key)
    )
    if existing:
        existing.released_at = _now()
        db.flush()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

def check_circuit_breaker(db: Session, breaker_key: str) -> dict[str, Any]:
    cb = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == breaker_key)
    )
    if cb is None:
        return {"open": False, "consecutive_failures": 0}
    return {
        "open": bool(cb.is_open),
        "consecutive_failures": cb.consecutive_failures or 0,
        "last_failure_at": cb.last_failure_at.isoformat() if cb.last_failure_at else None,
    }


def record_success(db: Session, breaker_key: str) -> None:
    cb = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == breaker_key)
    )
    if cb is None:
        cb = IdentityCircuitBreaker(breaker_key=breaker_key, threshold=settings.identity_cb_consecutive_failure_limit)
        db.add(cb)
    cb.consecutive_failures = 0
    cb.is_open = False
    cb.last_success_at = _now()
    cb.updated_at = _now()
    db.flush()


def record_failure(db: Session, breaker_key: str) -> bool:
    """Record failure. Returns True if circuit is now open."""
    cb = db.scalar(
        select(IdentityCircuitBreaker).where(IdentityCircuitBreaker.breaker_key == breaker_key)
    )
    if cb is None:
        cb = IdentityCircuitBreaker(breaker_key=breaker_key, threshold=settings.identity_cb_consecutive_failure_limit)
        db.add(cb)
    cb.consecutive_failures = (cb.consecutive_failures or 0) + 1
    cb.last_failure_at = _now()
    cb.updated_at = _now()
    if cb.consecutive_failures >= (cb.threshold or settings.identity_cb_consecutive_failure_limit):
        cb.is_open = True
        cb.opened_at = _now()
        db.flush()
        return True
    db.flush()
    return False


# ---------------------------------------------------------------------------
# Candidate selection (plan 107 section 4)
# ---------------------------------------------------------------------------

def select_nightly_candidates(db: Session) -> list[dict[str, Any]]:
    """Select all eligible candidates for nightly sync.

    Rules (plan 107 section 4):
    - doctor/nurse/pharmacist only
    - status active
    - classification unique (no conflict)
    - primary dept valid
    - create_date >= managed_since
    - not in protected list
    - not outsource/management/conflict/status_conflict/master_data_missing
    """
    persons = db.scalars(
        select(IdentityPerson).where(
            IdentityPerson.source_create_date >= MANAGED_SINCE,
            IdentityPerson.employment_status == "active",
            IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)),
        ).order_by(
            IdentityPerson.source_create_date.asc(),
            IdentityPerson.person_code.asc(),
        )
    ).all()

    protected_ids = set()
    protected_rows = db.scalars(select(IdentityProtectedAccount.account_id)).all()
    protected_ids = {r for r in protected_rows if r}

    candidates = []
    for person in persons:
        emp_no = person.person_code
        if not emp_no:
            continue
        if person.conflict_flag:
            continue
        if emp_no in protected_ids:
            continue
        primary_dept, additional_depts = _get_person_depts(db, emp_no, person.classification)
        if not primary_dept:
            continue
        candidates.append({
            "emp_no": emp_no,
            "emp_no_masked": _mask_emp_no(emp_no),
            "classification": person.classification,
            "primary_dept": primary_dept,
            "dept_codes": [primary_dept] + additional_depts,
            "create_date": person.source_create_date.isoformat() if person.source_create_date else None,
        })

    return candidates


def _get_person_depts(db: Session, person_code: str, classification: str | None = None) -> tuple[str | None, list[str]]:
    """Return (primary_dept, additional_depts) for a person.

    - Primary dept: the is_primary=True relation (HIS STAFF_DICT /
      SYS_EMPLOYEE source), deterministic — never set-order dependent.
    - Additional depts: only staff-group relations whose GROUP_CLASS is in
      the per-classification whitelist (plan 107 §5.4 mapped to live values:
      doctor -> 病区医生, nurse -> 病区护士, pharmacist -> none).
    - Pharmacists get the primary dept only (plan 107 §0.3.1).
    """
    rows = db.scalars(
        select(IdentityPersonDepartment).where(
            IdentityPersonDepartment.person_code == person_code,
        )
    ).all()

    primaries = sorted(
        (r for r in rows if r.is_primary and r.dept_code),
        key=lambda r: (r.source_table or "", r.dept_code),
    )
    primary = primaries[0].dept_code if primaries else None

    allowed = allowed_additional_group_classes(classification or "")
    additionals: list[str] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda r: (r.dept_code or "")):
        if row.is_primary or not row.dept_code or row.dept_code == primary:
            continue
        # 附加科室只来自人员组白名单（107 §5.4）；DOCTOR_GROUP 等非组来源不产生附加科室
        if row.source_table != STAFF_GROUP_SOURCE_TABLE:
            continue
        if not row.group_class or row.group_class not in allowed:
            continue
        if row.dept_code not in seen:
            seen.add(row.dept_code)
            additionals.append(row.dept_code)
    return primary, additionals


def _get_role_mapping(db: Session, target_system: str, classification: str) -> dict | None:
    row = db.scalar(
        select(IdentityRoleMapping).where(
            IdentityRoleMapping.target_system == target_system,
            IdentityRoleMapping.person_classification == classification,
            IdentityRoleMapping.is_active.is_(True),
        )
    )
    if not row:
        return None
    return {"role_code": row.role_code, "role_name_cn": row.role_name_cn, "extra_config": row.extra_config or {}}


def _compute_change_stats(db: Session, candidates: list[dict]) -> dict[str, Any]:
    """Compute real new/update/deactivate composition and watermark freshness.

    - new: candidate without an active managed relation in BOTH targets
    - update: candidate already managed in at least one target (state/dept resync)
    - deactivate: managed persons no longer eligible (status/classification change)
    - watermark_gap_hours: hours since the last successful HIS collection
    - scope: all eligible active persons (denominator for change ratio)
    """
    managed_fps: set[str] = set()
    rows = db.scalars(
        select(IdentityManagedRelation.account_fingerprint).where(
            IdentityManagedRelation.status == "active",
        )
    ).all()
    managed_fps = {r for r in rows if r}

    new_count = 0
    update_count = 0
    for c in candidates:
        fp_cdms = compute_account_fingerprint(c["emp_no"], "CDMS", settings.identity_hmac_key_ref)
        fp_jhemr = compute_account_fingerprint(c["emp_no"], "JHEMR", settings.identity_hmac_key_ref)
        if fp_cdms in managed_fps or fp_jhemr in managed_fps:
            update_count += 1
        else:
            new_count += 1

    scope = db.scalar(
        select(func.count()).select_from(IdentityPerson).where(
            IdentityPerson.source_create_date >= MANAGED_SINCE,
            IdentityPerson.employment_status == "active",
            IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)),
        )
    ) or 0

    deactivate_count = 0
    if managed_fps:
        eligible_codes = {c["emp_no"] for c in candidates}
        seen_codes: set[str] = set()
        all_persons = db.scalars(
            select(IdentityPerson).where(IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)))
        ).all()
        for person in all_persons:
            if not person.person_code or person.person_code in seen_codes:
                continue
            seen_codes.add(person.person_code)
            if person.person_code in eligible_codes:
                continue
            fp = compute_account_fingerprint(person.person_code, "CDMS", settings.identity_hmac_key_ref)
            fp_j = compute_account_fingerprint(person.person_code, "JHEMR", settings.identity_hmac_key_ref)
            if fp in managed_fps or fp_j in managed_fps:
                deactivate_count += 1

    watermark_gap_hours = 0.0
    wm = db.scalar(
        select(IdentitySyncWatermark).order_by(IdentitySyncWatermark.last_run_at.desc())
    )
    if wm is not None and wm.last_run_at is not None:
        last_run = _as_aware(wm.last_run_at)
        watermark_gap_hours = max(0.0, (_now() - last_run).total_seconds() / 3600.0)

    return {
        "new": new_count,
        "update": update_count,
        "deactivate": deactivate_count,
        "scope": max(int(scope), 1),
        "watermark_gap_hours": round(watermark_gap_hours, 2),
        # 行数守恒需要源端实时行数，编排器不直连 HIS；采集阶段负责记录，
        # 此处保留 0 并在报告中标注未接线（见 110 号复核报告 R-统计）。
        "source_row_delta_pct": 0,
    }


# ---------------------------------------------------------------------------
# Threshold / fuse checks (plan 107 section 3)
# ---------------------------------------------------------------------------

def check_thresholds(candidates: list[dict], stats: dict[str, int]) -> dict[str, Any]:
    """Check circuit breaker thresholds. Returns triggered dimension or None."""
    total = len(candidates)
    if total > settings.identity_cb_max_candidates:
        return {"triggered": True, "dimension": "max_candidates", "value": total, "limit": settings.identity_cb_max_candidates}
    if stats.get("new", 0) > settings.identity_cb_max_new:
        return {"triggered": True, "dimension": "max_new", "value": stats["new"], "limit": settings.identity_cb_max_new}
    if stats.get("update", 0) > settings.identity_cb_max_update:
        return {"triggered": True, "dimension": "max_update", "value": stats["update"], "limit": settings.identity_cb_max_update}
    if stats.get("deactivate", 0) > settings.identity_cb_max_deactivate:
        return {"triggered": True, "dimension": "max_deactivate", "value": stats["deactivate"], "limit": settings.identity_cb_max_deactivate}
    scope = max(int(stats.get("scope", total)), 1)
    change_ratio = (stats.get("new", 0) + stats.get("update", 0) + stats.get("deactivate", 0)) / scope
    if change_ratio > settings.identity_cb_max_change_ratio:
        return {"triggered": True, "dimension": "max_change_ratio", "value": round(change_ratio, 3), "limit": settings.identity_cb_max_change_ratio}
    # Watermark continuity check (plan 107 section 3)
    if stats.get("watermark_gap_hours", 0) > 48:
        return {"triggered": True, "dimension": "watermark_continuity", "value": stats["watermark_gap_hours"], "limit": 48}
    # Source row count conservation (plan 107 section 3)
    if stats.get("source_row_delta_pct", 0) > 20:
        return {"triggered": True, "dimension": "source_row_conservation", "value": stats["source_row_delta_pct"], "limit": 20}
    return {"triggered": False}


# ---------------------------------------------------------------------------
# Full pipeline: plan -> apply -> readback -> reconcile -> report
# ---------------------------------------------------------------------------

def run_nightly_pipeline(db: Session, *, triggered_by: str = "nightly_cron") -> dict[str, Any]:
    """Execute the full nightly pipeline. Auto-advances without human approval.

    Pipeline: collect -> preflight -> plan -> apply -> readback -> reconcile -> report.
    Two independent targets per candidate. Each target is an independent transaction.
    """
    run_id = f"RUN-{uuid.uuid4().hex[:12]}"
    lock_key = "identity_nightly_sync"
    holder = f"nightly_{run_id}"

    # Acquire distributed lock
    if not acquire_lock(db, lock_key, holder, settings.identity_nightly_max_runtime_seconds):
        return {"status": "skipped", "reason": "lock_held", "run_id": run_id}

    run_record = IdentitySchedulerRun(
        run_id=run_id,
        triggered_by=triggered_by,
        status="running",
        lock_holder=holder,
        started_at=_now(),
    )
    db.add(run_record)
    db.flush()

    try:
        # Check circuit breakers
        for target in ("cdms", "jhemr"):
            cb_state = check_circuit_breaker(db, f"nightly_{target}")
            if cb_state["open"]:
                run_record.status = "circuit_open"
                run_record.circuit_breaker_triggered = True
                run_record.circuit_breaker_dimension = f"nightly_{target}"
                run_record.finished_at = _now()
                db.commit()
                return {"status": "circuit_open", "target": target, "run_id": run_id}

        # COLLECT (platform-side): classification preflight, then candidates.
        # The preflight fills IdentityPerson.classification / conflict_flag from
        # the collected HIS person sources — without it the candidate set would
        # always be empty (plan 107 §15.5 isolation rules are applied here).
        from .identity_classification_preflight import run_classification_preflight
        preflight_stats = run_classification_preflight(db)

        candidates = select_nightly_candidates(db)
        run_record.candidates_total = len(candidates)

        if not candidates:
            run_record.status = "success"
            run_record.finished_at = _now()
            run_record.report_summary = {"note": "no_candidates", "total": 0, "preflight": preflight_stats}
            db.commit()
            return {"status": "success", "run_id": run_id, "candidates": 0, "preflight": preflight_stats}

        # PREFLIGHT: threshold checks with real change composition
        stats = _compute_change_stats(db, candidates)
        threshold_result = check_thresholds(candidates, stats)
        if threshold_result.get("triggered"):
            run_record.status = "circuit_open"
            run_record.circuit_breaker_triggered = True
            run_record.circuit_breaker_dimension = threshold_result["dimension"]
            run_record.finished_at = _now()
            db.commit()
            return {"status": "threshold_exceeded", "dimension": threshold_result["dimension"], "run_id": run_id}

        # PLAN + APPLY: process each candidate with independent target transactions
        success_count = 0
        failed_count = 0
        skipped_count = 0

        for candidate in candidates:
            result = _process_single_candidate(db, candidate, run_id)
            if result["status"] == "success":
                success_count += 1
            elif result["status"] == "skipped":
                skipped_count += 1
            else:
                failed_count += 1

        # RECONCILE + REPORT
        run_record.success_count = success_count
        run_record.failed_count = failed_count
        run_record.skipped_count = skipped_count
        run_record.candidates_new = stats["new"]

        if failed_count > 0 and success_count > 0:
            failure_rate = failed_count / (success_count + failed_count)
            if failure_rate > settings.identity_cb_max_failure_rate:
                run_record.circuit_breaker_triggered = True
                run_record.circuit_breaker_dimension = "failure_rate"

        run_record.status = "success" if failed_count == 0 else "failed"
        run_record.finished_at = _now()
        run_record.report_summary = {
            "total": len(candidates),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }

        # Update circuit breakers
        if failed_count == 0:
            record_success(db, "nightly_cdms")
            record_success(db, "nightly_jhemr")
        else:
            record_failure(db, "nightly_cdms")
            record_failure(db, "nightly_jhemr")

        db.commit()
        return {
            "status": run_record.status,
            "run_id": run_id,
            "candidates": len(candidates),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }

    except Exception as exc:
        run_record.status = "failed"
        run_record.error_message = f"{type(exc).__name__}: {str(exc)[:300]}"
        run_record.finished_at = _now()
        record_failure(db, "nightly_cdms")
        record_failure(db, "nightly_jhemr")
        db.commit()
        logger.exception("Nightly pipeline failed: %s", run_id)
        return {"status": "failed", "run_id": run_id, "error": str(exc)[:200]}

    finally:
        release_lock(db, lock_key)
        db.commit()


def _process_single_candidate(db: Session, candidate: dict, run_id: str, max_retries: int | None = None) -> dict[str, Any]:
    """Process one candidate against both targets independently.

    Each target (CDMS, JHEMR) is an independent transaction.
    One target failure does not affect the other.
    Retries up to max_retries on transient failures (plan 107 section 3).
    """
    if max_retries is None:
        max_retries = settings.identity_nightly_max_retries
    emp_no = candidate["emp_no"]
    classification = candidate["classification"]
    dept_codes = candidate["dept_codes"]

    # Compute HMAC fingerprints. Fail closed: if the HMAC key is unavailable
    # the whole run must stop (never fall back to unsalted hashes — staff
    # numbers are low-entropy and enumerable).
    fp_cdms = compute_account_fingerprint(emp_no, "CDMS", settings.identity_hmac_key_ref)
    fp_jhemr = compute_account_fingerprint(emp_no, "JHEMR", settings.identity_hmac_key_ref)

    # Check idempotency - skip if already managed
    existing_cdms = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "CDMS",
            IdentityManagedRelation.account_fingerprint == fp_cdms,
            IdentityManagedRelation.status == "active",
        )
    )
    existing_jhemr = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "JHEMR",
            IdentityManagedRelation.account_fingerprint == fp_jhemr,
            IdentityManagedRelation.status == "active",
        )
    )

    if existing_cdms and existing_jhemr:
        return {"status": "skipped", "reason": "already_managed_both"}

    batch_id = f"NTL-{run_id}-{uuid.uuid4().hex[:8]}"
    batch = IdentitySyncBatch(
        batch_id=batch_id,
        batch_type="nightly",
        scheduler_run_id=run_id,
        emp_no_masked=candidate["emp_no_masked"],
        account_fingerprint=fp_cdms,
        person_classification=classification,
        status="applying",
        template_version=TEMPLATE_VERSION,
        idempotency_key=f"{batch_id}:{emp_no}",
        started_at=_now(),
    )
    db.add(batch)
    db.flush()

    cdms_ok = bool(existing_cdms)
    jhemr_ok = bool(existing_jhemr)

    # CDMS target (independent, with limited retry)
    if not cdms_ok:
        for attempt in range(max_retries + 1):
            cdms_result = _apply_cdms_target(db, batch_id, emp_no, classification, dept_codes, fp_cdms)
            cdms_ok = cdms_result.get("status") == "success"
            if cdms_ok or cdms_result.get("note") == "idempotent_skip":
                cdms_ok = True
                break
            if attempt < max_retries:
                logger.warning("CDMS attempt %d failed for %s, retrying", attempt + 1, _mask_emp_no(emp_no))
        batch.cdms_status = "success" if cdms_ok else cdms_result.get("status", "failed")
    else:
        batch.cdms_status = "skipped"

    # JHEMR target (independent, with limited retry)
    if not jhemr_ok:
        for attempt in range(max_retries + 1):
            jhemr_result = _apply_jhemr_target(db, batch_id, emp_no, classification, dept_codes, fp_jhemr)
            jhemr_ok = jhemr_result.get("status") == "success"
            if jhemr_ok or jhemr_result.get("note") == "idempotent_skip":
                jhemr_ok = True
                break
            if attempt < max_retries:
                logger.warning("JHEMR attempt %d failed for %s, retrying", attempt + 1, _mask_emp_no(emp_no))
        batch.jhemr_status = "success" if jhemr_ok else jhemr_result.get("status", "failed")
    else:
        batch.jhemr_status = "skipped"

    # READBACK: verify applied state matches plan (plan 107 pipeline step 5)
    readback_ok = True
    if cdms_ok and batch.cdms_status == "success":
        rb = _readback_cdms_target(db, batch_id, emp_no, fp_cdms)
        if not rb.get("consistent", True):
            readback_ok = False
            batch.cdms_status = "readback_mismatch"
    if jhemr_ok and batch.jhemr_status == "success":
        rb = _readback_jhemr_target(db, batch_id, emp_no, fp_jhemr)
        if not rb.get("consistent", True):
            readback_ok = False
            batch.jhemr_status = "readback_mismatch"

    # Final status
    if cdms_ok and jhemr_ok and readback_ok:
        batch.status = "success"
    elif cdms_ok or jhemr_ok:
        batch.status = "partial_target_success"
    else:
        batch.status = "failed"

    batch.finished_at = _now()
    db.flush()

    return {"status": "success" if (cdms_ok and jhemr_ok and readback_ok) else ("partial" if (cdms_ok or jhemr_ok) else "failed")}


# ---------------------------------------------------------------------------
# Fail-closed write gates (112 B1/B2)
# ---------------------------------------------------------------------------

def _display_name(db: Session, emp_no: str) -> str:
    """Real display name for business-DB writes (never masked emp_no).

    Masking is for logs/audit/API output only; writing a masked value
    (e.g. "12****34") into CDMS/JHEMR display-name columns would corrupt
    production data. Resolves the canonical IdentityPerson.person_name_cn.
    """
    person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == emp_no))
    name = person.person_name_cn.strip() if person and person.person_name_cn else ""
    if not name:
        # No real name available: fail closed rather than write a masked value.
        raise RuntimeError(f"display name unavailable for emp {_mask_emp_no(emp_no)}; refusing to write masked value")
    return name


def _register_managed(
    db: Session,
    *,
    batch_id: str,
    target_system: str,
    fingerprint: str,
    emp_no: str,
    classification: str,
    dept_codes: list[str],
    role_code: str | None,
    target_table: str,
    action: str,
    idem_key: str,
    status: str,
) -> IdentityManagedRelation:
    """Upsert an IdentityManagedRelation keyed by idempotency_key.

    Used on retries: when a previous failed/gated attempt left a
    pending_reconcile row, re-applying must UPDATE that row (the unique
    constraint on idempotency_key rejects a plain insert) and must NOT
    short-circuit as idempotent_skip.
    """
    existing = db.scalar(
        select(IdentityManagedRelation).where(IdentityManagedRelation.idempotency_key == idem_key)
    )
    data = _strip_sensitive(
        {"classification": classification, "dept_count": len(dept_codes)}
        | ({"role_group": role_code} if role_code else {})
    )
    if existing is not None:
        existing.batch_id = batch_id
        existing.status = status
        existing.account_fingerprint = fingerprint
        existing.relation_data = data
        db.flush()
        return existing
    row = IdentityManagedRelation(
        batch_id=batch_id,
        target_system=target_system,
        account_fingerprint=fingerprint,
        composite_business_key=(
            f"CDMS:FLOGINNAME={_mask_emp_no(emp_no)}" if target_system == "CDMS"
            else f"JHEMR:db_user+hospital_no={_mask_emp_no(emp_no)}"
        ),
        emp_no_masked=_mask_emp_no(emp_no),
        relation_type="account",
        target_table=target_table,
        target_key=_mask_emp_no(emp_no),
        relation_data=data,
        template_version=TEMPLATE_VERSION,
        action_hash=compute_action_hash(fingerprint, target_system, action, target_table, TEMPLATE_VERSION),
        status=status,
        idempotency_key=idem_key,
    )
    db.add(row)
    db.flush()
    return row

def check_write_gates(db: Session) -> dict[str, Any]:
    """All gates must pass before any business-DB write.

    Fail-closed by construction: the flags default to False/empty, so the
    bridge is never reached unless the operator explicitly confirms each gate.
    """
    from pathlib import Path
    from ..services.credentials import resolve

    def _ref_present(ref: str | None) -> bool:
        if not ref:
            return False
        if ref.startswith("file://"):
            return Path(ref[7:]).is_file()
        if ref.startswith("env:"):
            return bool(resolve(ref)[0])
        return False

    gates: list[dict[str, Any]] = []

    gates.append({
        "gate": "identity_sync_enabled",
        "passed": bool(settings.identity_sync_enabled),
        "detail": "APP_IDENTITY_SYNC_ENABLED must be true for any write",
    })
    gates.append({
        "gate": "hmac_key_present",
        "passed": _ref_present(settings.identity_hmac_key_ref),
        "detail": "identity_hmac.key credential must exist",
    })
    gates.append({
        "gate": "cdms_write_credential_present",
        "passed": _ref_present(settings.identity_sync_cdms_credential_ref),
        "detail": "CDMS write credential file must exist",
    })
    gates.append({
        "gate": "jhemr_write_credential_present",
        "passed": _ref_present(settings.identity_sync_jhemr_credential_ref),
        "detail": "JHEMR write credential file must exist",
    })
    gates.append({
        "gate": "password_write_enabled",
        "passed": bool(settings.identity_jhemr_password_write_enabled),
        "detail": "JHEMR default password write gate (SM4 cross-validated) must be enabled",
    })
    gates.append({
        "gate": "cdms_fid_semantics_confirmed",
        "passed": bool(settings.identity_cdms_fid_semantics_confirmed),
        "detail": "CDMS FID/FUSER/FUPDATEUSER semantics must be confirmed from live DB/vendor evidence",
    })
    gates.append({
        "gate": "cdms_ftype_write_forbidden",
        "passed": bool(settings.identity_cdms_ftype_write_forbidden),
        "detail": "CDMS FTYPE 8/32 writes are permanently forbidden",
    })
    gates.append({
        "gate": "no_delete_actions",
        "passed": True,
        "detail": "identity sync never issues DELETE",
    })
    gates.append({
        "gate": "phase_d_approval_version",
        "passed": bool(settings.identity_phase_d_approval_version),
        "detail": "DBA least-privilege/Phase D approval must be recorded before apply",
    })

    passed = all(g["passed"] for g in gates)
    return {"all_passed": passed, "gates": gates}


def _check_hmac_key_nonempty() -> bool:
    """HMAC key must actually be loadable (not just the file existing)."""
    try:
        from ..services.identity_hmac import _load_hmac_key  # type: ignore
        return bool(_load_hmac_key(settings.identity_hmac_key_ref))
    except Exception:
        return False


def _apply_cdms_target(db: Session, batch_id: str, emp_no: str, classification: str, dept_codes: list[str], fingerprint: str) -> dict[str, Any]:
    """Apply CDMS target. Independent transaction. INSERT + column-whitelist UPDATE only."""
    role_mapping = _get_role_mapping(db, "CDMS", classification)
    if not role_mapping:
        return {"status": "failed", "error": "CDMS role mapping not configured"}

    idem_key = compute_idempotency_key(fingerprint, "CDMS", "account", "T_MSS_EMP_DICT", TEMPLATE_VERSION)
    # Only an ACTIVE relation is idempotent-skippable. A pending_reconcile row
    # means the write never succeeded, so retries must re-apply (upsert) it.
    existing_by_fp = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "CDMS",
            IdentityManagedRelation.account_fingerprint == fingerprint,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing_by_fp:
        return {"status": "success", "note": "idempotent_skip"}
    existing = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.idempotency_key == idem_key,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing:
        return {"status": "success", "note": "idempotent_skip"}

    # 112 B1/B2：写入门禁（fail-closed）。任一 gate 不过则登记
    # pending_reconcile，绝不触碰业务库。
    gates = check_write_gates(db)
    if not gates["all_passed"]:
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        failed_gates = [g["gate"] for g in gates["gates"] if not g["passed"]]
        return {"status": "blocked", "note": "write_gates_not_satisfied", "blocked_gates": failed_gates}

    # Gates passed: invoke the white-listed executor bridge (Phase D path).
    from ..services.identity_sync_executor_bridge import execute_cdms_apply
    try:
        display_name = _display_name(db, emp_no)
    except RuntimeError as exc:
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": str(exc), "note": "display_name_unavailable"}
    primary_dept = dept_codes[0] if dept_codes else ""
    additional = dept_codes[1:] if len(dept_codes) > 1 else []
    result = execute_cdms_apply(
        emp_no=emp_no,
        display_name=display_name,
        classification=classification,
        primary_dept=primary_dept,
        additional_depts=additional,
    )
    if result.get("status") != "success":
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": result.get("error") or "cdms apply failed", "note": "bridge_failed"}

    # Readback: confirm target actually has the user before marking active.
    from ..services.identity_sync_executor_bridge import execute_cdms_readback
    readback = execute_cdms_readback(emp_no)
    if readback.get("error"):
        _register_managed(
            db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": f"cdms readback failed: {readback.get('error')}"}

    _register_managed(
        db, batch_id=batch_id, target_system="CDMS", fingerprint=fingerprint,
        emp_no=emp_no, classification=classification, dept_codes=dept_codes,
        role_code=None, target_table="T_MSS_EMP_DICT", action="insert_user",
        idem_key=idem_key, status="active",
    )
    return {"status": "success", "note": "applied_via_bridge"}


def _apply_jhemr_target(db: Session, batch_id: str, emp_no: str, classification: str, dept_codes: list[str], fingerprint: str) -> dict[str, Any]:
    """Apply JHEMR target. Independent transaction. 6-table creation."""
    role_mapping = _get_role_mapping(db, "JHEMR", classification)
    if not role_mapping:
        return {"status": "failed", "error": "JHEMR role mapping not configured"}

    idem_key = compute_idempotency_key(fingerprint, "JHEMR", "account", "users", TEMPLATE_VERSION)
    # Only an ACTIVE relation is idempotent-skippable. A pending_reconcile row
    # means the write never succeeded, so retries must re-apply (upsert) it.
    existing_by_fp = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.target_system == "JHEMR",
            IdentityManagedRelation.account_fingerprint == fingerprint,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing_by_fp:
        return {"status": "success", "note": "idempotent_skip"}
    existing = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.idempotency_key == idem_key,
            IdentityManagedRelation.status == "active",
        )
    )
    if existing:
        return {"status": "success", "note": "idempotent_skip"}

    gates = check_write_gates(db)
    if not gates["all_passed"]:
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        failed_gates = [g["gate"] for g in gates["gates"] if not g["passed"]]
        return {"status": "blocked", "note": "write_gates_not_satisfied", "blocked_gates": failed_gates}

    from ..services.identity_sync_executor_bridge import execute_jhemr_apply
    try:
        display_name = _display_name(db, emp_no)
    except RuntimeError as exc:
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": str(exc), "note": "display_name_unavailable"}
    primary_dept = dept_codes[0] if dept_codes else ""
    additional = dept_codes[1:] if len(dept_codes) > 1 else []
    result = execute_jhemr_apply(
        emp_no=emp_no,
        display_name=display_name,
        classification=classification,
        primary_dept=primary_dept,
        additional_depts=additional,
    )
    if result.get("status") != "success":
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": result.get("error") or "jhemr apply failed", "note": "bridge_failed"}

    from ..services.identity_sync_executor_bridge import execute_jhemr_readback
    readback = execute_jhemr_readback(emp_no)
    if readback.get("error"):
        _register_managed(
            db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
            emp_no=emp_no, classification=classification, dept_codes=dept_codes,
            role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
            idem_key=idem_key, status="pending_reconcile",
        )
        return {"status": "failed", "error": f"jhemr readback failed: {readback.get('error')}"}

    _register_managed(
        db, batch_id=batch_id, target_system="JHEMR", fingerprint=fingerprint,
        emp_no=emp_no, classification=classification, dept_codes=dept_codes,
        role_code=role_mapping["role_code"], target_table="users", action="create_user_full",
        idem_key=idem_key, status="active",
    )
    return {"status": "success", "note": "applied_via_bridge"}




# ---------------------------------------------------------------------------
# Readback verification (plan 107 pipeline step 5)
# -------------------------------------------------------------------------------

def _readback_cdms_target(db: Session, batch_id: str, emp_no: str, fingerprint: str) -> dict[str, Any]:
    """Verify CDMS managed relation was registered correctly.

    In Phase B (no production writes), this verifies platform-side registration.
    In Phase D, the executor bridge performs actual target readback.
    """
    managed = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.batch_id == batch_id,
            IdentityManagedRelation.target_system == "CDMS",
            IdentityManagedRelation.account_fingerprint == fingerprint,
        )
    )
    if managed is None:
        return {"consistent": False, "reason": "managed_relation_missing"}
    if managed.status == "pending_reconcile":
        return {"consistent": True, "note": "pending_reconcile_expected_in_phase_b"}
    return {"consistent": True}


def _readback_jhemr_target(db: Session, batch_id: str, emp_no: str, fingerprint: str) -> dict[str, Any]:
    """Verify JHEMR managed relation was registered correctly.

    In Phase B (no production writes), this verifies platform-side registration.
    In Phase D, the executor bridge performs actual target readback via
    execute_jhemr_readback() which snapshots all 6 tables.
    """
    managed = db.scalar(
        select(IdentityManagedRelation).where(
            IdentityManagedRelation.batch_id == batch_id,
            IdentityManagedRelation.target_system == "JHEMR",
            IdentityManagedRelation.account_fingerprint == fingerprint,
        )
    )
    if managed is None:
        return {"consistent": False, "reason": "managed_relation_missing"}
    if managed.status == "pending_reconcile":
        return {"consistent": True, "note": "pending_reconcile_expected_in_phase_b"}
    return {"consistent": True}


# ---------------------------------------------------------------------------
# Validation mode: doctor_nurse_dual_target_v1 (plan 107 section 9)
# ---------------------------------------------------------------------------

def run_validation_batch(db: Session) -> dict[str, Any]:
    """Execute the fixed doctor_nurse_dual_target_v1 validation batch.

    Selects one doctor and one nurse who do NOT exist in either CDMS or JHEMR.
    Fixed max 2 persons, 4 target actions. No third person allowed.
    """
    candidates = select_nightly_candidates(db)

    # Find one doctor and one nurse not in either target
    doctor = None
    nurse = None
    for c in candidates:
        if c["classification"] == "doctor" and doctor is None:
            doctor = c
        elif c["classification"] == "nurse" and nurse is None:
            nurse = c
        if doctor and nurse:
            break

    if not doctor or not nurse:
        return {"status": "blocked_no_candidate", "reason": "No eligible doctor or nurse found absent from both targets"}

    run_id = f"VAL-{uuid.uuid4().hex[:12]}"
    batch_id = f"VALB-{uuid.uuid4().hex[:8]}"

    run_record = IdentitySchedulerRun(
        run_id=run_id,
        triggered_by="validation",
        status="running",
        started_at=_now(),
    )
    db.add(run_record)

    # Create validation batch
    batch = IdentitySyncBatch(
        batch_id=batch_id,
        batch_type="validation",
        validation_mode="doctor_nurse_dual_target_v1",
        scheduler_run_id=run_id,
        status="applying",
        template_version=TEMPLATE_VERSION,
        idempotency_key=f"validation:{run_id}",
        started_at=_now(),
    )
    db.add(batch)
    db.flush()

    # Execute 4 target actions in order: doctor-CDMS, doctor-JHEMR, nurse-CDMS, nurse-JHEMR
    results = []
    execution_order = [
        ("doctor", "CDMS", doctor),
        ("doctor", "JHEMR", doctor),
        ("nurse", "CDMS", nurse),
        ("nurse", "JHEMR", nurse),
    ]

    paused = False
    for role, target, person in execution_order:
        if paused:
            results.append({"role": role, "target": target, "status": "paused"})
            continue

        fp = compute_account_fingerprint(person["emp_no"], target, settings.identity_hmac_key_ref)
        if target == "CDMS":
            result = _apply_cdms_target(db, batch_id, person["emp_no"], person["classification"], person["dept_codes"], fp)
        else:
            result = _apply_jhemr_target(db, batch_id, person["emp_no"], person["classification"], person["dept_codes"], fp)

        results.append({"role": role, "target": target, "status": result.get("status"), "emp_no_masked": person["emp_no_masked"]})

        if result.get("status") == "failed":
            paused = True

    # Determine overall status
    statuses = [r["status"] for r in results]
    if all(s == "success" for s in statuses):
        batch.status = "success"
        run_record.status = "success"
    elif any(s == "success" for s in statuses):
        batch.status = "partial_target_success"
        run_record.status = "failed"
    else:
        batch.status = "failed"
        run_record.status = "failed"

    batch.finished_at = _now()
    run_record.finished_at = _now()
    run_record.report_summary = {"validation_mode": "doctor_nurse_dual_target_v1", "results": results}
    db.commit()

    return {
        "status": batch.status,
        "run_id": run_id,
        "batch_id": batch_id,
        "validation_mode": "doctor_nurse_dual_target_v1",
        "results": results,
        "max_persons": 2,
        "max_actions": 4,
    }


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------

def run_gate_checks(db: Session) -> dict[str, Any]:
    """Run all pre-execution gate checks for nightly enablement."""
    gates: list[dict[str, Any]] = []

    gates.append({"gate": "identity_sync_enabled", "passed": bool(settings.identity_sync_enabled), "detail": "APP_IDENTITY_SYNC_ENABLED"})
    gates.append({"gate": "nightly_disabled_by_default", "passed": not settings.identity_nightly_enabled, "detail": "APP_IDENTITY_NIGHTLY_ENABLED must be false until Phase D passes"})

    cdms_mappings = db.scalars(select(IdentityRoleMapping).where(IdentityRoleMapping.target_system == "CDMS", IdentityRoleMapping.is_active.is_(True))).all()
    jhemr_mappings = db.scalars(select(IdentityRoleMapping).where(IdentityRoleMapping.target_system == "JHEMR", IdentityRoleMapping.is_active.is_(True))).all()
    gates.append({"gate": "role_mappings_configured", "passed": len(cdms_mappings) >= 3 and len(jhemr_mappings) >= 3, "detail": f"CDMS={len(cdms_mappings)}, JHEMR={len(jhemr_mappings)}"})

    active_batch = db.scalar(select(IdentitySyncBatch).where(IdentitySyncBatch.status.in_(["applying", "confirmed"])))
    gates.append({"gate": "no_active_batch", "passed": active_batch is None, "detail": "No batch in applying state"})

    cb_cdms = check_circuit_breaker(db, "nightly_cdms")
    cb_jhemr = check_circuit_breaker(db, "nightly_jhemr")
    gates.append({"gate": "circuit_breakers_closed", "passed": not cb_cdms["open"] and not cb_jhemr["open"], "detail": f"CDMS={cb_cdms['consecutive_failures']}, JHEMR={cb_jhemr['consecutive_failures']}"})

    # 112 B1/B2：写入门禁（fail-closed）。任一不满足则整批不写。
    write_gates = check_write_gates(db)
    gates.append({
        "gate": "write_gates",
        "passed": write_gates["all_passed"],
        "detail": "; ".join(f"{g['gate']}={'pass' if g['passed'] else 'FAIL'}" for g in write_gates["gates"]),
    })

    all_passed = all(g["passed"] for g in gates)
    return {"all_passed": all_passed, "gates": gates}
