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
cur.execute("SELECT USER FROM DUAL")
print("当前连接身份:", cur.fetchone()[0])
cur.execute("SELECT OWNER, TABLE_NAME FROM ALL_TABLES WHERE TABLE_NAME LIKE '%KESHID%'")
rows = cur.fetchall()
print("KESHID 类表:", rows if rows else "全库不可见")
cur.execute("SELECT OWNER, TABLE_NAME FROM ALL_TABLES WHERE TABLE_NAME LIKE '%DEPT%' OR TABLE_NAME LIKE '%KS_%'")
print("DEPT/KS 类表:")
for r in (cur.fetchall() or [])[:15]:
    print(" ", r[0], r[1])
cur.execute("SELECT COUNT(*) FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME='004066' AND NVL(FFREE3,'x')='1'")
print("004066 FFREE3=1 仍在:", cur.fetchone()[0])
cdms.close()
