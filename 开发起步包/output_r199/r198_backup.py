# -*- coding: utf-8 -*-
"""r198 pre-apply backup: full CDMS user+auth rows and JHEMR state for
004076/001491, printed as JSON (captured to 8.83 evidence dir by the caller)."""
import json

from app.core.config import settings
from app.services.cdms_identity_adapter import CdmsIdentityAdapter
from app.services.identity_sync_action_gate import read_target_account_state

adapter = CdmsIdentityAdapter(
    credential_ref=settings.identity_sync_cdms_credential_ref,
    cdms_host=settings.identity_sync_cdms_host,
    cdms_port=settings.identity_sync_cdms_port,
    cdms_service=settings.identity_sync_cdms_service,
    jump_host=settings.his_source_jump_host,
    jump_port=settings.his_source_jump_port,
    jump_user=settings.his_source_jump_user,
    jump_key=settings.his_source_jump_key or None,
    oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
)
out = {"captured_at": "pre-apply", "people": {}}
adapter.connect()
try:
    for emp in ("004076", "001491"):
        out["people"][emp] = {
            "cdms_user": adapter.snapshot_user(emp),
            "cdms_auth": adapter.snapshot_auth(emp),
            "jhemr_state": read_target_account_state("JHEMR", emp),
        }
finally:
    adapter.close()
print(json.dumps(out, ensure_ascii=False, default=str))
