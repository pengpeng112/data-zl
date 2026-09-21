# -*- coding: utf-8 -*-
"""只读比对：003531 vs 003534（JHEMR）+ 004066 vs 000046（CDMS）。零写入。"""
from __future__ import annotations

import json
import os
import traceback

os.environ.setdefault("APP_IDENTITY_SYNC_DIRECT_CONNECTION", "true")

from app.core.config import settings
from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
from app.services.cdms_identity_adapter import CdmsIdentityAdapter

out: dict = {}
BAD = {
    "user_pwd", "user_pwd_sm", "is_sm", "identification", "phonenumber",
    "ca_no", "user_pki", "mailbox", "wechat", "expired_time_user_pki",
    "expiry_date_user_pki", "user_name", "username", "fusername", "fpwd",
}


def clean(row):
    if row is None:
        return None
    d = dict(row)
    return {str(k).lower(): (None if v is None else str(v)) for k, v in d.items() if str(k).lower() not in BAD}


def rows(rs):
    return [clean(r) for r in rs]


def seg(name):
    def deco(fn):
        try:
            out[name] = fn()
        except Exception:
            out[name] = {"error": traceback.format_exc(limit=4)[-1200:]}
        return fn
    return deco


SIGN_PAIR = ("003531", "003534")
CDMS_PAIR = ("004066", "000046")

j = JhemrIdentityAdapter(
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
j._ensure_conn()
try:
    j._conn.rollback()
except Exception:
    pass


def jf(sql, params):
    try:
        return j._fetch_all(sql, params)
    except Exception:
        try:
            j._conn.rollback()
        except Exception:
            pass
        raise


@seg("jhemr")
def _jhemr():
    result = {}
    for emp in SIGN_PAIR:
        block = {"emp": emp}
        u = rows(jf("SELECT * FROM jhemr.users WHERE user_id = %s", (emp,)))
        if u:
            keep = (
                "user_id", "user_type", "user_dept", "create_date", "stop_indicator",
                "hospital_no", "education_title", "user_state", "login_id",
            )
            block["users"] = [{k: r.get(k) for k in keep if k in r} for r in u]
        else:
            block["users"] = []
        block["control_mode"] = rows(jf(
            "SELECT * FROM jhemr.users_control_mode WHERE user_id = %s", (emp,)))
        block["sublogin"] = rows(jf(
            "SELECT * FROM jhemr.users_sublogin WHERE user_id = %s", (emp,)))
        block["subsign"] = rows(jf(
            "SELECT * FROM jhemr.users_subsign WHERE user_id = %s", (emp,)))
        try:
            block["pic"] = [dict(r) for r in jf(
                "SELECT user_id, CASE WHEN user_name_pic IS NULL THEN 0 ELSE 1 END AS has_pic, "
                "COALESCE(octet_length(user_name_pic),0) AS pic_bytes, "
                "extension_file_name, use_flag "
                "FROM jhemr.users_pic WHERE user_id = %s", (emp,))]
        except Exception as exc:
            block["pic"] = {"error": str(exc)[:200]}
        block["role_group"] = rows(jf(
            "SELECT user_id, role_group_id, hospital_no FROM jhemr.jhauth_user_vs_role_group "
            "WHERE user_id = %s", (emp,)))
        try:
            block["user_dept"] = rows(jf(
                "SELECT user_id, dept_code, default_flag FROM jhemr.user_dept "
                "WHERE user_id = %s ORDER BY default_flag DESC, dept_code", (emp,)))
        except Exception as exc:
            block["user_dept"] = {"error": str(exc)[:200]}
        result[emp] = block

    def pack(emp):
        ss = result[emp].get("subsign") or []
        sl = result[emp].get("sublogin") or []
        cm = (result[emp].get("control_mode") or [{}])[0] or {}
        pic = result[emp].get("pic") or []
        return {
            "sign_ways": sorted({r.get("sign_way") for r in ss if isinstance(r, dict)}),
            "defaults": [r.get("sign_way") for r in ss if isinstance(r, dict) and str(r.get("default_flag")) == "1"],
            "picmode": [(r.get("sign_way"), r.get("picmode")) for r in ss if isinstance(r, dict)],
            "login_ways": sorted({r.get("login_way") for r in sl if isinstance(r, dict)}),
            "in_sign_way": cm.get("in_sign_way"),
            "in_login_way": cm.get("in_login_way"),
            "cm_modifier": cm.get("last_modify_user_id"),
            "has_pic": pic[0].get("has_pic") if isinstance(pic, list) and pic else pic,
            "pic_bytes": pic[0].get("pic_bytes") if isinstance(pic, list) and pic else None,
            "role_group": result[emp].get("role_group"),
            "user_type": (result[emp].get("users") or [{}])[0].get("user_type") if result[emp].get("users") else None,
        }

    result["summary"] = {SIGN_PAIR[0]: pack(SIGN_PAIR[0]), SIGN_PAIR[1]: pack(SIGN_PAIR[1])}
    return result


try:
    j.close()
except Exception:
    pass


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


def csql(sql, binds=None):
    cur = c._conn.cursor()
    try:
        cur.execute(sql, binds or {})
        cols = [d[0] for d in cur.description] if cur.description else []
        fetched = cur.fetchall()
        data = []
        for r in fetched:
            d = dict(zip(cols, r))
            data.append(clean(d))
        return data
    finally:
        cur.close()


@seg("cdms")
def _cdms():
    result = {}
    for emp in CDMS_PAIR:
        emp_rows = csql(
            "SELECT FLOGINNAME, FDEPT, FSYSID, FUSERTYPE, FUSERSTATE, FFREE3, "
            "HOSPITALAREACODE, LOGINERRORCOUNT, "
            "TO_CHAR(LASTLOGINDATE,'YYYY-MM-DD HH24:MI') AS LASTLOGINDATE, "
            "LENGTH(FPWD) AS FPWD_LEN "
            "FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME = :e",
            {"e": emp},
        )
        auth = csql(
            "SELECT FID, FTYPE, FAUTHORITYID, FST, FUSER, FPRIVIEGETYPE, "
            "TO_CHAR(FDATE,'YYYY-MM-DD HH24:MI') AS FDATE "
            "FROM CDMS.T_MSS_AUTHMAPPING WHERE FID = :e ORDER BY FTYPE, FAUTHORITYID",
            {"e": emp},
        )
        fdept = (emp_rows[0] or {}).get("fdept") if emp_rows else None
        keshid = None
        try:
            keshid = csql(
                "SELECT AAA, BBB FROM CDMS.KESHID WHERE AAA = :c AND ROWNUM <= 3",
                {"c": fdept},
            )
        except Exception as exc:
            keshid = {"error": str(exc)[:180]}
        result[emp] = {
            "emp": emp_rows,
            "auth": auth,
            "auth_ftypes": sorted({r.get("ftype") for r in auth if r}),
            "role_rows": [r for r in auth if r and str(r.get("ftype")) == "0"],
            "dept_rows": [r for r in auth if r and str(r.get("ftype")) == "2"],
            "keshid_for_fdept": keshid,
        }
    # role GUID existence
    guids = set()
    for emp in CDMS_PAIR:
        for r in result[emp]["role_rows"]:
            if r.get("fauthorityid"):
                guids.add(r["fauthorityid"])
    role_names = {}
    for g in guids:
        try:
            role_names[g] = csql(
                "SELECT FROLEID, FROLENAME FROM CDMS.T_MSS_ROLE WHERE FROLEID = :g AND ROWNUM <= 1",
                {"g": g},
            )
        except Exception as exc:
            role_names[g] = {"error": str(exc)[:180]}
    result["role_dict"] = role_names
    return result


try:
    c.close()
except Exception:
    pass

print(json.dumps(out, ensure_ascii=False, default=str, indent=1))
