"""R189-T1 统一T+1抽取工程控制命令入口（包 R189-T1-ENGINEERING-20261019-v1.2）。

子命令按批次逐步落地：
- E01：list / validate（离线、只读任务包 JSON，不连库不外发）
- E02+：plan / simulate / capture / verify / apply / reconcile / delivery /
  resume / retry / daily-report / ticket-export。
- A02（2026-10-22）：capture/verify/apply/reconcile/delivery/retry 六个
  动作接口已提供，生产连接工厂尚未接线（doctor列明）；缺真实输入即拒绝
  （REFUSED_MISSING_*），不退回内存模拟；--allow-simulation 显式隔离验证；
  delivery 省端接口未接通如实 PENDING_RECEIPT；daily-report 缺省业务日
  改为院区时区昨天（不再硬编码 2026-10-19），无 --state-db 且未显式
  允许模拟时报错退出（拒绝静默回退模拟）。

退出码：0=通过；1=动作未完成（如实记录）；2=用法/配置/装配拒绝；3=结构
校验失败；4=业务校验失败。所有命令输出结构化 JSON（stdout），关键结论
同时给中文摘要字段。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_CONFIG_DIR = (
    REPO_ROOT / "开发起步包" / "output_r189" / "r189-20261015-upload-audit"
    / "daily_t1_20261015" / "python_datax_execution_20261019"
)

IMPLEMENTED_COMMANDS = (
    "list", "validate", "daily-report", "ticket-export",
    "plan", "simulate", "resume",
    "capture", "verify", "apply", "reconcile", "delivery", "retry",
    "backfill-plan", "gap-diff-plan", "publish-order",
    "freeze-config", "approval-register", "outbox-send", "outbox-inspect",
    "doctor",
)


def _state_db_url(args: argparse.Namespace) -> str | None:
    """Use a protected process environment without printing credential URLs."""
    return getattr(args, "state_db", None) or os.environ.get("APP_REPORTING_CONTROL_DB_URL")


def _emit(payload: dict) -> None:
    # reconfigure 幂等：避免重复 TextIOWrapper 包裹导致 buffer 被旧包装关闭
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _load_bundle(config_dir: Path):
    from app.services.reporting_pipeline.seed_loader import load_seed_bundle

    if not config_dir.exists():
        _emit({"ok": False, "error": f"配置目录不存在: {config_dir}", "exit_code": 2})
        raise SystemExit(2)
    try:
        return load_seed_bundle(config_dir)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        _emit({"ok": False, "error": f"任务包装载失败: {exc!r}", "exit_code": 2})
        raise SystemExit(2)


def cmd_list(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.contracts import as_dict

    bundle = _load_bundle(Path(args.config))
    rows = []
    for task in bundle.tasks:
        verdicts = {
            layer.value: verdict.status.value
            for layer, verdict in task.layer_verdicts().items()
        }
        rows.append(
            {
                "index": task.index,
                "canonical_table": task.canonical_table,
                "business_name": task.business_name,
                "engine": task.engine.value,
                "applicability": task.applicability.value,
                "sources": [s.object_id for s in task.source_candidates],
                "dual_source": task.dual_source(),
                "route_policy": bool(task.associations.route_policy_ref),
                "monthly_rescan": bool(task.associations.monthly_rescan_policy_ref),
                "datetime_dependency_ticket": task.associations.datetime_dependency_ticket,
                "deadline_state": task.associations.deadline_state.value,
                "human_view_ticket_state": task.associations.human_view_ticket_state,
                "writer_handoff_state": task.associations.running_writer_handoff_state,
                "enabled": task.enabled,
                "readiness": verdicts,
            }
        )
    _emit(
        {
            "ok": True,
            "package_id": bundle.package_id,
            "config_dir": str(Path(args.config)),
            "count": len(rows),
            "items": rows,
            "summary": {
                "readiness_layers": as_dict(bundle.readiness_summary()),
                "source_groups": bundle.source_group_counts(),
                "dual_source": [t.canonical_table for t in bundle.dual_source_tasks()],
                "not_provided": [t.canonical_table for t in bundle.not_provided_tasks()],
            },
        }
    )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.seed_loader import validate_bundle

    bundle = _load_bundle(Path(args.config))
    report = validate_bundle(bundle)
    structure_ok = report["validation"]["structure_ok"]
    ready_violations = report["validation"]["ready_violations"]
    ok = structure_ok and not ready_violations
    report["ok"] = ok
    report["exit_code"] = 0 if ok else (3 if not structure_ok else 4)
    report["结论"] = (
        "任务包结构校验通过；77项保持 disabled/UNKNOWN，生产层全部 UNKNOWN（未知不可变READY）"
        if ok else "任务包校验失败，详见 structural_problems/ready_violations"
    )
    _emit(report)
    return int(report["exit_code"])


def cmd_daily_report(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.manual_tickets import seed_tickets_from_package
    from app.services.reporting_pipeline.reports import build_daily_report
    from app.services.reporting_pipeline.repositories import InMemoryControlRepository
    from app.services.reporting_pipeline.seed_loader import _load_json

    bundle = _load_bundle(Path(args.config))
    state_db = _state_db_url(args)
    allow_simulation = bool(getattr(args, "allow_simulation", False))
    business_day = getattr(args, "business_day", None)
    if business_day is None:
        # 默认业务日 = 院区时区昨天（锚点语义），不再硬编码固定日期
        from datetime import datetime, timedelta, timezone

        local = datetime.now(timezone.utc).astimezone(
            timezone(timedelta(hours=8))
        )
        business_day = (local - timedelta(days=1)).date().isoformat()
    if state_db:
        # 真实持久化状态（R06）：读取耐久仓储，不再每次新建内存仓储
        from app.services.reporting_pipeline.pg_repository import (
            SqlAlchemyControlRepository,
        )
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(state_db)
        repository = SqlAlchemyControlRepository(sessionmaker(bind=engine))
        simulation = False
        state_note = "durable_state_db_configured"
    else:
        if not allow_simulation:
            _emit(
                {
                    "ok": False,
                    "error": (
                        "缺 --state-db：生产日报入口必须指向真实持久化状态库；"
                        "显式隔离验证请加 --allow-simulation（拒绝静默回退模拟）"
                    ),
                    "exit_code": 2,
                }
            )
            return 2
        repository = InMemoryControlRepository()
        simulation = True
        state_note = "simulation_memory_state"
    seed_doc = _load_json(Path(args.config) / "E01已知人工工单种子.json")
    registry = seed_tickets_from_package(seed_doc)
    report = build_daily_report(
        business_day=business_day,
        repository=repository,
        bundle=bundle,
        ticket_registry=registry,
        simulation=simulation,
    )
    payload = report.to_dict()
    payload["ok"] = True
    payload["state_source"] = state_note
    payload["结论"] = (
        "日报来自真实持久化仓储（PG）" if not simulation else
        "本地日报（模拟状态源，simulation=true）：77项 deadline 全部 "
        "UNCONFIGURED→SLA_UNKNOWN；relay 处于 WAITING_INTEGRATION_SETUP；"
        "无生产运行数据，不虚构进度"
    )
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    _emit(payload)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """离线计划：冻结业务日锚点 + 逐任务动作级就绪（不连库）。"""
    from datetime import datetime, timezone

    from app.services.reporting_pipeline.contracts import PipelineAction
    from app.services.reporting_pipeline.planner import freeze_daily_anchor

    bundle = _load_bundle(Path(args.config))
    now = datetime.now(timezone.utc)
    anchor = freeze_daily_anchor(now)
    rows = []
    for task in bundle.tasks:
        rows.append(
            {
                "canonical_table": task.canonical_table,
                "enabled": task.enabled,
                "action_readiness": task.action_readiness(),
                "action_gate": {
                    action.value: _gate_summary(task, action)
                    for action in PipelineAction
                },
            }
        )
    runnable = [
        r["canonical_table"] for r in rows
        if r["enabled"] and r["action_readiness"].get("CAPTURE") == "READY"
    ]
    _emit(
        {
            "ok": True,
            "business_day": anchor.business_day.isoformat(),
            "business_window": anchor.business_window().fingerprint(),
            "anchor_frozen_at": anchor.frozen_at.isoformat(),
            "planning_only": True,
            "simulation": True,
            "runnable_if_dispatched": runnable,
            "items": rows,
            "结论": (
                f"离线计划：业务日 {anchor.business_day}（半开窗冻结）；"
                f"77项 disabled，可派发=0（READ_READY 未核），动作级就绪已分层列出"
            ),
        }
    )
    return 0


def _gate_summary(task, action) -> dict:
    from app.services.reporting_pipeline.contracts import ContractViolation

    try:
        task.validate_action(action)
        return {"allowed": True}
    except ContractViolation as exc:
        return {"allowed": False, "blocked_by": str(exc)[:160]}


def cmd_backfill_plan(args: argparse.Namespace) -> int:
    """B02 离线拆窗预演：[start,end) 月→日→小时递归 + 互斥叶窗覆盖验收。"""
    from datetime import datetime

    from app.services.reporting_pipeline.backfill import (
        plan_backfill_windows,
        uniform_profile_estimate,
    )

    try:
        start = datetime.fromisoformat(args.start)
        end = datetime.fromisoformat(args.end)
    except ValueError as exc:
        _emit({"ok": False, "error": f"日期格式非法: {exc}", "exit_code": 2})
        return 2
    estimate = uniform_profile_estimate(args.rows_per_day, args.bytes_per_row)
    out = plan_backfill_windows(
        start, end, estimate,
        max_rows_per_leaf=args.max_rows_per_leaf,
        max_bytes_per_leaf=args.max_bytes_per_leaf,
    )
    coverage_ok = out["coverage"]["ok"]
    _emit(
        {
            "ok": coverage_ok,
            "planning_only": True,
            "profile_model": (
                f"均匀画像 rows_per_day={args.rows_per_day} "
                f"bytes_per_row={args.bytes_per_row}（预演假设，正式执行前用实测画像替换）"
            ),
            "totals": out["totals"],
            "coverage": out["coverage"],
            "leaves": out["leaves"],
            "结论": (
                f"历史范围 {start.date()}→{end.date()} 拆出 {out['totals']['leaves']} 个叶窗"
                f"（keyset 回退 {out['totals']['keyset_leaves']}），"
                + ("覆盖无空洞/重叠 ✔" if coverage_ok else "覆盖校验失败 ✘")
            ),
        }
    )
    return 0 if coverage_ok else 4


def cmd_gap_diff_plan(args: argparse.Namespace) -> int:
    """B02 缺口差异框架：产出双侧键集只读 SQL 模板 + 框架演示（真实执行等批准）。"""
    from datetime import datetime

    from app.services.reporting_pipeline.backfill import (
        build_gap_diff,
        gap_diff_keyset_sql,
    )
    from app.services.reporting_pipeline.planner import TimeWindow

    window = TimeWindow(datetime.fromisoformat(args.start), datetime.fromisoformat(args.end))
    source_sql = gap_diff_keyset_sql(args.source_object, args.key_expr, args.anchor)
    target_sql = gap_diff_keyset_sql(args.target_object, args.key_expr, args.anchor)
    # 框架演示（显式 DEMO 标记）：模拟键集证明分账逻辑，不连任何库
    demo = build_gap_diff(
        "DEMO_TABLE", window,
        source_keys=["k1", "k2", "k2", "k3"],
        target_keys={"k2", "k3", "k9"},
        content_equal=lambda k: k != "k3",
    ).to_dict()
    _emit(
        {
            "ok": True,
            "planning_only": True,
            "table": args.table,
            "window": window.fingerprint(),
            "source_keyset_sql": source_sql,
            "target_keyset_sql": target_sql,
            "demo_ledger": demo,
            "note": (
                "真实双侧键集读取（源=ODS只读已确认通道，目标=前置机只读凭据）与"
                "差异装载均等批准后执行；本命令只产出模板与框架分账演示"
            ),
        }
    )
    return 0


def cmd_publish_order(args: argparse.Namespace) -> int:
    """B02 父子发布顺序编排：父先子后波次 + 已有父复用 + 缺父等待自动唤醒。"""
    from app.services.reporting_pipeline.backfill import build_publish_order

    bundle = _load_bundle(Path(args.config))

    def _parent_name(raw) -> str:
        return raw["parent"] if isinstance(raw, dict) else str(raw)

    tasks = [
        {
            "index": t.index,
            "canonical_table": t.canonical_table,
            "declared_parent_candidates": [
                {"parent": _parent_name(p)} for p in t.declared_parent_candidates
            ],
        }
        for t in bundle.tasks
    ]
    if args.tables:
        keep = set(args.tables.split(","))
        tasks = [t for t in tasks if t["canonical_table"] in keep]
    out = build_publish_order(tasks)
    _emit(
        {
            "ok": True,
            "planning_only": True,
            "wave_count": len(out["waves"]),
            "waves": out["waves"],
            "tables": out["tables"],
            "waiting_parent_tables": out["waiting_parent_tables"],
            "semantics": out["semantics"],
            "结论": (
                f"{len(tasks)} 项编排为 {len(out['waves'])} 波（父先子后）；"
                f"缺父等待 {len(out['waiting_parent_tables'])} 项（父提交后自动唤醒）"
            ),
        }
    )
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """模拟日轮：内存仓储 + 假适配器，输出显式 simulation 标记（R05）。"""
    from datetime import datetime, timezone

    from app.services.reporting_pipeline.runtime import build_simulation_cycle

    bundle = _load_bundle(Path(args.config))
    ran: list[str] = []

    def fake_capture(context, task):
        ran.append(task.canonical_table)
        return {"ok": True, "rows": 0}

    service = build_simulation_cycle(bundle, capture_fn=fake_capture)
    outcome = service.run_day(datetime.now(timezone.utc))
    _emit(
        {
            "ok": True,
            **outcome,
            "结论": (
                "模拟日轮（simulation=true，内存状态）：77项 disabled → 无可派发"
                "任务，周期状态如实（无任务=NO_WORK/WAITING），不产生任何生产动作"
            ),
        }
    )
    return 0


def cmd_ticket_export(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.manual_tickets import seed_tickets_from_package
    from app.services.reporting_pipeline.seed_loader import _load_json

    bundle = _load_bundle(Path(args.config))
    seed_doc = _load_json(Path(args.config) / "E01已知人工工单种子.json")
    registry = seed_tickets_from_package(seed_doc)
    tickets = registry.export_machine_json()
    output = Path(args.output)
    output.write_text(
        json.dumps(
            {"package_id": bundle.package_id, "tickets": tickets,
             "never_auto_close": True},
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    _emit(
        {
            "ok": True,
            "count": len(tickets),
            "output": str(output),
            "结论": f"人工视图整改工单机器JSON已导出（{len(tickets)} 张，OPEN 状态，不自动关单）",
        }
    )
    return 0


# ---------------------------------------------------------------------------
# 批1 新增命令：freeze-config / approval-register / outbox-send /
# outbox-inspect / resume --execute
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_freeze_config(args: argparse.Namespace) -> int:
    """批1-1：首组四表候选 → 完整 TaskSpec 冻结件（路径/版本/哈希显式）。"""
    import re as _re
    from datetime import datetime, timedelta, timezone

    from app.services.reporting_pipeline.runtime_config import (
        RuntimeConfigError,
        build_freeze_document,
        build_table_document,
    )

    config_dir = Path(args.config)
    evidence_dir = config_dir / "2026补齐与T加1接续_20261022" / "核验证据_20261022"
    a01_path = (
        config_dir / "2026补齐与T加1接续_20261022"
        / "A01_首组运行配置冻结_v2候选_20261022.json"
    )
    target_dict_path = evidence_dir / "target_dict_bulk.json"
    views_bulk_path = evidence_dir / "ods_views_bulk.json"
    snapshot_path = Path(args.metadata_snapshot)
    for path in (a01_path, target_dict_path, views_bulk_path, snapshot_path):
        if not path.exists():
            _emit({"ok": False, "error": f"输入文件不存在: {path}", "exit_code": 2})
            return 2

    a01 = json.loads(a01_path.read_text(encoding="utf-8"))
    target_dict = json.loads(target_dict_path.read_text(encoding="utf-8"))
    views_bulk = json.loads(views_bulk_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    override_doc = {}
    if args.override and Path(args.override).exists():
        override_doc = json.loads(Path(args.override).read_text(encoding="utf-8"))

    # 目标列字典：{table: [ {name,type,length,nullable} ]}
    columns_by_table: dict[str, list[dict]] = {}
    for col in target_dict.get("columns") or []:
        columns_by_table.setdefault(col["TABLE_NAME"], []).append(
            {
                "name": col["COLUMN_NAME"],
                "target_type": (
                    f"{col['DATA_TYPE']}({col['DATA_LENGTH']})"
                    if col.get("DATA_LENGTH") and col["DATA_TYPE"].startswith("VAR")
                    else col["DATA_TYPE"]
                ),
                "nullable": col.get("NULLABLE") != "N",
                "data_length": col.get("DATA_LENGTH"),
            }
        )
    # 源视图 DDL 别名覆盖证明（目标列 ⊆ 视图暴露列）
    def view_aliases(view_name: str) -> set[str]:
        ddl = (
            snapshot.get("schemas", {}).get("ODS", {}).get("views", {})
            .get(view_name, {}).get("ddl", "")
        )
        return {
            a.upper()
            for a in _re.findall(r"as\s+([A-Za-z_][A-Za-z0-9_]+)", ddl or "", _re.IGNORECASE)
        }

    source_inputs = [
        {"path": str(a01_path), "sha256": _sha256_file(a01_path), "role": "A01候选"},
        {"path": str(target_dict_path), "sha256": _sha256_file(target_dict_path), "role": "目标字典(DBOPER)"},
        {"path": str(views_bulk_path), "sha256": _sha256_file(views_bulk_path), "role": "源视图定义哈希"},
        {"path": str(snapshot_path), "sha256": _sha256_file(snapshot_path), "role": "08元数据快照(视图DDL)"},
    ]
    definitions = (views_bulk.get("definitions") or {})
    defaults = {"max_rows_per_slice": 50000, "max_bytes_per_slice": 268435456, "max_attempts": 3}
    tables: dict[str, dict] = {}
    coverage_problems: list[str] = []
    for name, table_cfg in (a01.get("tables") or {}).items():
        target_table = table_cfg["target"]["table"]
        cols = columns_by_table.get(target_table)
        if not cols:
            _emit({"ok": False, "error": f"目标字典缺表 {target_table}", "exit_code": 3})
            return 3
        view_name = table_cfg["source"]["object"]
        aliases = view_aliases(view_name)
        missing = [c["name"] for c in cols if c["name"].upper() not in aliases]
        if missing:
            coverage_problems.append(f"{name}: 视图未暴露 {len(missing)} 列（如 {missing[:3]}）")
        system_time_column = (
            table_cfg.get("system_time_column")
            if isinstance(table_cfg.get("system_time_column"), str)
            and table_cfg.get("system_time_column")
            else None
        )
        projection = [
            {
                "name": c["name"],
                "target_type": c["target_type"],
                "source_expression": c["name"],
                "nullable": c["nullable"],
                "data_length": c["data_length"],
            }
            for c in sorted(cols, key=lambda item: item["name"])
            if c["name"] != system_time_column
        ]
        parent_cfg = table_cfg.get("parent")
        source_override = (override_doc.get("sources") or {}).get(
            table_cfg["source"].get("source_group")
        )
        target_override = (override_doc.get("targets") or {}).get(name)
        dialect = (source_override or {}).get("dialect", "oracle")
        tables[name] = build_table_document(
            canonical_table=name,
            business_name=table_cfg.get("business_name", name),
            engine=table_cfg.get("engine", "PYTHON"),
            modes=["T1", "HISTORICAL"],
            source_group=table_cfg["source"]["source_group"],
            dialect=dialect,
            source_object=(
                (source_override or {}).get("object")
                or f"ODS.{table_cfg['source']['object']}"
            ),
            credential_ref=(
                (source_override or {}).get("credential_ref")
                or table_cfg.get("credential_ref")
                or "container-credentials:ods_8_216"
            ),
            target_instance=(
                (target_override or {}).get("instance")
                or f"{table_cfg['target']['instance']}"
            ),
            tenant=(target_override or {}).get("tenant") or table_cfg["target"]["tenant"],
            target_table=(
                (target_override or {}).get("table") or table_cfg["target"]["table"]
            ),
            stable_key=table_cfg["key"]["candidate"],
            anchor_column=(
                "DATETIME"
                if not str(table_cfg.get("business_anchor", {}).get("column", "DATETIME")).startswith("DATETIME")
                else "DATETIME"
            ),
            anchor_inherited_from_parent=bool(table_cfg.get("parent")),
            projection=projection,
            change_mode=table_cfg.get("change_evidence", {}).get("mode", "SNAPSHOT_DIFF"),
            budget={**defaults, **(table_cfg.get("budget") or {})},
            object_sha256=(
                (definitions.get(view_name) or {}).get("sha256")
            ),
            system_time_column=system_time_column,
            receipt_table=table_cfg.get("receipt_table")
            if isinstance(table_cfg.get("receipt_table"), str)
            and table_cfg.get("receipt_table").startswith(("DBOPER", "t1_"))
            else None,
            parent=(
                {"table": parent_cfg["table"], "key_column": (
                    "DCS_ID" if name == "EMR_ICH_DIAGNOSIS" else "ICH_ID"
                )}
                if parent_cfg else None
            ),
            notes={
                "anchor_evidence": table_cfg.get("business_anchor", {}).get("verified_by", ""),
                "key_evidence": table_cfg.get("key", {}).get("verified_by", ""),
                "view_column_coverage": "verified" if not missing else f"missing={len(missing)}",
            },
        )
    if coverage_problems and not args.allow_view_gap:
        _emit({
            "ok": False,
            "error": "视图列覆盖不完整，拒绝冻结（--allow-view-gap 可强制但会留 notes）",
            "problems": coverage_problems,
            "exit_code": 3,
        })
        return 3
    environment = args.environment
    document = build_freeze_document(
        environment=environment,
        tables=tables,
        source_inputs=source_inputs,
        frozen_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        notes={
            "coverage_problems": coverage_problems or [],
            "candidate_h": a01.get("candidate_h", {}),
            "enabled": "全部 false（候选停用；启用另出冻结走 A05c）",
        },
    )
    output = Path(args.output)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    # 自校验：装载即验哈希
    from app.services.reporting_pipeline.runtime_config import (
        load_frozen_runtime_config,
    )

    try:
        loaded = load_frozen_runtime_config(output)
        _emit({
            "ok": True,
            "output": str(output),
            "environment": loaded.environment,
            "tables": sorted(loaded.tables),
            "config_fingerprint": loaded.config_fingerprint,
            "结论": (
                f"冻结件已生成并自校验通过（{len(loaded.tables)} 表，"
                f"environment={loaded.environment}，enabled 全 false）"
            ),
        })
        return 0
    except RuntimeConfigError as exc:
        _emit({"ok": False, "error": f"冻结件自校验失败: {exc}", "exit_code": 3})
        return 3


def cmd_approval_register(args: argparse.Namespace) -> int:
    """批1-2c：登记耐久批准（管理动作；管道永不自批）。"""
    from datetime import datetime, timedelta, timezone

    from app.services.reporting_pipeline.production_apply import (
        ProductionApplyError,
        register_approval,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    state_db = _state_db_url(args)
    if not state_db:
        _emit({"ok": False, "error": "approval-register 需要 --state-db", "exit_code": 2})
        return 2
    engine = create_engine(state_db)
    now = datetime.now(timezone.utc)
    try:
        record = register_approval(
            sessionmaker(bind=engine),
            approval_ref=args.approval_ref,
            executor_code=args.executor_code,
            target_scope=args.target_scope,
            valid_from=now,
            valid_until=now + timedelta(hours=int(args.valid_hours)),
            registered_by=args.registered_by,
            note=args.note,
        )
    except ProductionApplyError as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    record["结论"] = (
        f"批准已登记: {args.approval_ref}（{args.executor_code} → {args.target_scope}，"
        f"有效期 {args.valid_hours} 小时；管道装载时只读核验）"
    )
    _emit({"ok": True, **record})
    return 0


def _outbox_repository(args: argparse.Namespace):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.services.reporting_pipeline.pg_repository import (
        SqlAlchemyControlRepository,
    )

    state_db = _state_db_url(args)
    if not state_db:
        return None
    engine = create_engine(state_db)
    return SqlAlchemyControlRepository(sessionmaker(bind=engine))


def cmd_outbox_send(args: argparse.Namespace) -> int:
    """批1-6：独立 outbox sender（一轮或常驻循环；不同步 HTTP 卡抽取）。"""
    from app.services.reporting_pipeline.outbox_daemon import (
        DaemonConfig,
        OutboxDaemon,
        OutboxDaemonError,
        build_relay_client_from_env,
    )

    repository = _outbox_repository(args)
    if repository is None:
        _emit({"ok": False, "error": "outbox-send 需要 --state-db", "exit_code": 2})
        return 2
    try:
        client = build_relay_client_from_env()
    except OutboxDaemonError as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    daemon = OutboxDaemon(
        repository, client,
        config=DaemonConfig(
            interval_seconds=float(args.interval),
            max_cycles=int(args.max_cycles) if args.max_cycles else None,
        ),
    )
    summary = daemon.run_once() if not args.loop else daemon.run_loop()
    summary["ok"] = True
    summary["结论"] = (
        f"outbox 本轮派发完成：send={summary.get('send_attempted', 0)}，"
        f"newly_queued={summary.get('newly_queued', 0)}，polls={summary.get('polls', 0)}"
    )
    _emit(summary)
    return 0


def cmd_outbox_inspect(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.outbox_daemon import inspect_outbox

    repository = _outbox_repository(args)
    if repository is None:
        _emit({"ok": False, "error": "outbox-inspect 需要 --state-db", "exit_code": 2})
        return 2
    payload = inspect_outbox(repository)
    payload["ok"] = True
    payload["结论"] = (
        "outbox 巡检：" + "，".join(
            f"{key}={value}" for key, value in payload["summary"].items()
        ) + "（PAUSED_AUTH/NEEDS_ATTENTION 需人工）"
    )
    _emit(payload)
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    """恢复视图（--execute 时按恢复矩阵实际执行下一动作）。"""
    from app.services.reporting_pipeline.recovery import RecoveryService
    from app.services.reporting_pipeline.repositories import InMemoryControlRepository

    state_db = _state_db_url(args)
    if state_db:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.reporting_pipeline.pg_repository import (
            SqlAlchemyControlRepository,
        )

        engine = create_engine(state_db)
        repository = SqlAlchemyControlRepository(sessionmaker(bind=engine))
        simulation = False
    else:
        repository = InMemoryControlRepository()
        simulation = True
    execute = bool(getattr(args, "execute", False))
    service = RecoveryService(repository)
    actions = [a.to_dict() for a in service.resume_all()]
    executed: list[dict] = []
    if execute and not simulation:
        from app.services.reporting_pipeline.production_runtime import AssemblyRefused

        try:
            assembly, inputs = _build_assembly(args)
        except (AssemblyRefused, SystemExit):
            assembly = None
        if assembly is None:
            executed.append({"ok": False, "refused": "装配失败，未执行恢复动作"})
        else:
            for action in actions:
                batch_id = action["batch_id"]
                record = repository.get_batch(batch_id)
                try:
                    if action["action"] in ("START_CAPTURE", "REREAD_INCOMPLETE_SLICES", "RETRY_SAME_IDEMPOTENT_KEY"):
                        binding = _target_binding_from_args(args, record.task_id)
                        outcome = assembly.capture(
                            table=record.task_id,
                            business_day=record.business_day,
                            binding=binding,
                            mode=_mode_from_batch(batch_id),
                            bindings=_action_bindings_from_doc(_bindings_doc(args)),
                        )
                    elif action["action"] == "VALIDATE_QUALITY":
                        outcome = assembly.verify(batch_id=batch_id)
                    elif action["action"] in ("REQUEST_APPROVED_APPLY",):
                        if not args.approval_ref:
                            executed.append({
                                "batch_id": batch_id, "ok": False,
                                "refused": "resume --execute 的 apply 需要 --approval-ref",
                            })
                            continue
                        binding = _target_binding_from_args_for_record(args, record)
                        outcome = {"ok": False, "refused": "apply 须经正式 apply 命令（含租约获取），resume 不代办"}
                    elif action["action"] == "RECONCILE_AND_REPORT":
                        binding = _target_binding_from_args(args, record.task_id)
                        outcome = assembly.reconcile(batch_id=batch_id, binding=binding)
                    else:
                        outcome = {"ok": True, "note": f"动作 {action['action']} 需人工/外部输入，未自动执行"}
                    executed.append({"batch_id": batch_id, "action": action["action"], **{
                        k: v for k, v in outcome.items() if k in ("ok", "refused", "state", "rows")
                    }})
                except Exception as exc:  # noqa: BLE001 - 单批失败不连坐
                    executed.append({
                        "batch_id": batch_id, "ok": False,
                        "error_class": type(exc).__name__,
                    })
    _emit(
        {
            "ok": True,
            "simulation": simulation,
            "actions": actions,
            "executed": executed,
            "结论": (
                f"恢复视图：{len(actions)} 个批次待恢复动作"
                + ("（模拟：内存仓储无生产状态）" if simulation else "（来自持久化仓储）")
                + (f"；已执行 {len(executed)} 项" if executed else "")
            ),
        }
    )
    return 0


def _target_binding_from_args_for_record(args: argparse.Namespace, record):
    from app.services.reporting_pipeline.production_runtime import (
        TargetBindingConfig,
    )

    doc = {}
    bindings_file = getattr(args, "bindings_file", None)
    if bindings_file:
        doc = json.loads(Path(bindings_file).read_text(encoding="utf-8"))
    target = doc.get("target") or {}
    return TargetBindingConfig(
        target_instance=target.get(
            "target_instance", record.target_instance or "UNRESOLVED"
        ),
        tenant=target.get("tenant", record.tenant or "UNRESOLVED"),
        table=target.get("table", record.target_table or "UNRESOLVED"),
        key_columns=tuple(target.get("key_columns") or ("ID",)),
        write_columns=tuple(target.get("write_columns") or ("ID",)),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reporting_ctl",
        description="R189-T1 统一T+1抽取工程控制命令（默认离线，不连生产）",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_DIR),
        help="任务配置目录（执行包目录），默认指向 output_r189 执行包",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出77项任务及分层就绪")
    p_list.set_defaults(func=cmd_list)

    p_val = sub.add_parser("validate", help="离线结构校验+未知不可变READY检查")
    p_val.add_argument("--offline", action="store_true", help="显式离线（validate 本身不联网）")
    p_val.set_defaults(func=cmd_validate)

    p_doctor = sub.add_parser("doctor", help="离线核查生产装配缺口；不连库、不创建暂存目录")
    p_doctor.add_argument("--runtime-config", default=None, help="冻结运行配置 JSON（可选）")
    p_doctor.set_defaults(func=cmd_doctor)

    p_report = sub.add_parser("daily-report", help="生成日报（--state-db 真实持久库 / --allow-simulation 显式模拟）")
    p_report.add_argument("--business-day", default=None, help="业务日 YYYY-MM-DD；缺省=院区时区昨天（不再硬编码）")
    p_report.add_argument("--state-db", default=None, help="控制面 PG SQLAlchemy URL（缺省须 --allow-simulation）")
    p_report.add_argument("--allow-simulation", action="store_true", help="显式允许内存模拟状态源（隔离验证）")
    p_report.add_argument("--output", default=None, help="可选：写出 JSON 文件")
    p_report.set_defaults(func=cmd_daily_report)

    p_plan = sub.add_parser("plan", help="离线计划：冻结业务日锚点+动作级就绪分层")
    p_plan.set_defaults(func=cmd_plan)

    p_sim = sub.add_parser("simulate", help="模拟日轮（内存状态，显式 simulation 标记）")
    p_sim.set_defaults(func=cmd_simulate)

    p_resume = sub.add_parser("resume", help="恢复视图：批次恢复动作（--state-db 真实持久库；--execute 执行下一动作）")
    p_resume.add_argument("--state-db", default=None, help="控制面 PG SQLAlchemy URL（缺省=内存模拟）")
    p_resume.add_argument("--execute", action="store_true", help="按恢复矩阵实际执行下一动作（apply 仍走正式命令）")
    p_resume.add_argument("--approval-ref", default=None, help="execute 模式下 apply 动作的批准引用")
    p_resume.add_argument("--bindings-file", default=None, help="目标/源绑定 JSON")
    p_resume.add_argument("--stage-root", default=None, help="耐久暂存根目录")
    p_resume.add_argument("--runtime-config", default=None, help="冻结运行配置 JSON")
    p_resume.add_argument("--allow-simulation", action="store_true")
    p_resume.set_defaults(func=cmd_resume)

    p_ticket = sub.add_parser("ticket-export", help="导出人工视图工单机器JSON")
    p_ticket.add_argument("--output", required=True, help="输出 JSON 路径")
    p_ticket.set_defaults(func=cmd_ticket_export)

    p_freeze = sub.add_parser(
        "freeze-config",
        help="批1-1：首组候选 → 完整 TaskSpec 冻结件（路径/版本/哈希显式冻结）",
    )
    p_freeze.add_argument("--output", required=True, help="冻结件输出 JSON 路径")
    p_freeze.add_argument(
        "--metadata-snapshot",
        default=str(REPO_ROOT / "开发起步包" / "08_数据中心元数据快照.json"),
        help="08 元数据快照（视图 DDL 列覆盖证明）",
    )
    p_freeze.add_argument(
        "--environment",
        default="production",
        choices=["production", "isolated_acceptance"],
        help="冻结环境标记（隔离验收冻结件目标身份不同属正常）",
    )
    p_freeze.add_argument("--override", default=None, help="环境覆盖 JSON（sources/targets）")
    p_freeze.add_argument("--allow-view-gap", action="store_true", help="视图列覆盖不全时仍冻结（notes 留痕）")
    p_freeze.set_defaults(func=cmd_freeze_config)

    p_appr = sub.add_parser(
        "approval-register",
        help="批1-2c：登记耐久批准（管理动作，管道永不自批）",
    )
    p_appr.add_argument("--state-db", required=True, help="控制面 PG SQLAlchemy URL")
    p_appr.add_argument("--approval-ref", required=True)
    p_appr.add_argument("--executor-code", required=True)
    p_appr.add_argument("--target-scope", required=True, help="target:{instance}.{tenant}.{table}")
    p_appr.add_argument("--registered-by", required=True, help="登记人（可追溯）")
    p_appr.add_argument("--valid-hours", default=24)
    p_appr.add_argument("--note", default=None)
    p_appr.set_defaults(func=cmd_approval_register)

    p_osend = sub.add_parser(
        "outbox-send", help="批1-6：独立 outbox sender（一轮/常驻循环；配置取环境变量）"
    )
    p_osend.add_argument("--state-db", required=True)
    p_osend.add_argument("--loop", action="store_true", help="常驻循环（默认一轮）")
    p_osend.add_argument("--interval", default=30, help="循环间隔秒")
    p_osend.add_argument("--max-cycles", default=None, help="循环最大轮数")
    p_osend.set_defaults(func=cmd_outbox_send)

    p_oinfo = sub.add_parser(
        "outbox-inspect", help="批1-6：outbox 巡检（分组清单，不触发发送）"
    )
    p_oinfo.add_argument("--state-db", required=True)
    p_oinfo.set_defaults(func=cmd_outbox_inspect)

    # 六真实动作命令（A02）：真实输入缺失即拒；--allow-simulation 显式隔离验证
    common_real_args = [
        (
            "--state-db",
            dict(default=None, help="控制面 PG SQLAlchemy URL（真实运行必填）"),
        ),
        (
            "--stage-root",
            dict(default=None, help="耐久暂存根目录（真实运行必填）"),
        ),
        (
            "--bindings-file",
            dict(default=None, help="目标/源/批准绑定 JSON（真实运行必填）"),
        ),
        (
            "--runtime-config",
            dict(default=None, help="冻结运行配置 JSON（批1-1；装载即验哈希）"),
        ),
        (
            "--allow-simulation",
            dict(action="store_true", help="显式允许内存模拟（隔离验证专用）"),
        ),
    ]

    def _add_common(parser: argparse.ArgumentParser) -> None:
        for flag, kwargs in common_real_args:
            parser.add_argument(flag, **kwargs)

    p_capture = sub.add_parser(
        "capture", help="真实捕获：窗口冻结→读取→耐久暂存→manifest"
    )
    p_capture.add_argument("--table", required=True, help="canonical_table")
    p_capture.add_argument("--business-day", required=True, help="业务日 YYYY-MM-DD")
    p_capture.add_argument("--mode", default="T1", help="T1/HISTORICAL（默认 T1）")
    p_capture.add_argument("--dry-run", action="store_true", help="只产出计划，不读源")
    p_capture.set_defaults(func=cmd_capture)
    _add_common(p_capture)

    p_verify = sub.add_parser(
        "verify", help="质量验证：暂存完整性+行级规则+守恒（VALIDATED/QUARANTINED）"
    )
    p_verify.add_argument("--batch", required=True, help="稳定 batch_id")
    p_verify.set_defaults(func=cmd_verify)
    _add_common(p_verify)

    p_apply = sub.add_parser(
        "apply", help="正式装载：门禁→单事务 INSERT/UPDATE+SYSTEM_TIME+回执"
    )
    p_apply.add_argument("--batch", required=True, help="稳定 batch_id")
    p_apply.add_argument(
        "--approval-ref", required=True, help="批准引用（平台核验，非自批）"
    )
    p_apply.add_argument("--executor-id", default=None, help="白名单执行器 ID")
    p_apply.add_argument("--lease-ttl", default=900, help="本表写租约 TTL 秒（批1-2c 单写者）")
    p_apply.set_defaults(func=cmd_apply)
    _add_common(p_apply)

    p_reconcile = sub.add_parser(
        "reconcile", help="独立回读：全键存在性+内容一致性（RECONCILED）"
    )
    p_reconcile.add_argument("--batch", required=True, help="稳定 batch_id")
    p_reconcile.set_defaults(func=cmd_reconcile)
    _add_common(p_reconcile)

    p_delivery = sub.add_parser(
        "delivery", help="省端报送状态（接口未接通=PENDING_RECEIPT，不伪造）"
    )
    p_delivery.add_argument("--batch", required=True, help="稳定 batch_id")
    p_delivery.set_defaults(func=cmd_delivery)
    _add_common(p_delivery)

    p_retry = sub.add_parser(
        "retry", help="按恢复矩阵给出续跑动作（同稳定 batch_id）"
    )
    p_retry.add_argument("--batch", required=True, help="稳定 batch_id")
    p_retry.set_defaults(func=cmd_retry)
    _add_common(p_retry)

    # B02 离线工具（2026历史补齐；不连源不写目标）
    p_bf = sub.add_parser(
        "backfill-plan", help="B02 离线拆窗预演：月→日→小时 + 覆盖验收（均匀画像假设）"
    )
    p_bf.add_argument("--start", required=True, help="范围起点 YYYY-MM-DD（含）")
    p_bf.add_argument("--end", required=True, help="范围终点 YYYY-MM-DD（不含，=H）")
    p_bf.add_argument("--rows-per-day", type=int, default=100000, help="均匀画像假设行/日")
    p_bf.add_argument("--bytes-per-row", type=int, default=512, help="均匀画像假设字节/行")
    p_bf.add_argument("--max-rows-per-leaf", type=int, default=2_000_000)
    p_bf.add_argument("--max-bytes-per-leaf", type=int, default=512 * 1024 * 1024)
    p_bf.set_defaults(func=cmd_backfill_plan)

    p_gd = sub.add_parser(
        "gap-diff-plan", help="B02 缺口差异框架：双侧键集只读 SQL 模板 + 分账演示（真实执行等批准）"
    )
    p_gd.add_argument("--table", required=True, help="canonical_table")
    p_gd.add_argument("--source-object", required=True, help="源对象（如 ODS.V_EMR_ICH）")
    p_gd.add_argument("--target-object", required=True, help="目标对象（如 DBOPER.EMR_ICH）")
    p_gd.add_argument("--key-expr", default="ID", help="稳定键表达式")
    p_gd.add_argument("--anchor", default="DATETIME", help="业务时间锚点列")
    p_gd.add_argument("--start", required=True, help="窗起 YYYY-MM-DD（含）")
    p_gd.add_argument("--end", required=True, help="窗止 YYYY-MM-DD（不含）")
    p_gd.set_defaults(func=cmd_gap_diff_plan)

    p_po = sub.add_parser(
        "publish-order", help="B02 父子发布顺序编排（父先子后/已有父复用/缺父等待自动唤醒）"
    )
    p_po.add_argument("--tables", default=None, help="逗号分隔的表清单（缺省=全部77项）")
    p_po.set_defaults(func=cmd_publish_order)
    return parser


def _assembly_inputs(args: argparse.Namespace):
    """构造 AssemblyInputs（不 build）：真实输入缺失保持 None。"""
    from app.services.reporting_pipeline.production_runtime import AssemblyInputs

    bundle = _load_bundle(Path(args.config))
    state_db = _state_db_url(args)
    stage_root = getattr(args, "stage_root", None)

    repository = None
    session_factory = None
    if state_db:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.reporting_pipeline.pg_repository import (
            SqlAlchemyControlRepository,
        )

        engine = create_engine(state_db)
        session_factory = sessionmaker(bind=engine)
        repository = SqlAlchemyControlRepository(session_factory)
    stage_store = None
    if stage_root:
        from app.services.reporting_pipeline.durable_staging import (
            DurableFileStageStore,
        )

        stage_store = DurableFileStageStore(stage_root)
    inputs = AssemblyInputs(
        bundle=bundle,
        repository=repository,
        stage_store=stage_store,
        allow_simulation=bool(getattr(args, "allow_simulation", False)),
    )
    # 目标/源连接绑定文件：真实模式必填（受控连接器配置由运维提供）。
    # approval_refs 仅供显式模拟。生产必须另注入平台批准核验、耐久版本账
    # 和有效写租约；JSON中的字符串不是生产授权。
    bindings_file = getattr(args, "bindings_file", None)
    executor_id = getattr(args, "executor_id", None)
    doc: dict = {}
    if bindings_file:
        try:
            doc = json.loads(Path(bindings_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _emit({"ok": False, "error": f"绑定文件不可读: {exc!r}", "exit_code": 2})
            raise SystemExit(2)
        inputs.receipt_table = doc.get("receipt_table")
        inputs.system_time_column = doc.get("system_time_column")
        inputs.approval_refs = tuple(doc.get("approval_refs") or ())
        inputs.executor_id = doc.get("executor_id") or executor_id
    # 批1-1 冻结运行配置：装载即验哈希，漂移拒绝
    runtime_config_path = getattr(args, "runtime_config", None)
    if runtime_config_path:
        from app.services.reporting_pipeline.runtime_config import (
            RuntimeConfigError,
            load_frozen_runtime_config,
        )

        try:
            inputs.runtime_config = load_frozen_runtime_config(runtime_config_path)
        except RuntimeConfigError as exc:
            _emit({"ok": False, "refused": str(exc), "exit_code": 2})
            raise SystemExit(2)
    # 批1-2 源工厂：bindings.sources + 冻结配置 → 表级 RowSource
    if inputs.runtime_config is not None and doc.get("sources"):
        from app.services.reporting_pipeline.source_factory import (
            build_table_row_source,
        )

        runtime_tables = inputs.runtime_config.tables
        source_bindings = doc["sources"]

        def _table_source(table: str):
            return build_table_row_source(runtime_tables[table], source_bindings)

        inputs.table_row_source_factory = _table_source
    # 批1-2 目标连接工厂：bindings.target（方言/受控URL环境变量/凭据引用）
    target_cfg = doc.get("target") or {}
    if target_cfg.get("dialect"):
        from app.services.reporting_pipeline.target_factory import (
            TargetFactoryError,
            build_target_connection_factory,
        )

        try:
            inputs.target_connection_factory = build_target_connection_factory(
                dialect=target_cfg.get("dialect", ""),
                url_env=target_cfg.get("url_env"),
                dsn=target_cfg.get("dsn"),
                credential_ref=target_cfg.get("credential_ref"),
                fault_injection=doc.get("fault_injection"),
                lock_wait_seconds=int(target_cfg.get("lock_wait_seconds", 10)),
            )
        except TargetFactoryError as exc:
            _emit({"ok": False, "refused": str(exc), "exit_code": 2})
            raise SystemExit(2)
    # 批1-2c 生产 ApplyPort + 版本账只读器：真实模式有状态库与执行器时装配
    if (repository is not None and session_factory is not None
            and inputs.executor_id and not inputs.allow_simulation):
        from app.services.reporting_pipeline.production_apply import (
            ProductionApplyError,
            build_production_apply_port,
        )

        try:
            inputs.production_apply_port = build_production_apply_port(
                session_factory=session_factory,
                repository=repository,
                executor_codes=[inputs.executor_id],
            )
        except ProductionApplyError as exc:
            _emit({"ok": False, "refused": str(exc), "exit_code": 2})
            raise SystemExit(2)
        if inputs.runtime_config is not None:
            from app.services.reporting_pipeline.apply_port import VersionScope
            from app.services.reporting_pipeline.pg_repository import (
                PgVersionRegistry,
            )

            registry = PgVersionRegistry(session_factory)

            def _version_reader(target_object: str, key: tuple):
                parts = target_object.rsplit(".", 2)
                if len(parts) != 3:
                    return None
                return registry.current_version(VersionScope(*parts), tuple(key))

            inputs.version_reader = _version_reader
    return inputs


def cmd_doctor(args: argparse.Namespace) -> int:
    """如实说明命令行与生产装配的边界，禁止把离线测试当上线验收。"""
    bundle = _load_bundle(Path(args.config))
    runtime_config_path = getattr(args, "runtime_config", None)
    runtime_config_status = "未提供（--runtime-config 冻结运行配置）"
    if runtime_config_path:
        from app.services.reporting_pipeline.runtime_config import (
            RuntimeConfigError,
            load_frozen_runtime_config,
        )

        try:
            loaded = load_frozen_runtime_config(runtime_config_path)
            runtime_config_status = (
                f"已装载（environment={loaded.environment}，"
                f"{len(loaded.tables)} 表，指纹校验通过）"
            )
        except RuntimeConfigError as exc:
            runtime_config_status = f"装载失败: {exc}"
    _emit({
        "ok": False,
        "production_ready": False,
        "mode": "offline_inspection",
        "configured_tasks": len(bundle.tasks),
        "enabled_tasks": sum(bool(task.enabled) for task in bundle.tasks),
        "runtime_config": runtime_config_status,
        "wired_this_batch": [
            "批1-1 freeze-config 冻结件（路径/版本/哈希；装载即验）",
            "批1-2a 源工厂（Oracle ROWNUM/PG LIMIT 投影查询+受控连接器+双源路由器）",
            "批1-2b 目标连接工厂（PgTargetConnection 入 app；Oracle 方言已实现待隔离环境）",
            "批1-2c 生产 ApplyPort（平台白名单+耐久批准登记+租约围栏+耐久版本账）+ approval-register",
            "批1-3 DataX 固定暂存路线接入 capture（真实引擎实测须 8.53）",
            "批1-4 SNAPSHOT_DIFF CAS 分区+父存在性+隔离组账",
            "批1-5 恢复执行化（回读关缺口/水位门禁/RECOVERED/rescan 覆盖账）+ REPLACE_MONTH 执行器",
            "批1-6 outbox-send/outbox-inspect（独立 sender；真实外发须 R06 六项输入）",
        ],
        "still_missing_for_production": [
            "控制库迁移全链 apply（生产在 c0d1e2f3a4b5，整条报表链待批 PA5）",
            "目标回执表 DDL（PA3）、暂存持久卷挂载（PA6）",
            "正式调度注册与告警订阅（R06 外部输入）",
            "镜像发布与 8.53 DataX 引擎级实测（PA 批准后）",
        ],
        "note": "CLI 已可按 bindings+冻结配置装配真实运行链；生产部署与外发仍逐例待批。",
    })
    return 2


def _build_assembly(args: argparse.Namespace):
    """六真实命令共用装配：真实输入缺失即拒（A02 拒绝语义）。"""
    from app.services.reporting_pipeline.production_runtime import (
        ProductionAssembly,
    )

    inputs = _assembly_inputs(args)
    allow_simulation = bool(getattr(args, "allow_simulation", False))
    real = not allow_simulation
    assembly = ProductionAssembly.build(inputs, real=real)
    return assembly, inputs


def _action_bindings_from_doc(doc: dict):
    """K01：未 enabled 表的本地动作绑定（须带批准来源与有效期）。

    声明形如 {"action_bindings": [{"canonical_table": ..., "actions":
    ["CAPTURE","STAGE","APPLY"], "valid_hours": 8, "approval_ref": ...,
    "granted_by": ...}]}。程序不得自造绑定；来源对应平台批准登记。
    """
    from datetime import datetime, timedelta, timezone

    from app.services.reporting_pipeline.contracts import PipelineAction
    from app.services.reporting_pipeline.runtime import ActionBinding

    now = datetime.now(timezone.utc)
    out = []
    for item in doc.get("action_bindings") or []:
        out.append(ActionBinding(
            canonical_table=item["canonical_table"],
            actions=tuple(PipelineAction(a) for a in item.get("actions") or ()),
            valid_from=now,
            valid_until=now + timedelta(hours=int(item.get("valid_hours", 8))),
            approval_ref=item["approval_ref"],
            granted_by=item["granted_by"],
        ))
    return tuple(out)


def _bindings_doc(args: argparse.Namespace) -> dict:
    bindings_file = getattr(args, "bindings_file", None)
    if bindings_file:
        return json.loads(Path(bindings_file).read_text(encoding="utf-8"))
    return {}


def _table_from_batch(batch_id: str, doc: dict | None = None) -> str:
    """batch_id = {table}.{mode}.{day}.{digest}；table 为绑定表名（可为
    schema 限定）。返回 canonical_table：按 targets_by_table 反查绑定表名。"""
    parts = batch_id.rsplit(".", 3)
    prefix = parts[0] if len(parts) == 4 else batch_id.split(".", 1)[0]
    for canonical, entry in (doc or {}).get("targets_by_table", {}).items():
        if entry.get("table") == prefix or canonical == prefix:
            return canonical
    return prefix


def _mode_from_batch(batch_id: str) -> str:
    parts = batch_id.rsplit(".", 3)
    return parts[1] if len(parts) == 4 else "T1"


def _target_binding_from_args(args: argparse.Namespace, canonical_table: str | None = None):
    from app.services.reporting_pipeline.production_runtime import (
        TargetBindingConfig,
    )

    doc = _bindings_doc(args)
    target = doc.get("target") or {}
    per_table = (
        (doc.get("targets_by_table") or {}).get(canonical_table)
        if canonical_table else None
    ) or {}
    resolved = {**target, **per_table}
    return TargetBindingConfig(
        target_instance=resolved.get(
            "target_instance", resolved.get("instance") or "UNRESOLVED"
        ),
        tenant=resolved.get("tenant") or "UNRESOLVED",
        table=resolved.get("table") or getattr(args, "table", None) or "UNRESOLVED",
        key_columns=tuple(resolved.get("key_columns") or ("ID",)),
        write_columns=tuple(resolved.get("write_columns") or ("ID",)),
    )


def cmd_capture(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import (
        ProductionAssembly,
    )

    dry_run = bool(args.dry_run)
    # dry-run 只产出审阅计划（不读源不写状态）：缺状态库时允许离线装配，
    # 输出带 simulation 标记；真实 capture 缺输入仍拒绝。
    if dry_run and not _state_db_url(args):
        inputs = _assembly_inputs(args)
        inputs.allow_simulation = True  # dry-run 显式允许（仅产计划，不触源/状态）
        assembly = ProductionAssembly.build(inputs, real=False)
        binding = _target_binding_from_args(args, args.table)
        outcome = assembly.capture(
            table=args.table,
            business_day=args.business_day,
            binding=binding,
            mode=args.mode,
            dry_run=True,
        )
    else:
        from app.services.reporting_pipeline.production_runtime import (
            AssemblyRefused,
        )

        try:
            assembly, _inputs = _build_assembly(args)
            binding = _target_binding_from_args(args, args.table)
            outcome = assembly.capture(
                table=args.table,
                business_day=args.business_day,
                binding=binding,
                mode=args.mode,
                dry_run=dry_run,
                bindings=_action_bindings_from_doc(_bindings_doc(args)),
            )
        except AssemblyRefused as exc:
            _emit({"ok": False, "refused": str(exc), "exit_code": 2})
            return 2
    outcome.setdefault("ok", True)
    outcome["结论"] = (
        "capture 计划已产出（dry-run，未读源）" if outcome.get("dry_run")
        else ("capture 完成" if outcome.get("ok") else "capture 未完成（如实记录）")
    )
    _emit(outcome)
    return 0 if outcome.get("ok") else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import AssemblyRefused

    try:
        assembly, _inputs = _build_assembly(args)
        outcome = assembly.verify(batch_id=args.batch)
    except AssemblyRefused as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    outcome["结论"] = (
        "质量验证通过（VALIDATED）" if outcome.get("ok")
        else f"质量验证未全通过: {outcome.get('state')}"
    )
    _emit(outcome)
    return 0 if outcome.get("ok") else 1


def cmd_apply(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import AssemblyRefused

    state_db = _state_db_url(args)
    allow_simulation = bool(getattr(args, "allow_simulation", False))
    lease = None
    lease_repo = None
    if state_db and not allow_simulation:
        # 批1-2c：正式装载前取本表写租约（单写者 + 围栏 token），结束释放
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.reporting_pipeline.pg_repository import (
            SqlAlchemyControlRepository,
        )
        from app.services.reporting_pipeline.repositories import LeaseDenied
        from app.services.reporting_pipeline.runtime import unique_worker_id

        engine = create_engine(state_db)
        lease_repo = SqlAlchemyControlRepository(sessionmaker(bind=engine))
        doc = _bindings_doc(args)
        per_table = (doc.get("targets_by_table") or {}).get(
            _table_from_batch(args.batch, doc)
        ) or {}
        target = {**(doc.get("target") or {}), **per_table}
        resource = "target:{instance}.{tenant}.{table}".format(
            instance=target.get("target_instance") or target.get("instance", ""),
            tenant=target.get("tenant", ""),
            table=(target.get("table") or "").rsplit(".", 1)[-1],
        )
        try:
            lease = lease_repo.acquire_lease(
                resource, unique_worker_id("r189t1-apply"),
                ttl_seconds=int(getattr(args, "lease_ttl", 900)),
            )
        except LeaseDenied as exc:
            _emit({
                "ok": False, "refused": f"REFUSED_TARGET_LEASE：{exc}",
                "resource": resource, "exit_code": 2,
            })
            return 2
    try:
        assembly, _inputs = _build_assembly(args)
        binding = _target_binding_from_args(
            args, _table_from_batch(args.batch, _bindings_doc(args))
        )
        outcome = assembly.apply(
            batch_id=args.batch,
            binding=binding,
            approval_ref=args.approval_ref,
            lease_resource=lease.resource if lease else None,
            fencing_token=lease.fencing_token if lease else None,
        )
    except AssemblyRefused as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    finally:
        if lease is not None and lease_repo is not None:
            try:
                lease_repo.release_lease(
                    lease.resource, lease.holder, fencing_token=lease.fencing_token
                )
            except Exception:  # noqa: BLE001 - 释放失败不掩盖主结果（TTL兜底）
                pass
    outcome["结论"] = (
        "正式装载提交成功（回执+版本账已登记）" if outcome.get("ok")
        else f"装载未完成: {outcome.get('state') or outcome.get('refused', '')[:120]}"
    )
    _emit(outcome)
    return 0 if outcome.get("ok") else 1


def cmd_reconcile(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import AssemblyRefused

    try:
        assembly, _inputs = _build_assembly(args)
        binding = _target_binding_from_args(
            args, _table_from_batch(args.batch, _bindings_doc(args))
        )
        outcome = assembly.reconcile(batch_id=args.batch, binding=binding)
    except AssemblyRefused as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    outcome["结论"] = (
        "全键回读一致（RECONCILED）" if outcome.get("ok")
        else f"回读存在差异: 缺 {outcome.get('missing_keys')} / 差异 "
             f"{outcome.get('content_diffs')}"
    )
    _emit(outcome)
    return 0 if outcome.get("ok") else 1


def cmd_delivery(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import AssemblyRefused

    try:
        assembly, _inputs = _build_assembly(args)
        outcome = assembly.delivery(batch_id=args.batch)
    except AssemblyRefused as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    outcome["结论"] = (
        "省端接口未接通：delivery 保持 PENDING_RECEIPT（不伪造调用、"
        "不涂绿 REPORT_READY）"
    )
    _emit(outcome)
    return 0 if outcome.get("ok") else 1


def cmd_retry(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import AssemblyRefused

    try:
        assembly, _inputs = _build_assembly(args)
        outcome = assembly.retry(batch_id=args.batch)
    except AssemblyRefused as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
    outcome["结论"] = "恢复矩阵已给出下一动作（同稳定 batch_id 续跑）"
    _emit(outcome)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
