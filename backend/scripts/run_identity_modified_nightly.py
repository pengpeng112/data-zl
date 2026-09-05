"""Run the approved HIS MODIFIEDTIME identity sync as a one-shot job."""

import json
import sys

from app.core.db import SessionLocal
from app.services.identity_sync_orchestrator import run_nightly_pipeline
from app.services.identity_signature_sync import sync_missing_jhemr_signatures
from app.services.identity_title_sync import sync_jhemr_education_titles_daily
from app.services.identity_dept_sync import sync_jhemr_user_depts_daily
from app.services.identity_login_sign_sync import sync_jhemr_login_sign_daily
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

        # Title reconciliation is an independent required subtask.  It runs
        # whenever the main account task succeeded, even if signature sync
        # had item failures; a required subtask failure is aggregated later.
        if main_status == "skipped":
            title_result = {"status": "skipped", "reason": main_result.get("reason", "lock_held"), "failed": 0, "error_classes": {}}
        elif main_status in {"failed", "misconfigured", "overdue"}:
            title_result = {"status": "skipped", "reason": "main_account_sync_not_successful", "failed": 0, "error_classes": {}}
        else:
            title_result = sync_jhemr_education_titles_daily(run_id=run_id, db=db)

        # User-dept reconciliation (multi-department sync) follows the same
        # required-subtask contract: group-only HIS changes never bump
        # SYS_EMPLOYEE.MODIFIEDTIME, so this full-scope compare is the only
        # channel that carries them to JHEMR user_dept.
        if main_status == "skipped":
            dept_result = {"status": "skipped", "reason": main_result.get("reason", "lock_held"), "failed": 0, "error_classes": {}}
        elif main_status in {"failed", "misconfigured", "overdue"}:
            dept_result = {"status": "skipped", "reason": "main_account_sync_not_successful", "failed": 0, "error_classes": {}}
        else:
            dept_result = sync_jhemr_user_depts_daily(run_id=run_id, db=db)

        # Login/sign-way fill is independent of SYS_EMPLOYEE.MODIFIEDTIME.
        # Half-accounts created by HIS daytime sync have empty subsign rows
        # and cannot log into EMR until 0/2/4 are inserted.
        if main_status == "skipped":
            login_sign_result = {"status": "skipped", "reason": main_result.get("reason", "lock_held"), "failed": 0, "error_classes": {}}
        elif main_status in {"failed", "misconfigured", "overdue"}:
            login_sign_result = {"status": "skipped", "reason": "main_account_sync_not_successful", "failed": 0, "error_classes": {}}
        else:
            login_sign_result = sync_jhemr_login_sign_daily(run_id=run_id, db=db)

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
            upsert_subtask(
                db,
                run_id=run_id,
                subtask_code="jhemr_user_dept_sync",
                target_system="JHEMR",
                status=normalize_status(dept_result.get("status")),
                planned_count=int(dept_result.get("planned_count") or 0),
                succeeded_count=int(dept_result.get("dept_rows_added") or 0) + int(dept_result.get("primary_updated") or 0),
                skipped_count=int(dept_result.get("skipped_equal") or 0) + int(dept_result.get("skipped_no_user") or 0),
                failed_count=int(dept_result.get("failed") or 0),
                error_classes=dept_result.get("error_classes") or {},
                report_summary=redacted_summary(dept_result),
            )
            upsert_subtask(
                db,
                run_id=run_id,
                subtask_code="jhemr_education_title_sync",
                target_system="JHEMR",
                status=normalize_status(title_result.get("status")),
                planned_count=int(title_result.get("planned_count") or 0),
                succeeded_count=int(title_result.get("updated") or 0),
                skipped_count=int(title_result.get("skipped_equal") or 0) + int(title_result.get("skipped_no_user") or 0),
                failed_count=int(title_result.get("failed") or 0),
                error_classes=title_result.get("error_classes") or {},
                report_summary=redacted_summary(title_result),
            )
            upsert_subtask(
                db,
                run_id=run_id,
                subtask_code="jhemr_login_sign_sync",
                target_system="JHEMR",
                status=normalize_status(login_sign_result.get("status")),
                planned_count=int(login_sign_result.get("planned_count") or 0),
                succeeded_count=(
                    int(login_sign_result.get("control_inserted") or 0)
                    + int(login_sign_result.get("sublogin_inserted") or 0)
                    + int(login_sign_result.get("subsign_inserted") or 0)
                    + int(login_sign_result.get("default_repaired") or 0)
                ),
                skipped_count=int(login_sign_result.get("skipped_equal") or 0) + int(login_sign_result.get("skipped_no_user") or 0),
                failed_count=int(login_sign_result.get("failed") or 0),
                error_classes=login_sign_result.get("error_classes") or {},
                report_summary=redacted_summary(login_sign_result),
            )
        overall = finalize_run(
            db,
            run_id=run_id,
            main_result=main_result,
            signature_result=signature_result,
            title_result=title_result,
            dept_result=dept_result,
            login_sign_result=login_sign_result,
        )
        result = stdout_summary(overall_status=overall, run_id=run_id, main=main_result, signature=signature_result, title=title_result)
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
