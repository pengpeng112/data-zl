# -*- coding: utf-8 -*-
"""182-c0632940 修订 Step1：受影响行全量备份（只读 SELECT → stdout JSON）。
覆盖 16 张基表 × (PATIENT_ID, VISIT_ID='1', OPER_ID IN ('2','4'))；archive 用 ARCHIVE_KEY。"""
import json

from pathlib import Path

from app.services.db_connectors import OracleConnector

PID = "c0632940"
OPER_TABLES = [
    "MEDSURGERY.MED_ANESTHESIA_EVENT", "MEDSURGERY.MED_ANESTHESIA_EVENT_BACK",
    "MEDSURGERY.MED_ANESTHESIA_INPUT_DATA", "MEDSURGERY.MED_ANESTHESIA_PLAN",
    "MEDSURGERY.MED_ANESTHESIA_SUMMARY", "MEDSURGERY.MED_ANES_DOC_CHECK",
    "MEDSURGERY.MED_ANES_OPERHANDOVER", "MEDSURGERY.MED_APPLICATION_AUDIT_TRAIL",
    "MEDSURGERY.MED_CUSTOM_DATA", "MEDSURGERY.MED_HBCA_SIGNATURE",
    "MEDSURGERY.MED_OPERATION_ANALGESIC", "MEDSURGERY.MED_OPERATION_MASTER",
    "MEDSURGERY.MED_PATIENT_MONITOR_DATA", "MEDSURGERY.MED_PAT_MONITOR_DATA",
    "MEDSURGERY.MED_QIXIE_QINGDIAN",
]
ARCHIVE = "MEDCOMM.MED_EMR_ARCHIVE_DETIAL"

raw = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip()
user, pwd = raw.split(":", 1)
conn = OracleConnector(host="10.10.10.68", port=1521, database="docare",
                       user=user, password=pwd, connection_mode="direct",
                       oracle_client_lib_dir="/opt/oracle", timeout_ms=120000)


def norm(v):
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.hex()[:2000]
    if isinstance(v, memoryview):
        return v.tobytes().hex()[:2000]
    t = type(v).__name__
    if t == "LOB":
        try:
            data = v.read()
            return data.hex()[:2000] if isinstance(data, (bytes, memoryview)) else str(data)[:8000]
        except Exception:
            return "<LOB>"
    return str(v)[:8000]


def dump(fq, where, params):
    rows = conn.execute_readonly(f"SELECT * FROM {fq} WHERE {where}", params, max_rows=5000)
    return [[{k: norm(v) for k, v in r.items()}] for r in rows]


out = {"purpose": "c0632940 visit-id revision backup (1->2 oper2, 1->3 oper4)", "tables": {}}
for fq in OPER_TABLES:
    rows = conn.execute_readonly(
        f"SELECT * FROM {fq} WHERE PATIENT_ID=:p AND VISIT_ID='1' AND OPER_ID IN ('2','4')",
        {"p": PID}, max_rows=5000)
    out["tables"][fq] = [{k: norm(v) for k, v in r.items()} for r in rows]
rows = conn.execute_readonly(
    f"SELECT * FROM {ARCHIVE} WHERE PATIENT_ID=:p AND VISIT_ID='1' AND MR_CLASS='麻醉' AND ARCHIVE_KEY IN ('2','4')",
    {"p": PID}, max_rows=5000)
out["tables"][ARCHIVE] = [{k: norm(v) for k, v in r.items()} for r in rows]

out["counts"] = {k: len(v) for k, v in out["tables"].items()}
out["total"] = sum(out["counts"].values())
print(json.dumps(out, ensure_ascii=False))
