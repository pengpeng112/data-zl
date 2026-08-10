"""Authorized historical/batch JHEMR signature补跑 (plan 122/125).

Usage (production container only, never print emp nos):
  APP_IDENTITY_SYNC_ENABLED=true \\
  APP_BATCH_SIGNATURE_APPLY=true \\
  APP_BATCH_SIGNATURE_CONFIRM=BATCH-SIGNATURE-HISTORY \\
  APP_BATCH_SIGNATURE_MAX_ROWS=2000 \\
  python /app/scripts/run_batch_signature_sync.py

Hard rules:
- Requires explicit apply + confirmation env
- Does not run main account nightly pipeline
- Reuses planned action audit + whitelist adapter + image normalize
- Never prints emp no, signature bytes, or credentials
- Advances signature watermark only when failed==0 and not single-emp mode
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.identity_signature_sync import sync_missing_jhemr_signatures
from app.services.identity_sync_status import redacted_summary


CONFIRM = "BATCH-SIGNATURE-HISTORY"


def main() -> int:
    apply = (os.environ.get("APP_BATCH_SIGNATURE_APPLY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    confirm = (os.environ.get("APP_BATCH_SIGNATURE_CONFIRM") or "").strip()
    max_rows_raw = (os.environ.get("APP_BATCH_SIGNATURE_MAX_ROWS") or "2000").strip()
    try:
        max_rows = max(1, min(int(max_rows_raw), 20000))
    except ValueError:
        max_rows = 2000

    run_id = f"batch-signature-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    if not apply or confirm != CONFIRM:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "run_id": run_id,
                    "error": "APP_BATCH_SIGNATURE_APPLY=true and "
                    f"APP_BATCH_SIGNATURE_CONFIRM={CONFIRM} required",
                },
                ensure_ascii=True,
            )
        )
        return 2

    if not settings.identity_sync_enabled:
        print(json.dumps({"status": "failed", "error": "identity_sync_disabled", "run_id": run_id}))
        return 1

    db = SessionLocal()
    try:
        result = sync_missing_jhemr_signatures(
            run_id=run_id,
            db=db,
            max_rows=max_rows,
            advance_watermark_on_success=True,
        )
        out = {
            "status": result.get("status"),
            "run_id": run_id,
            "max_rows": max_rows,
            "planned_count": result.get("planned_count"),
            "inserted": result.get("inserted"),
            "skipped_existing": result.get("skipped_existing"),
            "skipped_no_user": result.get("skipped_no_user"),
            "failed": result.get("failed"),
            "error_classes": result.get("error_classes") or {},
            "failed_fingerprints": result.get("failed_fingerprints") or [],
            "watermark": result.get("watermark") or {},
            "summary": redacted_summary(result),
        }
        print(json.dumps(out, ensure_ascii=True, default=str))
        failed = int(result.get("failed") or 0)
        if failed == 0 and int(result.get("inserted") or 0) >= 0:
            return 0
        if failed > 0 and int(result.get("inserted") or 0) > 0:
            return 0  # partial_success still exit 0 with status in JSON
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
