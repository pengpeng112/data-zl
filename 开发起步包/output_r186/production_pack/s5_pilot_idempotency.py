"""试点收尾核验：托管关系随动（按指纹）+ 幂等重选。"""
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.identity_hmac import compute_account_fingerprint
from app.services.identity_sync_orchestrator import select_account_state_actions

db = SessionLocal()
print("=== 托管关系随动（按 attempt 指纹对账） ===")
for r in db.execute(text(
    "SELECT a.person_code, a.target_system, a.status, m.status AS rel_status "
    "FROM asset.asset_identity_account_state_attempts a "
    "LEFT JOIN asset.asset_identity_managed_relations m "
    "ON m.account_fingerprint = a.target_account_fingerprint AND m.target_system = a.target_system "
    "WHERE a.run_id='RUN-66c546ec1dbc' ORDER BY a.id")).fetchall():
    print(f"  {r[0]} {r[1]}: attempt={r[2]} relation={r[3]}")

settings.identity_run_mode = "disable_only"
settings.identity_sync_enabled = True
actions = select_account_state_actions(db, reserve_budget=False)
print("=== 幂等重选（试点后、基线未冻结） ===")
print("  disables:", [(e["person_code"], e["retry_targets"], e["done_targets"]) for e in actions["disables"]])
db.close()
print("IDEMPOTENCY_DONE")
