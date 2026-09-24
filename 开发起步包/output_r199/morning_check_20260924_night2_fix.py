# -*- coding: utf-8 -*-
"""第二夜晨检补充：outbox 正确表名 + 告警（09-23 12:00 以来）。零写入。"""
from sqlalchemy import text
from app.core.db import SessionLocal

def norm(v):
    if v is None:
        return ""
    return str(v)[:400]

with SessionLocal() as s:
    tbls = [r[0] for r in s.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='asset' AND table_name ILIKE '%outbox%'")).fetchall()]
    print("[outbox_tables]", tbls, flush=True)
    for t in tbls:
        cnt = s.execute(text(f"SELECT count(*) FROM asset.{t}")).scalar()
        print(f"[outbox_total] {t} n={cnt}", flush=True)
        try:
            for r in s.execute(text(
                    f"SELECT status, count(*) FROM asset.{t} "
                    "WHERE created_at >= now() - interval '48 hours' GROUP BY 1")).fetchall():
                print(f"[outbox_48h] {t} {r[0]} n={r[1]}", flush=True)
        except Exception as e:
            # 无 created_at 列时降级：全量按状态
            for r in s.execute(text(
                    f"SELECT status, count(*) FROM asset.{t} GROUP BY 1")).fetchall():
                print(f"[outbox_all] {t} {r[0]} n={r[1]}", flush=True)

    for r in s.execute(text(
            "SELECT id, created_at, run_id, alert_type, severity, message "
            "FROM asset.asset_identity_sync_alerts WHERE created_at >= '2026-09-23 12:00:00' "
            "ORDER BY id")).fetchall():
        print(f"[alert] id={r[0]} at={norm(r[1])} run={norm(r[2])} type={r[3]} sev={r[4]} msg={norm(r[5])[:160]}", flush=True)

    # 09-25 run 的批次动作（附加观察）
    for r in s.execute(text(
            "SELECT action_type, target_system, status, count(*) FROM asset.asset_identity_sync_actions "
            "WHERE batch_id IN (SELECT batch_id FROM asset.asset_identity_sync_batches "
            "WHERE scheduler_run_id='RUN-894125353bee') GROUP BY 1,2,3 ORDER BY 1,2,3")).fetchall():
        print(f"[n3_action] {r[0]} {r[1]} {r[2]} n={r[3]}", flush=True)
print("[done]", flush=True)
