from app.core.config import settings
from app.services.cdms_identity_adapter import CdmsIdentityAdapter

cdms = CdmsIdentityAdapter(
    credential_ref=settings.identity_sync_cdms_credential_ref,
    cdms_host=settings.identity_sync_cdms_host,
    cdms_port=settings.identity_sync_cdms_port,
    cdms_service=settings.identity_sync_cdms_service,
    jump_host=settings.his_source_jump_host,
    jump_port=settings.his_source_jump_port,
    jump_user=settings.his_source_jump_user,
    jump_key=settings.his_source_jump_key or None,
    oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
)
cdms.connect()
cur = cdms._require_conn().cursor()

print("== 1) KESHID 科室字典命中率（关键未验证假设）==")
for code in ['040465', '040507', '030310', '031006', '030422H', '030115H']:
    cur.execute("SELECT COUNT(*) FROM CDMS.KESHID WHERE AAA = :c", {"c": code})
    n = cur.fetchone()[0]
    cur.execute("SELECT BBB FROM CDMS.KESHID WHERE AAA = :c AND ROWNUM <= 1", {"c": code})
    r = cur.fetchone()
    print(f"  {code}: {'在字典(' + str(r[0]) + ')' if n else '!!! 不在 KESHID 字典 !!!'}")

print("== 2) 46 户 FDEPT 在 KESHID 的总命中率 ==")
cur.execute("""
SELECT SUM(CASE WHEN K.AAA IS NOT NULL THEN 1 ELSE 0 END) AS hit, COUNT(*) AS total
FROM CDMS.T_MSS_EMP_DICT E LEFT JOIN CDMS.KESHID K ON K.AAA = E.FDEPT
WHERE E.LASTLOGINDATE IS NULL""")
r = cur.fetchone()
print(f"  未登录46户: FDEPT 命中字典 {r[0]}/{r[1]}")
cur.execute("""
SELECT SUM(CASE WHEN K.AAA IS NOT NULL THEN 1 ELSE 0 END) AS hit, COUNT(*) AS total
FROM CDMS.T_MSS_EMP_DICT E LEFT JOIN CDMS.KESHID K ON K.AAA = E.FDEPT
WHERE E.LASTLOGINDATE IS NOT NULL""")
r = cur.fetchone()
print(f"  已登录1735户: FDEPT 命中字典 {r[0]}/{r[1]}")

print("== 3) AUTHMAPPING FTYPE=2 科室码在 KESHID 命中率（004066 vs 004019）==")
for emp in ('004066', '004019'):
    cur.execute("""
SELECT A.FAUTHORITYID, (SELECT COUNT(*) FROM CDMS.KESHID K WHERE K.AAA = A.FAUTHORITYID)
FROM CDMS.T_MSS_AUTHMAPPING A WHERE A.FID = :e AND A.FTYPE = '2'""", {"e": emp})
    rows = cur.fetchall()
    bad = [x[0] for x in rows if x[1] == 0]
    print(f"  {emp}: 科室权限行 {len(rows)} 条, 不在字典的: {bad if bad else '无'}")

print("== 4) 角色字典表存在性 ==")
cur.execute("SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER='CDMS' AND (TABLE_NAME LIKE '%ROLE%' OR TABLE_NAME LIKE '%AUTHORITY%' OR TABLE_NAME LIKE '%POWER%')")
for r in cur.fetchall():
    print(" ", r[0])
cur.execute("SELECT COUNT(*) FROM CDMS.T_MSS_AUTHMAPPING WHERE FAUTHORITYID='a1c9192fbe31423fab2dce6f81791b88' AND FTYPE='0'")
print("  使用 a1c9192f 角色GUID 的用户数:", cur.fetchone()[0])

print("== 5) 004066 修复后状态确认 ==")
cur.execute("SELECT NVL(FFREE3,'NULL'), NVL(LOGINERRORCOUNT,'NULL'), NVL(TO_CHAR(LASTLOGINDATE,'YYYY-MM-DD HH24:MI'),'未登录') FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME='004066'")
print("  004066 FFREE3/LOGINERR/LASTLOGIN:", cur.fetchone())
cur.execute("SELECT COUNT(*) FROM CDMS.T_MSS_AUTHMAPPING WHERE FID='004066'")
print("  004066 权限行:", cur.fetchone()[0])
cdms.close()
