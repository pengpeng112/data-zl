# -*- coding: utf-8 -*-
"""第二夜晨检补充2：alerts 实际列名自适应 + outbox 12 行状态 + 09-25 动作。零写入。"""
from sqlalchemy import text
from app.core.db import SessionLocal

def norm(v):
    if v is None:
        return ""
    return str(v)[:400]

with SessionLocal() as s:
    cols = [r[0] for r in s.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='asset' AND table_name='asset_identity_sync_alerts' "
        "ORDER BY ordinal_position")).fetchall()]
    print("[alert_cols]", cols, flush=True)
    sel = [c for c in ("id", "created_at", "run_id", "alert_type", "severity") if c in cols]
    detail = next((c for c in ("detail", "message_text", "description", "payload", "context") if c in cols), None)
    if detail:
        sel.append(detail)
    for r in s.execute(text(
            f"SELECT {', '.join(sel)} FROM asset.asset_identity_sync_alerts "
            "WHERE created_at >= '2026-09-23 12:00:00' ORDER BY id")).fetchall():
        print("[alert] " + " | ".join(norm(v) for v in r), flush=True)

    for r in s.execute(text(
            "SELECT status, count(*) FROM asset.asset_dict_sync_outbox GROUP BY 1")).fetchall():
        print(f"[outbox_all] {r[0]} n={r[1]}", flush=True)
    for r in s.execute(text(
            "SELECT max(created_at) FROM asset.asset_dict_sync_outbox")).fetchall():
        print(f"[outbox_last] {norm(r[0])}", flush=True)

    for r in s.execute(text(
            "SELECT action_type, target_system, status, count(*) FROM asset.asset_identity_sync_actions "
            "WHERE batch_id IN (SELECT batch_id FROM asset.asset_identity_sync_batches "
            "WHERE scheduler_run_id='RUN-894125353bee') GROUP BY 1,2,3 ORDER BY 1,2,3")).fetchall():
        print(f"[n3_action] {r[0]} {r[1]} {r[2]} n={r[3]}", flush=True)
print("[done]", flush=True)
