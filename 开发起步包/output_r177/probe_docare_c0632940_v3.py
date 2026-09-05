# -*- coding: utf-8 -*-
"""Docare c0632940 探查 v3：HIS 真实住院史 + archive/apply 视图换 owner。只读。"""
import json
import traceback

from pathlib import Path

from app.services.db_connectors import OracleConnector

PID = "c0632940"
CRED = Path("/etc/data-asset/credentials")


def conn_file(fname, host, service):
    raw = (CRED / fname).read_text(encoding="utf-8").strip()
    user, pwd = raw.split(":", 1)
    return OracleConnector(
        host=host, port=1521, database=service,
        user=user, password=pwd, connection_mode="direct",
        oracle_client_lib_dir="/opt/oracle", timeout_ms=60000,
    )


def pick(rows, keys):
    return [{k: (str(v) if v is not None else None)
             for k, v in r.items() if k.upper() in keys} for r in rows]


def run(conn, sql, keys, max_rows=300):
    try:
        rows = conn.execute_readonly(sql, {"pid": PID}, max_rows=max_rows)
        return {"count": len(rows), "rows": pick(rows, keys)}
    except Exception:
        return {"error": traceback.format_exc(limit=2)[-240:]}


out = {}

# 1) ODS(DATA_CENTER 8.216) HIS 侧 PAT_VISIT 真实住院史
ods = conn_file("ods_8_216", "10.10.8.216", "orcl")
out["his_pat_visit"] = run(
    ods,
    "SELECT * FROM HIS.PAT_VISIT WHERE PATIENT_ID = :pid",
    {"PATIENT_ID", "VISIT_ID", "ADMISSION_DATE_TIME", "DISCHARGE_DATE_TIME",
     "DEPT_ADMISSION", "DEPT_DISCHARGE", "INP_NO", "PATIENT_ID_SOURCE"},
)

# 2) Docare 两个对象换 owner 尝试
dc = conn_file("docare_oracle_10_10_10_68.readonly", "10.10.10.68", "docare")
for owner in ("MEDCOMM", "MEDICU"):
    out[f"archive_{owner}"] = run(
        dc, f"SELECT * FROM {owner}.MED_EMR_ARCHIVE_DETIAL WHERE PATIENT_ID = :pid",
        {"PATIENT_ID", "VISIT_ID", "OPER_ID", "DOCUMENT_NAME", "FILE_NAME",
         "CREATE_DATE_TIME", "ARCHIVE_TIME", "STATUS"},
    )
    out[f"apply_{owner}"] = run(
        dc, f"SELECT * FROM {owner}.MED_VS_HIS_OPER_APPLY_V2 WHERE MED_PATIENT_ID = :pid",
        {"MED_PATIENT_ID", "MED_VISIT_ID", "MED_SCHEDULE_ID", "VISIT_ID",
         "SCHEDULE_ID", "OPER_NAME", "APPLY_DATE", "STATUS"},
    )

print(json.dumps(out, ensure_ascii=False, indent=1))
