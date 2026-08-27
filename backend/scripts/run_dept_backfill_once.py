# -*- coding: utf-8 -*-
"""One-off manual JHEMR user-dept backfill (mirrors 124 one-off title apply).

Runs inside the production container:
  1. refresh platform HIS collection (so group data is current);
  2. plan-only pass -> backup affected primary-change users' current values;
  3. apply via identity_dept_sync.sync_jhemr_user_depts_daily under a manual
     run id with subtask + actions audit;
  4. verify: re-run plan-only, expect no changes.

Usage:
  python /tmp/run_dept_backfill_once.py --prepare-backup /tmp/<bk>.json
  python /tmp/run_dept_backfill_once.py --apply --backup-file ... --backup-sha256 ...
  python /tmp/run_dept_backfill_once.py            # plan-only / final verify
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from app.core.db import SessionLocal  # noqa: E402
from app.services.identity_dept_sync import (  # noqa: E402
    SUBTASK_CODE,
    _adapter,
    _read_expected_platform,
    _read_target,
    build_dept_plan,
    reconcile_pending_dept_actions,
    sync_jhemr_user_depts_daily,
)
from app.services.his_identity_sync import sync_his_identity  # noqa: E402
from app.services.identity_sync_audit import upsert_subtask  # noqa: E402
from app.services.identity_sync_status import normalize_status, redacted_summary  # noqa: E402
from app.models.identity_sync import IdentitySchedulerRun  # noqa: E402
from sqlalchemy import select  # noqa: E402

class _RetryAdapter:
    """Wrap the JHEMR adapter: 177 occasionally black-holes a TCP accept
    (intermittent, server-side); a few short retries ride it out."""

    def __init__(self, factory, attempts=6, wait=2.0):
        self._factory = factory
        self._attempts = attempts
        self._wait = wait
        self._real = None

    def connect(self):
        import time as _t
        last = None
        for _ in range(self._attempts):
            real = None
            try:
                real = self._factory()
                real.connect()
                self._real = real
                return self
            except Exception as exc:  # noqa: BLE001
                last = exc
                if real is not None:
                    try:
                        real.close()
                    except Exception:
                        pass
                _t.sleep(self._wait)
        raise last

    def __getattr__(self, name):
        return getattr(self._real, name)


import app.services.identity_dept_sync as _dept_service  # noqa: E402

_real_adapter_factory = _dept_service._adapter
_dept_service._adapter = lambda: _RetryAdapter(_real_adapter_factory)
_adapter = _dept_service._adapter



def _plan(db):
    expected = _read_expected_platform(db)
    adapter = _adapter()
    adapter.connect()
    try:
        target_users, target_depts, meta = _read_target(adapter)
    finally:
        adapter.close()
    return expected, target_users, target_depts, build_dept_plan(expected, target_users, target_depts), meta


def _fingerprint_hashes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-backup")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-file")
    parser.add_argument("--backup-sha256")
    parser.add_argument("--skip-collect", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.skip_collect:
            collect_stats = sync_his_identity(db)
            print(json.dumps({"step": "collect_refresh", "stats": collect_stats}, ensure_ascii=False, default=str))
        expected, target_users, target_depts, plan, meta = _plan(db)
        print(json.dumps({
            "step": "plan",
            "managed_persons": len(expected),
            "target": meta,
            "dept_adds": len(plan["dept_adds"]),
            "primary_changes": len(plan["primary_changes"]),
            "skipped_equal": plan["skipped_equal"],
            "skipped_no_user": plan["skipped_no_user"],
        }, ensure_ascii=False))

        if args.prepare_backup:
            adapter = _adapter()
            adapter.connect()
            backup = {"created_at": datetime.now(timezone.utc).isoformat(), "primary_changes": []}
            try:
                for emp, old_primary, new_primary in plan["primary_changes"]:
                    rows = adapter._fetch_all(
                        "SELECT user_dept, default_dept_flag FROM jhemr.user_dept "
                        "WHERE user_id = %s AND hospital_no = %s",
                        (emp, adapter.hospital_no),
                    )
                    backup["primary_changes"].append({
                        "emp_no": emp,
                        "old_primary": old_primary,
                        "new_primary": new_primary,
                        "user_dept_rows": [dict(r) for r in rows],
                    })
            finally:
                adapter.close()
            payload = json.dumps(backup, ensure_ascii=False, default=str).encode("utf-8")
            with open(args.prepare_backup, "wb") as fh:
                fh.write(payload)
            print(json.dumps({
                "step": "backup_prepared",
                "backup_sha256": _fingerprint_hashes(payload),
                "primary_change_users": len(backup["primary_changes"]),
                "note": "dept_adds are INSERT-only; no old values to back up",
            }))
            return 0

        if not args.apply:
            recon = reconcile_pending_dept_actions(db, expected, target_users, target_depts)
            print(json.dumps({"step": "plan_only_done", "pending_reconcile": recon}, ensure_ascii=False))
            return 0

        if not args.backup_file or not args.backup_sha256:
            print(json.dumps({"step": "error", "reason": "backup required for apply"}))
            return 2
        with open(args.backup_file, "rb") as fh:
            digest = _fingerprint_hashes(fh.read())
        if digest != args.backup_sha256:
            print(json.dumps({"step": "error", "reason": "backup_digest_mismatch"}))
            return 2

        run_id = f"deptbackfill-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        now = datetime.now(timezone.utc)
        db.add(IdentitySchedulerRun(
            run_id=run_id, triggered_by="manual_authorized_dept_backfill",
            status="running", started_at=now,
            candidates_total=len(plan["dept_adds"]) + len(plan["primary_changes"]),
            provider_code="manual_authorized",
            report_summary={"subtask": SUBTASK_CODE, "mode": "one_off_backfill"},
        ))
        db.commit()

        result = sync_jhemr_user_depts_daily(run_id=run_id, db=db, plan_only=False)
        upsert_subtask(
            db, run_id=run_id, subtask_code=SUBTASK_CODE, target_system="JHEMR",
            status=normalize_status(result.get("status")),
            planned_count=int(result.get("planned_count") or 0),
            succeeded_count=int(result.get("dept_rows_added") or 0) + int(result.get("primary_updated") or 0),
            skipped_count=int(result.get("skipped_equal") or 0) + int(result.get("skipped_no_user") or 0),
            failed_count=int(result.get("failed") or 0),
            error_classes=result.get("error_classes") or {},
            report_summary=redacted_summary(result),
        )
        run = db.scalar(select(IdentitySchedulerRun).where(IdentitySchedulerRun.run_id == run_id))
        if run is not None:
            run.status = normalize_status(result.get("status"))
            run.finished_at = datetime.now(timezone.utc)
        db.commit()
        out = dict(result)
        out["run_id"] = run_id
        out.pop("plan", None)
        print(json.dumps(out, ensure_ascii=False, default=str))

        # final verify: plan must be empty
        _e, _tu, _td, verify_plan, _m = _plan(db)
        print(json.dumps({
            "step": "final_verify",
            "dept_adds": len(verify_plan["dept_adds"]),
            "primary_changes": len(verify_plan["primary_changes"]),
        }, ensure_ascii=False))
        return 0 if result.get("status") == "success" and not verify_plan["dept_adds"] and not verify_plan["primary_changes"] else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
