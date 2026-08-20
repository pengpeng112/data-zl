"""One-shot backfill: reclassify status-conflict staff with FXHIS.SYS_EMPLOYEE
authority and supplementary-sync them to JHEMR + CDMS (paperless system).

Background (2026-08-20 user decision): nightly modified-sync excludes anyone
classified status_conflict. The authoritative employment status is now
FXHIS.SYS_EMPLOYEE, so those people are reclassified by the preflight and this
script pushes the newly-eligible ones through the SAME write path as the
nightly pipeline (_process_single_candidate: idempotent, per-target
transactions, readback, audit). People outside the HIS MODIFIEDTIME increment
are included deliberately — that is the point of the backfill.

Run inside the container with the same env overrides as the nightly cron:

  docker exec -e APP_IDENTITY_SYNC_ENABLED=true \
    -e APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED=true \
    -e APP_IDENTITY_CDMS_FID_SEMANTICS_CONFIRMED=true \
    -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true \
    data-asset-api python /app/scripts/backfill_status_conflict_sync.py \
    [--dry-run] [--emp 004063] [--limit 50]

Business source databases are only written through the audited identity
adapters; no direct SQL is executed by this script.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.identity import IdentityPerson
from app.models.identity_sync import IdentityProtectedAccount, IdentitySchedulerRun
from app.services.identity_classification_preflight import run_classification_preflight
from app.services.identity_sync_audit import upsert_subtask
from app.services.identity_sync_orchestrator import (
    ELIGIBLE_CLASSIFICATIONS,
    MANAGED_SINCE,
    _as_aware,
    _get_person_depts,
    _mask_emp_no,
    _process_single_candidate,
)


def _select_backfill_candidates(db, only_emp: str | None, include_legacy: bool = False) -> list[dict]:
    """Same eligibility chain as select_nightly_candidates, minus the
    MODIFIEDTIME increment filter (deliberate backfill scope).

    include_legacy: also admit staff whose source_create_date is before the
    2026-07-20 managed cutoff — for explicitly directed persons only (the
    legacy population is otherwise unmanaged by policy)."""
    protected = {r for r in db.scalars(select(IdentityProtectedAccount.account_id)).all() if r}
    persons = db.scalars(
        select(IdentityPerson).where(
            IdentityPerson.employment_status == "active",
            IdentityPerson.classification.in_(list(ELIGIBLE_CLASSIFICATIONS)),
        ).order_by(IdentityPerson.person_code.asc())
    ).all()
    candidates = []
    for person in persons:
        emp_no = person.person_code
        if not emp_no or (only_emp and emp_no != only_emp):
            continue
        if not include_legacy and (
            not person.source_create_date
            or _as_aware(person.source_create_date) < MANAGED_SINCE
        ):
            continue
        if person.conflict_flag or emp_no in protected:
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
            "modified_time": None,
            "job_title": person.job_title,
        })
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只重分类并打印候选清单，不写目标系统")
    parser.add_argument("--emp", default=None, help="只处理指定工号（先单人验证再批量）")
    parser.add_argument("--include-legacy", action="store_true", help="包含 2026-07-20 前入职的存量人员（仅限用户点名的定向补录）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少候选人")
    args = parser.parse_args()

    db = SessionLocal()
    run_id = f"RUN-BF-{uuid.uuid4().hex[:10]}"
    try:
        stats = run_classification_preflight(db)
        db.commit()
        print("[preflight]", json.dumps(stats, ensure_ascii=False, default=str))

        candidates = _select_backfill_candidates(db, args.emp, include_legacy=args.include_legacy)
        if args.limit:
            candidates = candidates[: args.limit]
        print(f"[backfill] candidates={len(candidates)} emp={'all' if not args.emp else args.emp} dry_run={args.dry_run}")
        for c in candidates[:20]:
            print("  -", c["emp_no_masked"], c["classification"], c["primary_dept"])
        if len(candidates) > 20:
            print(f"  ... and {len(candidates) - 20} more")
        if args.dry_run:
            print("[backfill] dry-run: no target writes")
            return 0

        run_record = IdentitySchedulerRun(
            run_id=run_id,
            triggered_by="backfill_status_conflict",
            status="running",
            lock_holder=f"backfill_{run_id}",
            started_at=datetime.now(timezone.utc),
            provider_code="manual",
        )
        db.add(run_record)
        db.commit()

        success = failed = skipped = 0
        error_classes: dict[str, int] = {}
        for candidate in candidates:
            result = _process_single_candidate(db, candidate, run_id, reconcile_existing=True)
            status = result.get("status")
            if status == "success":
                success += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
                key = str(result.get("error_class") or result.get("reason") or "unknown")
                error_classes[key] = error_classes.get(key, 0) + 1
            print(f"  [{status}] {candidate['emp_no_masked']} {candidate['classification']} ->",
                  result.get("reason") or result.get("error") or "ok")

        run_record.status = "success" if failed == 0 else "failed"
        run_record.finished_at = datetime.now(timezone.utc)
        run_record.candidates_total = len(candidates)
        run_record.success_count = success
        run_record.failed_count = failed
        run_record.skipped_count = skipped
        run_record.report_summary = {"scope": "status_conflict_backfill", "emp": args.emp or "all"}
        db.commit()

        upsert_subtask(
            db,
            run_id=run_id,
            subtask_code="main_account_sync",
            target_system="CDMS,JHEMR",
            status="success" if failed == 0 else "failed",
            planned_count=len(candidates),
            succeeded_count=success,
            skipped_count=skipped,
            failed_count=failed,
            error_classes=error_classes,
            report_summary={"scope": "status_conflict_backfill", "emp": args.emp or "all"},
        )
        db.commit()
        print(f"[backfill] done: success={success} skipped={skipped} failed={failed} run_id={run_id}")
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
