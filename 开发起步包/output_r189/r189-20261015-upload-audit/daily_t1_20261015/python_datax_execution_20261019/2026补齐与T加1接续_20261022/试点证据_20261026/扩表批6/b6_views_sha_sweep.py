"""批6 11 视图活源定义哈希全扫（只读）：ALL_VIEWS.TEXT sha256 对 ods_views_bulk（2026-10-22）。
目的：确认除 V_EMR_IN_FEE_INFO_MAIN（08 快照过期已知）外，其余 10 视图活源定义与
views_bulk 一致（冻结件 object_sha256 证据不过期）。
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b6_views_sha_sweep.py
"""
import hashlib

import oracledb

VIEWS = ["V_EMR_INFOR_TRANS_BLOOD", "V_EMR_HOS_CHANGE_MAJOR_RECORD",
         "V_EMR_ANES_RECORD_BLOOD", "V_EMR_INFOR_CRITICALLY_ILL",
         "V_EMR_HOS_POSTOPER_RECORD", "V_EMR_BOFORE_OPERA_RECORD",
         "V_EMR_ANESTHESIA_RECORD", "V_EMR_OPERA_RECORD", "V_EMR_IN_FEE_INFO_MAIN",
         "V_EMR_HOS_CONSUL_RECORD", "V_EMR_DOC_ORDER_CHECK"]

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()
for v in VIEWS:
    cur.execute(
        "SELECT TEXT FROM ALL_VIEWS WHERE OWNER='ODS' AND VIEW_NAME=:v", {"v": v})
    row = cur.fetchone()
    if row is None:
        print(f"{v}: LIVE_VIEW_MISSING")
        continue
    text = row[0]
    if hasattr(text, "read"):
        text = text.read()
    print(f"{v}: live_sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()}")
conn.close()
