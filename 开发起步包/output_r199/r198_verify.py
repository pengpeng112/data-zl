# -*- coding: utf-8 -*-
"""r198 independent read-only verification (do not trust the writer)."""
import json

from sqlalchemy import text
from app.core.db import SessionLocal
from app.core.config import settings
from app.services.cdms_identity_adapter import CdmsIdentityAdapter
from app.services.identity_sync_action_gate import read_target_account_state

RUN_ID = "RUN-ecdf507ca405"

adapter = CdmsIdentityAdapter(
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
adapter.connect()
try:
    for emp in ("004076", "001491"):
        u = adapter.snapshot_user(emp)
        a = adapter.snapshot_auth(emp)
        jh = read_target_account_state("JHEMR", emp)
        if u is None:
            print(f"CDMS {emp}: STILL ABSENT  <-- FAIL")
            continue
        types = sorted({str(r.get("FTYPE") or r.get("ftype")) for r in (a or [])})
        print(f"CDMS {emp}: user present | FDEPT={u.get('fdept')} FFREE3={u.get('ffree3')} "
              f"FSYSID={u.get('FSYSID')} | auth rows={len(a or [])} ftypes={types} "
              f"| JHEMR={'present' if jh else 'absent/failed'}")
finally:
    adapter.close()

db = SessionLocal()
try:
    fps = {
        "004076_CDMS": "ebced54d9bd422a7d496bd82c8cd301ce48e25c31949945ae6a35676a424ea1e",
        "004076_JHEMR": "9e294371a4ed4a17596634598095621238d66649e02d765c7f37acd881c0705e",
        "001491_CDMS": "dfc12cdffb62748ffd270665f971bffe122fea8413ac88046812942c7c5be93c",
        "001491_JHEMR": "f78e707d86c9cdc9c69456ada1af2bdc7bd38bd0cbb7e0fd8677754562600817",
    }
    print("\n== managed_relations per fingerprint (all statuses) ==")
    for label, fp in fps.items():
        rows = db.execute(text(
            "select target_system, status, count(*) from asset.asset_identity_managed_relations "
            "where account_fingerprint = :fp group by 1,2"), {"fp": fp}).fetchall()
        print(f"  {label}: {[tuple(r) for r in rows]}")
    print("\n== actions in apply run ==")
    acts = db.execute(text(
        "select target_system, subtask_code, status, reason_code, rows_affected, executed_at "
        "from asset.asset_identity_sync_actions where batch_id like :pat order by action_seq"),
        {"pat": f"%{RUN_ID}%"}).fetchall()
    for a in acts:
        print("  ", tuple(a))
    print("\n== pending_reconcile account backlog now ==")
    n = db.execute(text(
        "select count(*) from asset.asset_identity_managed_relations "
        "where status='pending_reconcile' and relation_type='account'")).scalar()
    print("  remaining:", n)
finally:
    db.close()
