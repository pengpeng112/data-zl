"""observe 受控首跑核验（只读）：RUN-e716c99a21cc。"""
from sqlalchemy import text

from app.core.db import SessionLocal

RUN_ID = "RUN-e716c99a21cc"
db = SessionLocal()

run = db.execute(text(
    "SELECT status, candidates_total, success_count, failed_count, skipped_count, report_summary "
    "FROM asset.asset_identity_scheduler_runs WHERE run_id = :rid"), {"rid": RUN_ID}).fetchone()
print("run_status:", run[0], "candidates:", run[1], "success:", run[2], "failed:", run[3], "skipped:", run[4])
summary = run[5] or {}
asr = summary.get("account_state", {})
print("run_mode:", summary.get("run_mode"))
print("note:", summary.get("note"))
print("population:", asr.get("population"), "scanned:", asr.get("scanned"),
      "truncated:", asr.get("truncated"), "remaining:", asr.get("remaining"))
print("blocked_unknown:", asr.get("blocked_unknown"), "backlog_unapproved:", asr.get("backlog_unapproved"),
      "backlog_pending:", asr.get("backlog_pending"))
print("collection.source_complete:", (summary.get("collection") or {}).get("source_complete"))
print("collection_sources:", (summary.get("collection") or {}).get("collection_sources"))

attempts = db.execute(text(
    "SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts WHERE run_id = :rid"), {"rid": RUN_ID}).scalar()
print("attempts_this_run(应为0):", attempts)
attempts_all = db.execute(text("SELECT COUNT(*) FROM asset.asset_identity_account_state_attempts")).scalar()
print("attempts_total(应为0):", attempts_all)

decisions = db.execute(text(
    "SELECT desired_state, COUNT(*) FROM asset.asset_identity_account_state_decisions "
    "WHERE rule_version='dual_source_v1' GROUP BY desired_state ORDER BY 1")).fetchall()
print("decisions_by_state:", decisions)
src_complete = db.execute(text(
    "SELECT source_complete, COUNT(*) FROM asset.asset_identity_account_state_decisions "
    "GROUP BY source_complete")).fetchall()
print("decisions_source_complete:", src_complete)
captured = db.execute(text(
    "SELECT MIN(captured_at), MAX(captured_at) FROM asset.asset_identity_account_state_decisions")).fetchone()
print("captured_at range:", captured[0], "->", captured[1])

clock = summary.get("clock_health")
print("clock_health_sampled:", (clock or {}).get("sampled"), "healthy:", (clock or {}).get("healthy"),
      "reasons:", (clock or {}).get("reasons"))

db.close()
print("VERIFY_DONE")
