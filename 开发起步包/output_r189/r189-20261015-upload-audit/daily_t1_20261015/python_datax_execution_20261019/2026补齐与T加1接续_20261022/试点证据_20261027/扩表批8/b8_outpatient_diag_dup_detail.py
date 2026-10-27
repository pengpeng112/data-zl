"""表4 OUTPATIENT_DIAG 同键多行定性（只读样例，脱敏：只取差异列名与计数，不取患者值）。
"""
import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
conn.call_timeout = 120000
cur = conn.cursor()
W = ("WHERE DATETIME >= TO_DATE('2026-10-26','YYYY-MM-DD') "
     "AND DATETIME < TO_DATE('2026-10-27','YYYY-MM-DD')")
cur.execute(
    f"SELECT ID, COUNT(*) FROM ODS.V_EMR_OUTPATIENT_DIAG {W} "
    "GROUP BY ID HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC")
dups = cur.fetchall()
print("同键多行组数:", len(dups), "| 行数分布:", sorted(set(n for _, n in dups)))
from collections import Counter
print("组大小分布:", dict(Counter(n for _, n in dups)))
print("隔离行数合计(组内全部行):", sum(n for _, n in dups))
# 取最大组一组样例，比较两行哪些列不同（只打印列名与DATETIME，不打印患者敏感值）
sid = dups[0][0]
cur.execute(
    f"SELECT * FROM ODS.V_EMR_OUTPATIENT_DIAG {W} AND ID = :i ORDER BY DATETIME",
    {"i": sid})
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print(f"样例组 ID 尾4位=…{str(sid)[-4:]} 行数={len(rows)}")
if len(rows) >= 2:
    diff_cols = [c for i, c in enumerate(cols) if rows[0][i] != rows[1][i]]
    print("两行差异列:", diff_cols)
    for c in diff_cols:
        i = cols.index(c)
        v0, v1 = rows[0][i], rows[1][i]
        if c.upper() in ("ID",):
            continue
        # DATETIME/时间类可打印，其余值域类只打类型与长度
        if any(k in c.upper() for k in ("DATE", "TIME")):
            print(f"  {c}: {v0} vs {v1}")
        else:
            print(f"  {c}: len={len(str(v0)) if v0 else 0} vs len={len(str(v1)) if v1 else 0} (值脱敏)")
# 全部组的差异列普查（列名+组数，值不取）
cur.execute(
    "SELECT column_name FROM all_tab_columns WHERE owner='ODS' AND table_name='V_EMR_OUTPATIENT_DIAG'")
allcols = [r[0] for r in cur.fetchall()]
from collections import Counter as C2
diffcnt = C2()
for did, _ in dups[:50]:
    cur.execute(
        f"SELECT * FROM ODS.V_EMR_OUTPATIENT_DIAG {W} AND ID = :i ORDER BY DATETIME",
        {"i": did})
    rs = cur.fetchall()
    if len(rs) >= 2:
        for i, c in enumerate(cols):
            if rs[0][i] != rs[1][i]:
                diffcnt[c] += 1
print("前50组差异列分布:", dict(diffcnt.most_common(10)))
conn.close()
