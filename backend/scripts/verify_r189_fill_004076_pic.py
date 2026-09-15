"""R189 single-account signature picture fill for 004076.

Authorized repair: one audited insert into jhemr.users_pic from the HIS
signature source. advance_watermark_on_success=False (single-account rerun
must never move the nightly watermark).
"""

import json

from app.core.db import SessionLocal
from app.services.identity_signature_sync import sync_missing_jhemr_signatures

db = SessionLocal()
result = sync_missing_jhemr_signatures(
    run_id="R189-PIC-004076",
    db=db,
    emp_no="004076",
    advance_watermark_on_success=False,
)
db.close()
result.pop("error_classes", None)
print("FILL_RESULT=", json.dumps(result, ensure_ascii=False, default=str))
