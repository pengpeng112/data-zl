"""批5 ADMISSION_RECORD 同键双行定性（只读）：两行差异列。"""
import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 60000
cur = conn.cursor()
cur.execute(
    "SELECT * FROM ODS.V_EMR_ADMISSION_RECORD "
    "WHERE DATETIME >= TO_DATE('2026-10-25','YYYY-MM-DD') AND DATETIME < TO_DATE('2026-10-26','YYYY-MM-DD')"
)
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
conn.close()
target = [r for r in rows if "c0714200" in str(r[cols.index("ID")])]
print("同键行数:", len(target))
if len(target) == 2:
    diffs = []
    for i, (a, b) in enumerate(zip(target[0], target[1])):
        if a != b:
            diffs.append((cols[i], str(a)[:60], str(b)[:60]))
    print("差异列数:", len(diffs))
    for c, a, b in diffs[:20]:
        print(f"  {c}: A={a!r} B={b!r}")
    i_dt = cols.index("DATETIME")
    print("DATETIME:", target[0][i_dt], "/", target[1][i_dt])
