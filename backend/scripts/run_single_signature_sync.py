"""Authorized single-account JHEMR signature补跑 (plan 125 H6).

Usage (production container, emp from env only):
  APP_SINGLE_SIGNATURE_EMP_NO=<emp> \\
  APP_IDENTITY_SYNC_ENABLED=true \\
  python /app/scripts/run_single_signature_sync.py

Hard rules:
- Only one emp from APP_SINGLE_SIGNATURE_EMP_NO
- Does not run main account nightly pipeline
- Does not advance signature watermark
- Reuses planned action audit + whitelist adapter
- Never prints emp no, signature bytes, or credentials
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.core.config import settings
from app.services.identity_hmac import compute_account_fingerprint
from app.services.identity_signature_sync import sync_missing_jhemr_signatures
from app.services.identity_sync_status import redacted_summary, short_fingerprint


def main() -> int:
    emp = (os.environ.get("APP_SINGLE_SIGNATURE_EMP_NO") or "").strip()
    if not emp:
        print(json.dumps({"status": "failed", "error": "APP_SINGLE_SIGNATURE_EMP_NO required"}))
        return 2
    # Never echo emp back.
    apply = (os.environ.get("APP_SINGLE_SIGNATURE_APPLY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    run_id = f"single-signature-125-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    fp_short = None
    try:
        fp_short = short_fingerprint(
            compute_account_fingerprint(emp, "JHEMR", settings.identity_hmac_key_ref)
        )
    except Exception:
        fp_short = "hmac-unavailable"

    if not apply:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "run_id": run_id,
                    "fingerprint_short": fp_short,
                    "error": "APP_SINGLE_SIGNATURE_APPLY=true required for write",
                },
                ensure_ascii=True,
            )
        )
        return 2

    if not settings.identity_sync_enabled:
        print(json.dumps({"status": "failed", "error": "identity_sync_disabled", "fingerprint_short": fp_short}))
        return 1

    db = SessionLocal()
    try:
        result = sync_missing_jhemr_signatures(
            run_id=run_id,
            db=db,
            emp_no=emp,
            max_rows=1,
            advance_watermark_on_success=False,
        )
        out = {
            "status": result.get("status"),
            "run_id": run_id,
            "fingerprint_short": fp_short,
            "planned_count": result.get("planned_count"),
            "inserted": result.get("inserted"),
            "skipped_existing": result.get("skipped_existing"),
            "skipped_no_user": result.get("skipped_no_user"),
            "failed": result.get("failed"),
            "error_classes": result.get("error_classes") or {},
            "summary": redacted_summary(result),
        }
        print(json.dumps(out, ensure_ascii=True, default=str))
        if int(result.get("inserted") or 0) == 1 and int(result.get("failed") or 0) == 0:
            return 0
        if int(result.get("skipped_existing") or 0) == 1:
            return 0
        return 1
    finally:
        db.close()
        # Best-effort scrub of process environment copy of emp.
        os.environ.pop("APP_SINGLE_SIGNATURE_EMP_NO", None)


if __name__ == "__main__":
    raise SystemExit(main())
