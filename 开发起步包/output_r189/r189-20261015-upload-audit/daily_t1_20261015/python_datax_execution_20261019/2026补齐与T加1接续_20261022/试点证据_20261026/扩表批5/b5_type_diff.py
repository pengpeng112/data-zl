"""批5 ADMISSION_RECORD 源/目标列类型对比（只读）。"""
import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME, DATA_TYPE, CHAR_LENGTH FROM ALL_TAB_COLUMNS "
            "WHERE OWNER='ODS' AND TABLE_NAME='V_EMR_ADMISSION_RECORD'")
src = {r[0].upper(): (r[1], r[2]) for r in cur.fetchall()}
conn.close()
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tconn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tconn.cursor()
tcur.execute("SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH FROM ALL_TAB_COLUMNS "
             "WHERE OWNER='DBOPER' AND TABLE_NAME='EMR_ADMISSION_RECORD'")
tgt = {r[0].upper(): (r[1], r[2]) for r in tcur.fetchall()}
tconn.close()
fam = {"VARCHAR2": "S", "CHAR": "S", "NCHAR": "S", "NVARCHAR2": "S", "CLOB": "S",
       "NUMBER": "N", "FLOAT": "N", "BINARY_FLOAT": "N", "BINARY_DOUBLE": "N",
       "DATE": "D", "TIMESTAMP": "D", "TIMESTAMP(6)": "D", "TIMESTAMP(3)": "D"}
print("源/目标类型错配（剔除 SYSTEM_TIME；同族视为匹配）：")
n = 0
for c in sorted(tgt):
    if c == "SYSTEM_TIME":
        continue
    s = src.get(c)
    t = tgt[c]
    if s is None:
        print(f"  {c}: 源无此列!")
        n += 1
        continue
    sf, tf = fam.get(s[0], "?"), fam.get(t[0], "?")
    if sf != tf:
        print(f"  {c}: src={s[0]}({s[1]}) tgt={t[0]}({t[1]}) fam {sf}->{tf}")
        n += 1
    elif s[0] != t[0]:
        print(f"  同族不同型 {c}: src={s[0]} tgt={t[0]}")
print("错配列数:", n)
