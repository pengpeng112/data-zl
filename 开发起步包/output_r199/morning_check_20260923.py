# -*- coding: utf-8 -*-
"""199 首夜晨检 v2——只读、逐段输出、按实际列名自适应。"""
import sys
from sqlalchemy import text
from app.core.db import SessionLocal

def norm(v):
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:200]
    return str(v)[:400]

def say(*a):
    print(*a, flush=True)

def cols(s, t):
    return [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name=:t ORDER BY ordinal_position"), {"t": t}).fetchall()]

def has(s, t):
    return bool(s.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='asset' AND table_name=:t"),
        {"t": t}).fetchall())

with SessionLocal() as s:
    say(f"[db_now] {s.execute(text('SELECT now()')).scalar()}")

    say("[tables] " + ", ".join(r[0] for r in s.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='asset' AND table_name LIKE '%identity%' ORDER BY table_name")).fetchall()))

    # 1. 最新 3 个 scheduler run
    rc = cols(s, "asset_identity_scheduler_runs")
    say("[run_cols] " + ", ".join(rc))
    want = [c for c in ["run_id","status","run_mode","trigger_by","circuit_breaker_triggered",
                        "circuit_breaker_dimension","candidates_total","success_count","failed_count",
                        "skipped_count","started_at","finished_at"] if c in rc]
    for r in s.execute(text(
            f"SELECT {', '.join(want)} FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 3")).fetchall():
        say("[run] " + " | ".join(f"{c}={norm(v)}" for c, v in zip(want, r)))

    latest = s.execute(text(
        "SELECT run_id FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 1")).scalar()
    say(f"[latest_run_id] {latest}")

    # 2. 子任务
    sc = cols(s, "asset_identity_sync_subtasks")
    say("[subtask_cols] " + ", ".join(sc))
    swant = [c for c in ["subtask_code","status","planned_count","succeeded_count","failed_count",
                         "skipped_count","reason","error_classes"] if c in sc]
    for r in s.execute(text(
            f"SELECT {', '.join(swant)} FROM asset.asset_identity_sync_subtasks WHERE run_id=:r ORDER BY subtask_code"),
            {"r": latest}).fetchall():
        say("[subtask] " + " | ".join(f"{c}={norm(v)}" for c, v in zip(swant, r)))

    # 3. 动作表（列名自适应）
    for tbl in ("asset_identity_sync_actions","asset_identity_actions"):
        if not has(s, tbl):
            continue
        ac = cols(s, tbl)
        say(f"[{tbl}_cols] " + ", ".join(ac))
        run_col = next((c for c in ("run_id","scheduler_run_id","run_ref") if c in ac), None)
        dim = [c for c in ["action_type","target_system","action_status","status"] if c in ac]
        if run_col and dim:
            for r in s.execute(text(
                    f"SELECT {', '.join(dim)}, count(*) FROM asset.{tbl} WHERE {run_col}=:r "
                    f"GROUP BY {', '.join(dim)} ORDER BY 1,2"), {"r": latest}).fetchall():
                say(f"[{tbl}.by_type] " + " | ".join(norm(v) for v in r))
            if "person_id" in ac:
                dup = s.execute(text(
                    "SELECT count(*) FROM (SELECT person_id, action_type FROM asset.%s "
                    "WHERE %s=:r AND status IN ('executed','success') "
                    "GROUP BY person_id, action_type HAVING count(*)>1) x" % (tbl, run_col)),
                    {"r": latest}).scalar()
                say(f"[{tbl}.dup_person_action] {dup}")
        tc = next((c for c in ("created_at","executed_at","updated_at") if c in ac), None)
        if tc:
            n, mn, mx = s.execute(text(
                f"SELECT count(*), min({tc}), max({tc}) FROM asset.{tbl}")).fetchone()
            say(f"[{tbl}.total] {n} min={norm(mn)} max={norm(mx)}")
        break

    # 4. managed_relations / pending_reconcile
    for tbl in ("asset_identity_managed_relations",):
        mc = cols(s, tbl)
        say(f"[{tbl}_cols] " + ", ".join(mc))
        st = next((c for c in ("status","relation_status") if c in mc), None)
        relt = next((c for c in ("relation_type","rtype","kind") if c in mc), None)
        grp = [c for c in [st, relt] if c]
        if grp:
            for r in s.execute(text(
                    f"SELECT {', '.join(grp)}, count(*) FROM asset.{tbl} GROUP BY {', '.join(grp)} ORDER BY 1")).fetchall():
                say(f"[{tbl}.agg] " + " | ".join(norm(v) for v in r))

    # 5. 告警 24h
    for tbl in ("asset_identity_alerts","asset_identity_alert_events","asset_identity_sync_alerts"):
        if not has(s, tbl):
            continue
        ac = cols(s, tbl)
        n = s.execute(text(
            f"SELECT count(*) FROM asset.{tbl} WHERE created_at >= now() - interval '24 hours'")).scalar()
        say(f"[{tbl}.24h] {n}")
        if n:
            lvl = next((c for c in ("severity","level","risk_level","alert_type") if c in ac), None)
            if lvl:
                for r in s.execute(text(
                        f"SELECT {lvl}, count(*) FROM asset.{tbl} "
                        "WHERE created_at >= now() - interval '24 hours' GROUP BY 1")).fetchall():
                    say(f"[{tbl}.by_level] {norm(r[0])} = {r[1]}")

    # 6. 执行器状态
    if has(s, "asset_action_executors"):
        ec = cols(s, "asset_action_executors")
        say("[executor_cols] " + ", ".join(ec))
        name_c = next((c for c in ("executor_code","code","name","executor_name") if c in ec), None)
        en_c = next((c for c in ("enabled","is_enabled","active") if c in ec), None)
        if name_c and en_c:
            for r in s.execute(text(
                    f"SELECT {name_c}, {en_c} FROM asset.asset_action_executors ORDER BY 1")).fetchall():
                say(f"[executor] {norm(r[0])} enabled={norm(r[1])}")

    # 7. 预算/窗口表
    say("[window_tables] " + (", ".join(r[0] for r in s.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='asset' AND (table_name LIKE '%window%' OR table_name LIKE '%budget%')")).fetchall()) or "无"))

    # 8. 夜跑日志尾部（容器 stdout 不取，查平台内错误分类）
    for tbl in ("asset_identity_sync_subtasks",):
        ec_col = next((c for c in ("error_classes","errors") if c in cols(s, tbl)), None)
        if ec_col:
            for r in s.execute(text(
                    f"SELECT subtask_code, {ec_col} FROM asset.{tbl} "
                    "WHERE run_id IN (SELECT run_id FROM asset.asset_identity_scheduler_runs "
                    "ORDER BY started_at DESC LIMIT 2) AND {0} IS NOT NULL AND {0}::text NOT IN ('','{{}}')".format(ec_col))).fetchall():
                say(f"[err_classes] {norm(r[0])} {norm(r[1])[:300]}")

say("[done]")
