from app.core.config import settings
from app.core.db import SessionLocal
from app.services.cdms_identity_adapter import CdmsIdentityAdapter
from app.services.identity_sync_orchestrator import _get_person_depts

EMPS = ['000110','000852','001163','001270','001306','001324','001407','001542','001670','001838','001974','002076','002106','002124','002137','002154','002214','002236','002340','002541','002542','002546','002590','002633','002751','002978','003176']
db = SessionLocal()
ROLE = 'a1c9192fbe31423fab2dce6f81791b88'
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
bad = []
cdms.connect()
for emp in EMPS:
    primary, additional = _get_person_depts(db, emp, "doctor")
    user = cdms.snapshot_user(emp)
    auth = cdms.snapshot_auth(emp) or []
    pairs = {(str(r.get("FTYPE")), str(r.get("FAUTHORITYID"))) for r in auth}
    need = ([("0", ROLE)]
            + [("2", d) for d in ([primary] + (additional or [])) if d]
            + [("3", "100005"), ("5", "A00001"), ("10", "1")])
    missing = [p for p in need if p not in pairs]
    fdept = (user or {}).get("FDEPT")
    fdept_ok = user is not None and str(fdept or "") == str(primary)
    status = "OK" if user and not missing and fdept_ok else "PROBLEM"
    if status != "OK":
        bad.append((emp, missing[:3], fdept_ok))
    print(f"{emp} in_db={bool(user)} rows={len(auth)} FDEPT={fdept}(want {primary}) missing={len(missing)} {status}")
cdms.close()
db.close()
print("RESULT:", "ALL_27_OK" if not bad else f"BAD={bad}")
