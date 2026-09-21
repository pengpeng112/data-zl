# -*- coding: utf-8 -*-
"""004066 科室码 040465 不在 CDMS.KESHID（对照正常户 000046 的 030701 在字典内）。
尝试 INSERT 科室字典。XTWH 可能无 KESHID 权限（ORA-00942）——失败则如实停止。
授权：用户 2026-09-05 反馈角色和科室都未授权成功，要求与 000046 比对并处理。
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.governance_base import GovernAuditLog
from app.services.cdms_identity_adapter import CdmsIdentityAdapter

CODE = "040465"
NAME = "创伤骨科(手足一组)"
OPERATOR = "manual-cdms-keshid-040465-20260905"

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
report = {"code": CODE, "name": NAME}

cur = c._conn.cursor()
try:
    try:
        cur.execute("SELECT AAA, BBB FROM CDMS.KESHID WHERE AAA = :c AND ROWNUM <= 1", {"c": CODE})
        existing = cur.fetchall()
        report["select_ok"] = True
        report["existing"] = [{"AAA": r[0], "BBB": r[1]} for r in existing]
    except Exception as exc:
        report["select_ok"] = False
        report["select_error"] = str(exc)[:300]
        existing = None

    if existing:
        report["status"] = "skip_exists"
    elif report.get("select_ok"):
        cur.execute(
            "INSERT INTO CDMS.KESHID (AAA, BBB, DDD, EEE, FFF, GGG) "
            "VALUES (:a, :b, :d, :e, :f, :g)",
            {"a": CODE, "b": NAME, "d": "0", "e": "1", "f": "1", "g": "CSGKSZYZ"},
        )
        c._conn.commit()
        cur.execute(
            "SELECT AAA, BBB, DDD, EEE, FFF, GGG FROM CDMS.KESHID WHERE AAA = :c",
            {"c": CODE},
        )
        row = cur.fetchone()
        report["status"] = "inserted"
        report["after"] = {
            "AAA": row[0], "BBB": row[1], "DDD": row[2],
            "EEE": row[3], "FFF": row[4], "GGG": row[5],
        }
    else:
        report["status"] = "blocked_no_keshid_privilege"
        try:
            c._conn.rollback()
        except Exception:
            pass
except Exception as exc:
    try:
        c._conn.rollback()
    except Exception:
        pass
    report["status"] = "failed"
    report["error"] = str(exc)[:400]
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
            entity_type="cdms.KESHID",
            entity_ref=CODE,
            action="manual_keshid_insert_attempt",
            operator=OPERATOR,
            reason="004066 FTYPE=2/FDEPT=040465 not in KESHID; 000046 030701 is in dict",
            before_data={"exists": bool(report.get("existing"))},
            after_data=report,
        )
    )
    db.commit()
    report["audit"] = "ok"
except Exception as exc:
    db.rollback()
    report["audit"] = str(exc)[:200]
finally:
    db.close()

print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
