"""调度桥：单入口周期编排（复用既有调度，不启动第二常驻循环）。

对应计划 §8 与 R05 整改（F08/F09/F10/F14）：
- 调度只保留一个入口：本桥提供 run_cycle() 供既有平台调度器/CLI 调用，
  自身不注册 cron、不起后台线程。
- DAG 排序只在**当前可运行节点集合**中按模式优先级选择（T1 优先），
  不再拓扑排完后全局按模式 sort——历史父任务的 T1 子任务不会跑到父前。
- 同表多模式/多窗口任务按唯一 task_key 排队与记录，不被 by_table 字典
  覆盖丢失。
- 领取的租约 fencing_token 通过 ExecutionContext 传入任务执行；生产
  装载在实际目标提交处还必须再验围栏（ApplyPort enforce_fence）。
- 目标写租约资源默认带 DBOPER 回退（模拟兼容，显式记录降级）；生产
  装配传 require_verified_target=True 时，未验证目标身份的任务直接跳过。
- 派发不等于成功：run() 返回失败/隔离/待父状态被识别并计入欠账；
  全部跳过或存在应完成未闭合窗口时，总体不是 SUCCESS。
- 异常摘要只保留错误类别与安全码，不把原始异常文本放进日报/告警。
- 每表单写：COMMIT_UNKNOWN 表的写任务被冻结（blocked_scopes），不派发。
- 按源预算：同物理源并发 1（初始候选），源熔断 OPEN 时不派发该源任务。
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.planner import DailyRunAnchor, build_dag
from app.services.reporting_pipeline.recovery import (
    COMMIT_UNKNOWN_FREEZE_PREFIX,
    RecoveryService,
    blocked_scopes,
)

# 计入"应完成但未闭合"的跳过原因类别（backlog）：这些不是无任务可跑
BACKLOG_SKIP_CODES = frozenset({
    "COMMIT_UNKNOWN_FROZEN",
    "SOURCE_BREAKER_OPEN",
    "SOURCE_BUDGET_BUSY",
    "LEASE_HELD",
    "PENDING_PARENT",
    "TARGET_IDENTITY_UNVERIFIED",
    "ACTION_NOT_READY",
    "ACTION_BINDING_MISSING",
})

# run() 返回结果中视为"未成功"的状态（派发≠成功）
NON_SUCCESS_RUN_STATES = frozenset({
    "FAILED", "QUARANTINED", "PENDING_PARENT", "WAITING_SOURCE",
    "WAITING_VIEW_FIX", "WAITING_APPROVAL", "WAITING_INPUT",
    "COMMIT_UNKNOWN", "RETRYABLE", "BLOCKED_DEPENDENCY", "DRIFT_DETECTED",
})

# K05 结果契约：显式成功状态白名单。未列名的 status/state 一律按协议错误
# 处理（不因"未识别"而冒充成功）；空结果同样不成功。
SUCCESS_RUN_STATES = frozenset({"OK"})

_SENSITIVE_VALUE_RE = re.compile(r"(password|passwd|secret|token|sql|patient|身份证|电话)", re.I)


class TaskRunnable(Protocol):
    canonical_table: str
    mode: str  # T1 / LATE_BACKLOG / LOOKBACK / MONTHLY_RESCAN / HISTORICAL_REPAIR
    physical_sources: tuple[str, ...]

    def run(self, context: "ExecutionContext | None" = None) -> dict:
        """执行一次任务步（由编排者组合适配器）；返回结构化结果。"""


@dataclass
class ExecutionContext:
    """任务执行上下文：租约围栏凭据 + 冻结的运行业务日锚点。

    - fencing_token 必须随装载请求传到实际目标提交处再验一次；
    - anchor 冻结本轮业务日与 H，跨午夜重试复用同一锚点不漂窗。
    """

    worker_id: str
    lease_resource: str
    fencing_token: int
    anchor: DailyRunAnchor | None = None
    renew: Callable[[], None] | None = None

    def require_fence(self) -> None:
        if self.fencing_token is None or not self.lease_resource:
            raise ContractViolation("执行上下文缺围栏凭据（禁止无 token 执行正式写）")


@dataclass
class CycleReport:
    dispatched: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # task_key -> 人读原因
    skip_codes: dict[str, str] = field(default_factory=dict)  # task_key -> 机器码
    failures: dict[str, dict] = field(default_factory=dict)  # task_key -> 结构化错误
    overall: str = "SUCCESS"
    identity_degraded: bool = False
    cycle_detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dispatched": self.dispatched,
            "skipped": self.skipped,
            "skip_codes": self.skip_codes,
            "failures": self.failures,
            "overall": self.overall,
            "identity_degraded": self.identity_degraded,
            **self.cycle_detail,
        }


MODE_PRIORITY = {
    "T1": 0,
    "LATE_BACKLOG": 1,
    "LOOKBACK": 2,
    "HISTORICAL_REPAIR": 3,
    "MONTHLY_RESCAN": 4,
}


def _task_key(task: TaskRunnable) -> str:
    """同表多任务唯一键：表+模式（+任务自带 window_key）。"""
    window_key = getattr(task, "window_key", None)
    key = f"{task.canonical_table}:{task.mode}"
    if window_key:
        key = f"{key}:{window_key}"
    return key


def sanitize_error(exc: BaseException) -> dict:
    """结构化安全错误：类别 + 安全码 + detail_ref 占位，不透出原始异常串。

    原始异常可能含连接串、SQL 或患者字段；日报/告警只允许结构化类别与
    受控 detail_ref（指向受权限保护的工单/日志存档）。
    """
    raw = f"{exc}"
    if _SENSITIVE_VALUE_RE.search(raw):
        # 含敏感词的原文完全不留，只留类别
        message = f"{type(exc).__name__}:<redacted>"
    else:
        message = (raw or type(exc).__name__)[:120]
    return {
        "error_class": type(exc).__name__,
        "message": message,
        "detail_ref": None,  # 由调用方落工单后回填
    }


class SchedulerBridge:
    def __init__(
        self,
        *,
        repository,
        source_open_predicate: Callable[[str], bool] | None = None,
        lease_ttl_seconds: int = 3600,
        worker_id: str = "worker-1",
        target_resource_for: Callable[[TaskRunnable], str | None] | None = None,
        require_verified_target: bool = False,
        anchor: DailyRunAnchor | None = None,
        action_gate: Callable[[TaskRunnable], None] | None = None,
        read_lease_ttl_seconds: int | None = None,
    ) -> None:
        self.repository = repository
        self.source_open_predicate = source_open_predicate or (lambda _s: False)
        self.lease_ttl_seconds = lease_ttl_seconds
        self.read_lease_ttl_seconds = read_lease_ttl_seconds or lease_ttl_seconds
        self.worker_id = worker_id
        self.target_resource_for = target_resource_for
        self.require_verified_target = require_verified_target
        self.anchor = anchor
        self.action_gate = action_gate  # 动作级就绪校验（validate_action 注入）

    # -- 排序：只在可运行节点中选择（父先子后不被全局模式排序颠倒） ------

    def plan_order(
        self,
        tasks: Sequence[TaskRunnable],
        parents_by_table: Mapping[str, Sequence[str]] | None = None,
    ) -> list[TaskRunnable]:
        """就绪队列调度：每步只在"父已全部输出"的可运行任务中按模式优先。

        F08 回归：历史父（HISTORICAL_REPAIR）+其 T1 子任务场景下，子任务
        在父输出前不可运行，不会被全局 T1 排序提前；独立 T1 任务不受
        父子约束，仍可最先执行。
        """
        parents = parents_by_table or {t.canonical_table: [] for t in tasks}
        build_dag(parents)  # 环/未登记依赖在排序前显式拒绝（与原语义一致）
        remaining = list(tasks)
        emitted_tables: set[str] = set()
        ordered: list[TaskRunnable] = []
        while remaining:
            runnable = [
                t for t in remaining
                if all(p in emitted_tables for p in parents.get(t.canonical_table, ()))
            ]
            if not runnable:
                # 不应发生（build_dag 已验环）；防御性保留全部剩余任务
                ordered.extend(sorted(remaining, key=lambda t: _task_key(t)))
                break
            runnable.sort(key=lambda t: (MODE_PRIORITY.get(t.mode, 99), _task_key(t)))
            chosen = runnable[0]
            ordered.append(chosen)
            remaining.remove(chosen)
            emitted_tables.add(chosen.canonical_table)
        return ordered

    # -- 周期 ------------------------------------------------------------

    @staticmethod
    def _task_target_triple(task: TaskRunnable) -> tuple[str, str, str] | None:
        """任务的目标三元组（实例/机构/表）；缺任一成分返回 None。

        生产装配注入 target_resource_for（verified_object_ref 形如
        instance.tenant.table）或任务自带 target_binding；模拟回退只给表名。
        """
        binding = getattr(task, "target_binding", None)
        if isinstance(binding, Mapping):
            triple = (
                binding.get("target_instance"),
                binding.get("tenant"),
                binding.get("target_table"),
            )
            if all(triple):
                return triple  # type: ignore[return-value]
        resource = getattr(task, "target_resource", None) or ""
        # target:DBOPER.{tenant}.{table} / target:{instance}.{tenant}.{table}
        body = resource[len("target:"):] if resource.startswith("target:") else ""
        parts = body.split(".")
        if len(parts) >= 3 and all(parts[:3]):
            return (parts[0], parts[1], parts[2])
        return None

    def _frozen_for(
        self,
        task: TaskRunnable,
        frozen_scopes: set[str],
    ) -> bool:
        """K02：提交不明只冻结同目标（实例/机构/表）的重叠写。

        - 结构化范围（含三元组）→ 只匹配同三元组任务；
        - 无后缀全局范围（批次未绑定目标，范围不可判定）→ 冻结全部
          APPLY 任务（临时全局保护，等待人工定位）；
        - 仅表名后缀（历史格式）→ 按表名匹配（兼容旧记录）。
        """
        if not frozen_scopes:
            return False
        if COMMIT_UNKNOWN_FREEZE_PREFIX in frozen_scopes:
            # 范围不可判定的全局保护：只有正式写（APPLY）任务被冻住；
            # capture 仍可继续（不写目标）
            return getattr(task, "primary_action", None) == "APPLY" or (
                getattr(task, "_apply_fn", None) is not None
            )
        table = task.canonical_table
        legacy = f"{COMMIT_UNKNOWN_FREEZE_PREFIX}:{table}"
        if legacy in frozen_scopes:
            return True
        triple = self._task_target_triple(task)
        if triple is None:
            return False
        structured = (
            f"{COMMIT_UNKNOWN_FREEZE_PREFIX}:{triple[0]}|{triple[1]}|{triple[2]}"
        )
        return structured in frozen_scopes

    def run_cycle(
        self,
        tasks: Sequence[TaskRunnable],
        parents_by_table: Mapping[str, Sequence[str]] | None = None,
    ) -> CycleReport:
        report = CycleReport()
        recovery = RecoveryService(self.repository)
        frozen_scopes = set(blocked_scopes(recovery.resume_all()))
        unresolved_freeze = COMMIT_UNKNOWN_FREEZE_PREFIX in frozen_scopes

        active_sources: set[str] = set()
        for task in self.plan_order(tasks, parents_by_table):
            table = task.canonical_table
            key = _task_key(task)
            # COMMIT_UNKNOWN 冻结（K02：按目标范围，单表不明不冻全批）
            if self._frozen_for(task, frozen_scopes):
                report.skipped[key] = "COMMIT_UNKNOWN 冻结同表写者"
                report.skip_codes[key] = "COMMIT_UNKNOWN_FROZEN"
                continue
            # 动作级就绪（R05）：未就绪动作跳过并显式记录，不改 READY
            if self.action_gate is not None:
                try:
                    self.action_gate(task)
                except ContractViolation as exc:
                    report.skipped[key] = f"动作未就绪: {str(exc)[:120]}"
                    report.skip_codes[key] = "ACTION_NOT_READY"
                    continue
            # 目标写租约资源：生产必须来自已验证 TaskSpec；模拟允许 DBOPER 回退
            resource = (
                self.target_resource_for(task)
                if self.target_resource_for is not None
                else getattr(task, "target_resource", None)
            )
            if resource is None and not self.require_verified_target:
                resource = f"target:DBOPER.{table}"
                report.identity_degraded = True
            if resource is None:
                report.skipped[key] = "目标实例身份未验证（禁止默认 DBOPER 写）"
                report.skip_codes[key] = "TARGET_IDENTITY_UNVERIFIED"
                continue
            # 源预算：同物理源并发 1 + 熔断 OPEN 不派发
            if any(self.source_open_predicate(s) for s in task.physical_sources):
                report.skipped[key] = "物理源熔断 OPEN"
                report.skip_codes[key] = "SOURCE_BREAKER_OPEN"
                continue
            busy = [s for s in task.physical_sources if s in active_sources]
            if busy:
                report.skipped[key] = f"源并发预算占用: {busy}"
                report.skip_codes[key] = "SOURCE_BUDGET_BUSY"
                continue
            # K06：物理源读取租约（跨进程共享预算，经仓储原子领取）；
            # CAPTURE 只拿读取资源，不占目标写租约。
            read_leases: list[tuple[str, object]] = []
            source_busy_cross_process = False
            for src in dict.fromkeys(task.physical_sources):
                try:
                    read_leases.append(
                        (src, self.repository.acquire_lease(
                            f"read:{src}", self.worker_id,
                            self.read_lease_ttl_seconds,
                        ))
                    )
                except ContractViolation:
                    report.skipped[key] = f"源读取预算被其他进程占用: {src}"
                    report.skip_codes[key] = "SOURCE_BUDGET_BUSY"
                    source_busy_cross_process = True
                    break
            if source_busy_cross_process:
                for src, lease in read_leases:
                    self._safe_release(f"read:{src}", lease)
                continue
            active_sources.update(task.physical_sources)
            # K06：目标写租约仅正式装载（APPLY）任务领取
            wants_apply = (
                getattr(task, "_apply_fn", None) is not None
                or getattr(task, "primary_action", None) == "APPLY"
            )
            write_lease = None
            if wants_apply:
                try:
                    write_lease = self.repository.acquire_lease(
                        resource, self.worker_id, self.lease_ttl_seconds
                    )
                except ContractViolation:
                    report.skipped[key] = "目标写租约被持有（同表单写者）"
                    report.skip_codes[key] = "LEASE_HELD"
                    for src, lease in read_leases:
                        self._safe_release(f"read:{src}", lease)
                    active_sources.difference_update(task.physical_sources)
                    continue
            if write_lease is not None:
                fence_resource, fence_token = resource, write_lease.fencing_token
            elif read_leases:
                first_src, first_lease = read_leases[0]
                fence_resource, fence_token = (
                    f"read:{first_src}", first_lease.fencing_token
                )
            else:
                # 无源无写（退化任务）：用目标资源兜底领读侧围栏，保证
                # ExecutionContext 仍有有效围栏（require_fence 硬门）
                fence_lease = self.repository.acquire_lease(
                    resource, self.worker_id, self.lease_ttl_seconds
                )
                fence_resource, fence_token = resource, fence_lease.fencing_token
                write_lease = fence_lease  # 释放路径一致
            context = ExecutionContext(
                worker_id=self.worker_id,
                lease_resource=fence_resource,
                fencing_token=fence_token,
                anchor=self.anchor,
                renew=(
                    lambda r=fence_resource, t=fence_token: self.repository.renew_lease(
                        r, self.worker_id, t, ttl_seconds=self.lease_ttl_seconds
                    )
                ),
            )
            try:
                # 兼容仅位置/仅关键字旧实现：能接收 context 则注入
                result = self._invoke_task(task, context)
                status = self._run_status(result)
                if status is None:
                    report.dispatched.append(key)
                else:
                    report.failures[key] = {
                        "error_class": "RUN_STATE",
                        "message": f"run() 返回未成功状态 {status}",
                        "run_state": status,
                        "detail_ref": None,
                    }
            except Exception as exc:  # noqa: BLE001 - 失败隔离继续：记录后继续其他任务
                report.failures[key] = sanitize_error(exc)
            finally:
                active_sources.difference_update(task.physical_sources)
                for src, lease in read_leases:
                    self._safe_release(f"read:{src}", lease)
                if write_lease is not None:
                    self._safe_release(resource, write_lease)
        if unresolved_freeze:
            report.cycle_detail["commit_unknown_scope_unresolved"] = True
            report.cycle_detail["commit_unknown_note"] = (
                "存在未绑定目标的 COMMIT_UNKNOWN 批次：全局临时保护（仅冻结"
                "正式写任务），须人工定位目标绑定后解除"
            )
        report.overall = self._overall(tasks, report)
        return report

    def _safe_release(self, resource: str, lease) -> None:
        """释放租约：绑定 token；失败只记录，不阻断后续任务释放。"""
        try:
            self.repository.release_lease(
                resource, self.worker_id, fencing_token=lease.fencing_token
            )
        except ContractViolation:
            pass  # 晚到释放被拒：租约已被新运行顶替，符合预期

    @staticmethod
    def _invoke_task(task: TaskRunnable, context: ExecutionContext) -> dict:
        try:
            sig = inspect.signature(task.run)
            accepts = any(
                p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
                for p in sig.parameters.values()
            )
        except (TypeError, ValueError):
            accepts = True
        if accepts:
            return task.run(context)
        # 旧签名 run()（无参数）：模拟任务兼容路径；生产适配器必须收 ctx
        return task.run()

    @staticmethod
    def _run_status(result: object) -> str | None:
        """K05 结果契约：成功只认白名单；未识别/空结果按协议错误处理。

        - Mapping 带 status/state：SUCCESS_RUN_STATES 白名单 → None（成功）；
          NON_SUCCESS_RUN_STATES → 该状态；其余任意值 → RUN_PROTOCOL_ERROR；
        - Mapping 无 status/state：ok=True 视为显式成功（旧模拟契约）；
          ok=False → FAILED；其余（含空 dict）→ RUN_PROTOCOL_ERROR；
        - 非 Mapping / None → RUN_PROTOCOL_ERROR。
        """
        if not isinstance(result, Mapping):
            return "RUN_PROTOCOL_ERROR"
        status = result.get("status") or result.get("state")
        if status is None:
            if result.get("ok") is True:
                return None
            if result.get("ok") is False:
                return "FAILED"
            return "RUN_PROTOCOL_ERROR"
        if not isinstance(status, str):
            return "RUN_PROTOCOL_ERROR"
        upper = status.upper()
        if upper in SUCCESS_RUN_STATES:
            return None
        if upper in NON_SUCCESS_RUN_STATES:
            return upper
        return "RUN_PROTOCOL_ERROR"

    def _overall(self, tasks: Sequence[TaskRunnable], report: CycleReport) -> str:
        """总体状态如实：派发≠成功；应完成未闭合 → 不能 SUCCESS。"""
        if report.failures:
            return "PARTIAL_SUCCESS_WITH_BACKLOG"
        backlog_skips = {
            k for k, code in report.skip_codes.items() if code in BACKLOG_SKIP_CODES
        }
        if backlog_skips:
            if report.dispatched:
                return "PARTIAL_SUCCESS_WITH_BACKLOG"
            return "WAITING_WITH_BACKLOG"
        if not tasks:
            return "NO_WORK"
        if not report.dispatched and report.skipped:
            # 全部跳过但均为非欠账原因：仍不是成功（未完成应跑任务）
            return "WAITING_WITH_BACKLOG"
        return "SUCCESS"
