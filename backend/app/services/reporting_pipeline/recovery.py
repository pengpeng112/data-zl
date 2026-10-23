"""恢复层：按批次状态与故障隔离规则给出下一安全动作。

对应《失败后继续抽取与补抽规则.md》机器规则：
- 抽取中断/部分分片：已完整分片可复用，未完整重取；不推进捕获水位。
- 质量错误：隔离组工单化，独立合法组继续。
- COMMIT_UNKNOWN：冻结同表写者，先核同事务凭据/目标内容，禁止盲写。
- 父失败只阻对应子键组。
- 默认 CONTINUE_INDEPENDENT_SCOPES：恢复动作不阻塞其他表/日/组。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.reporting_pipeline.contracts import (
    BatchState,
    ContractViolation,
)
from app.services.reporting_pipeline.repositories import ControlRepository


# COMMIT_UNKNOWN 冻结范围前缀（K02 结构化）：
# - "same_target_table_writers:{instance}|{tenant}|{table}" 按目标三元组冻结；
# - "same_target_table_writers"（无后缀）= 范围不可判定的全局保护，须配
#   人工定位告警，不得长期停留。
COMMIT_UNKNOWN_FREEZE_PREFIX = "same_target_table_writers"


@dataclass(frozen=True)
class RecoveryAction:
    batch_id: str
    action: str          # 机器动作码
    scope: str           # 作用范围（隔离边界）
    blocking: bool       # True=阻塞该范围，False=可与其他任务并行
    precondition: str    # 恢复前置
    alert_code: str | None = None
    # K02：冻结范围的结构化成分（实例/机构/表）；范围不可判定时为 None。
    target_instance: str | None = None
    tenant: str | None = None
    target_table: str | None = None
    scope_unresolved: bool = False

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id, "action": self.action, "scope": self.scope,
            "blocking": self.blocking, "precondition": self.precondition,
            "alert_code": self.alert_code,
            "target_instance": self.target_instance, "tenant": self.tenant,
            "target_table": self.target_table,
            "scope_unresolved": self.scope_unresolved,
        }


class RecoveryService:
    """恢复层（K04）：只经仓储公共接口读取批次，内存/PG 同一契约。"""

    def __init__(self, repository: ControlRepository) -> None:
        self.repository = repository

    def resume(self, batch_id: str) -> RecoveryAction:
        record = self.repository.get_batch(batch_id)
        # record.state 是两实现共同的权威状态（内存同步于状态机；PG 读行）
        return _next_action(batch_id, record.state, record=record)

    def resume_all(self) -> list[RecoveryAction]:
        actions: list[RecoveryAction] = []
        for record in self.repository.list_batches():
            state = record.state
            actions.append(_next_action(record.batch_id, state, record=record))
        return actions


def _commit_unknown_scope(record) -> tuple[str, bool, dict]:
    """K02：提交不明的冻结范围。

    批次带目标绑定（实例/机构/表）→ 结构化范围，只冻结同目标表重叠写；
    未绑定 → 全局保护 + scope_unresolved（需人工定位，产生明确告警）。
    """
    binding = {
        "target_instance": getattr(record, "target_instance", None),
        "tenant": getattr(record, "tenant", None),
        "target_table": getattr(record, "target_table", None),
    }
    if all(binding.values()):
        scope = (
            f"{COMMIT_UNKNOWN_FREEZE_PREFIX}:"
            f"{binding['target_instance']}|{binding['tenant']}|{binding['target_table']}"
        )
        return scope, False, binding
    return COMMIT_UNKNOWN_FREEZE_PREFIX, True, binding


def _next_action(
    batch_id: str,
    state: BatchState,
    *,
    record=None,
) -> RecoveryAction:
    if state == BatchState.PLANNED:
        return RecoveryAction(
            batch_id, "START_CAPTURE", "batch", False,
            "READ_READY 校验通过（未通过则保持等待）",
        )
    if state == BatchState.CAPTURING:
        return RecoveryAction(
            batch_id, "REREAD_INCOMPLETE_SLICES", "incomplete_slices", False,
            "完整分片复用；未完整分片重取，水位不推进",
            alert_code="EXTRACT_FAILED",
        )
    if state == BatchState.CAPTURED:
        return RecoveryAction(
            batch_id, "VALIDATE_QUALITY", "batch", False,
            "manifest 完整（分页完整+守恒）",
        )
    if state in (BatchState.VALIDATING, BatchState.VALIDATED):
        return RecoveryAction(
            batch_id, "ISOLATE_AND_CONTINUE", "quarantined_groups", False,
            "坏组工单化；独立合法组继续装载",
            alert_code="QUALITY_BLOCKED",
        )
    if state in (BatchState.APPLY_PENDING,):
        return RecoveryAction(
            batch_id, "REQUEST_APPROVED_APPLY", "batch", False,
            "APPLY_READY 门禁（批准+白名单+围栏）",
            alert_code="SLA_AT_RISK",
        )
    if state == BatchState.APPLYING:
        return RecoveryAction(
            batch_id, "AWAIT_COMMIT_RESULT", "batch", False,
            "等待执行器结果",
        )
    if state == BatchState.COMMIT_UNKNOWN:
        # K02：范围按批次目标绑定结构化；未绑定时全局保护并显式要求人工定位
        scope, unresolved, binding = _commit_unknown_scope(record)
        return RecoveryAction(
            batch_id, "RECONCILE_BEFORE_ANY_WRITE", scope, True,
            (
                "先核同事务提交凭据与目标内容；确认后再 APPLIED/APPLY_PENDING"
                + (
                    "（范围不可判定：全局临时保护，须人工定位目标绑定）"
                    if unresolved else ""
                )
            ),
            alert_code="COMMIT_UNKNOWN",
            target_instance=binding["target_instance"],
            tenant=binding["tenant"],
            target_table=binding["target_table"],
            scope_unresolved=unresolved,
        )
    if state == BatchState.APPLIED:
        return RecoveryAction(
            batch_id, "RECONCILE_AND_REPORT", "batch", False,
            "受影响键核存在性与内容",
            alert_code="RECONCILE_DIFF",
        )
    if state == BatchState.RECONCILED:
        return RecoveryAction(
            batch_id, "SUBMIT_DELIVERY", "batch", False,
            "反馈链 NOT_SUBMITTED 时上报",
        )
    if state == BatchState.WAITING_VIEW_FIX:
        return RecoveryAction(
            batch_id, "WAIT_HUMAN_VIEW_FIX", "failed_window_or_route", False,
            "人工修视图；修好复核后按原窗重取；其他独立表继续",
            alert_code="VIEW_BLOCKED",
        )
    if state == BatchState.WAITING_SOURCE:
        return RecoveryAction(
            batch_id, "BACKOFF_AND_SINGLE_PROBE", "physical_source", False,
            "有界退避抖动；源级熔断半开单探针",
            alert_code="SOURCE_LATE",
        )
    if state == BatchState.QUARANTINED:
        return RecoveryAction(
            batch_id, "TICKET_AND_CONTINUE", "affected_record_group", False,
            "隔离组可重放；任务 PARTIAL，报送未闭合",
            alert_code="QUALITY_BLOCKED",
        )
    if state == BatchState.BLOCKED_DEPENDENCY:
        return RecoveryAction(
            batch_id, "WAIT_PARENT_GROUPS", "affected_child_groups", False,
            "父组成功后恢复对应子组",
        )
    if state == BatchState.WAITING_APPROVAL:
        return RecoveryAction(
            batch_id, "WAIT_APPROVAL", "batch", False,
            "具体对象/操作/额度批准",
        )
    if state == BatchState.WAITING_INPUT:
        return RecoveryAction(
            batch_id, "WAIT_INPUT", "task", False,
            "业务输入/口径确认",
        )
    if state == BatchState.RETRYABLE:
        return RecoveryAction(
            batch_id, "RETRY_SAME_IDEMPOTENT_KEY", "failed_window", False,
            "同一幂等操作恢复；有界次数",
        )
    if state == BatchState.DRIFT_DETECTED:
        return RecoveryAction(
            batch_id, "SCHEDULE_RESCAN", "drifted_business_months", False,
            "月度轮巡队列补偿；不借后续日成功销旧缺口",
            alert_code="RESCAN_OVERDUE",
        )
    if state == BatchState.CANCELLED:
        return RecoveryAction(
            batch_id, "NO_ACTION_TERMINAL", "batch", False, "终态",
        )
    raise ContractViolation(f"未覆盖的批次状态: {state}")


def blocked_scopes(actions: Sequence[RecoveryAction]) -> list[str]:
    """当前真正阻塞的范围（COMMIT_UNKNOWN 的同表写者等）。"""
    return [a.scope for a in actions if a.blocking]


class RecoveryExecutor:
    """恢复执行化（第一批批1-5）：把建议落成账面动作。

    - close_success：reconcile 全键一致后只关闭对应窗口的缺口，再按
      缺口门禁推进捕获水位与连续完成水位（历史空洞未闭合不推连续
      完成）；曾有 OPEN 事件的表补发 RECOVERED（入 outbox，不 HTTP）。
    - plan_retry_windows：失败窗口自动排队（OPEN 缺口 → 待重跑业务日
      清单，供 resume --execute / 日轮派发消费）。
    - record_rescan_coverage：回看/月度重扫的独立覆盖账（route=
      RESCAN，与 T+1 水位分离，不互相冒充）。

    水位推进被缺口门禁拒绝时不抛异常：如实记 blocked 原因——门禁
    本身是核心不变量，不能为了推进而绕开。
    """

    def __init__(self, repository) -> None:
        self.repository = repository

    # -- 成功闭合 -----------------------------------------------------------

    def close_success(
        self,
        *,
        batch_id: str,
        task_id: str,
        business_day: str,
        window_fingerprint: str,
        evidence: str,
    ) -> dict:

        result: dict = {
            "batch_id": batch_id,
            "closed_gaps": [],
            "watermarks": {},
            "recovered_incident": None,
            "blocked": [],
        }
        gaps = [
            gap for gap in self.repository.open_gaps(task_id)
            if gap.window.fingerprint() == window_fingerprint
        ]
        for gap in gaps:
            self.repository.close_gap(gap.gap_id, evidence=f"{batch_id}:{evidence}")
            result["closed_gaps"].append(gap.gap_id)
        if not gaps:
            # 无对应缺口：直接按窗口端点尝试推水位（首日无缺口属正常）
            pass
        window_end = self._window_end_from_day(business_day)
        if window_end is not None:
            for name, advance in (
                ("capture_h", self.repository.advance_capture_watermark),
                ("continuous_through", self.repository.advance_continuous_completion),
            ):
                try:
                    advance(task_id, window_end)
                    result["watermarks"][name] = window_end.isoformat()
                except Exception as exc:  # noqa: BLE001 - 门禁拒绝如实记录
                    result["blocked"].append(f"{name}: {type(exc).__name__}")
        result["recovered_incident"] = self._emit_recovered_if_open(
            task_id, business_day
        )
        result["still_open_gaps"] = len(self.repository.open_gaps(task_id))
        return result

    def _emit_recovered_if_open(self, task_id: str, business_day: str):
        """该业务日曾 OPEN 且缺口已全闭合 → 补发 RECOVERED（幂等）。"""
        incident_key = f"T1:{business_day}:{task_id}"
        finder = getattr(self.repository, "find_open_incident", None)
        incident = finder(incident_key) if callable(finder) else None
        if incident is None:
            return None
        source_event_id = f"r189t1.{incident.incident_id}.RECOVERED.1"
        if self.repository.get_outbox_event(source_event_id) is not None:
            return source_event_id
        from datetime import datetime, timezone

        from app.services.reporting_pipeline.alerts_client import build_event_body

        opened_event_id = f"r189t1.{incident.incident_id}.OPENED.1"
        title = f"T+1任务 {task_id} 业务日 {business_day} 已恢复"
        metadata = {
            "system": "T1_REPORTING",
            "canonical_table": task_id,
            "business_date": business_day,
            "recovered": True,
            "detail_ref": f"gap://{business_day}/{task_id}",
        }
        body = build_event_body(
            source_event_id=source_event_id,
            event_type="alert",
            category="EXTRACT_FAILED",
            severity="yellow",
            title=title,
            body=(
                f"业务日 {business_day} 的 {task_id} 缺口已闭合并回读一致"
                f"（关联事件 {opened_event_id}）。"
            ),
            occurred_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )
        event = self.repository.append_incident_event(
            incident,
            event_kind="RECOVERED",
            severity="yellow",
            title=title,
            body_bytes=body,
            metadata=metadata,
        )
        return event.source_event_id

    @staticmethod
    def _window_end_from_day(business_day: str):
        from datetime import date, datetime, time, timedelta, timezone

        try:
            day = date.fromisoformat(business_day)
        except ValueError:
            return None
        # 院区时区次日 00:00（左闭右开窗端点）
        return datetime.combine(day + timedelta(days=1), time(0), tzinfo=timezone(timedelta(hours=8)))

    # -- 失败窗口自动排队 ------------------------------------------------------

    def plan_retry_windows(self, task_id: str | None = None) -> list[dict]:
        [task_id] if task_id else sorted(
            {gap.task_id for batch in self.repository.list_batches()
             for gap in self.repository.open_gaps(batch.task_id)}
        )
        # 上面按批次反查表集合代价高；直接扫缺口更简单——仓储未提供全表
        # 缺口扫描，这里按批次清单聚合。
        plan: dict[tuple[str, str], dict] = {}
        for record in self.repository.list_batches():
            for gap in self.repository.open_gaps(record.task_id):
                day = gap.window.start.date().isoformat()
                key = (record.task_id, day)
                if key not in plan:
                    plan[key] = {
                        "task_id": record.task_id,
                        "business_day": day,
                        "reason": gap.reason,
                        "window": gap.window.fingerprint(),
                    }
        if task_id:
            return [item for (tid, _), item in sorted(plan.items()) if tid == task_id]
        return [item for _, item in sorted(plan.items())]

    # -- 回看/重扫覆盖账 --------------------------------------------------------

    def record_rescan_coverage(
        self,
        *,
        table: str,
        business_month: str,
        reconciled_at,
        cycle_days: int = 30,
        pending_slices: int = 0,
        failed_slices: int = 0,
    ) -> None:
        """月度重扫/回看的独立覆盖账（RESCAN 路由，与 T+1 水位分离）。"""
        from app.services.reporting_pipeline.planner import MonthCoverageRecord

        self.repository.upsert_month_coverage(
            MonthCoverageRecord(
                table=table,
                business_month=business_month,
                route_or_origin="RESCAN",
                last_reconciled_at=reconciled_at,
                cycle_days=cycle_days,
                pending_slices=pending_slices,
                failed_slices=failed_slices,
            )
        )

    def rescan_overdue(self, table: str) -> list:
        return self.repository.overdue_months(table)


# 故障隔离与继续执行规则.json 的 error → 本工程实现落点（矩阵测试对拍用）。
# 每个 error 必须能指到具体模块/测试，未映射即视为规则未实现。
FAULT_RULE_IMPLEMENTATION = {
    "ROW_OR_GROUP_QUALITY": {
        "scope": "affected_record_group",
        "state": "QUARANTINED",
        "implemented_in": "quality.py（组隔离+独立合法组继续）",
        "tested_by": "test_quality_staging.test_bad_group_isolated_independent_groups_continue",
    },
    "READ_SQL_OR_VIEW_ERROR": {
        "scope": "failed_window_or_route",
        "state": "WAITING_VIEW_FIX",
        "implemented_in": "python_reader（SourceError 分类）+ manual_tickets（工单）+ repositories（gap 账本）",
        "tested_by": "test_adapters 断连分类 + test_repositories 水位缺口门禁",
    },
    "TRANSIENT_READ_DISCONNECT": {
        "scope": "window_then_physical_source_if_repeated",
        "state": "RETRYABLE_OR_WAITING_SOURCE",
        "implemented_in": "python_reader.SourceCircuitBreaker（有界退避抖动+单探针半开）",
        "tested_by": "test_adapters.TestCircuitBreaker",
    },
    "ROW_OR_BYTE_CAP": {
        "scope": "incomplete_slice",
        "state": "SPLIT_PENDING",
        "implemented_in": "python_reader（递归二分+稳定keyset回退+PARKED）",
        "tested_by": "test_adapters.TestPythonReaderSplit",
    },
    "KNOWN_ROLLBACK": {
        "scope": "affected_apply_batch",
        "state": "RETRYABLE",
        "implemented_in": "contracts 状态机（APPLY_PENDING 恢复）+ apply_port（同幂等键）",
        "tested_by": "test_contracts.test_commit_unknown_flow",
    },
    "COMMIT_UNKNOWN": {
        "scope": "same_target_table_writer",
        "state": "COMMIT_UNKNOWN",
        "implemented_in": "contracts 状态机（仅对账后 APPLIED/APPLY_PENDING）+ apply_port 拒盲重放 + scheduler_bridge 冻结派发 + recovery 阻塞范围",
        "tested_by": "test_apply_reconcile.test_commit_unknown_refused_replay + test_alerts_flow.TestRecovery + TestSchedulerBridge",
    },
    "PARENT_PENDING": {
        "scope": "affected_child_keys_or_groups",
        "state": "BLOCKED_DEPENDENCY",
        "implemented_in": "quality.py（PENDING_PARENT 待父）+ planner.affected_child_groups",
        "tested_by": "test_quality_staging.test_missing_parent_pending_not_quarantined + test_planner.test_parent_failure_blocks_only_children",
    },
    "SOURCE_IDENTITY_MISMATCH": {
        "scope": "affected_physical_source_routes",
        "state": "BLOCKED_IDENTITY",
        "implemented_in": "python_reader.classify_source_error + contracts READ_READY 身份核验",
        "tested_by": "test_adapters.test_transient_disconnect_classification",
    },
    "ALERT_RELAY_FAILURE": {
        "scope": "notification_channel",
        "state": "ALERT_PENDING",
        "implemented_in": "alerts_outbox（持久重试/401暂停/轮询预算；不递归发坏relay）",
        "tested_by": "test_alerts_flow.TestOutboxSenderFlow",
    },
    "CONTROL_STORE_OR_GLOBAL_FENCE_FAILURE": {
        "scope": "actual_shared_unprovable_scope",
        "state": "SAFETY_HOLD",
        "implemented_in": "repositories（租约/围栏不可得即不派发）+ scheduler_bridge（租约失败跳过）",
        "tested_by": "test_alerts_flow.test_single_writer_lease",
    },
}
