"""批5 ADMISSION_RECORD v2 渲染 SQL 手工执行探查（只读）。"""
import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()
tests = [
    ("两列TO_CHAR+窗谓词", 'SELECT TO_CHAR("BED_CODE"), TO_CHAR("SICKBED_NUM") FROM ODS.V_EMR_ADMISSION_RECORD '
     "WHERE DATETIME >= TO_DATE('2026-10-25','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-26','YYYY-MM-DD') "
     "AND ROWNUM <= 3"),
    ("TO_CHAR嵌套子查询", 'SELECT * FROM (SELECT TO_CHAR("BED_CODE") AS BED_CODE FROM ODS.V_EMR_ADMISSION_RECORD '
     "WHERE DATETIME >= TO_DATE('2026-10-25','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-26','YYYY-MM-DD') "
     "ORDER BY ID) WHERE ROWNUM <= 3"),
]
for name, sql in tests:
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        print(f"{name}: OK rows={len(rows)} sample={rows[:2]}")
    except Exception as exc:
        print(f"{name}: ERR {type(exc).__name__}: {str(exc)[:200]}")
        conn.rollback()
conn.close()
