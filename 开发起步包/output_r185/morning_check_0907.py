# -*- coding: utf-8 -*-
"""185 号 N1③ 晨检（09-07）：夜跑 02:00 行 + docare 00:10 cron 自愈核对。全部只读。"""
import json
from datetime import datetime
from pathlib import Path

def norm(v):
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:2000]
    if type(v).__name__ == "LOB":
        d = v.read()
        return bytes(d).hex()[:2000] if isinstance(d, (bytes, memoryview)) else str(d)[:8000]
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)[:8000]

out = {}

from app.core.db import SessionLocal
from sqlalchemy import text

s = SessionLocal()
try:
    rows = s.execute(text(
        "SELECT run_id,status,circuit_breaker_triggered,circuit_breaker_dimension,"
        "candidates_total,success_count,failed_count,skipped_count,started_at,finished_at "
        "FROM asset.asset_identity_scheduler_runs "
        "WHERE started_at >= :cutoff ORDER BY started_at"
    ), {"cutoff": "2026-09-07 01:30:00"}).mappings().all()
    out["N3_runs"] = [{k: norm(v) for k, v in r.items()} for r in rows]

    subs = []
    for r in s.execute(text(
        "SELECT run_id,subtask_code,status,planned_count,succeeded_count,failed_count,skipped_count,"
        "report_summary FROM asset.asset_identity_sync_subtasks "
        "WHERE run_id IN (SELECT run_id FROM asset.asset_identity_scheduler_runs "
        "WHERE started_at >= :cutoff) ORDER BY run_id,subtask_code"
    ), {"cutoff": "2026-09-07 01:30:00"}).mappings().all():
        d = {k: norm(v) for k, v in r.items()}
        if d["report_summary"] and len(str(d["report_summary"])) > 500:
            d["report_summary"] = str(d["report_summary"])[:500] + "…"
        subs.append(d)
    out["N3_subtasks"] = subs
finally:
    s.close()

# docare 00:10 cron 自愈核对
p = Path("/opt/data-asset/evidence/docare_mismatch/list_20260907.md")
if p.is_file():
    content = p.read_text(encoding="utf-8", errors="replace")
    out["docare_list_0907"] = {
        "exists": True, "bytes": p.stat().st_size,
        "head": content.splitlines()[:12],
        "groups": content.count("\n## "),
    }
else:
    out["docare_list_0907"] = {"exists": False}

log = Path("/opt/data-asset/evidence/docare_mismatch/cron.log")
if log.is_file():
    txt = log.read_text(encoding="utf-8", errors="replace")
    # 只看 09-06 19:00 之后是否有新增 traceback（此前尾部为 09-06 00:10 的 ORA-12541）
    out["cron_log_tail"] = txt[-600:]

print("===R185_MORNING_BEGIN===")
print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
print("===R185_MORNING_END===")
