"""窗口 2 批次明细核验。"""
from sqlalchemy import text

from app.core.db import SessionLocal

RID = "RUN-ab9eef2c0cce"
db = SessionLocal()

run = db.execute(text(
    "SELECT status, error_message, circuit_breaker_triggered, circuit_breaker_dimension, report_summary "
    "FROM asset.asset_identity_scheduler_runs WHERE run_id=:r"), {"r": RID}).fetchone()
print("status:", run[0], "| err:", run[1], "| cb:", run[2], run[3])
s = run[4] or {}
main = s.get("main_account_sync") or {}
ac = main.get("account_state") or {}
for k in ("disable_persons", "success", "partial", "failed", "blocked",
          "actual_updated_persons", "target_success_actions", "target_missing_persons",
          "backlog_pending", "backlog_missing_retry", "missing_recovered", "deferred_budget"):
    print(f"  {k}: {ac.get(k)}")
print("  window:", ac.get("window"))
thr = s.get("threshold")
if thr:
    print("  THRESHOLD:", thr)

print("=== 非 executed attempts ===")
for r in db.execute(text(
    "SELECT person_code, target_system, status, reason_code, error_class, error_code_masked "
    "FROM asset.asset_identity_account_state_attempts WHERE run_id=:r AND status!='executed' ORDER BY id"), {"r": RID}).fetchall():
    print(f"  {r[0]} {r[1]}: {r[2]} {r[3]} {r[4]}/{r[5]}")
print("  executed:", db.execute(text(
    "SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts WHERE run_id=:r AND status='executed'"), {"r": RID}).scalar())

print("=== 窗口 ===")
for r in db.execute(text(
    "SELECT b.window_key, b.limit_persons, b.opened_at, b.closed_at, COUNT(r2.id), "
    "SUM(CASE WHEN r2.status='executed' THEN 1 ELSE 0 END) "
    "FROM asset.asset_identity_window_budgets b LEFT JOIN asset.asset_identity_window_reservations r2 "
    "ON r2.window_id=b.id GROUP BY b.id, b.window_key, b.limit_persons, b.opened_at, b.closed_at ORDER BY b.id")).fetchall():
    print(f"  {r[0]} limit={r[1]} opened={r[2]} closed={r[3]} reserved={r[4]} executed={r[5]}")
print("  breaker:", db.execute(text(
    "SELECT breaker_key, consecutive_failures, is_open FROM asset.asset_identity_circuit_breaker")).fetchall())
db.close()
print("W2_DETAIL_DONE")
