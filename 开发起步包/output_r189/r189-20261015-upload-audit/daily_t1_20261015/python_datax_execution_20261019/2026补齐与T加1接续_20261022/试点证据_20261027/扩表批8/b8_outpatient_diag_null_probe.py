"""表4 OUTPATIENT_DIAG 隔离核因（只读）：19 个 NOT NULL 列 2026-10-26 窗内逐列 NULL 计数。
"""
import json
import oracledb

NN = json.loads(r"""["ADMIN_ILLNESS_CODE", "ADMIN_ILLNESS_NAME", "DIAGNOSIS_NO", "DIAG_DATE", "DISTRICT_CODE", "DOCTOR_NAME", "EXCHANGE_TYPE", "ID", "ID_NUM", "IF_MAIN", "LOCAL_DIAGNOSIS_CODE", "LOCAL_DIAGNOSIS_NAME", "NAME", "ORG_CODE", "ORG_NAME", "OUTPATIENT_NUM", "SEX_CODE", "TCM_WM_MARK_CODE", "TCM_WM_MARK_NAME"]""")
oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()
pred = " OR ".join(f'"{c}" IS NULL' for c in NN)
cur.execute(
    "SELECT COUNT(*) FROM ODS.V_EMR_OUTPATIENT_DIAG "
    "WHERE DATETIME >= TO_DATE('2026-10-26','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-27','YYYY-MM-DD') "
    f"AND ({pred})")
print("窗内至少缺一 NOT NULL 列的行数:", cur.fetchone()[0])
for c in NN:
    cur.execute(
        'SELECT COUNT(*) FROM ODS.V_EMR_OUTPATIENT_DIAG '
        "WHERE DATETIME >= TO_DATE('2026-10-26','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-27','YYYY-MM-DD') "
        f'AND "{c}" IS NULL')
    n = cur.fetchone()[0]
    if n:
        print(f"  {c} IS NULL: {n} 行")
conn.close()
