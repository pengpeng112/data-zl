"""Lock one JHEMR login after confirming HIS has disabled the employee.

Usage (container, production write authorized by operator):
    python -m scripts.disable_jhemr_account --emp-no 000151
    python -m scripts.disable_jhemr_account --emp-no 000151 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.his_identity_sync import _connector, _employee_employment_status, _value
from app.services.identity_hmac import compute_account_fingerprint
from app.services.identity_sync_audit import create_action, finish_action
from app.services.identity_sync_executor_bridge import execute_jhemr_lock


HIS_SQL = """
SELECT EMPLCODE, VALIDSTATE, ISDELETED
FROM FXHIS.SYS_EMPLOYEE
WHERE EMPLCODE = :emp_no
  AND ROWNUM <= 5
"""


def _his_status(emp_no: str) -> dict:
    his = _connector()
    try:
        rows = his.execute_readonly(HIS_SQL, params={"emp_no": emp_no}, max_rows=5)
    finally:
        his.close()
    if not rows:
        return {"found": False, "employment_status": None, "row_count": 0}
    statuses = {_employee_employment_status(row) for row in rows}
    validstates = {str(_value(row, "VALIDSTATE") or "") for row in rows}
    deleted = {str(_value(row, "ISDELETED") or "") for row in rows}
    return {
        "found": True,
        "employment_status": "inactive" if statuses == {"inactive"} else (
            "active" if statuses == {"active"} else "ambiguous"
        ),
        "row_count": len(rows),
        "validstate_values": sorted(validstates),
        "isdeleted_values": sorted(deleted),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emp-no", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    emp_no = str(args.emp_no).strip()
    if not emp_no or len(emp_no) > 32:
        print(json.dumps({"status": "failed", "error": "invalid_emp_no"}, ensure_ascii=False))
        return 2

    his = _his_status(emp_no)
    report = {"emp_no_len": len(emp_no), "his": his, "dry_run": args.dry_run}
    if not his["found"]:
        report["status"] = "failed"
        report["error"] = "his_employee_not_found"
        print(json.dumps(report, ensure_ascii=False))
        return 1
    if his["employment_status"] != "inactive":
        report["status"] = "failed"
        report["error"] = "his_not_inactive"
        print(json.dumps(report, ensure_ascii=False))
        return 1
    if args.dry_run:
        report["status"] = "dry_run"
        print(json.dumps(report, ensure_ascii=False))
        return 0

    db = SessionLocal()
    try:
        fingerprint = compute_account_fingerprint(emp_no, "JHEMR", settings.identity_hmac_key_ref)
        action = create_action(
            db,
            run_id=f"manual-jhemr-lock-{int(__import__('time').time())}",
            fingerprint=fingerprint,
            subtask_code="main_account_sync",
            action_type="account_lock",
            target_table="jhemr.users",
            emp_no=emp_no,
        )
        result = execute_jhemr_lock(emp_no)
        report["jhemr"] = {key: result.get(key) for key in ("status", "reason", "rows_affected", "account_status", "error")}
        if action is not None:
            if result.get("status") == "success":
                finish_action(db, action, status="executed", rows_affected=int(result.get("rows_affected") or 1))
            elif result.get("status") in {"skipped", "missing_target"}:
                finish_action(db, action, status="skipped", reason_code=str(result.get("reason") or result.get("status")))
            else:
                finish_action(db, action, status="failed", error_class="target_write")
        db.commit()
        report["status"] = result.get("status") or "failed"
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] in {"success", "skipped"} else 1
    except Exception as exc:
        db.rollback()
        report["status"] = "failed"
        report["error"] = type(exc).__name__
        print(json.dumps(report, ensure_ascii=False))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
