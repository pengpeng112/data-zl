"""试点 run 明细核验（只读）。"""
import json

from sqlalchemy import text

from app.core.db import SessionLocal

RID = "RUN-66c546ec1dbc"
db = SessionLocal()

run = db.execute(text(
    "SELECT status, error_message, report_summary FROM asset.asset_identity_scheduler_runs "
    "WHERE run_id=:r"), {"r": RID}).fetchone()
print("run status:", run[0], "| error_message:", run[1])
s = run[2] or {}
main = s.get("main_account_sync") or {}
ac = main.get("account_state") or {}
print("main.status:", main.get("status"))
for k in ("disable_persons", "success", "partial", "failed", "skipped", "blocked",
          "actual_updated_persons", "target_success_actions", "target_missing_persons"):
    print(f"  {k}: {ac.get(k)}")

print("=== attempts ===")
rows = db.execute(text(
    "SELECT person_code, target_system, action, status, reason_code, after_state, "
    "error_class, error_code_masked, lock_attribution, attribution_evidence "
    "FROM asset.asset_identity_account_state_attempts WHERE run_id=:r ORDER BY id"), {"r": RID}).all()
for r in rows:
    ev = r[9] or {}
    print(f"  {r[0]} {r[1]} {r[2]} -> {r[3]} reason={r[4]} after={r[5]} err={r[6]}/{r[7]} attr={r[8]}")
    print(f"    evidence: raw_time={ev.get('target_raw_time')} rows={ev.get('rows_affected')} "
          f"gate={ev.get('gate_reason')} approval={ev.get('approval_ref')}")

print("=== subtasks ===")
for r in db.execute(text(
    "SELECT subtask_code, status, planned_count, succeeded_count, skipped_count, failed_count "
    "FROM asset.asset_identity_sync_subtasks WHERE run_id=:r"), {"r": RID}).fetchall():
    print(f"  {r[0]} | {r[1]} | planned={r[2]} succ={r[3]} skip={r[4]} fail={r[5]}")

print("=== 窗口预算 ===")
w = db.execute(text(
    "SELECT b.window_key, b.limit_persons, COUNT(r.id), "
    "SUM(CASE WHEN r.status='executed' THEN 1 ELSE 0 END) "
    "FROM asset.asset_identity_window_budgets b LEFT JOIN asset.asset_identity_window_reservations r "
    "ON r.window_id=b.id GROUP BY b.id, b.window_key, b.limit_persons")).fetchall()
print("  windows:", w)

print("=== 熔断 ===")
for r in db.execute(text(
    "SELECT breaker_key, consecutive_failures, is_open FROM asset.asset_identity_circuit_breakers")).fetchall():
    print(f"  {r[0]}: fails={r[1]} open={r[2]}")

db.close()
print("DETAIL_DONE")
