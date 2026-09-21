"""2026-09-11 晨检：昨晚 02:00 定时 disable_only 夜 + 窗口状态 + 门禁无漂移。"""
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal

db = SessionLocal()

print("=== 最近 5 次调度运行 ===")
for r in db.execute(text(
    "SELECT run_id, status, started_at, finished_at, circuit_breaker_triggered, "
    "error_message IS NOT NULL FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 5")).fetchall():
    print(f"  {r[0][:16]} | {r[1]} | {r[2]} -> {r[3]} | cb={r[4]} | err={r[5]}")

print("=== 昨晚定时 run 详情 ===")
run = db.execute(text(
    "SELECT run_id, status, report_summary FROM asset.asset_identity_scheduler_runs "
    "WHERE triggered_by='host_cron_modified_sync' AND started_at > '2026-09-11 01:00' "
    "ORDER BY started_at DESC LIMIT 1")).fetchone()
if run is None:
    print("  !! 昨晚无定时 run")
else:
    rid = run[0]
    s = run[1 + 1] or {}
    main = s.get("main_account_sync") or {}
    ac = main.get("account_state") or {}
    print(f"  run_id={rid} status={run[1]}")
    print(f"  run_mode={main.get('run_mode')} | note={main.get('note')}")
    print(f"  disable_persons={ac.get('disable_persons')} deferred={ac.get('deferred_budget')} "
          f"backlog_pending={ac.get('backlog_pending')} missing_retry={ac.get('backlog_missing_retry')}")
    ch = main.get("clock_health") or {}
    print(f"  clock sampled={ch.get('sampled')} healthy={ch.get('healthy')} reasons={ch.get('reasons')}")
    for tgt, data in (ch.get("targets") or {}).items():
        print(f"    {tgt}: offset {data.get('offset_min_s')}..{data.get('offset_max_s')} stable={data.get('stable')}")
    att = db.execute(text(
        "SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts WHERE run_id=:r"), {"r": rid}).scalar()
    print(f"  attempts={att}")

print("=== 窗口/预算状态 ===")
for r in db.execute(text(
    "SELECT b.window_key, b.limit_persons, b.opened_at, b.closed_at, COUNT(r.id), "
    "SUM(CASE WHEN r.status='executed' THEN 1 ELSE 0 END) "
    "FROM asset.asset_identity_window_budgets b LEFT JOIN asset.asset_identity_window_reservations r "
    "ON r.window_id=b.id GROUP BY b.id, b.window_key, b.limit_persons, b.opened_at, b.closed_at "
    "ORDER BY b.id")).fetchall():
    print(f"  {r[0]} limit={r[1]} opened={r[2]} closed={r[3]} reserved={r[4]} executed={r[5]}")

print("=== 门禁无漂移 ===")
print("  executors:", db.execute(text(
    "SELECT executor_code, enabled FROM asset.asset_action_executors WHERE executor_code LIKE '%ACCOUNT%' ORDER BY 1")).fetchall())
print("  scopes:", db.execute(text(
    "SELECT scope_type, status, action FROM asset.asset_identity_action_scopes")).fetchall())
print("  attempts_total:", db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts")).scalar())
print("  executed_total:", db.execute(text(
    "SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts WHERE status='executed'")).scalar())
print("  decisions:", db.execute(text(
    "SELECT desired_state, COUNT(*) FROM asset.asset_identity_account_state_decisions GROUP BY 1 ORDER BY 1")).fetchall())
print("  breaker:", db.execute(text(
    "SELECT breaker_key, consecutive_failures, is_open FROM asset.asset_identity_circuit_breaker")).fetchall())
db.close()
print("MORNING_CHECK_20260911_DONE")
