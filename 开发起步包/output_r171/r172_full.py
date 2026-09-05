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
conn = cdms._require_conn()
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER='CDMS' AND TABLE_NAME='T_MSS_EMP_DICT' ORDER BY COLUMN_ID")
cols = [r[0] for r in cur.fetchall()]
print("EMP_DICT 全列:", cols)
sel = ", ".join(cols)
cur.execute(f"SELECT {sel} FROM CDMS.T_MSS_EMP_DICT WHERE FLOGINNAME IN ('004066','004019') ORDER BY FLOGINNAME")
rows = cur.fetchall()
a = dict(zip(cols, rows[0])) if rows else {}
b = dict(zip(cols, rows[1])) if len(rows) > 1 else {}
print(f"\n{'列':24} {'004066(不对)':40} {'004019(对)':40}")
for c in cols:
    va, vb = a.get(c), b.get(c)
    def fmt(v):
        s = str(v) if v is not None else "NULL"
        if c in ("FPWD",) and v:
            return f"<{len(str(v))}字符:{str(v)[:4]}...>"
        return s[:38]
    mark = "  <<< DIFF" if fmt(va) != fmt(vb) else ""
    print(f"{c:24} {fmt(va):40} {fmt(vb):40}{mark}")
print("\n== AUTHMAPPING 含 FDATE 对比 ==")
cur.execute("SELECT FID, FTYPE, FAUTHORITYID, FST, FPRIVIEGETYPE, TO_CHAR(FDATE,'YYYY-MM-DD HH24:MI'), FUSER, FUPDATEUSER FROM CDMS.T_MSS_AUTHMAPPING WHERE FID IN ('004066','004019') ORDER BY FID, FTYPE")
for r in cur.fetchall():
    print(" ", r)
cdms.close()
