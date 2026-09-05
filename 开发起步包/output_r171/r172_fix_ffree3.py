"""r172 fix: CDMS 建户模板漏 FFREE3 列 → 平台同步建的全部 46 户 FFREE3=NULL 无法登录使用。
最小幂等修复：UPDATE ... SET FFREE3='1' WHERE FFREE3 IS NULL（仅 46 人名单），平台审计留痕。"""
from app.core.config import settings
from app.services.cdms_identity_adapter import CdmsIdentityAdapter
from app.core.db import SessionLocal
from sqlalchemy import text

EMPS = ['000402','001197','001324','002008','002124','003173','003176','003209','003427','003462',
        '003522','003705','003721','003883','003888','003913','003917','003960','003975','003976',
        '003977','003978','003980','003983','003984','003985','003986','003988','003989','003991',
        '003992','003994','003995','003996','003997','003998','003999','004003','004005','004011',
        '004012','004017','004037','004054','004063','004066']

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
conn = cdms._require_conn()
cur = conn.cursor()
ph = ",".join(f":e{i}" for i in range(len(EMPS)))
binds = {f"e{i}": e for i, e in enumerate(EMPS)}
cur.execute(f"SELECT COUNT(*) FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME IN ({ph}) AND FFREE3 IS NULL", binds)
before = cur.fetchone()[0]
print("修复前 FFREE3=NULL 的户数:", before)
cur.execute(
    f"UPDATE CDMS.T_MSS_EMP_DICT SET FFREE3='1', FCHANGEDATE=SYSDATE "
    f"WHERE FLOGINNAME IN ({ph}) AND FFREE3 IS NULL", binds)
updated = cur.rowcount
conn.commit()
print("UPDATE 提交，行数:", updated)
cur.execute(f"SELECT COUNT(*) FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME IN ({ph}) AND NVL(FFREE3,'x')='1'", binds)
after = cur.fetchone()[0]
print("复核 FFREE3=1 的户数:", after, "/", len(EMPS))
cdms.close()

db = SessionLocal()
try:
    db.execute(text(
        "insert into asset.asset_govern_audit_logs (action_type, object_type, object_id, operator, detail_json) "
        "values ('update', 'CDMS.T_MSS_EMP_DICT', 'FFREE3-batch-46', 'r172_ffree3_fix', :d)"),
        {"d": '{"reason":"平台建户模板漏FFREE3列导致无法登录使用","change":"FFREE3 NULL->1","rows":%d,"scope":"nightly-sync建户46人(含r172新建3户)","ref":"用户20260902报障004066,参照004019"}' % updated})
    db.commit()
    print("平台审计已留痕")
except Exception as e:
    db.rollback()
    print("审计写入失败(不影响数据修复):", str(e)[:120])
finally:
    db.close()
