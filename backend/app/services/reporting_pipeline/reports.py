"""日报与看板汇总：必列分节 + 分母分开 + SLA_UNKNOWN。

对应契约 daily_report_required 与 R06 整改：
failed_windows_and_next_retry / commit_unknown_tables / affected_child_groups /
monthly_coverage_overdue / deadline_unconfigured / relay_delivery_state。
R06 新增：per_table_daily（每表昨天捕获/合格/隔离/待父/装载/回读）、
earliest_open_gap（待补最早窗及数量）、continuous_completion（最后连续
完成日，与捕获水位分开——RT1-025）、rescan_coverage_age（历史重扫最老
月份与覆盖年龄，只扫当月不得冒充全历史保障）、source_latency、
recommended_actions。

日报数据一律来自注入仓储（内存=模拟并显式标记；PG=真实持久化状态），
不依赖进程内临时变量；异常只出现结构化类别与 detail_ref。
另有：全77项、实际适用项、已批准上线项分母分别显示（不自除未提供项）；
DEADLINE_UNCONFIGURED 单列并标 SLA_UNKNOWN 与 A12 省端反馈待办。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.services.reporting_pipeline.contracts import BatchState
from app.services.reporting_pipeline.planner import (
    coverage_age_report,
    missing_months_in_scope,
    month_sequence,
)
from app.services.reporting_pipeline.repositories import (
    ControlRepository,
    InMemoryControlRepository,
)
from app.services.reporting_pipeline.seed_loader import SeedBundle


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class DailyReport:
    business_day: str
    sections: dict
    simulation: bool = False

    def to_dict(self) -> dict:
        return {
            "business_day": self.business_day,
            "simulation": self.simulation,
            **self.sections,
        }


def build_daily_report(
    *,
    business_day: str,
    repository: ControlRepository,
    bundle: SeedBundle,
    parents_by_table: dict[str, Sequence[str]] | None = None,
    rescan_scope: tuple[str | None, str | None] = (None, None),
    approved_for_production: set[str] | None = None,
    ticket_registry=None,
    simulation: bool | None = None,
    rescan_cycle_days: int = 30,
) -> DailyReport:
    parents_by_table = parents_by_table or {}
    if simulation is None:
        simulation = isinstance(repository, InMemoryControlRepository)
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

    # R06：历史重扫覆盖年龄（每个月被重访的最长间隔；RT1-026）
    rescan_coverage_age = {}
    for task in bundle.rescan_tasks():
        table = task.canonical_table
        managed = (
            month_sequence(start_month, end_month) if start_month and end_month else []
        )
        visits = {
            row["month"]: (
                row["reconciled"][:7] if row.get("reconciled") else None
            )
            for row in coverage_rows
            if row["table"] == table and row.get("reconciled")
        }
        rescan_coverage_age[table] = coverage_age_report(
            managed_months=managed,
            last_visit_month_by_key={
                m: v for m, v in visits.items() if v
            },
            now_month=business_day[:7],
            cycle_days=rescan_cycle_days,
        )

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

    # A04：告警通道自身监控——outbox 最老未送达年龄与人工升级建议。
    # 通道自保障声明以实测数据为准：无独立值守渠道时，日报本节即发现手段。
    now = _now()
    undelivered = [
        r for r in relay_rows if r.get("delivery") != "DELIVERED"
    ]
    oldest_pending_age_seconds: int | None = None
    if undelivered:
        ages = []
        for r in undelivered:
            created = _parse_iso(r.get("created_at"))
            if created is not None:
                ages.append(max(0, int((now - created).total_seconds())))
        if ages:
            oldest_pending_age_seconds = max(ages)
    alert_channel_monitor = {
        "oldest_undelivered_age_seconds": oldest_pending_age_seconds,
        "undelivered_events": len(undelivered),
        "escalation_threshold_seconds": 3600,
        "escalate_now": (
            oldest_pending_age_seconds is not None
            and oldest_pending_age_seconds > 3600
        ),
        "note": (
            "无独立值守渠道时，本节即告警通道故障的发现手段：最老未送达"
            "事件超过阈值须人工介入（复检 relay 配置与 worker 心跳）"
        ),
    }

    # A04：等待项升级账——未闭合缺口按年龄给出负责人角色/下次动作建议，
    # 避免永久静默等待（等待记录的负责人/次数由工单系统补全）。
    gap_escalation: list[dict] = []
    for gap in snapshot["open_gaps"]:
        age_hours: float | None = None
        created = _parse_iso(gap.get("created_at"))
        if created is not None:
            age_hours = round((now - created).total_seconds() / 3600, 1)
        gap_escalation.append(
            {
                "task": gap.get("task"),
                "window": gap.get("window"),
                "reason": gap.get("reason"),
                "age_hours": age_hours,
                "owner_role": "数据工程值班（自动续补失败 3 次后转 DBA/源侧）",
                "next_action": (
                    "按恢复矩阵自动续补；age>24h 未闭合列日报头条并升级"
                ),
                "escalate": age_hours is not None and age_hours > 24,
            }
        )

    # R06：每表昨日运行行（捕获/隔离/待父/装载/回读来自持久化状态）
    per_table = snapshot.get("per_table", {})
    per_table_daily = {
        table: {
            "batches": row.get("batches", 0),
            "by_state": row.get("by_state", {}),
            "quarantined": row.get("quarantined", 0),
            "pending_parent": row.get("pending_parent", 0),
            "applied": row.get("applied", 0),
            "commit_unknown": row.get("commit_unknown", 0),
            "readback": row.get("by_state", {}).get("RECONCILED", 0),
            "earliest_open_gap": row.get("earliest_open_gap"),
        }
        for table, row in per_table.items()
    }

    # R06：待补最早窗（逐表，含数量）
    earliest_open_gap = {
        table: row["earliest_open_gap"]
        for table, row in per_table.items()
        if row.get("earliest_open_gap")
    }

    # R06：最后连续完成日（与捕获水位分开；RT1-025）
    continuous_completion = {
        table: {
            "capture_h": wm.get("capture_h"),
            "continuous_through": wm.get("continuous_through"),
            "note": (
                "capture_h=已捕获可见上界；continuous_through=最后连续完成日。"
                "两者之间即待补缺口，日报不得用捕获水位冒充连续完成"
            ),
        }
        for table, wm in snapshot.get("watermarks", {}).items()
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

    # R06：建议动作（按欠账类型给下一步，不带患者/SQL）
    recommended_actions: list[dict] = []
    if failed_windows:
        recommended_actions.append({
            "action": "BACKFILL_OPEN_GAPS",
            "scope": "按最早缺口逐窗补抽",
            "count": len(failed_windows),
        })
    if commit_unknown_tables:
        recommended_actions.append({
            "action": "RECONCILE_COMMIT_UNKNOWN",
            "scope": f"核同事务提交凭据后解冻: {commit_unknown_tables[:5]}",
            "count": len(commit_unknown_tables),
        })
    paused = relay_section["needs_attention_or_paused"]
    if paused:
        recommended_actions.append({
            "action": "CHECK_ALERT_CHANNEL",
            "scope": "告警通道待处理/暂停事件",
            "count": paused,
        })
    for table, age in rescan_coverage_age.items():
        if age.get("coverage_level") in ("NO_HISTORY_VISIT", "DEGRADED_BEYOND_DECLARED_CYCLE"):
            recommended_actions.append({
                "action": "RESCAN_SCHEDULE_REVIEW",
                "scope": f"{table}: 覆盖等级 {age['coverage_level']}",
                "count": age.get("managed_months", 0),
            })

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
        "rescan_coverage_age": rescan_coverage_age,
        "deadline_unconfigured": {
            "sla": "SLA_UNKNOWN",
            "tables": deadline_unconfigured,
            "todo": "A12：省端截止/达标环节/反馈协议待业务确认；不猜截止",
        },
        "relay_delivery_state": relay_section,
        "alert_channel_monitor": alert_channel_monitor,
        "gap_escalation": gap_escalation,
        "per_table_daily": per_table_daily,
        "earliest_open_gap": earliest_open_gap,
        "continuous_completion": continuous_completion,
        "denominators": denominators,
        "recommended_actions": recommended_actions,
        "waiting_human_view_fix": (
            [
                {"ticket_id": t.ticket_id, "tables": t.tables, "state": t.state}
                for t in ticket_registry.all_tickets()
                if t.state not in ("CLOSED", "VERIFIED")
            ]
            if ticket_registry is not None else []
        ),
    }
    return DailyReport(business_day=business_day, sections=sections, simulation=simulation)
