# -*- coding: utf-8 -*-
"""Docare c0632940 精简探查 v2：只投影住院次对照相关列。只读。"""
import json
import traceback

from pathlib import Path

from app.services.db_connectors import OracleConnector

PID = "c0632940"
raw = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip()
user, pwd = raw.split(":", 1)
conn = OracleConnector(
    host="10.10.10.68", port=1521, database="docare",
    user=user, password=pwd, connection_mode="direct",
    oracle_client_lib_dir="/opt/oracle", timeout_ms=60000,
)


def pick(rows, keys):
    out = []
    for r in rows:
        item = {k: (str(v) if v is not None else None)
                for k, v in r.items() if k.upper() in keys}
        out.append(item)
    return out


def run(name, sql, keys):
    try:
        rows = conn.execute_readonly(sql, {"pid": PID}, max_rows=300)
        return {"count": len(rows), "rows": pick(rows, keys)}
    except Exception:
        return {"error": traceback.format_exc(limit=2)[-260:]}


out = {}
out["master"] = run(
    "master",
    "SELECT * FROM MEDSURGERY.MED_OPERATION_MASTER WHERE PATIENT_ID = :pid",
    {"PATIENT_ID", "VISIT_ID", "OPER_ID", "EMERGENCY_INDICATOR", "START_DATE_TIME",
     "END_DATE_TIME", "OPER_STATUS", "DEPT_STAYED", "IN_DATE_TIME", "OUT_DATE_TIME",
     "SCHEDULED_DATE_TIME", "REQ_DATE_TIME", "MEN_ZHEN"},
)
out["archive"] = run(
    "archive",
    "SELECT * FROM MEDSURGERY.MED_EMR_ARCHIVE_DETIAL WHERE PATIENT_ID = :pid",
    {"PATIENT_ID", "VISIT_ID", "OPER_ID", "ARCHIVE_ID", "DOCUMENT_NAME", "DOC_NAME",
     "FILE_NAME", "CREATE_DATE_TIME", "CREATED_DATE_TIME", "ARCHIVE_TIME", "STATUS"},
)
out["apply_v2"] = run(
    "apply",
    "SELECT * FROM MEDSURGERY.MED_VS_HIS_OPER_APPLY_V2 WHERE MED_PATIENT_ID = :pid",
    {"MED_PATIENT_ID", "MED_VISIT_ID", "MED_SCHEDULE_ID", "PATIENT_ID", "VISIT_ID",
     "APPLY_DATE", "SCHEDULE_ID", "OPER_ID", "OPER_NAME", "REQ_DATE_TIME",
     "APPLICATION_DATE", "CREATE_TIME", "STATUS"},
)
out["itf_sm"] = run(
    "itf",
    "SELECT * FROM MEDSURGERY.T_ITF_SM WHERE UPPER(PATIENTID) = UPPER(:pid)",
    {"PATIENTID", "FBIHID", "FBINCU", "REPORTNAME", "FUPDATE", "FREPORTSTYLE", "PDFNAME"},
)
print(json.dumps(out, ensure_ascii=False, indent=1))
