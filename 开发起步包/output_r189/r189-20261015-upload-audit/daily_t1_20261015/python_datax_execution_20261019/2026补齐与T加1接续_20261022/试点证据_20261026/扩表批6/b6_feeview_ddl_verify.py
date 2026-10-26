"""批6 视图覆盖缺口核因（只读）：活源拉 V_EMR_IN_FEE_INFO_MAIN DDL（DBMS_METADATA）
+ USER_VIEWS.TEXT 哈希对 ods_views_bulk（2026-10-22）+ as 别名覆盖投影列核对。
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b6_feeview_ddl_verify.py
"""
import hashlib
import json
import re

import oracledb

VIEWS_BULK_SHA = {
    "V_EMR_IN_FEE_INFO_MAIN": "ec71a05caff495685536861b7f759f49bc557f01e452fe3068d3578436d36757",
}
PROJ = ["DB_PAY", "DISCHARGE_DATE_TIME", "DISTRICT_CODE", "EXCHANGE_TYPE", "GWY_PAY",
        "ID", "ID_NUM", "INUMBERD_PAY", "MZJZ_PAY", "ORG_CODE", "ORG_NAME",
        "PATIENT_ID", "PAY_MODE", "PAY_MODE_NAME", "QT_PAY", "SO_CARD", "TC_PAY",
        "TOTAL_FEE", "YB_PAY"]

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()

cur.execute(
    "SELECT DBMS_METADATA.GET_DDL('VIEW','V_EMR_IN_FEE_INFO_MAIN','ODS') FROM DUAL")
ddl = cur.fetchone()[0]
if hasattr(ddl, "read"):
    ddl = ddl.read()
print("== live DDL (DBMS_METADATA) ==")
print(ddl)

cur.execute(
    "SELECT TEXT FROM ALL_VIEWS WHERE OWNER='ODS' AND VIEW_NAME='V_EMR_IN_FEE_INFO_MAIN'")
text = cur.fetchone()[0]
if hasattr(text, "read"):
    text = text.read()
conn.close()

for label, s in (("dbms_metadata", ddl), ("all_views.text", text)):
    print(f"sha256({label}) = {hashlib.sha256(s.encode('utf-8')).hexdigest()}")
    print(f"len({label}) = {len(s)}")
print("views_bulk sha256 =", VIEWS_BULK_SHA["V_EMR_IN_FEE_INFO_MAIN"])

aliases = {a.upper() for a in re.findall(r"as\s+([A-Za-z_][A-Za-z0-9_]+)", ddl, re.IGNORECASE)}
missing = [c for c in PROJ if c not in aliases]
print("as-aliases count:", len(aliases))
print("projection missing from as-aliases:", missing if missing else "NONE")
print("DATETIME in aliases:", "DATETIME" in aliases)
print("hardcoded 2021/2025 filter present:", "2021-01-01" in ddl and "2025-01-01" in ddl)
