# -*- coding: utf-8 -*-
"""批9 ODS 历史回补驱动（25 表 × 10 月窗，[2026-01-01, 2026-10-26)）。
范式=首组 backfill_months.py（2026-10-24 先例）：
- 表外层、月窗内层；每表用各自批的 freeze/bindings 配置对；
- 批准 T1-BACKFILL-B9-20261027:<小写表名>（已由 approval-register CLI 预登记 72h）；
- 每窗 capture(HISTORICAL,--window)→verify→apply(租约+批准)→reconcile；
- 单窗失败不连坐：留痕（含 RETRYABLE 批次）继续后续窗；
- 批号含 .HISTORICAL. 与 T+1 日批互不干扰；月窗>5万行自动分片续捕（设计行为）。
执行顺序由 b9_exec_order.json（差距普查产出）给出；统计落
/opt/data-asset/t1-stage/b9_backfill_<table>.json + 汇总 b9_backfill_summary_20261027.json。
运行：docker exec -i data-asset-api python /opt/data-asset/t1-stage/b9_backfill_driver.py
（nohup 后台，日志同目录 b9_backfill_driver.log）
"""
import argparse
import json
import os
import time
import traceback
from datetime import datetime, timedelta, timezone

STAGE = "/opt/data-asset/t1-stage"
CFG = "/opt/data-asset/t1-config"
H = "2026-10-26"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09", "2026-10P"]
GROUPS = {
    "b5": "freeze_batch5_v3.json|bindings_batch5.json",
    "b6": "freeze_batch6_v1.json|bindings_batch6.json",
    "b7": "freeze_batch7_v5.json|bindings_batch7.json",
}

order_doc = json.load(open(f"{STAGE}/b9_exec_order.json", encoding="utf-8"))
# 形如 [{"table": "...", "group": "b5", "window_total": 123}, ...]（小差距先通、大表殿后）

from scripts.reporting_ctl import (  # noqa: E402
    _action_bindings_from_doc,
    _assembly_inputs,
    _target_binding_from_args,
)
from app.services.reporting_pipeline.production_runtime import (  # noqa: E402
    ProductionAssembly,
)
from app.services.reporting_pipeline.planner import TimeWindow  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.services.reporting_pipeline.pg_repository import (  # noqa: E402
    SqlAlchemyControlRepository,
)
from app.services.reporting_pipeline.runtime import unique_worker_id  # noqa: E402

TZ = timezone(timedelta(hours=8))


def month_window(label: str) -> TimeWindow:
    if label.endswith("P"):  # 十月部分月：[10-01, H)
        start = datetime(2026, 10, 1, tzinfo=TZ)
        end = datetime(2026, 10, 26, tzinfo=TZ)
    else:
        year, month = (int(x) for x in label.split("-"))
        start = datetime(year, month, 1, tzinfo=TZ)
        end = (
            datetime(year + 1, 1, 1, tzinfo=TZ) if month == 12
            else datetime(year, month + 1, 1, tzinfo=TZ)
        )
    return TimeWindow(start, end)


def make_args(freeze: str, bindings: str) -> argparse.Namespace:
    return argparse.Namespace(
        config=CFG, state_db=os.environ["APP_DB_URL"], stage_root=STAGE,
        bindings_file=f"{CFG}/{bindings}", runtime_config=f"{CFG}/{freeze}",
        allow_simulation=False, batch="", table=None,
        approval_ref="", executor_id="sql-target-apply-1",
    )


engine = create_engine(os.environ["APP_DB_URL"])
lease_repo = SqlAlchemyControlRepository(sessionmaker(bind=engine))
from sqlalchemy import text as _sql_text  # noqa: E402

assemblies = {}  # group -> (assembly, ab, args)
summary = {}


def window_done(table: str, batch_day: str) -> bool:
    """幂等保护：该表该业务日已有 RECONCILED 的 HISTORICAL 批次则跳过
    （防中断重跑/双跑重复装载；留痕 stats 里）。"""
    from datetime import date

    with engine.connect() as conn:
        row = conn.execute(_sql_text(
            "SELECT batch_id, state FROM asset.asset_reporting_batches "
            "WHERE canonical_table = :t AND business_day = :d "
            "AND mode = 'HISTORICAL' AND state = 'RECONCILED' LIMIT 1"),
            {"t": table, "d": date.fromisoformat(batch_day)}).first()
    return bool(row)



for item in order_doc:
    table, grp = item["table"], item["group"]
    if grp not in assemblies:
        freeze, bindings = GROUPS[grp].split("|")
        a = make_args(freeze, bindings)
        assemblies[grp] = (
            ProductionAssembly(_assembly_inputs(a), simulation=False),
            _action_bindings_from_doc(json.load(
                open(f"{CFG}/{bindings}", encoding="utf-8"))),
            a,
        )
    assembly, ab, args = assemblies[grp]
    binding = _target_binding_from_args(args, table)
    ref = f"T1-BACKFILL-B9-20261027:{table.lower()}"
    stats = {}
    print(f"==== TABLE {table} ({grp}, ref={ref}) ====", flush=True)
    for label in MONTHS:
        t0 = time.time()
        batch_day = "2026-10-01" if label.endswith("P") else f"{label}-01"
        try:
            if window_done(table, batch_day):
                stats[label] = {"skipped": "ALREADY_RECONCILED"}
                print(f"[{table}][{label}] SKIP already RECONCILED", flush=True)
                continue
            cap = assembly.capture(
                table=table, business_day=batch_day, binding=binding,
                bindings=ab, mode="HISTORICAL", window=month_window(label),
            )
            if not cap.get("ok"):
                stats[label] = {"capture": cap.get("refused") or cap.get("state"),
                                "batch_id": cap.get("batch_id")}
                print(f"[{table}][{label}] capture FAIL", stats[label], flush=True)
                continue
            batch_id = cap["batch_id"]
            rec = {"rows": cap["rows"], "batch_id": batch_id}
            ver = assembly.verify(batch_id=batch_id)
            rec["verify_state"] = ver.get("state")
            if not ver.get("ok"):
                rec["verify"] = {"state": ver.get("state"), "rows": ver.get("rows"),
                                 "quality": ver.get("quality")}
                stats[label] = rec
                print(f"[{table}][{label}] verify {ver.get('state')} rows={ver.get('rows')}", flush=True)
                continue
            lease = lease_repo.acquire_lease(
                f"target:10.10.8.74:1521/orcl.DBOPER.{table}",
                unique_worker_id("b9backfill"), ttl_seconds=7200,
            )
            try:
                app_out = assembly.apply(
                    batch_id=batch_id, binding=binding, approval_ref=ref,
                    lease_resource=lease.resource, fencing_token=lease.fencing_token,
                )
            finally:
                lease_repo.release_lease(lease.resource, lease.holder,
                                         fencing_token=lease.fencing_token)
            rec["apply_ok"] = bool(app_out.get("ok"))
            rec["partition"] = app_out.get("partition")
            rec["apply_refused"] = app_out.get("refused")
            if not app_out.get("ok"):
                stats[label] = rec
                print(f"[{table}][{label}] apply FAIL", rec, flush=True)
                continue
            rc = assembly.reconcile(batch_id=batch_id, binding=binding)
            rec["reconciled"] = bool(rc.get("ok"))
            rec["missing"] = rc.get("missing_keys")
            rec["diffs"] = rc.get("content_diffs")
            rec["quarantined_pending"] = rc.get("quarantined_pending")
            stats[label] = rec
            print(f"[{table}][{label}]", json.dumps(
                {k: rec.get(k) for k in
                 ("rows", "partition", "reconciled", "missing", "diffs",
                  "quarantined_pending")}, ensure_ascii=False),
                f"cost={time.time()-t0:.0f}s", flush=True)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            stats[label] = {"error": "EXCEPTION"}
            print(f"[{table}][{label}] EXCEPTION", flush=True)
    out = f"{STAGE}/b9_backfill_{table}.json"
    json.dump(stats, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total_rows = sum(s.get("rows", 0) for s in stats.values() if isinstance(s, dict))
    total_insert = sum((s.get("partition") or {}).get("insert", 0)
                       for s in stats.values() if isinstance(s, dict))
    windows_ok = sum(1 for s in stats.values()
                     if isinstance(s, dict) and s.get("reconciled"))
    summary[table] = {"windows": len(stats), "windows_reconciled": windows_ok,
                      "rows": total_rows, "insert": total_insert,
                      "stat_file": out}
    json.dump(summary, open(f"{STAGE}/b9_backfill_summary_20261027.json", "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"DONE {table}: windows={len(stats)} reconciled={windows_ok} "
          f"rows={total_rows} inserts={total_insert}", flush=True)

print("B9_BACKFILL_ALL_DONE", flush=True)
