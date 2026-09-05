# -*- coding: utf-8 -*-
"""A-2 备份：000219/003531 三表快照（stdout → 8.83 evidence 文件）。只读。"""
import json
import os

os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from app.core.config import settings
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

a = JhemrIdentityAdapter(
    credential_ref=settings.identity_sync_jhemr_credential_ref,
    hospital_no=settings.identity_sync_jhemr_hospital_no,
    jump_host=settings.his_source_jump_host,
    jump_port=settings.his_source_jump_port,
    jump_user=settings.his_source_jump_user,
    jump_key=settings.his_source_jump_key or None,
    db_host=settings.identity_sync_jhemr_host,
    db_port=settings.identity_sync_jhemr_port,
    db_name=settings.identity_sync_jhemr_dbname,
)
a._ensure_conn()
out = {"purpose": "003531 signway fix backup (align-inserted sign_way=0 rows)", "users": {}}
for u in ("000219", "003531"):
    out["users"][u] = {
        "users_subsign": [dict(r) for r in a._fetch_all(
            "select * from jhemr.users_subsign where user_id=%s and hospital_no=%s", (u, a.hospital_no))],
        "users_sublogin": [dict(r) for r in a._fetch_all(
            "select * from jhemr.users_sublogin where user_id=%s and hospital_no=%s", (u, a.hospital_no))],
        "users_control_mode": [dict(r) for r in a._fetch_all(
            "select * from jhemr.users_control_mode where user_id=%s and hospital_no=%s", (u, a.hospital_no))],
    }
print(json.dumps(out, ensure_ascii=False, default=str, indent=1))
