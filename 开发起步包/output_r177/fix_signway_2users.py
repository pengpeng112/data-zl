# -*- coding: utf-8 -*-
"""A-3 受控修复：删除 000219/003531 两行 align 后补的 sign_way=0（恢复人工 2/4/8 配置）。
每户独立事务：重验判据 → DELETE（精确时间戳）→ rowcount==1 → 回读比对 → commit。
失败整户 rollback。平台审计每户一行。授权：用户 2026-09-05「方案A和方案C都执行下」。
"""
import json
import os
from datetime import datetime

os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.config import settings
from app.models.governance_base import GovernAuditLog
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

USERS = ("000219", "003531")
OPERATOR = "manual-signway-fix-20260905"


def _pt(s):
    s = str(s)
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def _night(d):
    return d and ((d.hour == 1 and d.minute >= 55) or (d.hour == 2 and d.minute <= 35))


def _brief(rows):
    return [{"sign_way": str(r["sign_way"]), "fvt": str(r.get("file_visit_type")),
             "default": str(r.get("default_flag")), "t": str(r["last_modify_time"])} for r in rows]


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
report = []
audit_rows = []
for u in USERS:
    item = {"user": u}
    try:
        before = a._fetch_all(
            "select * from jhemr.users_subsign where user_id=%s and hospital_no=%s",
            (u, a.hospital_no))
        zeros = [r for r in before if str(r["sign_way"]) == "0"]
        others = [r for r in before if str(r["sign_way"]) != "0"]
        assert others, "no other sign ways; abort"
        other_max = max(_pt(r["last_modify_time"]) for r in others)
        tgt = [z for z in zeros
               if _night(_pt(z["last_modify_time"])) and _pt(z["last_modify_time"]) > other_max]
        assert len(tgt) == 1 and len(zeros) == 1, f"target not unique: zeros={len(zeros)} tgt={len(tgt)}"
        expected_ways = sorted(str(r["sign_way"]) for r in others)

        n = a._execute_write(
            "DELETE FROM jhemr.users_subsign "
            "WHERE user_id=%s AND hospital_no=%s AND sign_way='0' "
            "AND file_visit_type=%s AND last_modify_time=%s",
            (u, a.hospital_no, str(tgt[0]["file_visit_type"]), tgt[0]["last_modify_time"]),
        )
        assert n == 1, f"delete affected {n} rows; expected 1"

        after = a._fetch_all(
            "select * from jhemr.users_subsign where user_id=%s and hospital_no=%s",
            (u, a.hospital_no))
        after_ways = sorted(str(r["sign_way"]) for r in after)
        assert after_ways == expected_ways, f"readback ways {after_ways} != {expected_ways}"
        defaults = [str(r["default_flag"]) for r in after].count("1")
        assert defaults <= 1, f"still {defaults} default rows"

        conn.commit()
        item.update({"status": "fixed", "removed": _brief(tgt),
                     "after_ways": after_ways, "after_defaults": defaults})
        audit_rows.append({
            "user": u, "before": _brief(before), "after": _brief(after),
        })
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        item.update({"status": "ROLLED_BACK", "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    report.append(item)

# 平台审计（独立于 JHEMR 事务）
if audit_rows:
    db = SessionLocal()
    try:
        for r in audit_rows:
            db.add(GovernAuditLog(
                module="identity",
                entity_type="jhemr.users_subsign",
                entity_ref=r["user"],
                action="manual_repair_remove_align_inserted_signway0",
                operator=OPERATOR,
                reason="夜间主同步 align_existing_user 按模板补插 sign_way=0(default=1)，"
                       "破坏 2025-06-10 人工 2/4/8 配置致 EMR 报「必须设置两种以上的签名模式」；"
                       "删除该行恢复原状。备份 evidence/signway-fix-20260905/backup_before_delete.json",
                before_data={"subsign": r["before"]},
                after_data={"subsign": r["after"]},
            ))
        db.commit()
    finally:
        db.close()

print(json.dumps({"operator": OPERATOR, "report": report,
                  "audit_rows_written": len(audit_rows)}, ensure_ascii=False, default=str, indent=1))
