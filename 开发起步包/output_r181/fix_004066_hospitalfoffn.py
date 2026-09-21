# -*- coding: utf-8 -*-
"""004066 无纸化新用户页（RoleManage/User）读 T_MSS_HOSPITALFOFFN，不读 KESHID。
对照 000046 有院区科室行，004066 0 行 → 列表/编辑「所属科室」「角色」都空。
幂等插入 HOSPITALFOFFN，并把 FUSERTYPE 从 0(其他) 改为 1(医生) 对齐 000046。
"""
from __future__ import annotations

import json
import os
import uuid

os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.governance_base import GovernAuditLog
from app.services.cdms_identity_adapter import CdmsIdentityAdapter

EMP = "004066"
DEPT = "040465"
HOSPITAL = "A00001"
OPERATOR = "manual-cdms-hospitalfoffn-20260906"

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
report = {"emp": EMP, "dept": DEPT}

try:
    cur.execute("SELECT USER FROM DUAL")
    report["user"] = cur.fetchone()[0]
    cur.execute(
        "SELECT TABLE_NAME FROM ALL_TABLES "
        "WHERE TABLE_NAME = 'T_MSS_HOSPITALFOFFN' AND ROWNUM <= 5"
    )
    report["tables"] = [r[0] for r in cur.fetchall()]

    cur.execute(
        "SELECT COUNT(*) FROM CDMS.T_MSS_HOSPITALFOFFN WHERE LOGINNAME = :e",
        {"e": EMP},
    )
    report["hf_before"] = int(cur.fetchone()[0])

    free1 = "I"
    try:
        cur.execute(
            "SELECT FTYPE FROM CDMS.TOFFIM WHERE FOFFN = :d AND ROWNUM <= 1",
            {"d": DEPT},
        )
        toffim = cur.fetchone()
        if toffim and toffim[0]:
            free1 = str(toffim[0])
        report["toffim_ftype"] = free1
    except Exception as toffim_exc:
        report["toffim_error"] = str(toffim_exc)[:200]
        report["toffim_ftype"] = free1

    inserted = 0
    if report["hf_before"] == 0:
        fid = uuid.uuid4().hex.upper()
        cur.execute(
            "INSERT INTO CDMS.T_MSS_HOSPITALFOFFN "
            "(FID, LOGINNAME, HOSPITALAREASCODE, FOFFIN, ISDEFAULTFOFFIN, FREE1, FREE2, FREE3) "
            "VALUES (:fid, :login, :hosp, :dept, 1, :free1, '1', '1')",
            {"fid": fid, "login": EMP, "hosp": HOSPITAL, "dept": DEPT, "free1": free1},
        )
        inserted = cur.rowcount
        report["inserted_fid"] = fid

    cur.execute(
        "UPDATE CDMS.T_MSS_EMP_DICT SET FUSERTYPE = 1 "
        "WHERE FLOGINNAME = :e AND NVL(FUSERTYPE, -1) <> 1",
        {"e": EMP},
    )
    report["fusertype_updated"] = int(cur.rowcount)
    c._conn.commit()

    cur.execute(
        "SELECT FID, LOGINNAME, HOSPITALAREASCODE, FOFFIN, ISDEFAULTFOFFIN, FREE1, FREE2, FREE3 "
        "FROM CDMS.T_MSS_HOSPITALFOFFN WHERE LOGINNAME = :e",
        {"e": EMP},
    )
    rows = cur.fetchall()
    report["hf_after"] = [
        {
            "FID": r[0],
            "LOGINNAME": r[1],
            "HOSPITALAREASCODE": r[2],
            "FOFFIN": r[3],
            "ISDEFAULTFOFFIN": str(r[4]),
            "FREE1": r[5],
            "FREE2": r[6],
            "FREE3": r[7],
        }
        for r in rows
    ]
    cur.execute(
        "SELECT FUSERTYPE, FSYSID, FDEPT FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME = :e",
        {"e": EMP},
    )
    emp_row = cur.fetchone()
    report["emp_after"] = {
        "FUSERTYPE": str(emp_row[0]) if emp_row else None,
        "FSYSID": emp_row[1] if emp_row else None,
        "FDEPT": emp_row[2] if emp_row else None,
    }
    report["inserted"] = inserted
    report["status"] = "ok"
except Exception as exc:
    try:
        c._conn.rollback()
    except Exception:
        pass
    report["status"] = "failed"
    report["error"] = str(exc)[:500]
finally:
    try:
        cur.close()
        c.close()
    except Exception:
        pass

db = SessionLocal()
try:
    db.add(
        GovernAuditLog(
            module="identity",
            entity_type="cdms.T_MSS_HOSPITALFOFFN",
            entity_ref=EMP,
            action="manual_hospitalfoffn_insert_attempt",
            operator=OPERATOR,
            reason="004066 missing T_MSS_HOSPITALFOFFN; RoleManage/User reads this table for 角色/科室",
            before_data={"hf_before": report.get("hf_before")},
            after_data=report,
        )
    )
    db.commit()
    report["audit"] = "ok"
except Exception as audit_exc:
    db.rollback()
    report["audit"] = str(audit_exc)[:200]
finally:
    db.close()

print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
