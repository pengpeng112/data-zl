# -*- coding: utf-8 -*-
"""199 首夜晨检 v4——收尾：dup 明细（含 target_system 维度）、熔断表、水位、窗口预算。"""
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
    bids = ["NTL-RUN-ce9f0ba54376-402ef13e", "NTL-RUN-ce9f0ba54376-0c59ea83"]
    ph = ":b0,:b1"
    # 1. dup 明细：同 person+action_type+target_system 才是真重复
    for r in s.execute(text(
            f"SELECT emp_no_masked, action_type, target_system, count(*) FROM asset.asset_identity_sync_actions "
            f"WHERE batch_id IN ({ph}) AND status IN ('executed','success') "
            "GROUP BY 1,2,3 HAVING count(*)>1"), {"b0": bids[0], "b1": bids[1]}).fetchall():
        say(f"[dup_same_target] {r[0]} {r[1]} {r[2]} x{r[3]}")
    say("[dup_same_target_end]")

    # 2. 两批次的动作行数与 rows_affected 合计
    for r in s.execute(text(
            f"SELECT batch_id, count(*), sum(rows_affected) FROM asset.asset_identity_sync_actions "
            f"WHERE batch_id IN ({ph}) GROUP BY 1"), {"b0": bids[0], "b1": bids[1]}).fetchall():
        say(f"[batch_rows] {r[0]} rows={r[1]} rows_affected_sum={r[2]}")
    for r in s.execute(text(
            "SELECT batch_id, status, cdms_status, jhemr_status, validation_mode, error_message "
            "FROM asset.asset_identity_sync_batches WHERE scheduler_run_id='RUN-ce9f0ba54376'"), {}).fetchall():
        say(f"[batch] {r[0]} status={r[1]} cdms={r[2]} jhemr={r[3]} mode={r[4]} err={norm(r[5])[:120]}")

    # 3. 熔断表
    for r in s.execute(text(
            "SELECT * FROM asset.asset_identity_circuit_breaker ORDER BY 1 DESC LIMIT 3")).fetchall():
        say("[circuit_breaker] " + " | ".join(norm(v) for v in r))

    # 4. 最新 run 水位
    row = s.execute(text(
        "SELECT candidate_watermark, committed_watermark, watermark_advanced, last_error_class, duration_ms "
        "FROM asset.asset_identity_scheduler_runs WHERE run_id='RUN-ce9f0ba54376'")).fetchone()
    say(f"[watermark] cand={norm(row[0])} committed={norm(row[1])} advanced={row[2]} last_err={norm(row[3])} dur_ms={row[4]}")

    # 5. 窗口预算（近 3 窗）
    for r in s.execute(text(
            "SELECT window_key, approval_ref, limit_persons, opened_at, closed_at "
            "FROM asset.asset_identity_window_budgets ORDER BY id DESC LIMIT 3")).fetchall():
        say("[window_budget] " + " | ".join(norm(v) for v in r))

    # 6. 24h 内 deactivated/新建账户侧 managed_relations 变化（停用未越预算）
    for r in s.execute(text(
            "SELECT status, relation_type, count(*) FROM asset.asset_identity_managed_relations "
            "WHERE created_at >= now() - interval '24 hours' GROUP BY 1,2")).fetchall():
        say("[managed_rel_24h] " + " | ".join(str(x) for x in r))

say("[done]")
