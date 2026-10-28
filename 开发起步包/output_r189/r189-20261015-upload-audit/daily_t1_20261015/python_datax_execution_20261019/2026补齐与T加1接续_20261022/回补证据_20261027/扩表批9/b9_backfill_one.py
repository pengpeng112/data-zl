# -*- coding: utf-8 -*-
"""批9 ODS 历史回补驱动·单表版 v2（进程隔离防 SIGSEGV 连坐）。
用法：python b9_backfill_one.py <TABLE>
v2 变更（对照首组/批5 先例补齐语义）：
- verify QUARANTINED 不再跳过：直接 apply 装载合法子集（QUARANTINED 批在 apply
  状态门禁内，隔离组留 OPEN 待用户裁定）——计划§五"NOT NULL 缺失走质量隔离
  合法子集+工单留账"；
- 补跑分支：stats 已记 verify_state=QUARANTINED 且未 apply 的窗，跳过 capture
  直接按存档 batch_id apply 合法子集（QUARANTINED 批不允许重 capture）；
- T1_DEBUG_TRACEBACK=1 默认开（apply 拒绝详情打印到日志，production_runtime
  既有钩子）。
"""
import os

os.environ.setdefault("T1_DEBUG_TRACEBACK", "1")

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

STAGE = "/opt/data-asset/t1-stage"
CFG = "/opt/data-asset/t1-config"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09", "2026-10P"]
GROUPS = {
    "b5": "freeze_batch5_v3.json|bindings_batch5.json",
    "b6": "freeze_batch6_v1.json|bindings_batch6.json",
    "b7": "freeze_batch7_v5.json|bindings_batch7.json",
}
TABLE = sys.argv[1].upper()
GROUP = None
ORDER = json.load(open(f"{STAGE}/b9_exec_order.json", encoding="utf-8"))
for _i in ORDER:
    if _i["table"] == TABLE:
        GROUP = _i["group"]
        break
if GROUP is None:
    print(f"UNKNOWN TABLE {TABLE}", flush=True)
    sys.exit(2)

from scripts.reporting_ctl import (  # noqa: E402
    _action_bindings_from_doc,
    _assembly_inputs,
    _target_binding_from_args,
)
from app.services.reporting_pipeline.production_runtime import (  # noqa: E402
    ProductionAssembly,
)
from app.services.reporting_pipeline.planner import TimeWindow  # noqa: E402
from sqlalchemy import create_engine, text as _sql  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.services.reporting_pipeline.pg_repository import (  # noqa: E402
    SqlAlchemyControlRepository,
)
from app.services.reporting_pipeline.runtime import unique_worker_id  # noqa: E402

TZ = timezone(timedelta(hours=8))
REF = f"T1-BACKFILL-B9-20261027:{TABLE.lower()}"
STAT_FILE = f"{STAGE}/b9_backfill_{TABLE}.json"


def month_window(label: str) -> TimeWindow:
    if label.endswith("P"):
        return TimeWindow(datetime(2026, 10, 1, tzinfo=TZ),
                          datetime(2026, 10, 26, tzinfo=TZ))
    year, month = (int(x) for x in label.split("-"))
    return TimeWindow(datetime(year, month, 1, tzinfo=TZ),
                      datetime(year + 1, 1, 1, tzinfo=TZ) if month == 12
                      else datetime(year, month + 1, 1, tzinfo=TZ))


freeze, bindings = GROUPS[GROUP].split("|")
args = argparse.Namespace(
    config=CFG, state_db=os.environ["APP_DB_URL"], stage_root=STAGE,
    bindings_file=f"{CFG}/{bindings}", runtime_config=f"{CFG}/{freeze}",
    allow_simulation=False, batch="", table=None,
    approval_ref="", executor_id="sql-target-apply-1",
)
_inputs = _assembly_inputs(args)
# 月窗慢查询处置（2026-10-27 实测复现：DPY-4024 call timeout of 600000 ms exceeded
# =build_oracle_connection_factory 默认连接级 call_timeout 600s；ODS 月窗全投影
# 冷缓存下服务端 500-700s+。处置=驱动侧组合公开工厂参数把连接级 call_timeout 提到
# 1800s、RowSource 看门狗同步 1800s：不改任何代码文件/镜像/冻结件（参数级，
# 同首组驱动租约 TTL 900→7200 先例）；硬取消能力保留。
from app.services.reporting_pipeline.source_factory import (  # noqa: E402
    build_oracle_connection_factory,
    build_row_source,
)

_rt_tables = _inputs.runtime_config.tables
_odsb = json.load(open(f"{CFG}/{bindings}", encoding="utf-8"))["sources"]["ods"]
_conn_factory = build_oracle_connection_factory(
    dsn=_odsb["dsn"], credential_ref=_odsb["credential_ref"],
    timeout_ms=1_800_000,
)


def _b9_table_source(table: str):
    return build_row_source(
        _rt_tables[table], connection_factory=_conn_factory,
        fetch_timeout_seconds=1800.0)


_inputs.table_row_source_factory = _b9_table_source
assembly = ProductionAssembly(_inputs, simulation=False)
ab = _action_bindings_from_doc(json.load(open(f"{CFG}/{bindings}", encoding="utf-8")))
binding = _target_binding_from_args(args, TABLE)

engine = create_engine(os.environ["APP_DB_URL"])
lease_repo = SqlAlchemyControlRepository(sessionmaker(bind=engine))

try:
    stats = json.load(open(STAT_FILE, encoding="utf-8"))
except FileNotFoundError:
    stats = {}


def save_stats():
    json.dump(stats, open(STAT_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def window_done(batch_day: str) -> bool:
    from datetime import date

    with engine.connect() as conn:
        row = conn.execute(_sql(
            "SELECT batch_id FROM asset.asset_reporting_batches "
            "WHERE canonical_table = :t AND business_day = :d "
            "AND batch_id LIKE '%.HISTORICAL.%' AND state = 'RECONCILED' LIMIT 1"),
            {"t": TABLE, "d": date.fromisoformat(batch_day)}).first()
    return bool(row)


def do_apply(rec: dict, batch_id: str) -> dict:
    lease = lease_repo.acquire_lease(
        f"target:10.10.8.74:1521/orcl.DBOPER.{TABLE}",
        unique_worker_id("b9backfill"), ttl_seconds=7200,
    )
    try:
        app_out = assembly.apply(
            batch_id=batch_id, binding=binding, approval_ref=REF,
            lease_resource=lease.resource, fencing_token=lease.fencing_token,
        )
    finally:
        lease_repo.release_lease(lease.resource, lease.holder,
                                 fencing_token=lease.fencing_token)
    rec["apply_ok"] = bool(app_out.get("ok"))
    rec["partition"] = app_out.get("partition")
    rec["apply_refused"] = app_out.get("refused")
    return rec, app_out


print(f"==== TABLE {TABLE} ({GROUP}, ref={REF}) ====", flush=True)
for label in MONTHS:
    t0 = time.time()
    batch_day = "2026-10-01" if label.endswith("P") else f"{label}-01"
    prior = stats.get(label)
    try:
        if isinstance(prior, dict) and prior.get("reconciled"):
            print(f"[{TABLE}][{label}] SKIP stats_reconciled", flush=True)
            continue
        if window_done(batch_day):
            stats[label] = {"skipped": "ALREADY_RECONCILED"}
            save_stats()
            print(f"[{TABLE}][{label}] SKIP already RECONCILED", flush=True)
            continue
        # 补跑分支：QUARANTINED 已在档未 apply → 直接合法子集 apply
        if (isinstance(prior, dict)
                and prior.get("verify_state") == "QUARANTINED"
                and "apply_ok" not in prior and prior.get("batch_id")):
            batch_id = prior["batch_id"]
            rec = dict(prior)
            rec["mopup"] = "legal_subset_apply"
            print(f"[{TABLE}][{label}] MOPUP legal-subset apply {batch_id}", flush=True)
        elif (isinstance(prior, dict) and prior.get("partition") is not None):
            # apply 已出 partition（全进隔离组被拒/或 quarantined_pending 未清）：
            # 重试不会改变结果，留 OPEN 待用户裁定，不覆盖 stats
            print(f"[{TABLE}][{label}] SKIP partition-recorded "
                  f"(adjudication pending)", flush=True)
            continue
        else:
            cap = assembly.capture(
                table=TABLE, business_day=batch_day, binding=binding,
                bindings=ab, mode="HISTORICAL", window=month_window(label),
            )
            if not cap.get("ok"):
                stats[label] = {"capture": cap.get("refused") or cap.get("state"),
                                "batch_id": cap.get("batch_id")}
                save_stats()
                print(f"[{TABLE}][{label}] capture FAIL", stats[label], flush=True)
                continue
            batch_id = cap["batch_id"]
            rec = {"rows": cap["rows"], "batch_id": batch_id}
            ver = assembly.verify(batch_id=batch_id)
            rec["verify_state"] = ver.get("state")
            if not ver.get("ok"):
                rec["verify"] = {"state": ver.get("state"), "rows": ver.get("rows"),
                                 "quality": ver.get("quality")}
                if ver.get("state") != "QUARANTINED":
                    # 拒绝类（暂存不完整等）：留痕，补跑时重捕
                    stats[label] = rec
                    save_stats()
                    print(f"[{TABLE}][{label}] verify {ver.get('state')} "
                          f"rows={ver.get('rows')}", flush=True)
                    continue
                # QUARANTINED：落档后走合法子集 apply（隔离组留 OPEN）
                stats[label] = rec
                save_stats()
                print(f"[{TABLE}][{label}] verify QUARANTINED "
                      f"rows={ver.get('rows')} → legal-subset apply", flush=True)
        rec, _app_out = do_apply(rec, batch_id)
        if not rec.get("apply_ok"):
            stats[label] = rec
            save_stats()
            print(f"[{TABLE}][{label}] apply FAIL", rec, flush=True)
            continue
        rc = assembly.reconcile(batch_id=batch_id, binding=binding)
        rec["reconciled"] = bool(rc.get("ok"))
        rec["missing"] = rc.get("missing_keys")
        rec["diffs"] = rc.get("content_diffs")
        rec["quarantined_pending"] = rc.get("quarantined_pending")
        stats[label] = rec
        save_stats()
        print(f"[{TABLE}][{label}]", json.dumps(
            {k: rec.get(k) for k in
             ("rows", "partition", "reconciled", "missing", "diffs",
              "quarantined_pending")}, ensure_ascii=False),
            f"cost={time.time()-t0:.0f}s", flush=True)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        stats[label] = {"error": "EXCEPTION"}
        save_stats()
        print(f"[{TABLE}][{label}] EXCEPTION", flush=True)

total_rows = sum(s.get("rows", 0) for s in stats.values() if isinstance(s, dict))
total_insert = sum((s.get("partition") or {}).get("insert", 0)
                   for s in stats.values() if isinstance(s, dict))
windows_ok = sum(1 for s in stats.values()
                 if isinstance(s, dict) and s.get("reconciled"))
print(f"DONE {TABLE}: windows={len(stats)} reconciled={windows_ok} "
      f"rows={total_rows} inserts={total_insert}", flush=True)
print("ONE_TABLE_DONE", flush=True)
