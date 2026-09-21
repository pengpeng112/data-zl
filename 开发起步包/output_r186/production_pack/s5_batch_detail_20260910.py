"""本窗批次 run 明细核验（只读）。"""
from sqlalchemy import text

from app.core.db import SessionLocal

RID = "RUN-e9d81ddb808c"
db = SessionLocal()

run = db.execute(text(
    "SELECT status, report_summary FROM asset.asset_identity_scheduler_runs WHERE run_id=:r"), {"r": RID}).fetchone()
s = run[1] or {}
main = s.get("main_account_sync") or {}
ac = main.get("account_state") or {}
print("run:", run[0])
for k in ("disable_persons", "success", "partial", "failed", "blocked", "actual_updated_persons",
          "target_success_actions", "target_missing_persons", "already_desired_persons",
          "backlog_pending", "deferred_budget", "unchanged"):
    print(f"  {k}: {ac.get(k)}")
print("  window:", ac.get("window"))

print("=== 失败/缺失 attempt 明细 ===")
rows = db.execute(text(
    "SELECT person_code, target_system, status, reason_code, error_class, error_code_masked "
    "FROM asset.asset_identity_account_state_attempts WHERE run_id=:r AND status != 'executed' "
    "ORDER BY id"), {"r": RID}).all()
for r in rows:
    print(f"  {r[0]} {r[1]}: {r[2]} reason={r[3]} err={r[4]}/{r[5]}")

print("=== 成功计数 ===")
ok = db.execute(text(
    "SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts WHERE run_id=:r AND status='executed'"), {"r": RID}).scalar()
print("  executed attempts:", ok)

print("=== 窗口预算状态 ===")
for r in db.execute(text(
    "SELECT b.window_key, b.limit_persons, b.opened_at, COUNT(r.id), "
    "SUM(CASE WHEN r.status='executed' THEN 1 ELSE 0 END), SUM(CASE WHEN r.status='failed' THEN 1 ELSE 0 END) "
    "FROM asset.asset_identity_window_budgets b LEFT JOIN asset.asset_identity_window_reservations r "
    "ON r.window_id=b.id GROUP BY b.id, b.window_key, b.limit_persons, b.opened_at")).fetchall():
    print(f"  {r[0]} limit={r[1]} opened={r[2]} reserved={r[3]} executed={r[4]} failed={r[5]}")

print("=== 熔断器 ===")
for r in db.execute(text(
    "SELECT breaker_key, consecutive_failures, is_open FROM asset.asset_identity_circuit_breaker")).fetchall():
    print(f"  {r[0]}: fails={r[1]} open={r[2]}")
db.close()
print("BATCH_DETAIL_DONE")
