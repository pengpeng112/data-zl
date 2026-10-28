# -*- coding: utf-8 -*-
"""批9 收口（阶段③后）：读驱动统计 JSON → 登记 25 表 × 10 月窗月覆盖账
（route=HISTORICAL_BACKLOG，首组先例）+ 产出收口状态 JSON
（RECONCILED_CLOSED / OPEN_QUARANTINE(ng/nr) / FAILED / SKIPPED）。
运行：docker exec -i data-asset-api python /opt/data-asset/t1-stage/b9_closeout.py
"""
import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.reporting_pipeline.pg_repository import SqlAlchemyControlRepository
from app.services.reporting_pipeline.planner import MonthCoverageRecord

STAGE = "/opt/data-asset/t1-stage"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09", "2026-10P"]
order_doc = json.load(open(f"{STAGE}/b9_exec_order.json", encoding="utf-8"))

engine = create_engine(os.environ["APP_DB_URL"])
repo = SqlAlchemyControlRepository(sessionmaker(bind=engine))
sess = sessionmaker(bind=engine)()

# OPEN 隔离组计数（按表+批号前缀 .HISTORICAL.）
quar = {}
for item in order_doc:
    t = item["table"]
    rows = sess.execute(
        __import__("sqlalchemy").text(
            "SELECT batch_id, group_key, rows_quarantined FROM "
            "asset.asset_reporting_quarantine_groups "
            f"WHERE canonical_table = :t AND state = 'OPEN'"),
        {"t": t},
    ).fetchall()
    quar[t] = [tuple(r) for r in rows]
sess.close()

closeout = {}
for item in order_doc:
    t = item["table"]
    try:
        stats = json.load(open(f"{STAGE}/b9_backfill_{t}.json", encoding="utf-8"))
    except FileNotFoundError:
        closeout[t] = "STAT_MISSING"
        continue
    per_month = {}
    for label in MONTHS:
        s = stats.get(label)
        if not isinstance(s, dict):
            per_month[label] = f"NO_RECORD({s})"
            continue
        if s.get("skipped") == "ALREADY_RECONCILED":
            per_month[label] = "RECONCILED_CLOSED(prev)"
            continue
        if s.get("reconciled"):
            per_month[label] = "RECONCILED_CLOSED"
        elif (isinstance(s.get("apply_refused"), str)
                and "隔离组" in s["apply_refused"]):
            # 全行进隔离组被拒（首组 ICH 01月同款）：留裁定
            per_month[label] = "OPEN_QUARANTINE(all-rows-group)"
        elif s.get("verify", {}).get("state") == "QUARANTINED" or (
                s.get("verify_state") == "QUARANTINED"):
            per_month[label] = "OPEN_QUARANTINE(quality)"
        elif s.get("apply_ok") and s.get("quarantined_pending"):
            per_month[label] = (
                f"OPEN_QUARANTINE(pending g={s.get('quarantined_pending')})")
        elif s.get("apply_ok") is False:
            per_month[label] = f"APPLY_FAIL({str(s.get('apply_refused'))[:60]})"
        elif "capture" in s and s.get("capture"):
            per_month[label] = f"CAPTURE_FAIL({s['capture']})"
        elif s.get("error"):
            per_month[label] = "EXCEPTION"
        else:
            per_month[label] = (
                f"OPEN_PENDING(missing={s.get('missing')},"
                f"diffs={s.get('diffs')})")
    closeout[t] = per_month
    # 月覆盖账登记（首组形态：route=HISTORICAL_BACKLOG，business_month=YYYY-MM）
    now = datetime.now(timezone.utc)
    for label in MONTHS:
        st = per_month[label]
        failed = 0 if st.startswith("RECONCILED_CLOSED") else 1
        repo.upsert_month_coverage(MonthCoverageRecord(
            table=t,
            business_month=label[:7],  # 2026-10P → 2026-10（首组同形）
            route_or_origin="HISTORICAL_BACKLOG",
            last_reconciled_at=now,
            cycle_days=30,
            pending_slices=0,
            failed_slices=failed,
        ))
    print(f"month_coverage registered: {t} x{len(MONTHS)}", flush=True)

json.dump({"closeout": closeout, "open_quarantine": quar},
          open(f"{STAGE}/b9_closeout_20261027.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("CLOSEOUT_DONE", f"{STAGE}/b9_closeout_20261027.json", flush=True)
