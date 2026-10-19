"""调度桥：单入口周期编排（复用既有调度，不启动第二常驻循环）。

对应计划 §8：
- 调度只保留一个入口：本桥提供 run_cycle() 供既有平台调度器/CLI 调用，
  自身不注册 cron、不起后台线程。
- 优先级：日常 T+1 优先，补历史/月重扫低优先。
- 每表单写：领取任务前取目标写租约+围栏；COMMIT_UNKNOWN 表的写任务被
  冻结（blocked_scopes），不派发。
- 按源预算：同物理源并发 1（初始候选），源熔断 OPEN 时不派发该源任务。
- 失败继续：任务级异常被隔离记录（gap/工单/告警引用），周期继续其他任务，
  周期末汇总 PARTIAL_SUCCESS_WITH_BACKLOG。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.planner import build_dag
from app.services.reporting_pipeline.recovery import RecoveryService, blocked_scopes


class TaskRunnable(Protocol):
    canonical_table: str
    mode: str  # T1 / LATE_BACKLOG / LOOKBACK / MONTHLY_RESCAN / HISTORICAL_REPAIR
    physical_sources: tuple[str, ...]

    def run(self) -> dict:
        """执行一次任务步（由编排者组合适配器）；返回结构化结果。"""


@dataclass
class CycleReport:
    dispatched: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    overall: str = "SUCCESS"

    def to_dict(self) -> dict:
        return {
            "dispatched": self.dispatched,
            "skipped": self.skipped,
            "failures": self.failures,
            "overall": self.overall,
        }


MODE_PRIORITY = {
    "T1": 0,
    "LATE_BACKLOG": 1,
    "LOOKBACK": 2,
    "HISTORICAL_REPAIR": 3,
    "MONTHLY_RESCAN": 4,
}


class SchedulerBridge:
    def __init__(
        self,
        *,
        repository,
        source_open_predicate: Callable[[str], bool] | None = None,
        lease_ttl_seconds: int = 3600,
        worker_id: str = "worker-1",
    ) -> None:
        self.repository = repository
        self.source_open_predicate = source_open_predicate or (lambda _s: False)
        self.lease_ttl_seconds = lease_ttl_seconds
        self.worker_id = worker_id

    def plan_order(
        self,
        tasks: Sequence[TaskRunnable],
        parents_by_table: Mapping[str, Sequence[str]] | None = None,
    ) -> list[TaskRunnable]:
        """DAG 拓扑（父先子后）+ 模式优先级（日常优先）。"""
        tables = [t.canonical_table for t in tasks]
        order = build_dag(parents_by_table or {t: [] for t in tables})
        by_table = {t.canonical_table: t for t in tasks}
        ordered = [by_table[t] for t in order if t in by_table]
        ordered.sort(key=lambda t: MODE_PRIORITY.get(t.mode, 99))
        return ordered

    def run_cycle(
        self,
        tasks: Sequence[TaskRunnable],
        parents_by_table: Mapping[str, Sequence[str]] | None = None,
    ) -> CycleReport:
        report = CycleReport()
        recovery = RecoveryService(self.repository)
        frozen_scopes = set(blocked_scopes(recovery.resume_all()))

        active_sources: set[str] = set()
        for task in self.plan_order(tasks, parents_by_table):
            table = task.canonical_table
            # COMMIT_UNKNOWN 冻结：同表写任务不派发
            if any(scope in frozen_scopes for scope in (
                f"same_target_table_writers:{table}", "same_target_table_writers",
            )):
                report.skipped[table] = "COMMIT_UNKNOWN 冻结同表写者"
                continue
            # 源预算：同物理源并发 1 + 熔断 OPEN 不派发
            if any(self.source_open_predicate(s) for s in task.physical_sources):
                report.skipped[table] = "物理源熔断 OPEN"
                continue
            busy = [s for s in task.physical_sources if s in active_sources]
            if busy:
                report.skipped[table] = f"源并发预算占用: {busy}"
                continue
            try:
                self.repository.acquire_lease(
                    f"target:DBOPER.{table}", self.worker_id, self.lease_ttl_seconds
                )
            except ContractViolation:
                report.skipped[table] = "目标写租约被持有（同表单写者）"
                continue
            active_sources.update(task.physical_sources)
            try:
                task.run()
                report.dispatched.append(table)
            except Exception as exc:  # noqa: BLE001 - 失败隔离继续：记录后继续其他任务
                report.failures[table] = f"{type(exc).__name__}: {exc}"[:200]
            finally:
                active_sources.difference_update(task.physical_sources)
                self.repository.release_lease(
                    f"target:DBOPER.{table}", self.worker_id
                )
        report.overall = (
            "PARTIAL_SUCCESS_WITH_BACKLOG" if report.failures else "SUCCESS"
        )
        return report
