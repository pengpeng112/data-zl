"""表3 CONSUMABLES 隔离核因（只读）：15 个 NOT NULL 列在 2026-10-26 窗内逐列 NULL 计数 + 至少缺一列的行数。
运行：ssh -F .ssh/config_ai data-asset-83 "docker exec -i data-asset-api python -" < b8_consumables_null_probe.py
"""
import json
import oracledb

NN = json.loads(r"""["ADMISSION_ID", "AMOUNT", "DEPT_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "ID", "MATERIAL_CODE", "MATERIAL_NAME", "NAME", "ORG_CODE", "ORG_NAME", "RECORD_DATE", "RECORD_SIGN_DATE", "SEX_CODE", "SEX_NAME"]""")
oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()
pred = " OR ".join(f'"{c}" IS NULL' for c in NN)
cur.execute(
    f"SELECT COUNT(*) FROM ODS.V_EMR_CONSUMABLES "
    "WHERE DATETIME >= TO_DATE('2026-10-26','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-27','YYYY-MM-DD') "
    f"AND ({pred})")
print("窗内至少缺一 NOT NULL 列的行数:", cur.fetchone()[0])
for c in NN:
    cur.execute(
        f'SELECT COUNT(*) FROM ODS.V_EMR_CONSUMABLES '
        "WHERE DATETIME >= TO_DATE('2026-10-26','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-27','YYYY-MM-DD') "
        f'AND "{c}" IS NULL')
    n = cur.fetchone()[0]
    if n:
        print(f"  {c} IS NULL: {n} 行")
conn.close()
