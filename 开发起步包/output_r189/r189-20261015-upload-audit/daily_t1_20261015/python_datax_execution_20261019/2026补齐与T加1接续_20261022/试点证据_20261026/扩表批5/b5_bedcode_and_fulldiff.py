"""批5 目标既有床号样例 + 全八表跨族类型错配普查（只读）。"""
import oracledb

TABLES = ["EMR_MEDICAL_RECORD_INFO", "EMR_ADMISSION_DIAGNOSIS", "EMR_DEATH_RECORD",
          "EMR_ICH_ALLERGIES", "EMR_DISCHARGE_RECORD", "EMR_OUTPATIENT_RECORD",
          "EMR_OUTPATIENT_REGISTER", "EMR_ADMISSION_RECORD"]

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tconn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tconn.cursor()
print("== 目标既有 ADMISSION_RECORD 床号样例（RTRIP 后）==")
tcur.execute("SELECT DISTINCT RTRIM(BED_CODE), RTRIM(SICKBED_NUM) FROM DBOPER.EMR_ADMISSION_RECORD "
             "WHERE ROWNUM <= 200000 AND BED_CODE IS NOT NULL AND ROWNUM <= 8")
for r in tcur.fetchall():
    print("  bed_code=%r sickbed_num=%r" % (r[0], r[1]))

tgt = {}
for t in TABLES:
    tcur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS "
                 "WHERE OWNER='DBOPER' AND TABLE_NAME=:t", {"t": t})
    tgt[t] = {r[0].upper(): r[1].upper() for r in tcur.fetchall()}
tconn.close()

line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
cur = conn.cursor()
fam = {"VARCHAR2": "S", "CHAR": "S", "NCHAR": "S", "NVARCHAR2": "S", "CLOB": "S",
       "NUMBER": "N", "FLOAT": "N", "BINARY_FLOAT": "N", "BINARY_DOUBLE": "N",
       "DATE": "D", "TIMESTAMP": "D"}
print("== 全八表跨族错配普查（N->S / S->N / S<->D / N<->D）==")
for t in TABLES:
    cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS "
                "WHERE OWNER='ODS' AND TABLE_NAME=:v", {"v": "V_" + t})
    src = {r[0].upper(): r[1].upper() for r in cur.fetchall()}
    bad = []
    for c, tt in tgt[t].items():
        if c == "SYSTEM_TIME" or c not in src:
            continue
        sf, tf = fam.get(src[c], "?"), fam.get(tt, "?")
        if sf != tf:
            bad.append(f"{c}:{src[c]}->{tt}")
    print(f"{t}: {'; '.join(bad) if bad else 'NONE'}")
conn.close()
print("== 结束 ==")
