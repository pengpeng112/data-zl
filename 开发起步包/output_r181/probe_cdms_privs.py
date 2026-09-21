# -*- coding: utf-8 -*-
"""只读：当前 CDMS 连接账号能看见哪些对象、对 KESHID 有何权限。"""
import json
import os
os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")
from app.core.config import settings
from app.services.cdms_identity_adapter import CdmsIdentityAdapter

c = CdmsIdentityAdapter(
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
c.connect()
cur = c._conn.cursor()
out = {}
cur.execute("SELECT USER FROM DUAL")
out["user"] = cur.fetchone()[0]
cur.execute(
    "SELECT OWNER, TABLE_NAME FROM ALL_TABLES WHERE TABLE_NAME IN "
    "('KESHID','T_MSS_AUTHMAPPING','T_MSS_EMP_DICT') ORDER BY 1,2"
)
out["tables"] = [{"owner": r[0], "table": r[1]} for r in cur.fetchall()]
cur.execute(
    "SELECT TABLE_NAME, PRIVILEGE FROM USER_TAB_PRIVS "
    "WHERE TABLE_NAME IN ('KESHID','T_MSS_AUTHMAPPING') ORDER BY 1,2"
)
out["user_tab_privs"] = [{"table": r[0], "priv": r[1]} for r in cur.fetchall()]
cur.execute(
    "SELECT TABLE_NAME, PRIVILEGE FROM ALL_TAB_PRIVS "
    "WHERE TABLE_NAME='KESHID' AND ROWNUM<=20"
)
out["all_tab_privs_keshid"] = [{"table": r[0], "priv": r[1]} for r in cur.fetchall()]
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
cur.close()
c.close()
