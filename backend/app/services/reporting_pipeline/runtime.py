"""运行用例串联（R05）：单一入口把 plan→capture→stage→quality→apply→
readback→状态/缺口/日报 串成一条链。

对应整改计划 §R05：
- CLI 与既有调度调用同一服务；不新增第二常驻调度循环。
- 模拟装配与生产装配显式分开：build_simulation_cycle 一律内存仓储 +
  假适配器 + simulation 标记；build_production_cycle 提供 PG 耐久仓储、
  目标身份检查和暂存，真实读取/质量/装载及批准围栏由注入步骤负责。
  失败告警只冻结到 outbox；生产步骤与 HTTP sender 尚须明确接线。
- 任务执行以 ExecutionContext（租约 token + 冻结锚点）贯穿；正式装载
  在目标提交处再验围栏（ApplyPort enforce_fence）。
- 失败留缺口、隔离组工单化、独立任务继续；总体状态如实（派发≠成功）。
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence

from app.services.reporting_pipeline.apply_port import (
    ApplyPort,
    ApplyRequest,
    ApplyRefused,
)
from app.services.reporting_pipeline.alerts_client import build_event_body
from app.services.reporting_pipeline.contracts import (
    ContractViolation,
    PipelineAction,
    SourceRef,
)
from app.services.reporting_pipeline.durable_staging import DurableFileStageStore
from app.services.reporting_pipeline.planner import DailyRunAnchor, freeze_daily_anchor
from app.services.reporting_pipeline.reports import build_daily_report
from app.services.reporting_pipeline.repositories import (
    ControlRepository,
    InMemoryControlRepository,
)
from app.services.reporting_pipeline.scheduler_bridge import SchedulerBridge
from app.services.reporting_pipeline.seed_loader import SeedBundle


def unique_worker_id(base: str = "worker") -> str:
    """K03：每次进程一个唯一运行身份——同名新运行不得继承旧租约语义。"""
    return f"{base}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def physical_source_key(src: SourceRef) -> str:
    """K06：稳定物理源资源键（源组+实例地址），不是视图级 object_id。

    同一物理实例上的不同视图共享同一预算资源；不同实例不互相阻塞。
    """
    return f"{src.source_group}@{src.host}:{src.port}"


@dataclass(frozen=True)
class ActionBinding:
    """K01：本地动作排程绑定——不放宽整链 enabled 的显式授权面。

    - 整链 enabled 仍走 validate_enable 五层 READY 门禁（REPORT 含在内）；
    - 未 enabled 的任务要派发本地动作（CAPTURE/STAGE/APPLY），必须有
      覆盖该表该动作、在有效期内的绑定，且 spec.validate_action 通过；
    - REPORT 不在本绑定范围：省端报送仍要求全链 READY；
    - 绑定须带批准来源（approval_ref/granted_by），程序不得自行产生。
    """

    canonical_table: str
    actions: tuple[PipelineAction, ...]
    valid_from: datetime
    valid_until: datetime
    approval_ref: str
    granted_by: str
    tenant: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def active(self, now: datetime) -> bool:
        return self.valid_from <= now < self.valid_until

    def covers(self, action: PipelineAction) -> bool:
        return action in self.actions

    def validate(self) -> None:
        problems: list[str] = []
        if not self.approval_ref or not self.granted_by:
            problems.append("绑定缺批准来源（approval_ref/granted_by）")
        if self.valid_from >= self.valid_until:
            problems.append("绑定有效期非法（valid_from >= valid_until）")
        if not self.actions:
            problems.append("绑定未声明任何动作")
        if PipelineAction.REPORT in self.actions:
            problems.append("REPORT 不在本地绑定范围（省端报送须全链 READY）")
        if problems:
            raise ContractViolation(
                f"ActionBinding[{self.canonical_table}]: " + "; ".join(problems)
            )


@dataclass
class DailyCycleConfig:
    business_tz_name: str = "Asia/Shanghai"
    worker_id: str = "worker-1"
    lease_ttl_seconds: int = 3600
    rescan_cycle_days: int = 30
    parents_by_table: dict[str, Sequence[str]] = field(default_factory=dict)


def resolve_bound_action(
    spec,
    bindings: Sequence[ActionBinding],
    now: datetime,
) -> PipelineAction | None:
    """K01 调度判定：enabled 走全链；否则找有效绑定覆盖的最高动作。

    返回 None = 不可派发（无绑定或绑定失效或动作未就绪）。
    动作优先级 APPLY > STAGE > CAPTURE：绑定覆盖且 validate_action 通过的
    最高动作作为任务主动作（apply_fn 缺失时由 PipelineTask 拒绝执行）。
    """
    if spec.enabled:
        return PipelineAction.REPORT  # 全链任务：按原 enabled 语义派发
    for action in (PipelineAction.APPLY, PipelineAction.STAGE, PipelineAction.CAPTURE):
        binding = next(
            (b for b in bindings
             if b.canonical_table == spec.canonical_table
             and b.active(now) and b.covers(action)),
            None,
        )
        if binding is None:
            continue
        try:
            spec.validate_action(action)
        except ContractViolation:
            continue
        return action
    return None


class PipelineTask:
    """一个表×模式的任务步：组合注入的采集/装载适配器。

    适配器协议（由 R03 真实实现或离线假实现提供）：
    - capture_fn(ctx, task) -> CaptureOutcome（行分类+manifest）
    - apply_fn(ctx, task, capture) -> ApplyOutcome（committed/unknown）
    生产装配传真实实现；模拟装配传假实现，输出带 simulation 标记。
    """

    def __init__(
        self,
        *,
        canonical_table: str,
        mode: str,
        physical_sources: tuple[str, ...],
        target_resource: str | None,
        spec,
        capture_fn: Callable | None = None,
        apply_fn: Callable | None = None,
        window_key: str | None = None,
        declared_action: PipelineAction | None = None,
        target_binding: Mapping[str, str] | None = None,
    ) -> None:
        self.canonical_table = canonical_table
        self.mode = mode
        self.physical_sources = physical_sources
        self.target_resource = target_resource
        self.spec = spec
        self._capture_fn = capture_fn
        self._apply_fn = apply_fn
        self.window_key = window_key
        self.declared_action = declared_action
        self.target_binding = target_binding
        if (
            declared_action == PipelineAction.APPLY
            and apply_fn is None
        ):
            # K05：正式 APPLY 缺真实 apply 实现，构造即拒绝——不允许
            # "运行绿了、数据没进"的 stage_only 冒充装载。
            raise ContractViolation(
                f"[{canonical_table}] 声明动作 APPLY 但缺 apply_fn 实现"
                "（正式装载不得以 stage_only 冒充）"
            )

    @property
    def primary_action(self) -> PipelineAction:
        if self.declared_action is not None:
            return self.declared_action
        return PipelineAction.APPLY if self._apply_fn is not None else PipelineAction.CAPTURE

    def run(self, context=None) -> dict:
        if context is None or self._capture_fn is None:
            return {"status": "FAILED", "reason": "缺执行上下文或采集适配器"}
        if (
            self.declared_action == PipelineAction.APPLY
            and self._apply_fn is None
        ):
            return {
                "status": "FAILED",
                "reason": "正式APPLY缺apply实现（stage_only 不计已入前置机）",
            }
        try:
            context.require_fence()
        except ContractViolation as exc:
            return {"status": "FAILED", "reason": str(exc)}
        capture = self._capture_fn(context, self)
        if not capture.get("ok"):
            return {"status": capture.get("state", "FAILED")}
        if self._apply_fn is None:
            return {"status": "OK", "stage_only": True, "capture": capture}
        apply_result = self._apply_fn(context, self, capture)
        if apply_result.get("committed") is None:
            return {"status": "COMMIT_UNKNOWN", "capture": capture}
        if not apply_result.get("committed"):
            return {"status": "FAILED", "capture": capture}
        return {"status": "OK", "capture": capture, "apply": apply_result}


class DailyCycleService:
    """日轮服务：锚点冻结 → 桥调度 → 日报（同一入口，可重复调用）。"""

    def __init__(
        self,
        *,
        repository: ControlRepository,
        bundle: SeedBundle,
        task_factory: Callable[[DailyRunAnchor], Sequence[PipelineTask]],
        config: DailyCycleConfig | None = None,
        simulation: bool = True,
        source_open_predicate: Callable[[str], bool] | None = None,
        daily_report_builder: Callable[..., object] = build_daily_report,
        unbound_tables_provider: Callable[[], Sequence[str]] | None = None,
    ) -> None:
        self.repository = repository
        self.bundle = bundle
        self.task_factory = task_factory
        self.config = config or DailyCycleConfig()
        self.simulation = simulation
        self.source_open_predicate = source_open_predicate
        self._daily_report_builder = daily_report_builder
        self._unbound_tables_provider = unbound_tables_provider

    def run_day(self, now: datetime) -> dict:
        anchor = freeze_daily_anchor(
            now, business_tz_name=self.config.business_tz_name
        )
        tasks = list(self.task_factory(anchor))
        bridge = SchedulerBridge(
            repository=self.repository,
            source_open_predicate=self.source_open_predicate,
            lease_ttl_seconds=self.config.lease_ttl_seconds,
            worker_id=self.config.worker_id,
            require_verified_target=not self.simulation,
            anchor=anchor,
            action_gate=self._action_gate,
        )
        cycle = bridge.run_cycle(tasks, self.config.parents_by_table or None)
        failure_handling = self._record_cycle_failures(cycle, anchor)
        report = self._daily_report_builder(
            business_day=anchor.business_day.isoformat(),
            repository=self.repository,
            bundle=self.bundle,
            parents_by_table=dict(self.config.parents_by_table),
            simulation=self.simulation,
            rescan_cycle_days=self.config.rescan_cycle_days,
        )
        return {
            "anchor": {
                "business_day": anchor.business_day.isoformat(),
                "business_tz": anchor.business_tz_name,
                "frozen_at": anchor.frozen_at.isoformat(),
                "window": anchor.business_window().fingerprint(),
            },
            "simulation": self.simulation,
            "cycle": cycle.to_dict(),
            "failure_handling": failure_handling,
            "daily_report": report.to_dict(),
            "unbound_tables": (
                list(self._unbound_tables_provider())
                if self._unbound_tables_provider is not None
                else []
            ),
        }

    def _record_cycle_failures(self, cycle, anchor: DailyRunAnchor) -> dict:
        """把本轮失败记入缺口账本并冻结脱敏 OPENED 事件到本地 outbox。

        此处仅入队，不调用 HTTP sender。失败详情保留在受控的 cycle 结构中；
        gap 与 outbox 只写稳定表名、业务日和通用错误码，避免异常文本或患者键外泄。
        """
        if not cycle.failures:
            return {"status": "NO_FAILURES", "queued": [], "errors": []}

        window = anchor.business_window()
        window_fingerprint = window.fingerprint()
        business_day = anchor.business_day.isoformat()
        failed_tables = sorted(
            {task_key.split(":", 1)[0] for task_key in cycle.failures}
        )
        queued: list[dict] = []
        errors: list[dict] = []

        for table in failed_tables:
            stage = "GAP_RECORD"
            detail_ref = f"gap://{business_day}/{table}"
            try:
                existing_gaps = self.repository.open_gaps(table)
                if not any(
                    gap.window.fingerprint() == window_fingerprint
                    and gap.reason == "SCHEDULER_TASK_FAILED"
                    for gap in existing_gaps
                ):
                    self.repository.record_gap(
                        table, window, "SCHEDULER_TASK_FAILED"
                    )

                stage = "ALERT_OUTBOX_ENQUEUE"
                incident = self.repository.create_incident(
                    incident_key=f"T1:{business_day}:{table}",
                    category="EXTRACT_FAILED",
                    affected_tables=[table],
                )
                recommended_action = (
                    "检查任务配置与源端状态，修复后按原业务日重跑并核对缺口。"
                )
                opened_event_id = f"r189t1.{incident.incident_id}.OPENED.1"
                event = self.repository.get_outbox_event(opened_event_id)
                if event is None:
                    title = f"T+1任务 {table} 在 {business_day} 运行失败"
                    event_metadata = {
                        "system": "T1_REPORTING",
                        "environment": "production" if not self.simulation else "simulation",
                        "canonical_table": table,
                        "stage": "CAPTURE_OR_APPLY",
                        "business_date": business_day,
                        "error_code": "SCHEDULER_RUN_FAILED",
                        "task_status": "FAILED",
                        "detail_ref": detail_ref,
                        "recommended_action": recommended_action,
                    }
                    body = build_event_body(
                        source_event_id=opened_event_id,
                        event_type="alert",
                        category="EXTRACT_FAILED",
                        severity="yellow",
                        title=title,
                        body=(
                            f"业务日 {business_day} 的 {table} 任务未完成。"
                            f"建议动作：{recommended_action} 详情引用：{detail_ref}。"
                        ),
                        occurred_at=datetime.now(timezone.utc).isoformat(),
                        metadata=event_metadata,
                    )
                    event = self.repository.append_incident_event(
                        incident,
                        event_kind="OPENED",
                        severity="yellow",
                        title=title,
                        body_bytes=body,
                        metadata=event_metadata,
                    )
                queued.append(
                    {
                        "table": table,
                        "source_event_id": event.source_event_id,
                        "detail_ref": detail_ref,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - retain independent failures, report safe class only
                error_class = type(exc).__name__
                errors.append(
                    {
                        "table": table,
                        "stage": stage,
                        "error_class": (
                            error_class
                            if error_class.isascii() and error_class.isidentifier()
                            else "UNKNOWN_ERROR"
                        ),
                        "error_code": "FAILURE_HANDLING_FAILED",
                    }
                )

        result = {
            "status": "FAILED" if errors else "QUEUED",
            "queued": queued,
            "errors": errors,
        }
        if errors:
            cycle.cycle_detail["failure_handling"] = result
            cycle.overall = (
                "PARTIAL_SUCCESS_WITH_BACKLOG"
                if cycle.dispatched else "WAITING_WITH_BACKLOG"
            )
        return result

    def _action_gate(self, task: PipelineTask) -> None:
        spec = getattr(task, "spec", None)
        if spec is None:
            raise ContractViolation(
                f"[{task.canonical_table}] 无 TaskSpec，动作就绪无法核验"
            )
        action = task.primary_action
        spec.validate_action(action)


def make_apply_step(
    port: ApplyPort,
    *,
    executor,
    request_builder: Callable[[PipelineTask, dict], ApplyRequest],
    target_rows_reader: Callable[[PipelineTask], Mapping],
) -> Callable:
    """装载步骤工厂：执行器/请求构造/目标回读由装配方注入（受控边界在外层）。

    ExecutionContext 的租约资源与 fencing_token 写入装载请求，由
    ApplyPort（enforce_fence）在实际提交门前核验。
    """

    def apply_fn(context, task, capture):
        request = request_builder(task, capture)
        request = ApplyRequest(
            **{
                **{
                    f: getattr(request, f)
                    for f in request.__dataclass_fields__
                },
                "lease_resource": context.lease_resource,
                "fencing_token": context.fencing_token,
            }
        )
        try:
            result = port.apply(request, executor=executor, target_rows=target_rows_reader(task))
        except ApplyRefused as exc:
            return {"committed": False, "refused": str(exc)[:200]}
        return {
            "committed": result.committed,
            "operation_id": result.operation_id,
            "rows_affected": result.rows_affected,
        }

    return apply_fn


def build_simulation_cycle(
    bundle: SeedBundle,
    *,
    repository: ControlRepository | None = None,
    capture_fn: Callable | None = None,
    apply_fn: Callable | None = None,
    config: DailyCycleConfig | None = None,
    source_open_predicate: Callable[[str], bool] | None = None,
    action_bindings: Sequence[ActionBinding] = () ,
    now_fn: Callable[[], datetime] | None = None,
) -> DailyCycleService:
    """模拟装配（离线/隔离验证用）：内存状态 + 可注入假适配器。

    输出整体带 simulation=True；不得用于生产排程。
    K01：未 enabled 的任务要出现在模拟日轮中，必须有有效 ActionBinding
    且动作就绪（与生产同规则，不允许靠模拟放宽）。
    """
    repository = repository or InMemoryControlRepository()
    now_fn = now_fn or datetime.now

    def task_factory(anchor: DailyRunAnchor) -> list[PipelineTask]:
        tasks: list[PipelineTask] = []
        for spec in bundle.tasks:
            action = resolve_bound_action(spec, action_bindings, now_fn())
            if action is None and not spec.enabled:
                continue
            tasks.append(
                PipelineTask(
                    canonical_table=spec.canonical_table,
                    mode="T1",
                    physical_sources=tuple(
                        physical_source_key(s) for s in spec.source_candidates
                    ),
                    target_resource=None,  # 模拟：桥记录降级；生产必须已验证
                    spec=spec,
                    capture_fn=capture_fn,
                    apply_fn=(
                        apply_fn
                        if action in (PipelineAction.REPORT, PipelineAction.APPLY)
                        or (spec.enabled and apply_fn is not None)
                        else None
                    ),
                    declared_action=(
                        None if spec.enabled else action
                    ),
                )
            )
        return tasks

    return DailyCycleService(
        repository=repository,
        bundle=bundle,
        task_factory=task_factory,
        config=config,
        simulation=True,
        source_open_predicate=source_open_predicate,
    )


def build_production_cycle(
    *,
    session_factory,
    bundle: SeedBundle,
    stage_root: str,
    business_tz_name: str = "Asia/Shanghai",
    worker_id: str | None = None,
    relay_base_url: str | None = None,
    capture_fn: Callable | None = None,
    apply_fn: Callable | None = None,
    config: DailyCycleConfig | None = None,
    action_bindings: Sequence[ActionBinding] = (),
    now_fn: Callable[[], datetime] | None = None,
) -> DailyCycleService:
    """生产装配：耐久仓储 + 平台批准 + 围栏 + 耐久暂存。

    - 仓储换 SqlAlchemyControlRepository（PG asset schema）；
    - require_verified_target=True：目标身份未验证的任务不派发；
    - K01：未 enabled 任务按 ActionBinding 派发本地动作（CAPTURE/STAGE/
      APPLY），REPORT 仍走五层门禁；无绑定不派发；
    - K03：worker_id 缺省生成唯一运行身份（pid+uuid），同名新运行不继承
      旧租约；
    - K06：physical_sources 用稳定物理实例资源键（源组@实例:端口），
      读取预算跨进程经仓储租约共享；
    - 告警仅冻结到 PG outbox；HTTP sender 尚未接入。本 builder 不接受
      relay_base_url，以免 URL 参数造成已装配真实外发的误判；
    - 本函数不产生任何授权：真实读取/stage/apply 仍按各自门禁逐例批准。
    """
    if relay_base_url:
        raise ContractViolation(
            "生产告警 HTTP sender 尚未接线；当前仅写入 outbox，不使用 relay_base_url"
        )
    from app.services.reporting_pipeline.pg_repository import (
        SqlAlchemyControlRepository,
    )

    repository = SqlAlchemyControlRepository(session_factory)
    # 耐久暂存目录在建线时校验可写；采集适配器经 task 注入使用
    DurableFileStageStore(stage_root)
    effective_worker = worker_id or unique_worker_id("r189t1")
    now_fn = now_fn or datetime.now

    def task_factory(anchor: DailyRunAnchor) -> list[PipelineTask]:
        tasks: list[PipelineTask] = []
        for spec in bundle.tasks:
            action = resolve_bound_action(spec, action_bindings, now_fn())
            if action is None and not spec.enabled:
                continue
            tgt = spec.target
            verified = getattr(tgt, "current_identity_verified", False)
            # K02：目标三元组显式传递（实例/机构/表），冻结范围不靠字符串猜
            binding = (
                {
                    "target_instance": f"{tgt.host}:{tgt.port}/{tgt.service}",
                    "tenant": tgt.owner,
                    "target_table": tgt.table,
                }
                if verified
                else None
            )
            target_resource = (
                "target:{instance}.{tenant}.{table}".format(**binding)
                if binding
                else None
            )
            wants_apply = (
                spec.enabled and apply_fn is not None
            ) or action == PipelineAction.APPLY
            tasks.append(
                PipelineTask(
                    canonical_table=spec.canonical_table,
                    mode="T1",
                    physical_sources=tuple(
                        physical_source_key(s) for s in spec.source_candidates
                    ),
                    target_resource=target_resource,
                    spec=spec,
                    capture_fn=capture_fn,
                    apply_fn=apply_fn if wants_apply else None,
                    declared_action=(
                        None if spec.enabled else action
                    ),
                    target_binding=binding,
                )
            )
        return tasks

    return DailyCycleService(
        repository=repository,
        bundle=bundle,
        task_factory=task_factory,
        config=config or DailyCycleConfig(
            business_tz_name=business_tz_name, worker_id=effective_worker
        ),
        simulation=False,
    )
