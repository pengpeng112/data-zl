"""试点后置回读（只读）：目标实际状态 + 熔断器 + 托管关系随动。"""
from sqlalchemy import text

from app.core.db import SessionLocal
from app.services.identity_sync_executor_bridge import execute_jhemr_state_read, execute_cdms_state_read

print("=== 目标侧回读 ===")
for emp in ("003740", "001554"):
    j = execute_jhemr_state_read(emp)
    c = execute_cdms_state_read(emp)
    js = j.get("state") or {}
    cs = c.get("state") or {}
    print(f"{emp} | JHEMR: {j.get('status')} account_status={js.get('account_status')} "
          f"locked_time={js.get('locked_time')} | CDMS: {c.get('status')} "
          f"fuserstate={cs.get('fuserstate')} fchangedate={cs.get('fchangedate')}")

db = SessionLocal()
print("=== 熔断器 ===")
for r in db.execute(text(
    "SELECT breaker_key, consecutive_failures, is_open, last_failure_at, last_success_at "
    "FROM asset.asset_identity_circuit_breaker")).fetchall():
    print(f"  {r[0]}: fails={r[1]} open={r[2]} last_fail={r[3]} last_ok={r[4]}")

print("=== 托管关系随动 ===")
for r in db.execute(text(
    "SELECT person_code, target_system, status FROM asset.asset_identity_managed_relations "
    "WHERE person_code IN ('003740','001554') ORDER BY 1, 2")).fetchall():
    print(f"  {r[0]} {r[1]}: {r[2]}")

print("=== 决策幂等（重跑视角） ===")
from app.core.config import settings
from app.services.identity_sync_orchestrator import select_account_state_actions
settings.identity_run_mode = "disable_only"
settings.identity_sync_enabled = True
actions = select_account_state_actions(db, reserve_budget=False)
print("  再次选择 disables:", [e["person_code"] for e in actions["disables"]],
      "| deferred:", actions.get("deferred_budget"))
db.close()
print("AFTER_STATE_DONE")
