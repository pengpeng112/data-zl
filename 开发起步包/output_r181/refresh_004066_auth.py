# -*- coding: utf-8 -*-
"""004066：XTWH 对 AUTHMAPPING 有 INSERT/UPDATE，对 KESHID 仍无权限。
幂等确认 5 行权限在，并刷新 FDATE 便于界面核对。"""
import json
import os
os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.governance_base import GovernAuditLog
from app.services.cdms_identity_adapter import CdmsIdentityAdapter

EMP = "004066"
OPERATOR = "manual-cdms-auth-refresh-20260905"
TEMPLATE = [
    ("0", "a1c9192fbe31423fab2dce6f81791b88"),
    ("2", "040465"),
    ("3", "100005"),
    ("5", "A00001"),
    ("10", "1"),
]

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
report = {"emp": EMP}
try:
    cur.execute(
        "SELECT FTYPE, FAUTHORITYID, TO_CHAR(FDATE,'YYYY-MM-DD HH24:MI') FDATE "
        "FROM CDMS.T_MSS_AUTHMAPPING WHERE FID = :e ORDER BY FTYPE",
        {"e": EMP},
    )
    before = [{"ftype": r[0], "id": r[1], "fdate": r[2]} for r in cur.fetchall()]
    report["before"] = before
    have = {(str(r["ftype"]), str(r["id"])) for r in before}
    inserted = 0
    for ftype, auth in TEMPLATE:
        if (ftype, auth) in have:
            continue
        import uuid
        cur.execute(
            "INSERT INTO CDMS.T_MSS_AUTHMAPPING "
            "(FAUTHMAPPINGID, FID, FAUTHORITYID, FTYPE, FDATE, FUSER, FST, FPRIVIEGETYPE) "
            "VALUES (:id, :fid, :auth, :tp, SYSDATE, 'admin', '0', :tp)",
            {"id": uuid.uuid4().hex, "fid": EMP, "auth": auth, "tp": ftype},
        )
        inserted += 1
    cur.execute(
        "UPDATE CDMS.T_MSS_AUTHMAPPING SET FDATE = SYSDATE, FUPDATEUSER = 'admin' "
        "WHERE FID = :e",
        {"e": EMP},
    )
    updated = cur.rowcount
    c._conn.commit()
    cur.execute(
        "SELECT FTYPE, FAUTHORITYID, TO_CHAR(FDATE,'YYYY-MM-DD HH24:MI') FDATE "
        "FROM CDMS.T_MSS_AUTHMAPPING WHERE FID = :e ORDER BY FTYPE",
        {"e": EMP},
    )
    report["after"] = [{"ftype": r[0], "id": r[1], "fdate": r[2]} for r in cur.fetchall()]
    report["inserted"] = inserted
    report["updated"] = updated
    report["status"] = "ok"
except Exception as exc:
    c._conn.rollback()
    report["status"] = "failed"
    report["error"] = str(exc)[:400]
finally:
    cur.close()
    c.close()

db = SessionLocal()
try:
    db.add(GovernAuditLog(
        module="identity",
        entity_type="cdms.T_MSS_AUTHMAPPING",
        entity_ref=EMP,
        action="manual_auth_refresh",
        operator=OPERATOR,
        reason="user authorized AUTHMAPPING insert; KESHID still not granted to XTWH",
        before_data={"before": report.get("before")},
        after_data=report,
    ))
    db.commit()
    report["audit"] = "ok"
except Exception as exc:
    db.rollback()
    report["audit"] = str(exc)[:200]
finally:
    db.close()

print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
