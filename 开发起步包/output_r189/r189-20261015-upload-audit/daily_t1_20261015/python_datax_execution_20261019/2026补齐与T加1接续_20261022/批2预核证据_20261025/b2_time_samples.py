line = open("/etc/data-asset/credentials/physical_exam_sqlserver_10_10_10_96.readonly").readline().strip()
u, _, p = line.partition(":")
import pymssql
conn = pymssql.connect(server="10.10.10.96", port=1433, user=u, password=p,
                       database="JZCIS", login_timeout=20, timeout=60, tds_version="7.0")
cur = conn.cursor()
cur.execute(
    "SELECT TOP 3 ASSTART_DTIME, END_DTIME, DATETIME FROM dbo.V_EMR_PHYSICAL_REPORT "
    "WHERE ASSTART_DTIME IS NOT NULL AND ASSTART_DTIME <> '' ORDER BY DATETIME DESC")
for r in cur.fetchall():
    print(r)
cur.execute(
    "SELECT COUNT(*) FROM dbo.V_EMR_PHYSICAL_REPORT WHERE ASSTART_DTIME IS NULL OR ASSTART_DTIME=''")
print("ASSTART_DTIME 空:", cur.fetchone()[0])
cur.execute(
    "SELECT COUNT(*) FROM dbo.V_EMR_PHYSICAL_REPORT WHERE END_DTIME IS NULL OR END_DTIME=''")
print("END_DTIME 空:", cur.fetchone()[0])
conn.close()
