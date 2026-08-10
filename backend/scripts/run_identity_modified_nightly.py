"""Run the approved HIS MODIFIEDTIME identity sync as a one-shot job."""

import json
import sys

from app.core.db import SessionLocal
from app.services.identity_sync_orchestrator import run_nightly_pipeline
from app.services.identity_signature_sync import sync_missing_jhemr_signatures
from app.services.identity_sync_audit import AuditWriteError, finalize_run, upsert_subtask
from app.services.identity_sync_status import normalize_status, redacted_summary, runner_exit_code, stdout_summary


def main() -> int:
    db = SessionLocal()
    run_id = None
    try:
        main_result = run_nightly_pipeline(
            db,
            triggered_by="host_cron_modified_sync",
            refresh_source=True,
        )
        run_id = main_result.get("run_id")
        main_status = normalize_status(main_result.get("status"))
        if run_id:
            upsert_subtask(
                db,
                run_id=run_id,
                subtask_code="main_account_sync",
                target_system="CDMS,JHEMR",
                status=main_status,
                planned_count=int(main_result.get("candidates") or main_result.get("candidates_total") or 0),
                succeeded_count=int(main_result.get("success_count") or 0),
                skipped_count=int(main_result.get("skipped_count") or 0),
                failed_count=int(main_result.get("failed_count") or 0),
                error_classes=main_result.get("error_classes") or {},
                report_summary=redacted_summary(main_result),
            )

        # A held lock is skipped, never success, and never starts a second
        # target action. A failed main task also fails closed for signatures.
        if main_status == "skipped":
            signature_result = {"status": "skipped", "reason": main_result.get("reason", "lock_held"), "failed": 0, "error_classes": {}}
        elif main_status in {"failed", "misconfigured", "overdue"}:
            signature_result = {"status": "skipped", "reason": "main_account_sync_not_successful", "failed": 0, "error_classes": {}}
        else:
            signature_result = sync_missing_jhemr_signatures(run_id=run_id, db=db)

        if run_id:
            upsert_subtask(
                db,
                run_id=run_id,
                subtask_code="jhemr_signature_sync",
                target_system="JHEMR",
                status=normalize_status(signature_result.get("status")),
                planned_count=int(signature_result.get("planned_count") or 0),
                succeeded_count=int(signature_result.get("inserted") or 0),
                skipped_count=int(signature_result.get("skipped_existing") or 0) + int(signature_result.get("skipped_no_user") or 0),
                failed_count=int(signature_result.get("failed") or 0),
                error_classes=signature_result.get("error_classes") or {},
                report_summary=redacted_summary(signature_result),
            )
        overall = finalize_run(db, run_id=run_id, main_result=main_result, signature_result=signature_result)
        result = stdout_summary(overall_status=overall, run_id=run_id, main=main_result, signature=signature_result)
        print(json.dumps(result, ensure_ascii=True, default=str))
        return runner_exit_code(overall)
    except AuditWriteError as exc:
        # Never report successful work if the durable audit fact failed.
        result = {"status": "failed", "run_id": run_id, "error_classes": {"audit_write": {type(exc).__name__: 1}}}
        print(json.dumps(result, ensure_ascii=True, default=str))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
