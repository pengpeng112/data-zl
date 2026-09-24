# -*- coding: utf-8 -*-
"""199 第二夜晨检（2026-09-24 02:00 run）——203 L1 授权只读核验。
覆盖：run/子任务/计数守恒、main_account_sync、already_managed 幂等、pending_reconcile、
熔断、同目标重复动作、outbox、action 状态、停用窗口、enable 执行器、24h 关系对账、告警。
顺带只读记录 09-25 夜 run（附加观察，不作门禁）。零写入。"""
from sqlalchemy import text
from app.core.db import SessionLocal

def norm(v):
    if v is None:
        return ""
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:200]
    return str(v)[:500]

def say(*a):
    print(*a, flush=True)

with SessionLocal() as s:
    # 0. 近 5 个 run 总览（定位 09-24 与 09-25 夜跑）
    runs = s.execute(text(
        "SELECT run_id, status, started_at, duration_ms, candidates_total, success_count, "
        "failed_count, skipped_count, circuit_breaker_triggered, circuit_breaker_dimension "
        "FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 5")).fetchall()
    for r in runs:
        say(f"[run] {r[0]} status={r[1]} started={norm(r[2])} dur_ms={r[3]} cand={r[4]} "
            f"ok={r[5]} fail={r[6]} skip={r[7]} cb={r[8]} cb_dim={norm(r[9])}")

    # 找 09-24 02:00 ±3h 的 run 作为第二夜主对象
    night2 = s.execute(text(
        "SELECT run_id FROM asset.asset_identity_scheduler_runs "
        "WHERE started_at >= '2026-09-24 00:30:00' AND started_at < '2026-09-24 05:00:00' "
        "ORDER BY started_at LIMIT 1")).scalar()
    say(f"[night2_run] {night2}")

    if not night2:
        say("[night2_run] NOT_FOUND —— 第二夜无 run，按 203 §5.2 记 FAILED_RECOVERABLE（只生成恢复包，不补跑）")
    else:
        for r in s.execute(text(
                "SELECT subtask_code, status, planned_count, succeeded_count, failed_count, skipped_count "
                "FROM asset.asset_identity_sync_subtasks WHERE run_id=:r ORDER BY subtask_code"),
                {"r": night2}).fetchall():
            say(f"[subtask] {r[0]} status={r[1]} planned={r[2]} ok={r[3]} fail={r[4]} skip={r[5]}")

        # main_account_sync 专项
        row = s.execute(text(
            "SELECT status, planned_count, succeeded_count, failed_count, skipped_count, error_classes "
            "FROM asset.asset_identity_sync_subtasks WHERE run_id=:r AND subtask_code='main_account_sync'"),
            {"r": night2}).fetchone()
        if row:
            say(f"[main_account_sync] status={row[0]} planned={row[1]} ok={row[2]} fail={row[3]} "
                f"skip={row[4]} err_classes={norm(row[5])}")
        else:
            say("[main_account_sync] MISSING")

        # 批次与动作
        bids = [r[0] for r in s.execute(text(
            "SELECT batch_id FROM asset.asset_identity_sync_batches WHERE scheduler_run_id=:r"),
            {"r": night2}).fetchall()]
        say(f"[batches] {bids}")
        for r in s.execute(text(
                "SELECT batch_id, status, cdms_status, jhemr_status, validation_mode, error_message "
                "FROM asset.asset_identity_sync_batches WHERE scheduler_run_id=:r"),
                {"r": night2}).fetchall():
            say(f"[batch] {r[0]} status={r[1]} cdms={r[2]} jhemr={r[3]} mode={norm(r[4])} err={norm(r[5])[:150]}")
        if bids:
            ph = ",".join(f":b{i}" for i in range(len(bids)))
            params = {f"b{i}": b for i, b in enumerate(bids)}
            for r in s.execute(text(
                    f"SELECT action_type, target_system, status, count(*), sum(rows_affected) "
                    f"FROM asset.asset_identity_sync_actions WHERE batch_id IN ({ph}) "
                    "GROUP BY 1,2,3 ORDER BY 1,2,3"), params).fetchall():
                say(f"[action_group] {r[0]} {r[1]} {r[2]} n={r[3]} rows={r[4]}")
            # 同 person+action_type+target_system 真重复
            dups = s.execute(text(
                f"SELECT emp_no_masked, action_type, target_system, count(*) "
                f"FROM asset.asset_identity_sync_actions WHERE batch_id IN ({ph}) "
                "AND status IN ('executed','success') GROUP BY 1,2,3 HAVING count(*)>1"),
                params).fetchall()
            say(f"[dup_same_target] count={len(dups)}")
            for d in dups[:10]:
                say(f"[dup_detail] {d[0]} {d[1]} {d[2]} x{d[3]}")

        # run 水位
        row = s.execute(text(
            "SELECT candidate_watermark, committed_watermark, watermark_advanced, last_error_class "
            "FROM asset.asset_identity_scheduler_runs WHERE run_id=:r"), {"r": night2}).fetchone()
        if row:
            say(f"[watermark] cand={norm(row[0])} committed={norm(row[1])} advanced={row[2]} last_err={norm(row[3])}")

    # 通用（与第二夜无绑定）：熔断、pending_reconcile、停用窗口、执行器、24h 关系、告警
    for r in s.execute(text(
            "SELECT * FROM asset.asset_identity_circuit_breaker ORDER BY 1 DESC LIMIT 3")).fetchall():
        say("[circuit_breaker] " + " | ".join(norm(v) for v in r))

    for r in s.execute(text(
            "SELECT status, relation_type, count(*) FROM asset.asset_identity_managed_relations "
            "GROUP BY 1,2 ORDER BY 1,2")).fetchall():
        say(f"[managed_rel_all] {r[0]} {r[1]} n={r[2]}")
    pend = s.execute(text(
        "SELECT count(*) FROM asset.asset_identity_managed_relations WHERE status='pending_reconcile'")).scalar()
    say(f"[pending_reconcile_total] {pend}")

    for r in s.execute(text(
            "SELECT window_key, approval_ref, limit_persons, opened_at, closed_at "
            "FROM asset.asset_identity_window_budgets ORDER BY id DESC LIMIT 3")).fetchall():
        say("[window_budget] " + " | ".join(norm(v) for v in r))

    try:
        for r in s.execute(text(
                "SELECT executor_code, enabled FROM asset.asset_action_executors "
                "WHERE executor_code ILIKE '%ACCOUNT%' OR executor_code ILIKE '%identity%' "
                "ORDER BY 1")).fetchall():
            say(f"[executor] {r[0]} enabled={r[1]}")
    except Exception as e:
        say(f"[executor] schema_probe_failed {norm(e)[:120]}")

    for r in s.execute(text(
            "SELECT status, relation_type, count(*) FROM asset.asset_identity_managed_relations "
            "WHERE created_at >= '2026-09-24 00:00:00' GROUP BY 1,2")).fetchall():
        say(f"[managed_rel_since_0924] {r[0]} {r[1]} n={r[2]}")

    # outbox 近 48h
    try:
        for r in s.execute(text(
                "SELECT status, count(*) FROM asset.asset_outbox_messages "
                "WHERE created_at >= now() - interval '48 hours' GROUP BY 1")).fetchall():
            say(f"[outbox_48h] {r[0]} n={r[1]}")
    except Exception as e:
        say(f"[outbox] probe_failed {norm(e)[:120]}")

    # 告警：09-23 首夜以来全部，标已知/未知
    for r in s.execute(text(
            "SELECT id, created_at, run_id, alert_type, severity, message "
            "FROM asset.asset_identity_sync_alerts WHERE created_at >= '2026-09-23 12:00:00' "
            "ORDER BY id")).fetchall():
        say(f"[alert] id={r[0]} at={norm(r[1])} run={norm(r[2])} type={r[3]} sev={r[4]} msg={norm(r[5])[:160]}")

say("[done]")
