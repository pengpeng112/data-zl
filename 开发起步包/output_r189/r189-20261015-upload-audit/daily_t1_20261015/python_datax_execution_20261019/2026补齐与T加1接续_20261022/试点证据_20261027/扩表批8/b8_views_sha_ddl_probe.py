"""批8 10 视图活源 TEXT sha256 vs ods_views_bulk（过期证据）+ V_EMR_OUT_FEE_INFO_MAIN 活源 DBMS_METADATA DDL 拉取（VISIT_DATE 核因）。
运行：ssh -F .ssh/config_ai data-asset-83 "docker exec -i data-asset-api python -" < b8_views_sha_ddl_probe.py
只读 ODS（白天例外），逐视图限量+60s 超时。
"""
import hashlib
import json

import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()

TABLES = ["EMR_ANES_RECORD_MED","EMR_ADMISSION_RECORD_EXAM","EMR_CONSUMABLES","EMR_OUTPATIENT_DIAG","EMR_DOC_ORDER_DRUG","EMR_OUT_FEE_INFO_MAIN","EMR_OUT_FEE_INFO_CHILD","EMR_IN_FEE_INFO_CHILD","EMR_INFOR_OPERATION","EMR_INFOR_OTHERS"]
print("== 10 视图 ALL_VIEWS.TEXT sha256 vs ods_views_bulk(2026-10-22) ==")
for t in TABLES:
    v = "V_" + t
    cur.execute("SELECT TEXT FROM ALL_VIEWS WHERE OWNER='ODS' AND VIEW_NAME=:v", {"v": v})
    row = cur.fetchone()
    sha = hashlib.sha256(row[0].encode("utf-8")).hexdigest() if row and row[0] else None
    print(f"{v}: live_sha={sha}")

print()
print("== V_EMR_OUT_FEE_INFO_MAIN 活源 DBMS_METADATA DDL（VISIT_DATE 核因）==")
cur.execute(
    "SELECT DBMS_METADATA.GET_DDL('VIEW','V_EMR_OUT_FEE_INFO_MAIN','ODS') FROM DUAL")
ddl = cur.fetchone()[0].read()
print("live ddl length:", len(ddl))
import re
m = re.match(r'\s*CREATE.*?VIEW\s+"?ODS"?\.?"?\w+"?\s*\((.*?)\)\s*AS', ddl, re.S | re.I)
if m:
    header_cols = re.findall(r'"([^"]+)"', m.group(1))
    print("live header cols:", len(header_cols))
    print("VISIT_DATE in live header:", "VISIT_DATE" in header_cols)
for mm in list(re.finditer(re.escape("VISIT_DATE"), ddl, re.I))[:6]:
    ctx = ddl[max(0, mm.start()-80):mm.end()+50].replace("\n", " ")
    print("ctx: ...", ctx, "...")
open("/tmp/b8_out_fee_main_live_ddl.sql", "w", encoding="utf-8").write(ddl)
print("ddl saved to /tmp/b8_out_fee_main_live_ddl.sql (container side)")
conn.close()
