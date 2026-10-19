"""R189-T1 统一T+1抽取工程控制命令入口（包 R189-T1-ENGINEERING-20261019-v1.2）。

子命令按批次逐步落地：
- E01：list / validate（离线、只读任务包 JSON，不连库不外发）
- E02+：plan / simulate / capture / verify / apply / reconcile / delivery /
  resume / retry / daily-report / ticket-export（实现一批登记一批，未实现的
  子命令显式报 NOT_IMPLEMENTED，不假装成功）。

退出码：0=通过；2=用法/配置错误；3=结构校验失败；4=业务校验失败。
所有命令输出结构化 JSON（stdout），关键结论同时给中文摘要字段。
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

IMPLEMENTED_COMMANDS = ("list", "validate", "daily-report", "ticket-export")


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
    repo = InMemoryControlRepository()
    seed_doc = _load_json(Path(args.config) / "E01已知人工工单种子.json")
    registry = seed_tickets_from_package(seed_doc)
    report = build_daily_report(
        business_day=args.business_day,
        repository=repo,
        bundle=bundle,
        ticket_registry=registry,
    )
    payload = report.to_dict()
    payload["ok"] = True
    payload["结论"] = (
        "本地日报（模拟状态源）：77项 deadline 全部 UNCONFIGURED→SLA_UNKNOWN；"
        "relay 处于 WAITING_INTEGRATION_SETUP；无生产运行数据，不虚构进度"
    )
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    _emit(payload)
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

    p_report = sub.add_parser("daily-report", help="生成日报结构（本地模拟状态）")
    p_report.add_argument("--business-day", default="2026-10-19")
    p_report.add_argument("--output", default=None, help="可选：写出 JSON 文件")
    p_report.set_defaults(func=cmd_daily_report)

    p_ticket = sub.add_parser("ticket-export", help="导出人工视图工单机器JSON")
    p_ticket.add_argument("--output", required=True, help="输出 JSON 路径")
    p_ticket.set_defaults(func=cmd_ticket_export)

    for name in ("plan", "simulate", "capture", "verify", "apply", "reconcile",
                 "delivery", "resume", "retry"):
        p = sub.add_parser(name, help=f"{name}（按批次实现中）")
        p.set_defaults(func=_not_implemented, command_name=name)
    return parser


def _not_implemented(args: argparse.Namespace) -> int:
    _emit(
        {
            "ok": False,
            "error": f"子命令 {getattr(args, 'command_name', '?')} 尚未实现（按批次落地）",
            "exit_code": 2,
        }
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
