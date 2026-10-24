line = open("/etc/data-asset/credentials/bloodnew_sqlserver_10_10_8_7.readonly").readline().strip()
u, _, p = line.partition(":")
import pymssql
conn = pymssql.connect(server="10.10.8.7", port=1433, user=u, password=p,
                       database="XH_BIS", login_timeout=20, timeout=60)
cur = conn.cursor()
print("[输血87] connected, user=", u[:3] + "***")
cur.execute(
    "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_NAME LIKE '%EMR%' OR TABLE_NAME LIKE '%BLOOD%' OR TABLE_NAME LIKE '%TRANSF%'")
objs = cur.fetchall()
print("[输血87] 候选对象:", len(objs))
for r in objs[:30]:
    print("  ", r)
conn.close()
