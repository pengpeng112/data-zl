"""批2 计划预核（只读限量）：体检 10.10.10.96/JZCIS + 输血 10.10.10.67/ORCLBIS。
凭据只进内存；每查询限量/聚合；全部 SELECT。"""
import sys


def sqlserver_probe(tag, host, port, cred, database, tables):
    line = open(f"/etc/data-asset/credentials/{cred}").readline().strip()
    u, _, p = line.partition(":")
    import pymssql
    try:
        conn = pymssql.connect(server=host, port=port, user=u, password=p,
                               database=database, login_timeout=20, timeout=60)
        tds = "default"
    except pymssql.exceptions.OperationalError:
        conn = pymssql.connect(server=host, port=port, user=u, password=p,
                               database=database, login_timeout=20, timeout=60,
                               tds_version="7.0")
        tds = "7.0"
    print(f"[{tag}] connected, tds={tds}, db={database}")
    cur = conn.cursor()
    cur.execute(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME IN (%s)",
        tuple(tables))
    views = [r[0] for r in cur.fetchall()]
    print(f"[{tag}] views found:", views)
    for t in tables:
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = %s AND COLUMN_NAME IN ('ID','DATETIME','HEALTH_EXAM_NO')",
            (t,))
        cols = cur.fetchall()
        cur.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s", (t,))
        ncols = cur.fetchone()[0]
        print(f"[{tag}] {t}: cols={ncols} key/anchor={cols}")
    conn.close()
    return views


def sqlserver_freshness(tag, cred, database, view, anchor="DATETIME"):
    line = open(f"/etc/data-asset/credentials/{cred}").readline().strip()
    u, _, p = line.partition(":")
    import pymssql
    try:
        conn = pymssql.connect(server="10.10.10.96", port=1433, user=u, password=p,
                               database=database, login_timeout=20, timeout=90)
    except pymssql.exceptions.OperationalError:
        conn = pymssql.connect(server="10.10.10.96", port=1433, user=u, password=p,
                               database=database, login_timeout=20, timeout=90,
                               tds_version="7.0")
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*), MAX({anchor}) FROM dbo.{view}")
    cnt, mx = cur.fetchone()
    print(f"[{tag}] {view}: total={cnt} max({anchor})={mx}")
    conn.close()


# -- 体检 10.10.10.96 / JZCIS（SQLServer）----------------------------------
PHYS = ["V_EMR_PHYSICAL_REPORT", "V_EMR_PHYSICAL_EXAM", "V_EMR_PHYSICAL_EXAM_ITEM"]
views = sqlserver_probe("体检96", "10.10.10.96", 1433,
                        "physical_exam_sqlserver_10_10_10_96.readonly", "JZCIS", PHYS)
if "V_EMR_PHYSICAL_REPORT" in views:
    sqlserver_freshness("体检96", "physical_exam_sqlserver_10_10_10_96.readonly",
                        "JZCIS", "V_EMR_PHYSICAL_REPORT")

# -- 输血旧库 10.10.10.67 / ORCLBIS（Oracle）--------------------------------
line = open("/etc/data-asset/credentials/bloodold_oracle_10_10_10_67.readonly").readline().strip()
u, _, p = line.partition(":")
import oracledb
oracledb.init_oracle_client(lib_dir="/opt/oracle")
try:
    conn = oracledb.connect(user=u, password=p, dsn="10.10.10.67:1521/ORCLBIS",
                            tcp_connect_timeout=20, call_timeout=120000)
    print("[输血67] connected, service=ORCLBIS, user=", u[:3] + "***")
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
        cur.execute(
            "SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE OWNER=:o AND TABLE_NAME=:t",
            {"o": owner, "t": oname})
        ncols = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*), MAX(DATETIME) FROM {owner}.{oname}")
        cnt, mx = cur.fetchone()
        print(f"[输血67] {owner}.{oname}: cols={ncols} {cols} total={cnt} max={mx}")
    conn.close()
except Exception as e:
    print("[输血67] CONN_ERR:", type(e).__name__, str(e)[:300])
