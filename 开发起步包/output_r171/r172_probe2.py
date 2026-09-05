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

print("== 登录过（LASTLOGINDATE 非空）用户的特征分布 ==")
cur.execute("""
SELECT FSYSID, FUSERTYPE, NVL(FFREE3,'NULL'), COUNT(*) FROM CDMS.T_MSS_EMP_DICT
WHERE LASTLOGINDATE IS NOT NULL GROUP BY FSYSID, FUSERTYPE, NVL(FFREE3,'NULL') ORDER BY 4 DESC""")
total_login = 0
for r in cur.fetchall():
    total_login += r[3]
    print(f"  FSYSID={r[0]} FUSERTYPE={r[1]} FFREE3={r[2]}: {r[3]} 人")
print("  登录过总数:", total_login)

print("== 从未登录（LASTLOGINDATE 空）用户特征分布 ==")
cur.execute("""
SELECT FSYSID, FUSERTYPE, NVL(FFREE3,'NULL'), COUNT(*) FROM CDMS.T_MSS_EMP_DICT
WHERE LASTLOGINDATE IS NULL GROUP BY FSYSID, FUSERTYPE, NVL(FFREE3,'NULL') ORDER BY 4 DESC""")
for r in cur.fetchall()[:8]:
    print(f"  FSYSID={r[0]} FUSERTYPE={r[1]} FFREE3={r[2]}: {r[3]} 人")

print("== FFREE3=1 全库分布 ==")
cur.execute("SELECT FSYSID, COUNT(*) FROM CDMS.T_MSS_EMP_DICT WHERE FFREE3='1' GROUP BY FSYSID")
for r in cur.fetchall():
    print(f"  FFREE3=1 & FSYSID={r[0]}: {r[1]} 人")

print("== 关键组明细（含登录时间）==")
KEYS = ['001429','001708','002249','002339','003245','003847','000852','002076','002590','001324','003176','002124','004019','004066']
cur.execute(f"""
SELECT FLOGINNAME, FUSERNAME, FSYSID, FUSERTYPE, NVL(FFREE3,'NULL'), NVL(TO_CHAR(LASTLOGINDATE,'YYYY-MM-DD'),'未登录'), FDEPT
FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME IN ({",".join(f"'{k}'" for k in KEYS)}) ORDER BY FLOGINNAME""")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]:<4} FSYSID={r[2]} FUSERTYPE={r[3]} FFREE3={r[4]} 最后登录={r[5]} FDEPT={r[6]}")
cdms.close()
