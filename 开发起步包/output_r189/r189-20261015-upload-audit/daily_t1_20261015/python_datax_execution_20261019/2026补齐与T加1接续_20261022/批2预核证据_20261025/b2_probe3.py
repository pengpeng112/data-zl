"""批2 预核第三轮（只读限量）：两套视图对比、varchar 锚点格式、父子覆盖率（JOIN 版）、输血67。"""

line = open("/etc/data-asset/credentials/physical_exam_sqlserver_10_10_10_96.readonly").readline().strip()
u, _, p = line.partition(":")
import pymssql
conn = pymssql.connect(server="10.10.10.96", port=1433, user=u, password=p,
                       database="JZCIS", login_timeout=20, timeout=180, tds_version="7.0")
cur = conn.cursor()
print("[体检96] 两套视图对比（V_ 大写 vs v_ 小写）：")
for nm in ("V_EMR_PHYSICAL_REPORT", "v_EMR_PHYSICAL_REPORT",
           "V_EMR_PHYSICAL_EXAM", "v_EMR_PHYSICAL_EXAM",
           "V_EMR_PHYSICAL_EXAM_ITEM", "v_EMR_PHYSICAL_EXAM_ITEM"):
    cur.execute(f"SELECT COUNT(*), MAX(DATETIME) FROM dbo.[{nm}]")
    print("  ", nm, cur.fetchone())

print("[体检96] EXAM/ITEM DATETIME 样本（格式确认）：")
cur.execute("SELECT TOP 3 DATETIME FROM dbo.V_EMR_PHYSICAL_EXAM ORDER BY DATETIME DESC")
print("  V_EXAM:", [r[0] for r in cur.fetchall()])
cur.execute("SELECT TOP 3 DATETIME FROM dbo.V_EMR_PHYSICAL_EXAM_ITEM ORDER BY DATETIME DESC")
print("  V_ITEM:", [r[0] for r in cur.fetchall()])
cur.execute(
    "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS "
    "WHERE TABLE_NAME='V_EMR_PHYSICAL_EXAM' AND COLUMN_NAME='DATETIME'")
print("  V_EXAM DATETIME 列定义:", cur.fetchone())

print("[体检96] 父子覆盖率（子 HEALTH_EXAM_NO 无父行的数量）：")
for child in ("V_EMR_PHYSICAL_EXAM", "V_EMR_PHYSICAL_EXAM_ITEM"):
    cur.execute(
        f"SELECT COUNT(*) FROM dbo.[{child}] c "
        f"LEFT JOIN dbo.V_EMR_PHYSICAL_REPORT r ON r.HEALTH_EXAM_NO = c.HEALTH_EXAM_NO "
        f"WHERE r.HEALTH_EXAM_NO IS NULL")
    orphans = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM dbo.[{child}]")
    total = cur.fetchone()[0]
    print(f"  {child}: total={total} 无父行={orphans} 覆盖率={100*(total-orphans)/total:.2f}%")
conn.close()

# -- 输血 67 ------------------------------------------------------------------
line = open("/etc/data-asset/credentials/bloodold_oracle_10_10_10_67.readonly").readline().strip()
u, _, p = line.partition(":")
import oracledb
oracledb.init_oracle_client(lib_dir="/opt/oracle")
try:
    conn = oracledb.connect(user=u, password=p, dsn="10.10.10.67:1521/ORCLBIS",
                            tcp_connect_timeout=20)
    conn.call_timeout = 180000
    print("[输血67] connected, user=", u[:3] + "***")
    cur = conn.cursor()
    cur.execute(
        "SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OBJECT_NAME IN "
        "('V_EMR_BLOOD_APPLY_REPORT','V_EMR_BLOOD_APPLY_REPORT_ITEM',"
        "'V_EMR_TRANSFUSION_RECORD','V_EMR_BLOOD_DESTROY_RECORD')")
    objs = cur.fetchall()
    print("[输血67] objects:", objs)
    for owner, oname, otype in objs:
        if not oname.upper().startswith("V_"):
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
