# -*- coding: utf-8 -*-
"""003531：登录方式含 0，签名方式只有 2/4/8。对照正常户 003534（0/2/4 对齐）。
最小修复：补 sign_way=0 且 default_flag=0（默认仍为 4），并把 control_mode.in_sign_way
扩成 0,2,4,8。不删 8、不改默认。授权：用户 2026-09-05「还不行，与 003534 比对并继续处理」。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

os_env_set = True
import os
os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.config import settings
from app.models.governance_base import GovernAuditLog
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

EMP = "003531"
HOSP = None
OPERATOR = "manual-signway-add0-20260905"


def brief_ss(rows):
    return [
        {
            "sign_way": str(r["sign_way"]),
            "fvt": str(r.get("file_visit_type")),
            "default": str(r.get("default_flag")),
            "picmode": str(r.get("picmode")),
        }
        for r in rows
    ]


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
conn = a._ensure_conn()
HOSP = a.hospital_no
report = {"emp": EMP}

try:
    conn.rollback()
    ss = a._fetch_all(
        "SELECT * FROM jhemr.users_subsign WHERE user_id=%s AND hospital_no=%s",
        (EMP, HOSP),
    )
    cm = a._fetch_all(
        "SELECT * FROM jhemr.users_control_mode WHERE user_id=%s AND hospital_no=%s",
        (EMP, HOSP),
    )
    sl = a._fetch_all(
        "SELECT login_way FROM jhemr.users_sublogin WHERE user_id=%s AND hospital_no=%s",
        (EMP, HOSP),
    )
    report["before_subsign"] = brief_ss(ss)
    report["before_cm"] = {
        "in_sign_way": None if not cm else str(cm[0].get("in_sign_way")),
        "login_way": None if not cm else str(cm[0].get("login_way")),
        "in_pic_mode": None if not cm else str(cm[0].get("in_pic_mode")),
    }
    ways = {str(r["sign_way"]) for r in ss}
    defaults = [str(r["sign_way"]) for r in ss if str(r.get("default_flag")) == "1"]
    login_ways = {str(r["login_way"]) for r in sl}
    assert "2" in ways and "4" in ways and "8" in ways, ways
    assert defaults == ["4"], defaults
    assert "0" in login_ways, login_ways

    if "0" in ways:
        report["status"] = "skip_already_has_0"
    else:
        n = a._execute_write(
            "INSERT INTO jhemr.users_subsign "
            "(user_id, hospital_no, file_visit_type, sign_way, picmode, default_flag, last_modify_time) "
            "VALUES (%s, %s, '2', '0', '2', '0', CURRENT_TIMESTAMP)",
            (EMP, HOSP),
        )
        assert n == 1, n
        n2 = a._execute_write(
            "UPDATE jhemr.users_control_mode "
            "SET in_sign_way=%s, in_pic_mode=%s, last_modify_date=CURRENT_TIMESTAMP, "
            "last_modify_user_id=%s "
            "WHERE user_id=%s AND hospital_no=%s",
            ("0,2,4,8", "2,2,2,2", "IDENTITY_SYNC", EMP, HOSP),
        )
        assert n2 == 1, n2
        conn.commit()
        report["status"] = "ok"

    after_ss = a._fetch_all(
        "SELECT * FROM jhemr.users_subsign WHERE user_id=%s AND hospital_no=%s",
        (EMP, HOSP),
    )
    after_cm = a._fetch_all(
        "SELECT in_sign_way, login_way, in_pic_mode FROM jhemr.users_control_mode "
        "WHERE user_id=%s AND hospital_no=%s",
        (EMP, HOSP),
    )
    report["after_subsign"] = brief_ss(after_ss)
    report["after_cm"] = {
        "in_sign_way": str(after_cm[0]["in_sign_way"]) if after_cm else None,
        "login_way": str(after_cm[0]["login_way"]) if after_cm else None,
        "in_pic_mode": str(after_cm[0]["in_pic_mode"]) if after_cm else None,
    }
    after_ways = {str(r["sign_way"]) for r in after_ss}
    after_def = [str(r["sign_way"]) for r in after_ss if str(r.get("default_flag")) == "1"]
    assert after_ways == {"0", "2", "4", "8"}, after_ways
    assert after_def == ["4"], after_def
except Exception as exc:
    conn.rollback()
    report["status"] = "failed"
    report["error"] = str(exc)
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    raise
finally:
    try:
        a.close()
    except Exception:
        pass

db = SessionLocal()
try:
    db.add(
        GovernAuditLog(
            module="identity",
            entity_type="jhemr.users_subsign",
            entity_ref=EMP,
            action="manual_repair_add_signway0_keep_248",
            before_data=report.get("before_subsign"),
            after_data=report.get("after_subsign"),
            operator=OPERATOR,
            reason="003531 still cannot sign vs 003534; login_way has 0 but subsign had 2/4/8 only",
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
