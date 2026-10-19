"""日报与看板汇总：必列分节 + 分母分开 + SLA_UNKNOWN。

对应契约 daily_report_required：
failed_windows_and_next_retry / commit_unknown_tables / affected_child_groups /
monthly_coverage_overdue / deadline_unconfigured / relay_delivery_state。
另有：全77项、实际适用项、已批准上线项分母分别显示（不自除未提供项）；
DEADLINE_UNCONFIGURED 单列并标 SLA_UNKNOWN 与 A12 省端反馈待办。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.reporting_pipeline.contracts import BatchState
from app.services.reporting_pipeline.planner import missing_months_in_scope
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.seed_loader import SeedBundle


@dataclass
class DailyReport:
    business_day: str
    sections: dict

    def to_dict(self) -> dict:
        return {"business_day": self.business_day, **self.sections}


def build_daily_report(
    *,
    business_day: str,
    repository: InMemoryControlRepository,
    bundle: SeedBundle,
    parents_by_table: dict[str, Sequence[str]] | None = None,
    rescan_scope: tuple[str | None, str | None] = (None, None),
    approved_for_production: set[str] | None = None,
    ticket_registry=None,
) -> DailyReport:
    parents_by_table = parents_by_table or {}
    snapshot = repository.snapshot()

    # 1) 失败窗与下次补抽（缺口账本）
    failed_windows = [
        {
            "task": gap["task"], "window": gap["window"], "reason": gap["reason"],
            "next_retry": "按补抽规则有界重试/人工修复后原窗重取",
        }
        for gap in snapshot["open_gaps"]
    ]

    # 2) COMMIT_UNKNOWN 表（冻结写者清单）
    commit_unknown_tables = [
        batch["task"] for batch in snapshot["batches"].values()
        if batch["state"] == BatchState.COMMIT_UNKNOWN.value
    ]

    # 3) 受影响父子组
    affected_child_groups: dict[str, list[str]] = {}
    for table in commit_unknown_tables:
        affected_child_groups[table] = [
            child for child, parents in parents_by_table.items()
            if table in parents
        ]

    # 4) 月度覆盖欠账（范围未冻结 → 显式 SCOPE_UNFROZEN，不算就绪）
    start_month, end_month = rescan_scope
    coverage_rows = snapshot["month_coverage"]
    covered = {(row["table"], row["month"]) for row in coverage_rows}
    overdue_rows = []
    for task in bundle.rescan_tasks():
        table = task.canonical_table
        for row in repository.overdue_months(table):
            overdue_rows.append(
                {"table": table, "month": row.business_month, "state": "OVERDUE"}
            )
        for month in missing_months_in_scope(start_month, end_month, {m for t, m in covered if t == table}):
            overdue_rows.append({"table": table, "month": month, "state": "MISSING"})
    scope_state = "SCOPE_UNFROZEN_E01_TO_FILL" if not start_month else "SCOPE_FROZEN"

    # 5) DEADLINE_UNCONFIGURED（SLA_UNKNOWN，不伪算 SLA_AT_RISK）
    deadline_unconfigured = [
        task.canonical_table for task in bundle.tasks
        if task.associations.deadline_state.value == "UNCONFIGURED"
    ]

    # 6) relay 投递状态（入队与送达分开）
    relay_rows = snapshot["outbox"]
    delivered = sum(1 for r in relay_rows if r["delivery"] == "DELIVERED")
    relay_section = {
        "integration_state": "WAITING_INTEGRATION_SETUP",
        "events_total": len(relay_rows),
        "delivered": delivered,
        "queued_or_pending": sum(
            1 for r in relay_rows
            if r["delivery"] in ("NOT_SENT",) and r["acceptance"] in ("ACK_QUEUED", "DUPLICATE")
        ),
        "needs_attention_or_paused": sum(
            1 for r in relay_rows
            if r["delivery"] in ("NEEDS_ATTENTION", "PAUSED_AUTH", "ROUTE_UNRESOLVED")
        ),
        "note": "202=入队≠送达；全期望目标 sent 才 DELIVERED",
    }

    # 分母分开：全77 / 实际适用 / 已批准上线
    applicable = [
        t for t in bundle.tasks
        if t.applicability.value != "WAITING_BUSINESS_CONFIRMATION"
    ]
    approved = approved_for_production or set()
    denominators = {
        "canonical_items_total": len(bundle.tasks),
        "applicable_now": len(applicable),
        "not_provided_pending_applicability": len(bundle.tasks) - len(applicable),
        "approved_for_production": len(approved),
        "warning": "完成率不自除未提供项；approved 为 0（无生产授权）",
    }

    sections = {
        "overall": (
            "PARTIAL_SUCCESS_WITH_BACKLOG" if failed_windows or commit_unknown_tables
            else "SUCCESS_WITH_WAITING_ITEMS"
        ),
        "failed_windows_and_next_retry": failed_windows,
        "commit_unknown_tables": commit_unknown_tables,
        "affected_child_groups": affected_child_groups,
        "monthly_coverage_overdue": {
            "scope_state": scope_state, "rows": overdue_rows,
            "rescan_tables": [t.canonical_table for t in bundle.rescan_tasks()],
        },
        "deadline_unconfigured": {
            "sla": "SLA_UNKNOWN",
            "tables": deadline_unconfigured,
            "todo": "A12：省端截止/达标环节/反馈协议待业务确认；不猜截止",
        },
        "relay_delivery_state": relay_section,
        "denominators": denominators,
        "waiting_human_view_fix": (
            [
                {"ticket_id": t.ticket_id, "tables": t.tables, "state": t.state}
                for t in ticket_registry.all_tickets()
                if t.state not in ("CLOSED", "VERIFIED")
            ]
            if ticket_registry is not None else []
        ),
    }
    return DailyReport(business_day=business_day, sections=sections)
