# -*- coding: utf-8 -*-
"""T+1 每日值守驱动（扩表 A3，2026-10-24）：当日窗 capture→verify→apply→reconcile。

值守语义（硬约定）：
- 批准不自动登记：每表批准引用形如 T1-DAILY-<业务日>:<表>，操作员先用
  reporting_ctl approval-register 人工登记（或对既有登记续期），本脚本
  只核验批准存在且有效，缺批准即打印登记命令并跳过该表，不代批；
- 不自动外发告警（R06 输入未齐）、不自动重试超过失败矩阵（单表失败
  只记录并继续下一表，恢复动作由值守操作员按 resume/retry 语义执行）；
- 日志与统计 JSON 落暂存卷（/opt/data-asset/t1-stage/daily/）。

容器内用法：
  python /app/scripts/t1_daily_run.py --tables EMR_ICH,EMR_ICH_DIAGNOSIS \
      [--business-day 2026-10-23] [--dry-run] [--allow-missing-approval]
本机隔离验收用法：--config/--state-db/--stage-root/--bindings-file/
--runtime-config 全部显式传入。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _emit(document: dict) -> None:
    print(json.dumps(document, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="t1_daily_run")
    parser.add_argument("--tables", required=True, help="逗号分隔表名清单")
    parser.add_argument("--business-day", default=None,
                        help="业务日 YYYY-MM-DD（默认=院区时区昨天）")
    parser.add_argument("--config", default="/opt/data-asset/t1-config",
                        help="任务配置目录（默认生产配置卷）")
    parser.add_argument("--state-db", default=None,
                        help="控制面 PG SQLAlchemy URL（默认取环境 APP_DB_URL）")
    parser.add_argument("--stage-root", default="/opt/data-asset/t1-stage",
                        help="暂存根目录（统计 JSON 落 <root>/daily/）")
    parser.add_argument("--bindings-file", default=None)
    parser.add_argument("--runtime-config", default=None)
    parser.add_argument("--executor-id", default="sql-target-apply-1")
    parser.add_argument("--dry-run", action="store_true",
                        help="只核验批准与装配，不执行 capture")
    parser.add_argument("--allow-missing-approval", action="store_true",
                        help="缺批准表仍执行 capture/verify（apply 会被门禁拒绝）")
    return parser


def _business_day(explicit: str | None) -> str:
    if explicit:
        return explicit
    tz = timezone(timedelta(hours=8))
    return (datetime.now(tz) - timedelta(days=1)).strftime("%Y-%m-%d")


def _approval_active(session_factory, approval_ref: str, executor_code: str,
                     target_scope: str) -> bool:
    from sqlalchemy import text

    session = session_factory()
    try:
        row = session.execute(text(
            "SELECT valid_from, valid_until FROM "
            "asset.asset_reporting_approval_refs "
            "WHERE approval_ref = :ref AND executor_code = :exec "
            "AND target_scope = :scope ORDER BY valid_until DESC LIMIT 1"
        ), {"ref": approval_ref, "exec": executor_code, "scope": target_scope}).fetchone()
        if row is None:
            return False
        now = datetime.now(timezone.utc)
        start = row[0] if row[0].tzinfo else row[0].replace(tzinfo=timezone.utc)
        end = row[1] if row[1].tzinfo else row[1].replace(tzinfo=timezone.utc)
        return bool(start <= now <= end)
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # backend 根入 sys.path：本机=backend/，容器=/app（脚本在 <root>/scripts/）
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    business_day = _business_day(args.business_day)
    tables = [name.strip() for name in args.tables.split(",") if name.strip()]
    state_db = args.state_db or os.environ.get("APP_DB_URL")
    bindings_path = args.bindings_file or str(
        Path(args.config) / "bindings_production.json")
    runtime_config_path = args.runtime_config or None
    if runtime_config_path is None:
        candidate = Path(args.config) / "freeze_production_v4.json"
        runtime_config_path = str(candidate) if candidate.exists() else None
    if not state_db:
        _emit({"ok": False, "error": "缺 --state-db 或 APP_DB_URL"})
        return 2
    for path in (bindings_path,):
        if not Path(path).exists():
            _emit({"ok": False, "error": f"绑定文件不存在: {path}"})
            return 2

    from scripts.reporting_ctl import (
        _action_bindings_from_doc,
        _assembly_inputs,
        _target_binding_from_args,
    )
    from app.services.reporting_pipeline.production_runtime import ProductionAssembly
    from app.services.reporting_pipeline.runtime import unique_worker_id
    from app.services.reporting_pipeline.pg_repository import (
        SqlAlchemyControlRepository,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    namespace = argparse.Namespace(
        config=args.config, state_db=state_db, stage_root=args.stage_root,
        bindings_file=bindings_path, runtime_config=runtime_config_path,
        allow_simulation=False, batch="", table=None,
        approval_ref="", executor_id=args.executor_id,
    )
    inputs = _assembly_inputs(namespace)
    assembly = ProductionAssembly(inputs, simulation=False)
    bindings_doc = json.loads(Path(bindings_path).read_text(encoding="utf-8"))
    action_bindings = _action_bindings_from_doc(bindings_doc)

    engine = create_engine(state_db)
    session_factory = sessionmaker(bind=engine)
    lease_repo = SqlAlchemyControlRepository(session_factory)

    daily_root = Path(args.stage_root) / "daily"
    daily_root.mkdir(parents=True, exist_ok=True)
    stats_path = daily_root / f"t1_daily_{business_day}.json"

    stats: dict = {
        "as_of": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "business_day": business_day,
        "dry_run": args.dry_run,
        "tables": {},
        "skipped_missing_approval": [],
    }
    overall_ok = True
    for table in tables:
        ref = f"T1-DAILY-{business_day}:{table}"
        target_scope = f"10.10.8.74:1521/orcl.DBOPER.{table}"
        entry: dict = {"approval_ref": ref}
        try:
            approved = _approval_active(
                session_factory, ref, args.executor_id, target_scope)
            entry["approval_active"] = approved
            if not approved and not args.allow_missing_approval:
                stats["skipped_missing_approval"].append(table)
                entry["action"] = (
                    "缺当日批准，已跳过。人工登记命令："
                    f"python /app/scripts/reporting_ctl.py approval-register "
                    f"--state-db \"$APP_DB_URL\" --approval-ref {ref} "
                    f"--executor-code {args.executor_id} "
                    f"--target-scope {target_scope} "
                    f"--registered-by <值守人> --valid-hours 24"
                )
                stats["tables"][table] = entry
                overall_ok = False
                continue
            namespace.table = table
            binding = _target_binding_from_args(namespace, table)
            if args.dry_run:
                dry = assembly.capture(
                    table=table, business_day=business_day, binding=binding,
                    bindings=action_bindings, dry_run=True)
                entry["dry_run"] = {
                    "dispatchable": dry.get("plan", {}).get("dispatchable"),
                    "blocked_by": dry.get("plan", {}).get("blocked_by"),
                }
                stats["tables"][table] = entry
                if not dry.get("plan", {}).get("dispatchable"):
                    overall_ok = False
                continue
            cap = assembly.capture(
                table=table, business_day=business_day, binding=binding,
                bindings=action_bindings)
            if not cap.get("ok"):
                entry["capture"] = cap.get("refused") or cap.get("state")
                stats["tables"][table] = entry
                overall_ok = False
                continue
            batch_id = cap["batch_id"]
            entry["batch_id"] = batch_id
            entry["rows"] = cap.get("rows")
            ver = assembly.verify(batch_id=batch_id)
            if not ver.get("ok"):
                entry["verify"] = {"state": ver.get("state"), "rows": ver.get("rows")}
                stats["tables"][table] = entry
                overall_ok = False
                continue
            lease = lease_repo.acquire_lease(
                f"target:{target_scope}", unique_worker_id("t1-daily"),
                ttl_seconds=7200)
            try:
                app_out = assembly.apply(
                    batch_id=batch_id, binding=binding, approval_ref=ref,
                    lease_resource=lease.resource,
                    fencing_token=lease.fencing_token)
            finally:
                lease_repo.release_lease(
                    lease.resource, lease.holder, fencing_token=lease.fencing_token)
            if not app_out.get("ok"):
                entry["apply"] = app_out.get("refused") or app_out.get("state")
                stats["tables"][table] = entry
                overall_ok = False
                continue
            rec = assembly.reconcile(batch_id=batch_id, binding=binding)
            entry.update(
                partition=app_out.get("partition"),
                reconciled=rec.get("ok"),
                missing=rec.get("missing_keys"),
                diffs=rec.get("content_diffs"),
                quarantined=rec.get("quarantined_pending"),
            )
            if not rec.get("ok"):
                overall_ok = False
        except Exception:  # noqa: BLE001 - 单表失败不连坐
            traceback.print_exc()
            entry["error"] = "EXCEPTION"
            overall_ok = False
        stats["tables"][table] = entry
        _emit({"table": table, "entry": entry})

    stats["ok"] = overall_ok
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    _emit({"ok": overall_ok, "stats_path": str(stats_path),
           "skipped_missing_approval": stats["skipped_missing_approval"]})
    return 0 if overall_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
