# -*- coding: utf-8 -*-
"""199 首夜晨检 v3——追查：2 条 error 告警、main_account_sync partial 原因、
动作类型聚合（经 batch 关联）、窗口预算、熔断表、24h run 数。全部只读。"""
from sqlalchemy import text
from app.core.db import SessionLocal

def norm(v):
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:200]
    return str(v)[:600]

def say(*a):
    print(*a, flush=True)

def cols(s, t):
    return [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name=:t ORDER BY ordinal_position"), {"t": t}).fetchall()]

with SessionLocal() as s:
    latest = "RUN-ce9f0ba54376"

    # 1. 24h 内告警明细
    ac = cols(s, "asset_identity_sync_alerts")
    say("[alert_cols] " + ", ".join(ac))
    sel = [c for c in ["id","created_at","run_id","subtask_code","target_system","severity",
                       "alert_type","alert_code","emp_no_masked","message","error_message","detail"] if c in ac]
    for r in s.execute(text(
            f"SELECT {', '.join(sel)} FROM asset.asset_identity_sync_alerts "
            "WHERE created_at >= now() - interval '24 hours' ORDER BY created_at")).fetchall():
        say("[alert] " + " | ".join(f"{c}={norm(v)}" for c, v in zip(sel, r)))

    # 2. main_account_sync 的 report_summary（最新 run + 昨日手动 run 对照）
    for rid in (latest, "RUN-2ad5a120c108"):
        row = s.execute(text(
            "SELECT status, planned_count, succeeded_count, failed_count, skipped_count, report_summary "
            "FROM asset.asset_identity_sync_subtasks WHERE run_id=:r AND subtask_code='main_account_sync'"),
            {"r": rid}).fetchone()
        if row:
            say(f"[main@{rid[:12]}] status={row[0]} planned={row[1]} succ={row[2]} fail={row[3]} skip={row[4]}")
            say(f"[main@{rid[:12]}.summary] {norm(row[5])[:1200]}")

    # 3. 24h 内 run 数（防重复触发）
    n = s.execute(text(
        "SELECT count(*) FROM asset.asset_identity_scheduler_runs WHERE started_at >= now() - interval '24 hours'")).scalar()
    say(f"[runs_24h] {n}")

    # 4. 动作聚合：经 batches 找最新 run 的 batch
    bc = cols(s, "asset_identity_sync_batches")
    say("[batch_cols] " + ", ".join(bc))
    run_col_b = next((c for c in ("run_id","scheduler_run_id") if c in bc), None)
    if run_col_b:
        bids = [r[0] for r in s.execute(text(
            f"SELECT batch_id FROM asset.asset_identity_sync_batches WHERE {run_col_b}=:r"),
            {"r": latest}).fetchall()] if "batch_id" in bc else []
        say(f"[batches_of_latest] {bids}")
        if bids:
            ph = ",".join(f":b{i}" for i in range(len(bids)))
            par = {f"b{i}": b for i, b in enumerate(bids)}
            for r in s.execute(text(
                    f"SELECT action_type, target_system, status, count(*) FROM asset.asset_identity_sync_actions "
                    f"WHERE batch_id IN ({ph}) GROUP BY 1,2,3 ORDER BY 1,2,3"), par).fetchall():
                say("[action_agg] " + " | ".join(str(x) for x in r))
            dup = s.execute(text(
                f"SELECT count(*) FROM (SELECT emp_no_masked, action_type, count(*) c "
                f"FROM asset.asset_identity_sync_actions WHERE batch_id IN ({ph}) "
                "AND status IN ('executed','success') GROUP BY 1,2 HAVING count(*)>1) x"), par).scalar()
            say(f"[action_dup_person_type] {dup}")
            # 失败/异常动作明细（不含人员标识，emp_no 已掩码列仍不输出值）
            for r in s.execute(text(
                    f"SELECT action_type, target_system, status, reason_code, error_class, count(*) "
                    f"FROM asset.asset_identity_sync_actions WHERE batch_id IN ({ph}) "
                    "AND status NOT IN ('executed','success') GROUP BY 1,2,3,4,5 ORDER BY 1"), par).fetchall():
                say("[action_nonsuccess] " + " | ".join(str(x) for x in r))
    else:
        # 回退：按时间窗聚合今日 02:00-02:05 动作
        for r in s.execute(text(
                "SELECT action_type, target_system, status, count(*) FROM asset.asset_identity_sync_actions "
                "WHERE created_at >= '2026-09-23 01:55:00' AND created_at < '2026-09-23 02:10:00' "
                "GROUP BY 1,2,3 ORDER BY 1,2,3")).fetchall():
            say("[action_agg_by_time] " + " | ".join(str(x) for x in r))

    # 5. 窗口预算现状
    wb = cols(s, "asset_identity_window_budgets")
    say("[window_budget_cols] " + ", ".join(wb))
    rows = s.execute(text("SELECT * FROM asset.asset_identity_window_budgets ORDER BY 1 DESC LIMIT 3")).fetchall()
    for r in rows:
        say("[window_budget] " + " | ".join(norm(v) for v in r))

    # 6. 熔断表
    cb = cols(s, "asset_identity_circuit_breaker")
    say("[cb_cols] " + ", ".join(cb))
    rows = s.execute(text("SELECT * FROM asset.asset_identity_circuit_breaker ORDER BY 1 DESC LIMIT 3")).fetchall()
    for r in rows:
        say("[circuit_breaker] " + " | ".join(norm(v) for v in r))

    # 7. watermark（候选水位推进）
    row = s.execute(text(
        "SELECT candidate_watermark, committed_watermark, watermark_advanced, last_error_class "
        "FROM asset.asset_identity_scheduler_runs WHERE run_id=:r"), {"r": latest}).fetchone()
    say(f"[watermark] cand={norm(row[0])} committed={norm(row[1])} advanced={row[2]} last_err={norm(row[3])}")

say("[done]")
