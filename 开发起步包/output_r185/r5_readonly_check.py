# -*- coding: utf-8 -*-
"""185 号 R5 只读核对三合一（N1 夜跑三行对账 / N1b docare 清单 / N2 孤儿排班）。
全部 SELECT/文件读取，零写入；在 data-asset-api 容器内执行。
"""
import json
from pathlib import Path
from datetime import datetime

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

# ---------- N1: 夜跑三行对账（平台库只读） ----------
from app.core.db import SessionLocal
from sqlalchemy import text

s = SessionLocal()
try:
    rows = s.execute(text(
        "SELECT run_id,status,circuit_breaker_triggered,circuit_breaker_dimension,"
        "candidates_total,success_count,failed_count,skipped_count,started_at,finished_at "
        "FROM asset.asset_identity_scheduler_runs "
        "WHERE run_id IN (:r1,:r2) ORDER BY started_at"
    ), {"r1": "RUN-69e87f7f27dd", "r2": "RUN-2df6cd6db381"}).mappings().all()
    out["N1_runs"] = [{k: norm(v) for k, v in r.items()} for r in rows]

    subs = []
    for rid in ("RUN-69e87f7f27dd", "RUN-2df6cd6db381"):
        for r in s.execute(text(
            "SELECT * FROM asset.asset_identity_sync_subtasks WHERE run_id=:rid ORDER BY subtask_code"
        ), {"rid": rid}).mappings().all():
            subs.append({k: norm(v) for k, v in r.items()})
    out["N1_subtasks"] = subs

    future = s.execute(text(
        "SELECT run_id,status,started_at FROM asset.asset_identity_scheduler_runs "
        "WHERE started_at >= :cutoff ORDER BY started_at"
    ), {"cutoff": "2026-09-06 12:00:00"}).mappings().all()
    out["N1_rows_after_0906_noon"] = [{k: norm(v) for k, v in r.items()} for r in future]
finally:
    s.close()

# ---------- N1b: docare 每日任务首份清单形态核对（容器内文件只读） ----------
p = Path("/opt/data-asset/evidence/docare_mismatch/list_20260906.md")
if p.is_file():
    content = p.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    out["N1b"] = {
        "exists": True,
        "bytes": p.stat().st_size,
        "line_count": len(lines),
        "head": lines[:40],
        "markers": {
            "auto_fix_or_dry": ("自动" in content) or ("dry" in content.lower()),
            "manual_group": ("人工" in content),
        },
    }
else:
    out["N1b"] = {"exists": False, "path": str(p)}

# ---------- N2: Docare 孤儿排班核对（只读，键限定，禁猜列名） ----------
# 列名证据：开发起步包/80_手麻Docare系统Oracle元数据快照.json MEDSURGERY.MED_OPERATION_MASTER
# 状态列为 OPER_STATUS（NUMBER）；值域库 confirmed：>=35 完成、-80 作废；0 的精确含义
# 【值域待确认：DOCARE.MEDSURGERY.MED_OPERATION_MASTER.OPER_STATUS=0】，本查询只回读原值。
from app.services.db_connectors import OracleConnector

def src_conn(cred, host, service):
    u, p = Path(f"/etc/data-asset/credentials/{cred}").read_text(encoding="utf-8").strip().split(":", 1)
    return OracleConnector(host=host, port=1521, database=service, user=u, password=p,
                           connection_mode="direct", oracle_client_lib_dir="/opt/oracle", timeout_ms=120000)

try:
    conn = src_conn("docare_10_10_10_68", "10.10.10.68", "docare")
    rows = conn.execute_readonly(
        "SELECT * FROM (SELECT PATIENT_ID, VISIT_ID, OPER_ID, OPER_STATUS, "
        "SCHEDULED_DATE_TIME, START_DATE_TIME, END_DATE_TIME, OPERATING_ROOM, OPERATION_NAME "
        "FROM MEDSURGERY.MED_OPERATION_MASTER "
        "WHERE PATIENT_ID=:pid AND VISIT_ID=:vid AND OPER_ID=:oid) WHERE ROWNUM<=10",
        {"pid": "c0632940", "vid": 3, "oid": 1},
        max_rows=10,
    )
    out["N2"] = [{k: norm(v) for k, v in row.items()} for row in rows]
except Exception as exc:
    out["N2"] = {"error": f"{type(exc).__name__}: {exc}"}

print("===R185_R5_BEGIN===")
print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
print("===R185_R5_END===")
