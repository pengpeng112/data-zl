"""R189 post-deploy read-only verification.

1. Gate matrix under the exact cron env (disable_only + reconcile allowlist).
2. login/sign daily subtask in plan_only mode: reads platform + JHEMR, builds
   the repair plan, performs ZERO target writes.
"""

import json

from app.core.config import settings
from app.services.identity_sync_action_gate import gate_legacy_identity_write
from app.services.identity_login_sign_sync import sync_jhemr_login_sign_daily

print("run_mode=", settings.identity_run_mode)
print("allowlist=", settings.identity_disable_only_allowed_legacy_kinds)
for kind in ("login_sign_sync", "jhemr_signature_sync", "education_title_sync", "jhemr_dept_sync", "jhemr_apply", "jhemr_lock"):
    d = gate_legacy_identity_write(None, kind)
    print("gate", kind, d.allowed, d.reason)

from app.core.db import SessionLocal

db = SessionLocal()
result = sync_jhemr_login_sign_daily(run_id="R189-VERIFY-PLANONLY", db=db, plan_only=True)
db.close()
safe = {k: v for k, v in result.items()}
print("PLAN_ONLY_RESULT=", json.dumps(safe, ensure_ascii=False, default=str))
