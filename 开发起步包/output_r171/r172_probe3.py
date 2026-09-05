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

print("== 模板参考账号 904/1036 的 FFREE3/FUSERTYPE/FSYSID ==")
cur.execute("SELECT FLOGINNAME, FUSERNAME, FSYSID, FUSERTYPE, NVL(FFREE3,'NULL') FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME IN ('904','1036')")
for r in cur.fetchall():
    print(" ", r)

print("== 全部 46 个未登录户（FUSERTYPE=0 & FFREE3 空 & 无登录）明细 + 权限行数 ==")
cur.execute("""
SELECT E.FLOGINNAME, E.FUSERNAME, E.FDEPT, NVL(TO_CHAR(E.FCHANGEDATE,'YYYY-MM-DD'),'-'),
       (SELECT COUNT(*) FROM CDMS.T_MSS_AUTHMAPPING A WHERE A.FID = E.FLOGINNAME)
FROM CDMS.T_MSS_EMP_DICT E
WHERE E.LASTLOGINDATE IS NULL AND E.FFREE3 IS NULL
ORDER BY E.FLOGINNAME""")
rows = cur.fetchall()
print("总数:", len(rows))
for r in rows:
    print(f"  {r[0]} {r[1]:<6} FDEPT={r[2]} 配置日期={r[3]} 权限行={r[4]}")
cdms.close()
