from app.core.db import SessionLocal
from sqlalchemy import text
db = SessionLocal()
try:
    db.execute(text(
        "insert into asset.asset_govern_audit_logs (module, entity_type, entity_ref, action, after_data, operator, reason) "
        "values ('identity_sync', 'CDMS.T_MSS_EMP_DICT', 'FFREE3-batch-46', 'update', :after, 'r172_ffree3_fix', :reason)"),
        {"after": '{"FFREE3":"1","rows":46,"scope":"nightly-sync建户43+r172新建3"}',
         "reason": "平台建户模板漏FFREE3列导致建户后无法登录使用；用户20260902报障004066，参照004019（FFREE3=1可登录）。全库1735登录用户99.7%为FFREE3=1，未登录46户全部FFREE3=NULL"})
    db.commit()
    print("audit ok")
finally:
    db.close()
