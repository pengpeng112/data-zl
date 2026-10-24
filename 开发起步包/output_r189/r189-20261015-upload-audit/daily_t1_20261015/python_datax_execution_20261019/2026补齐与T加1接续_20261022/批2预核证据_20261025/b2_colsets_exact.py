import json

line = open("/etc/data-asset/credentials/physical_exam_sqlserver_10_10_10_96.readonly").readline().strip()
u, _, p = line.partition(":")
import pymssql
conn = pymssql.connect(server="10.10.10.96", port=1433, user=u, password=p,
                       database="JZCIS", login_timeout=20, timeout=60, tds_version="7.0")
cur = conn.cursor()
tgt = json.load(open("/tmp/b2_targets.json", encoding="utf-8"))
tset = set(tgt["EMR_PHYSICAL_REPORT"])
for view in ("V_EMR_PHYSICAL_REPORT", "v_EMR_PHYSICAL_REPORT"):
    cur.execute(
        "SELECT c.name, TYPE_NAME(c.user_type_id) FROM sys.columns c "
        "JOIN sys.objects o ON c.object_id = o.object_id "
        "WHERE o.name = %s COLLATE Latin1_General_BIN AND o.schema_id = SCHEMA_ID('dbo')",
        (view,))
    src = {r[0].upper(): r[1] for r in cur.fetchall()}
    print(f"[{view}] 精确列数={len(src)}")
    print(f"  目标有源无: {sorted(tset - set(src))}")
    extra = sorted(set(src) - tset)
    print(f"  源有目标无({len(extra)}): {extra}")
# 大写 V_ 视图的时间列样本与空率
for cols in (("START_DTIME","END_DTIME"),):
    try:
        cur.execute(
            f"SELECT TOP 3 {', '.join(cols)}, DATETIME FROM dbo.V_EMR_PHYSICAL_REPORT "
            f"WHERE DATETIME >= '2026-10-01'")
        print("[V_大写] 时间列样本:", cur.fetchall())
    except Exception as e:
        print("[V_大写] 查询失败:", str(e)[:150])
conn.close()
