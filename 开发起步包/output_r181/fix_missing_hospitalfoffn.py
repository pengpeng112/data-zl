# -*- coding: utf-8 -*-
"""补齐「有角色 AUTHMAPPING、无 T_MSS_HOSPITALFOFFN」的无纸化用户院区科室行。
口径同 004066：FOFFIN=EMP.FDEPT，FREE1=TOFFIM.FTYPE（I/O/T/H，其他→T），默认院区=1。
XTWH 看不见 TOFFIM，FREE1 用 sjzc 预先核对的科室类别表。无 FDEPT 的跳过。
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

OPERATOR = "manual-cdms-hospitalfoffn-batch-20260906"

# sjzc live 2026-09-06：缺行用户 FDEPT × TOFFIM.FTYPE；非 I/O/T/H 的「其他」按医疗 T。
_DEPT_TYPE = {
    "010302": "T",
    "020202": "I",
    "020205H": "H",
    "020305": "I",
    "020702": "I",
    "0209": "T",
    "021117H": "H",
    "021202": "I",
    "021502": "I",
    "021729": "I",
    "021738": "I",
    "021742": "I",
    "030112": "I",
    "030115H": "H",
    "030124": "I",
    "030210": "I",
    "030233H": "H",
    "030234H": "H",
    "030310": "I",
    "030326": "I",
    "030327": "I",
    "030328H": "H",
    "030329H": "H",
    "030412H": "H",
    "030417": "I",
    "030418": "T",
    "030421": "I",
    "030422H": "H",
    "030429H": "H",
    "030439": "I",
    "030602H": "H",
    "030611": "O",
    "031006": "O",
    "040112": "I",
    "040132H": "H",
    "040205H": "H",
    "040301": "O",
    "040455": "I",
    "040460": "I",
    "040466": "I",
    "040467H": "H",
    "040513H": "H",
    "040514H": "H",
    "040704": "I",
    "0501": "T",
    "050102": "T",
    "050121": "T",
    "050202": "T",
    "0503": "O",
    "050701": "T",
}


def _free1(dept: str) -> str:
    raw = _DEPT_TYPE.get(dept, "I")
    return raw if raw in ("I", "O", "T", "H") else "T"


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
report: dict = {"operator": OPERATOR}

try:
    cur.execute(
        "SELECT e.FLOGINNAME, e.FDEPT, NVL(e.HOSPITALAREACODE, 'A00001') "
        "FROM CDMS.T_MSS_EMP_DICT e "
        "WHERE EXISTS ("
        "  SELECT 1 FROM CDMS.T_MSS_AUTHMAPPING a "
        "  WHERE a.FID = e.FLOGINNAME AND a.FTYPE = '0'"
        ") AND NOT EXISTS ("
        "  SELECT 1 FROM CDMS.T_MSS_HOSPITALFOFFN h "
        "  WHERE h.LOGINNAME = e.FLOGINNAME"
        ") AND e.FLOGINNAME <> 'admin' "
        "ORDER BY e.FLOGINNAME"
    )
    candidates = [(str(r[0]), r[1], str(r[2])) for r in cur.fetchall()]
    report["candidate_count"] = len(candidates)

    inserted: list[str] = []
    skipped: list[dict] = []
    for login, dept, hosp in candidates:
        dept_s = "" if dept is None else str(dept).strip()
        if not dept_s or dept_s == "0":
            skipped.append({"login": login, "reason": "no_fdept"})
            continue
        fid = uuid.uuid4().hex.upper()
        cur.execute(
            "INSERT INTO CDMS.T_MSS_HOSPITALFOFFN "
            "(FID, LOGINNAME, HOSPITALAREASCODE, FOFFIN, ISDEFAULTFOFFIN, FREE1, FREE2, FREE3) "
            "VALUES (:fid, :login, :hosp, :dept, 1, :free1, '1', '1')",
            {
                "fid": fid,
                "login": login,
                "hosp": hosp or "A00001",
                "dept": dept_s,
                "free1": _free1(dept_s),
            },
        )
        inserted.append(login)

    c._conn.commit()
    report["inserted_count"] = len(inserted)
    report["inserted"] = inserted
    report["skipped"] = skipped
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
            entity_ref="batch",
            action="manual_hospitalfoffn_batch_insert",
            operator=OPERATOR,
            reason="RoleManage/User empty role/dept: missing T_MSS_HOSPITALFOFFN; same gap as 004066",
            before_data={"candidate_count": report.get("candidate_count")},
            after_data={
                "status": report.get("status"),
                "inserted_count": report.get("inserted_count"),
                "inserted": report.get("inserted"),
                "skipped": report.get("skipped"),
                "error": report.get("error"),
            },
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
