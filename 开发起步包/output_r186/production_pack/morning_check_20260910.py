"""2026-09-10 晨检：昨晚 02:00 observe 夜跑只读核验。"""
from sqlalchemy import text

from app.core.db import SessionLocal

db = SessionLocal()

print("=== 最近 6 次调度运行 ===")
rows = db.execute(text(
    "SELECT run_id, triggered_by, status, started_at, finished_at, circuit_breaker_triggered, "
    "error_message IS NOT NULL AS has_err "
    "FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 6")).fetchall()
for r in rows:
    print(f"  {r[0][:16]} | {r[1]} | {r[2]} | {r[3]} -> {r[4]} | cb={r[5]} | err={r[6]}")

print("=== 昨晚定时 run（最近一条 host_cron）详情 ===")
run = db.execute(text(
    "SELECT run_id, status, candidates_total, success_count, failed_count, skipped_count, report_summary "
    "FROM asset.asset_identity_scheduler_runs WHERE triggered_by='host_cron_modified_sync' "
    "ORDER BY started_at DESC LIMIT 1")).fetchone()
rid = run[0]
print(f"  run_id={rid} status={run[1]} candidates={run[2]} succ={run[3]} fail={run[4]} skip={run[5]}")
s = run[6] or {}
main = s.get("main_account_sync") or s
ac = main.get("account_state") or {}
print("  note:", main.get("note") or s.get("note"), "| run_mode:", main.get("run_mode") or s.get("run_mode"))
print("  population:", ac.get("population"), "| scanned:", ac.get("scanned"),
      "| source_complete(main):", main.get("source_complete"))
ch = main.get("clock_health") or s.get("clock_health") or {}
print("  clock_health sampled:", ch.get("sampled"), "healthy:", ch.get("healthy"),
      "reasons:", ch.get("reasons"))
coll = main.get("collection") or s.get("collection") or {}
print("  collection source_complete:", coll.get("source_complete"),
      "| sources:", {k: v.get("status") for k, v in (coll.get("collection_sources") or {}).items()})

print("=== 该 run 子任务 ===")
subs = db.execute(text(
    "SELECT subtask_code, status, planned_count, succeeded_count, skipped_count, failed_count "
    "FROM asset.asset_identity_sync_subtasks WHERE run_id = :rid"), {"rid": rid}).fetchall()
for r in subs:
    print(f"  {r[0]} | {r[1]} | planned={r[2]} succ={r[3]} skip={r[4]} fail={r[5]}")

print("=== 零写核验 ===")
print("  attempts_total:", db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts")).scalar())
print("  attempts_this_run:", db.execute(text(
    "SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts WHERE run_id=:rid"), {"rid": rid}).scalar())
print("  window_budgets:", db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_window_budgets")).scalar())
print("  reservations:", db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_window_reservations")).scalar())

print("=== 决策采集（应增长且 captured_at=昨晚） ===")
print("  by_state:", db.execute(text(
    "SELECT desired_state, COUNT(*) FROM asset.asset_identity_account_state_decisions GROUP BY 1 ORDER BY 1")).fetchall())
print("  total/complete:", db.execute(text(
    "SELECT COUNT(*), SUM(CASE WHEN source_complete THEN 1 ELSE 0 END) "
    "FROM asset.asset_identity_account_state_decisions")).fetchone())
print("  captured range:", db.execute(text(
    "SELECT MIN(captured_at), MAX(captured_at) FROM asset.asset_identity_account_state_decisions")).fetchone())

print("=== 门禁状态未漂移 ===")
print("  executors:", db.execute(text(
    "SELECT executor_code, enabled FROM asset.asset_action_executors "
    "WHERE executor_code LIKE '%ACCOUNT%' ORDER BY 1")).fetchall())
print("  scopes:", db.execute(text(
    "SELECT scope_type, approval_ref, status, action FROM asset.asset_identity_action_scopes")).fetchall())
wm = db.execute(text(
    "SELECT watermark_key, watermark_status, last_run_at FROM asset.asset_identity_sync_watermarks "
    "WHERE source_code='HIS'")).fetchall()
print("  HIS watermarks:", wm)

db.close()
print("MORNING_CHECK_DONE")
