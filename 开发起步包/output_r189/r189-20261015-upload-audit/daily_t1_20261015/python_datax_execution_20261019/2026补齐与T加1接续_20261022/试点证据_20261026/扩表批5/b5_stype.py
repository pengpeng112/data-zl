"""批5 八目标表 SYSTEM_TIME 列类型核查（只读）。"""
import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
cur = conn.cursor()
TABLES = ["EMR_MEDICAL_RECORD_INFO", "EMR_ADMISSION_DIAGNOSIS", "EMR_DEATH_RECORD",
          "EMR_ICH_ALLERGIES", "EMR_DISCHARGE_RECORD", "EMR_OUTPATIENT_RECORD",
          "EMR_OUTPATIENT_REGISTER", "EMR_ADMISSION_RECORD"]
for t in TABLES:
    cur.execute("SELECT DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='DBOPER' "
                "AND TABLE_NAME=:t AND COLUMN_NAME='SYSTEM_TIME'", {"t": t})
    r = cur.fetchone()
    print(f"{t}: SYSTEM_TIME={r[0] if r else '无此列'}")
# DEATH_RECORD 现有 SYSTEM_TIME 样例
cur.execute("SELECT DISTINCT SYSTEM_TIME FROM DBOPER.EMR_DEATH_RECORD WHERE ROWNUM <= 6")
print("DEATH_RECORD SYSTEM_TIME 样例:", [str(r[0])[:30] for r in cur.fetchall()])
conn.close()
