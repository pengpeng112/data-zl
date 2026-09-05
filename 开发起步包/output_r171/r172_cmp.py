from app.core.config import settings
from app.core.db import SessionLocal
from app.services.cdms_identity_adapter import CdmsIdentityAdapter
from sqlalchemy import text

EMPS = ["004066", "004019"]
db = SessionLocal()
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
for emp in EMPS:
    print("=" * 20, emp, "=" * 20)
    user = cdms.snapshot_user(emp)
    print("EMP_DICT:", {k: v for k, v in (user or {}).items() if k != "FPWD"} if user else "无户")
    auth = cdms.snapshot_auth(emp) or []
    print(f"AUTHMAPPING {len(auth)} 行:")
    for r in sorted(auth, key=lambda x: (str(x.get("FTYPE")), str(x.get("FAUTHORITYID")))):
        print("  FTYPE=%s FAUTHORITYID=%s FST=%s FPRIVIEGETYPE=%s FUSER=%s" % (
            r.get("FTYPE"), r.get("FAUTHORITYID"), r.get("FST"), r.get("FPRIVIEGETYPE"), r.get("FUSER")))
    row = db.execute(text(
        "select person_name_cn, classification, employment_status, raw_job, job_title, raw_title "
        "from asset.asset_identity_persons where person_code=:e"), {"e": emp}).fetchone()
    print("平台persons:", row)
    depts = db.execute(text(
        "select dept_code, is_primary, source_table from asset.asset_identity_person_departments "
        "where person_code=:e order by is_primary desc, dept_code"), {"e": emp}).fetchall()
    print("平台科室:", depts[:12])
cdms.close()
db.close()
