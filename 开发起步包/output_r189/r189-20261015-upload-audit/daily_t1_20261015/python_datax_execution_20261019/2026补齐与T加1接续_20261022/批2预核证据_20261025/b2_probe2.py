"""批2 预核第二轮（只读限量）：对象类型/实名、新鲜度、体检父子覆盖率、输血67连通。"""

# -- 体检 SQLServer ----------------------------------------------------------
line = open("/etc/data-asset/credentials/physical_exam_sqlserver_10_10_10_96.readonly").readline().strip()
u, _, p = line.partition(":")
import pymssql
conn = pymssql.connect(server="10.10.10.96", port=1433, user=u, password=p,
                       database="JZCIS", login_timeout=20, timeout=120, tds_version="7.0")
cur = conn.cursor()
print("[体检96] 对象类型与实名：")
cur.execute(
    "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_NAME LIKE '%EMR_PHYSICAL%'")
objs = cur.fetchall()
for r in objs:
    print("  ", r)
realnames = {r[0] for r in objs}

def _rn(base):
    for cand in (base, base.lower(), "v_" + base[2:], base.replace("V_", "v_")):
        if cand in realnames:
            return cand
    return base

RPT, EXAM, ITEM = _rn("V_EMR_PHYSICAL_REPORT"), _rn("V_EMR_PHYSICAL_EXAM"), _rn("V_EMR_PHYSICAL_EXAM_ITEM")
print("[体检96] 实名：", RPT, EXAM, ITEM)
for nm in (RPT, EXAM, ITEM):
    cur.execute(f"SELECT COUNT(*), MAX(DATETIME) FROM dbo.{nm}")
    cnt, mx = cur.fetchone()
    print(f"  {nm}: total={cnt} max(DATETIME)={mx!r}")

print("[体检96] 父子覆盖率（子 HEALTH_EXAM_NO 在父 REPORT 中存在率）：")
cur.execute(
    f"SELECT COUNT(*), SUM(CASE WHEN EXISTS (SELECT 1 FROM dbo.{RPT} r WHERE r.HEALTH_EXAM_NO = c.HEALTH_EXAM_NO) THEN 1 ELSE 0 END) "
    f"FROM dbo.{EXAM} c")
print("  EXAM:", cur.fetchone())
cur.execute(
    f"SELECT COUNT(*), SUM(CASE WHEN EXISTS (SELECT 1 FROM dbo.{RPT} r WHERE r.HEALTH_EXAM_NO = c.HEALTH_EXAM_NO) THEN 1 ELSE 0 END) "
    f"FROM dbo.{ITEM} c")
print("  ITEM:", cur.fetchone())
cur.execute(f"SELECT COUNT(DISTINCT HEALTH_EXAM_NO) FROM dbo.{RPT}")
print("  REPORT distinct HEALTH_EXAM_NO:", cur.fetchone())
conn.close()

# -- 输血旧库 10.10.10.67 / ORCLBIS ------------------------------------------
line = open("/etc/data-asset/credentials/bloodold_oracle_10_10_10_67.readonly").readline().strip()
u, _, p = line.partition(":")
import oracledb
oracledb.init_oracle_client(lib_dir="/opt/oracle")
try:
    conn = oracledb.connect(user=u, password=p, dsn="10.10.10.67:1521/ORCLBIS",
                            tcp_connect_timeout=20)
    conn.call_timeout = 120000
    print("[输血67] connected")
    cur = conn.cursor()
    cur.execute(
        "SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OBJECT_NAME IN "
        "('V_EMR_BLOOD_APPLY_REPORT','V_EMR_BLOOD_APPLY_REPORT_ITEM',"
        "'V_EMR_TRANSFUSION_RECORD','V_EMR_BLOOD_DESTROY_RECORD')")
    objs = cur.fetchall()
    print("[输血67] objects:", objs)
    for owner, oname, otype in objs:
        if not oname.startswith("V_"):
            continue
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS "
            "WHERE OWNER=:o AND TABLE_NAME=:t AND COLUMN_NAME IN ('ID','DATETIME')",
            {"o": owner, "t": oname})
        cols = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE OWNER=:o AND TABLE_NAME=:t",
                    {"o": owner, "t": oname})
        ncols = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*), MAX(DATETIME) FROM {owner}.{oname}")
        cnt, mx = cur.fetchone()
        print(f"  {owner}.{oname}: cols={ncols} {cols} total={cnt} max(DATETIME)={mx!r}")
    conn.close()
except Exception as e:
    print("[输血67] CONN_ERR:", type(e).__name__, str(e)[:300])
