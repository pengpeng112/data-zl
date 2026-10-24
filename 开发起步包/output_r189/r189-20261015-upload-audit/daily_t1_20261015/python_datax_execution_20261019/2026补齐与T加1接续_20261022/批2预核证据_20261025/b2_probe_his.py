line = open("/etc/data-asset/credentials/his_source_10_10_10_15").readline().strip()
u, _, p = line.partition(":")
import oracledb
oracledb.init_oracle_client(lib_dir="/opt/oracle")
conn = oracledb.connect(user=u, password=p, dsn="10.10.10.15:1521/his", tcp_connect_timeout=20)
conn.call_timeout = 90000
cur = conn.cursor()
cur.execute(
    "SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OBJECT_NAME IN "
    "('V_EMR_EXAM_IMAGE_REP','V_EMR_EXAM_IMAGE_PATH')")
print("[HIS15] objects:", cur.fetchall())
for owner, oname in [("HISUSER","V_EMR_EXAM_IMAGE_REP"),("HISUSER","V_EMR_EXAM_IMAGE_PATH")]:
    cur.execute(
        "SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER=:o AND TABLE_NAME=:t AND COLUMN_NAME IN ('ID','DATETIME')",
        {"o": owner, "t": oname})
    print(f"[HIS15] {oname} 键/锚:", cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE OWNER=:o AND TABLE_NAME=:t",
                {"o": owner, "t": oname})
    print(f"[HIS15] {oname} 总列数:", cur.fetchone()[0])
try:
    cur.execute("SELECT MAX(DATETIME) FROM HISUSER.V_EMR_EXAM_IMAGE_REP")
    print("[HIS15] REP max(DATETIME):", cur.fetchone())
except Exception as e:
    print("[HIS15] REP max 超时/失败:", type(e).__name__, str(e)[:120])
conn.close()
