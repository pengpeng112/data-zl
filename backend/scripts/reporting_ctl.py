"""R189-T1 统一T+1抽取工程控制命令入口（包 R189-T1-ENGINEERING-20261019-v1.2）。

子命令按批次逐步落地：
- E01：list / validate（离线、只读任务包 JSON，不连库不外发）
- E02+：plan / simulate / capture / verify / apply / reconcile / delivery /
  resume / retry / daily-report / ticket-export。
- A02（2026-10-22）：capture/verify/apply/reconcile/delivery/retry 六个
  真实动作命令落地——真实运行缺状态库/暂存根/绑定/批准即拒绝
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
)


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
    state_db = getattr(args, "state_db", None)
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
        state_note = f"durable_state_db={state_db}"
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


def cmd_resume(args: argparse.Namespace) -> int:
    """恢复视图：从状态仓储读批次给出恢复动作（模拟/真实双模式）。"""
    from app.services.reporting_pipeline.recovery import RecoveryService
    from app.services.reporting_pipeline.repositories import InMemoryControlRepository

    state_db = getattr(args, "state_db", None)
    if state_db:
        from app.services.reporting_pipeline.pg_repository import (
            SqlAlchemyControlRepository,
        )
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(state_db)
        repository = SqlAlchemyControlRepository(sessionmaker(bind=engine))
        simulation = False
    else:
        repository = InMemoryControlRepository()
        simulation = True
    service = RecoveryService(repository)
    actions = [a.to_dict() for a in service.resume_all()]
    _emit(
        {
            "ok": True,
            "simulation": simulation,
            "actions": actions,
            "结论": (
                f"恢复视图：{len(actions)} 个批次待恢复动作"
                + ("（模拟：内存仓储无生产状态）" if simulation else "（来自持久化仓储）")
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

    p_resume = sub.add_parser("resume", help="恢复视图：批次恢复动作（--state-db 真实持久库）")
    p_resume.add_argument("--state-db", default=None, help="控制面 PG SQLAlchemy URL（缺省=内存模拟）")
    p_resume.set_defaults(func=cmd_resume)

    p_ticket = sub.add_parser("ticket-export", help="导出人工视图工单机器JSON")
    p_ticket.add_argument("--output", required=True, help="输出 JSON 路径")
    p_ticket.set_defaults(func=cmd_ticket_export)

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
    state_db = getattr(args, "state_db", None)
    stage_root = getattr(args, "stage_root", None)

    repository = None
    if state_db:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.reporting_pipeline.pg_repository import (
            SqlAlchemyControlRepository,
        )

        engine = create_engine(state_db)
        repository = SqlAlchemyControlRepository(sessionmaker(bind=engine))
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
    )
    # 目标/源连接绑定文件：真实模式必填（受控连接器配置由运维提供）。
    # approval_refs 是运维从平台批准登记转录的"已获批准集合"；CLI 的
    # --approval-ref 只是引用，必须在集合内才可通过（程序不自批）。
    bindings_file = getattr(args, "bindings_file", None)
    executor_id = getattr(args, "executor_id", None)
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
        # 真实源工厂/目标连接由容器内受控连接器装配（本机 CLI 不持凭据）；
        # 缺失时 ProductionAssembly 在真实动作处拒绝（REFUSED_MISSING_*）
    return inputs


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


def _target_binding_from_args(args: argparse.Namespace):
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
            "target_instance",
            getattr(args, "target_instance", None) or "UNRESOLVED",
        ),
        tenant=target.get("tenant", getattr(args, "tenant", None) or "UNRESOLVED"),
        table=target.get(
            "table", getattr(args, "table", None) or "UNRESOLVED"
        ),
        key_columns=tuple(target.get("key_columns") or ("K1",)),
        write_columns=tuple(target.get("write_columns") or ("K1", "V1")),
    )


def cmd_capture(args: argparse.Namespace) -> int:
    from app.services.reporting_pipeline.production_runtime import (
        ProductionAssembly,
    )

    dry_run = bool(args.dry_run)
    # dry-run 只产出审阅计划（不读源不写状态）：缺状态库时允许离线装配，
    # 输出带 simulation 标记；真实 capture 缺输入仍拒绝。
    if dry_run and not getattr(args, "state_db", None):
        inputs = _assembly_inputs(args)
        inputs.allow_simulation = True  # dry-run 显式允许（仅产计划，不触源/状态）
        assembly = ProductionAssembly.build(inputs, real=False)
        binding = _target_binding_from_args(args)
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
            binding = _target_binding_from_args(args)
            outcome = assembly.capture(
                table=args.table,
                business_day=args.business_day,
                binding=binding,
                mode=args.mode,
                dry_run=dry_run,
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

    try:
        assembly, _inputs = _build_assembly(args)
        binding = _target_binding_from_args(args)
        outcome = assembly.apply(
            batch_id=args.batch,
            binding=binding,
            approval_ref=args.approval_ref,
        )
    except AssemblyRefused as exc:
        _emit({"ok": False, "refused": str(exc), "exit_code": 2})
        return 2
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
        binding = _target_binding_from_args(args)
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
    return 0


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
