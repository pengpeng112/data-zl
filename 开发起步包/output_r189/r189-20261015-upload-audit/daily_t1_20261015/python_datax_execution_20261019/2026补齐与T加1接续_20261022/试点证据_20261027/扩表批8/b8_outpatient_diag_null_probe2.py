"""表4 OUTPATIENT_DIAG 隔离核因二（只读）：VARCHAR2 列 LENGTHB 超长 + 同键（ID）双行/不同内容。
"""
import json
import oracledb

VC = json.loads(r"""[["ID", "VARCHAR2", 200], ["OUTPATIENT_NUM", "VARCHAR2", 40], ["TCM_WM_MARK_NAME", "VARCHAR2", 20], ["ADMIN_ILLNESS_CODE", "VARCHAR2", 2000], ["ADMIN_ILLNESS_NAME", "VARCHAR2", 2000], ["DOCTOR_ID_NUM", "VARCHAR2", 36], ["DOCTOR_NAME", "VARCHAR2", 50], ["DISTRICT_CODE", "VARCHAR2", 6], ["ORG_CODE", "VARCHAR2", 32], ["ORG_NAME", "VARCHAR2", 70], ["EXCHANGE_TYPE", "VARCHAR2", 10], ["NAME", "VARCHAR2", 100], ["ID_NUM", "VARCHAR2", 36], ["DIAGNOSIS_NO", "VARCHAR2", 40], ["LOCAL_DIAGNOSIS_CODE", "VARCHAR2", 100], ["LOCAL_DIAGNOSIS_NAME", "VARCHAR2", 400], ["NHS_DX_CODE", "VARCHAR2", 80], ["NHS_DX_NAME", "VARCHAR2", 320], ["CHINA_MED_SYNDROME_CODE", "VARCHAR2", 12], ["CHINA_MED_SYNDROME_NAME", "VARCHAR2", 100]]""")
oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 120000
cur = conn.cursor()
W = ("WHERE DATETIME >= TO_DATE('2026-10-26','YYYY-MM-DD') "
     "AND DATETIME < TO_DATE('2026-10-27','YYYY-MM-DD')")
print("== LENGTHB 超长（目标 DATA_LENGTH，字节）==")
for col, dtype, dl in VC:
    if not dl:
        continue
    cur.execute(
        f"SELECT COUNT(*) FROM ODS.V_EMR_OUTPATIENT_DIAG {W} "
        f"AND \"{col}\" IS NOT NULL AND LENGTHB(\"{col}\") > {int(dl)}")
    n = cur.fetchone()[0]
    if n:
        cur.execute(
            f"SELECT MAX(LENGTHB(\"{col}\")) FROM ODS.V_EMR_OUTPATIENT_DIAG {W}")
        print(f"  {col} > {dl}B: {n} 行 (max LENGTHB={cur.fetchone()[0]})")
print("== 同键（ID）多行 ==")
cur.execute(
    f"SELECT COUNT(*) FROM (SELECT ID FROM ODS.V_EMR_OUTPATIENT_DIAG {W} "
    "GROUP BY ID HAVING COUNT(*) > 1)")
print("  同 ID 多行组数:", cur.fetchone()[0])
conn.close()
