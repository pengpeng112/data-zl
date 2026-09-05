# -*- coding: utf-8 -*-
"""只读排查 v2：003531 签名模式报错 + 昨夜 run。零写入，输出脱敏。"""
import json
import os
import traceback

os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.config import settings
from app.services.identity_hmac import compute_account_fingerprint

EMP = "003531"
out = {}


def seg(name):
    def deco(fn):
        try:
            out[name] = fn()
        except Exception:
            out[name] = {"error": traceback.format_exc(limit=2)[-400:]}
    return deco


db = SessionLocal()


@seg("runs")
def _runs():
    return [dict(r) for r in db.execute(text(
        "select run_id, status, circuit_breaker_triggered, "
        "coalesce(circuit_breaker_dimension,'-') as dim, candidates_total, "
        "success_count, failed_count, skipped_count, started_at "
        "from asset.asset_identity_scheduler_runs order by started_at desc limit 5"
    )).mappings().all()]


@seg("identity_tables")
def _tbls():
    return db.execute(text(
        "select table_name from information_schema.tables "
        "where table_schema='asset' and table_name like 'asset_identity%' order by 1"
    )).scalars().all()


tbls = out.get("identity_tables") or []

@seg("latest_run_subtasks")
def _subs():
    rid = (out.get("runs") or [{}])[0]["run_id"]
    for cand in ("asset_identity_sync_subtasks", "asset_identity_subtask_runs",
                 "asset_identity_sync_subtask_runs", "asset_identity_sync_task_runs"):
        if cand in tbls:
            rows = db.execute(text(
                f"select * from asset.{cand} where run_id = :r order by 1"
            ), {"r": rid}).mappings().all()
            return {"table": cand, "rows": [dict(s) for s in rows]}
    return {"note": "no subtask table matched", "tables": tbls}


@seg("emp_actions")
def _acts():
    fps = [compute_account_fingerprint(EMP, sys_, settings.identity_hmac_key_ref)
           for sys_ in ("JHEMR", "CDMS")]
    act_tbl = next((t for t in tbls if "action" in t), None)
    if not act_tbl:
        return {"note": "no action table"}
    rows = db.execute(text(
        f"select * from asset.{act_tbl} where account_fingerprint = any(:f) "
        f"order by id desc limit 25"
    ), {"f": fps}).mappings().all()
    keep = ("id", "batch_id", "target_system", "action_type", "target_table",
            "status", "emp_no_masked", "created_at", "executed_at", "result_summary")
    return [{k: dict(r).get(k) for k in keep if k in dict(r)} for r in rows]


@seg("latest_run_summary")
def _sum():
    rid = (out.get("runs") or [{}])[0].get("run_id")
    r = db.execute(text(
        "select report_summary from asset.asset_identity_scheduler_runs "
        "where run_id = :r"
    ), {"r": rid}).scalar()
    s = json.dumps(r, ensure_ascii=False, default=str) if r else "{}"
    return s[:2200]


db.close()

# JHEMR 四表
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
BAD = {"user_pwd", "user_pwd_sm", "is_sm", "identification", "phonenumber",
       "ca_no", "user_pki", "mailbox", "wechat", "expired_time_user_pki",
       "expiry_date_user_pki"}


@seg("jhemr_users")
def _u():
    a._ensure_conn()
    return [{k: str(v) for k, v in r.items() if k.lower() not in BAD}
            for r in a._fetch_all("select * from jhemr.users where user_id = %s", (EMP,))]


@seg("jhemr_control_mode")
def _cm():
    return [dict(r) for r in a._fetch_all(
        "select * from jhemr.users_control_mode where user_id = %s", (EMP,))]


@seg("jhemr_sublogin")
def _sl():
    return [dict(r) for r in a._fetch_all(
        "select * from jhemr.users_sublogin where user_id = %s", (EMP,))]


@seg("jhemr_subsign")
def _ss():
    return [dict(r) for r in a._fetch_all(
        "select * from jhemr.users_subsign where user_id = %s", (EMP,))]


@seg("jhemr_subsign_ref_004019")
def _ref():
    return [dict(r) for r in a._fetch_all(
        "select * from jhemr.users_subsign where user_id = %s", ("004019",))]


try:
    a.close()
except Exception:
    pass

print(json.dumps(out, ensure_ascii=False, default=str, indent=1))
