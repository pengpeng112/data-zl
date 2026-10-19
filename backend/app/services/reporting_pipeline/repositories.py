"""控制状态仓储：接口协议 + 内存模拟实现（PG 实现按 E08 隔离验收落地）。

对应计划 §3.2/§5：
- 批次事务状态不能靠进程内变量保存——Repository 是唯一事实源（生产为
  asset schema PG；测试/模拟用 InMemoryControlRepository）。
- 幂等租约带单调 fencing token：旧 worker 租约过期不自动获得写权，写前
  必须校验围栏（无目标端栅栏时禁止自动多 writer 接管，见 E05）。
- 捕获水位/装载进度/反馈进度分离；捕获水位不得越过未闭合缺口。
- attempt 隔离：DataX 多次部分提交的 manifest 各自成账，只有完整版本才可
  被选中；重复 stage 不等于正式重复。
- 告警 incident/outbox：事件初次发送前冻结 UTF-8 字节与 payload_hash；
  同 source_event_id 重试必须字节不变；生命周期变化用新 revision。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping, Sequence

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    BatchState,
    BatchStateMachine,
    ContractViolation,
    FeedbackState,
    FeedbackStateMachine,
)
from app.services.reporting_pipeline.planner import (
    MonthCoverageRecord,
    TimeWindow,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Watermarks:
    task_id: str
    capture_h: datetime | None = None
    apply_cursor: datetime | None = None
    delivery_cursor: datetime | None = None


@dataclass
class GapRecord:
    gap_id: int
    task_id: str
    window: TimeWindow
    reason: str
    state: str = "OPEN"  # OPEN / CLOSED
    created_at: datetime = field(default_factory=_utcnow)
    closed_at: datetime | None = None
    close_evidence: str | None = None
    attempt: int = 0


@dataclass
class Lease:
    resource: str
    holder: str
    fencing_token: int
    expires_at: datetime


class LeaseDenied(ContractViolation):
    """租约被有效持有或围栏校验失败。"""


@dataclass
class OutboxEvent:
    """告警 outbox 事件：不可变请求字节 + 投递状态跟踪（E06 客户端使用）。"""

    source_event_id: str
    incident_id: str
    revision: int
    event_kind: str  # OPENED/ESCALATED/REMINDER/RECOVERED/...
    severity: str
    title: str
    immutable_body_bytes: bytes
    payload_sha256: str
    metadata: dict
    source_id: str | None = None
    secret_ref: str | None = None
    acceptance_state: str = "PENDING"  # PENDING/ACK_QUEUED/DUPLICATE/REJECTED_PERMANENT
    delivery_state: str = "NOT_SENT"  # NOT_SENT/DELIVERED/ROUTE_UNRESOLVED/NEEDS_ATTENTION/PAUSED_AUTH
    relay_event_id: str | None = None
    target_status_summary: dict = field(default_factory=dict)
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_error_class: str | None = None
    last_http_code: int | None = None
    retry_after_seconds: int | None = None
    poll_count: int = 0
    needs_attention_reason: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class AlertIncident:
    incident_id: str
    incident_key: str  # 环境/任务/表/错误类别/受影响窗口摘要（不含患者/SQL）
    category: str
    state: str = "OPEN"  # OPEN/ESCALATED/RECOVERED
    revision: int = 0
    affected_tables: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    last_event_source_id: str | None = None


@dataclass
class BatchRecord:
    batch_id: str
    task_id: str
    business_day: str
    state: BatchState
    feedback_state: FeedbackState = FeedbackState.NOT_SUBMITTED
    manifest: BatchManifest | None = None
    attempts: dict[str, BatchManifest] = field(default_factory=dict)
    machine: BatchStateMachine = field(default_factory=BatchStateMachine)
    feedback_machine: FeedbackStateMachine = field(default_factory=FeedbackStateMachine)
    created_at: datetime = field(default_factory=_utcnow)


class InMemoryControlRepository:
    """模拟控制存储：单进程确定性实现，时钟可注入；不含任何凭据/患者数据。"""

    def __init__(self, now_fn: Callable[[], datetime] = _utcnow) -> None:
        self._now = now_fn
        self._tasks: dict[str, dict] = {}
        self._batches: dict[str, BatchRecord] = {}
        self._watermarks: dict[str, Watermarks] = {}
        self._gaps: list[GapRecord] = []
        self._gap_seq = 0
        self._month_coverage: dict[tuple[str, str, str], MonthCoverageRecord] = {}
        self._leases: dict[str, Lease] = {}
        self._fencing_seq: dict[str, int] = {}
        self._incidents: dict[str, AlertIncident] = {}
        self._outbox: dict[str, OutboxEvent] = {}

    # -- 任务配置 -------------------------------------------------------

    def save_task(self, task_id: str, spec_dict: dict) -> None:
        self._tasks[task_id] = dict(spec_dict)

    def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    # -- 批次与 manifest（attempt 隔离） --------------------------------

    def create_batch(self, batch_id: str, task_id: str, business_day: str) -> BatchRecord:
        if batch_id in self._batches:
            raise ContractViolation(f"batch_id 已存在: {batch_id}")
        record = BatchRecord(
            batch_id=batch_id,
            task_id=task_id,
            business_day=business_day,
            state=BatchState.PLANNED,
        )
        self._batches[batch_id] = record
        return record

    def attach_attempt_manifest(self, batch_id: str, manifest: BatchManifest) -> None:
        """按 attempt 归档 manifest；不覆盖其他 attempt 的部分结果。"""
        record = self._require_batch(batch_id)
        record.attempts[manifest.attempt_id] = manifest

    def select_manifest(self, batch_id: str) -> BatchManifest:
        """只选完整 attempt 的最新 manifest；无完整版本时报未完整而非返回部分。"""
        record = self._require_batch(batch_id)
        complete = [
            m for m in record.attempts.values() if m.pagination_complete
        ]
        if not complete:
            raise ContractViolation(
                f"[{batch_id}] 无完整 attempt manifest（部分 stage 不能当完整批次）"
            )
        chosen = max(complete, key=lambda m: m.attempt_id)
        record.manifest = chosen
        return chosen

    def transition_batch(
        self,
        batch_id: str,
        target: BatchState,
        *,
        reason: str,
        evidence: str | None = None,
    ) -> BatchState:
        record = self._require_batch(batch_id)
        record.machine.transition(
            target, reason=reason, evidence=evidence, manifest=record.manifest
        )
        record.state = record.machine.state
        return record.state

    def transition_feedback(
        self, batch_id: str, target: FeedbackState, *, reason: str, evidence: str | None = None
    ) -> FeedbackState:
        record = self._require_batch(batch_id)
        record.feedback_machine.transition(target, reason=reason, evidence=evidence)
        record.feedback_state = record.feedback_machine.state
        return record.feedback_state

    def _require_batch(self, batch_id: str) -> BatchRecord:
        record = self._batches.get(batch_id)
        if record is None:
            raise ContractViolation(f"批次不存在: {batch_id}")
        return record

    def list_batches(self) -> list[BatchRecord]:
        return [self._batches[bid] for bid in sorted(self._batches)]

    # -- 水位（分离 + 缺口门禁） ----------------------------------------

    def get_watermarks(self, task_id: str) -> Watermarks:
        return self._watermarks.setdefault(task_id, Watermarks(task_id=task_id))

    def advance_capture_watermark(self, task_id: str, new_h: datetime) -> Watermarks:
        """连续捕获水位不得越过未闭合缺片（失败后继续策略的核心不变量）。"""
        wm = self.get_watermarks(task_id)
        if wm.capture_h is not None and new_h <= wm.capture_h:
            raise ContractViolation("捕获水位只能前进")
        for gap in self.open_gaps(task_id):
            if gap.window.end_exclusive > (wm.capture_h or gap.window.start):
                raise ContractViolation(
                    f"存在未闭合缺口 {gap.window.fingerprint()}，禁止把捕获水位推到 {new_h}"
                )
        wm.capture_h = new_h
        return wm

    def advance_apply_cursor(self, task_id: str, new_cursor: datetime) -> Watermarks:
        wm = self.get_watermarks(task_id)
        if wm.apply_cursor is not None and new_cursor < wm.apply_cursor:
            raise ContractViolation("装载游标不能后退")
        wm.apply_cursor = new_cursor
        return wm

    def advance_delivery_cursor(self, task_id: str, new_cursor: datetime) -> Watermarks:
        wm = self.get_watermarks(task_id)
        if wm.delivery_cursor is not None and new_cursor < wm.delivery_cursor:
            raise ContractViolation("反馈游标不能后退")
        wm.delivery_cursor = new_cursor
        return wm

    # -- 缺口账本 ---------------------------------------------------------

    def record_gap(self, task_id: str, window: TimeWindow, reason: str) -> GapRecord:
        self._gap_seq += 1
        gap = GapRecord(
            gap_id=self._gap_seq, task_id=task_id, window=window, reason=reason
        )
        self._gaps.append(gap)
        return gap

    def open_gaps(self, task_id: str) -> list[GapRecord]:
        return [g for g in self._gaps if g.task_id == task_id and g.state == "OPEN"]

    def close_gap(self, gap_id: int, evidence: str) -> GapRecord:
        for gap in self._gaps:
            if gap.gap_id == gap_id:
                if gap.state == "CLOSED":
                    raise ContractViolation(f"缺口 {gap_id} 已闭合")
                gap.state = "CLOSED"
                gap.closed_at = self._now()
                gap.close_evidence = evidence
                return gap
        raise ContractViolation(f"缺口不存在: {gap_id}")

    # -- 历史月覆盖账 ------------------------------------------------------

    def upsert_month_coverage(self, record: MonthCoverageRecord) -> MonthCoverageRecord:
        key = (record.table, record.business_month, record.route_or_origin)
        self._month_coverage[key] = record
        return record

    def month_coverage(self, table: str) -> list[MonthCoverageRecord]:
        return [r for (t, _, _), r in self._month_coverage.items() if t == table]

    def overdue_months(self, table: str) -> list[MonthCoverageRecord]:
        now = self._now()
        return [r for r in self.month_coverage(table) if r.is_overdue(now)]

    # -- 幂等租约 + fencing token -----------------------------------------

    def acquire_lease(self, resource: str, holder: str, ttl_seconds: int) -> Lease:
        now = self._now()
        existing = self._leases.get(resource)
        if existing and existing.expires_at > now and existing.holder != holder:
            raise LeaseDenied(
                f"资源 {resource} 被 {existing.holder} 持有至 {existing.expires_at}"
            )
        token = self._fencing_seq.get(resource, 0) + 1
        self._fencing_seq[resource] = token
        lease = Lease(
            resource=resource,
            holder=holder,
            fencing_token=token,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._leases[resource] = lease
        return lease

    def renew_lease(self, resource: str, holder: str, fencing_token: int) -> Lease:
        lease = self._leases.get(resource)
        if lease is None or lease.holder != holder:
            raise LeaseDenied(f"租约不存在或持有者不符: {resource}")
        if lease.fencing_token != fencing_token:
            raise LeaseDenied(
                f"围栏不匹配: 持有 {fencing_token} < 当前 {lease.fencing_token}（旧 worker 不得续期）"
            )
        if lease.expires_at <= self._now():
            raise LeaseDenied(f"租约已过期，不能续期: {resource}")
        lease.expires_at = self._now() + timedelta(seconds=3600)
        return lease

    def validate_fencing(self, resource: str, fencing_token: int) -> None:
        lease = self._leases.get(resource)
        if lease is None or lease.fencing_token != fencing_token:
            raise LeaseDenied(
                f"围栏校验失败: {resource} 期望 token={lease.fencing_token if lease else None}"
            )

    def release_lease(self, resource: str, holder: str) -> None:
        lease = self._leases.get(resource)
        if lease and lease.holder == holder:
            del self._leases[resource]

    # -- 告警 incident / outbox（不可变事件） ------------------------------

    def create_incident(
        self,
        incident_key: str,
        category: str,
        affected_tables: Sequence[str] | None = None,
    ) -> AlertIncident:
        for inc in self._incidents.values():
            if inc.incident_key == incident_key and inc.state != "RECOVERED":
                return inc  # 聚合：同 key 未恢复的 incident 复用
        incident_id = f"INC-{len(self._incidents) + 1:06d}"
        incident = AlertIncident(
            incident_id=incident_id,
            incident_key=incident_key,
            category=category,
            affected_tables=list(affected_tables or []),
        )
        self._incidents[incident_id] = incident
        return incident

    def append_incident_event(
        self,
        incident: AlertIncident,
        *,
        event_kind: str,
        severity: str,
        title: str,
        body_bytes: bytes,
        metadata: Mapping[str, object] | None = None,
        source_id: str | None = None,
        secret_ref: str | None = None,
    ) -> OutboxEvent:
        """生命周期事件用新 revision；同 revision 幂等重放要求字节一致。"""
        if not body_bytes:
            raise ContractViolation("事件 body 不能为空")
        candidate_id = (
            f"r189t1.{incident.incident_id}.{event_kind}.{incident.revision}"
            if incident.revision > 0 else None
        )
        if candidate_id:
            existing = self._outbox.get(candidate_id)
            if existing is not None:
                if existing.immutable_body_bytes != body_bytes:
                    raise ContractViolation(
                        f"同 source_event_id 事件字节冲突: {candidate_id}"
                        "（需新 revision，不得改内容）"
                    )
                return existing  # 同 revision 同字节：幂等重放，不加版本
        incident.revision += 1
        source_event_id = (
            f"r189t1.{incident.incident_id}.{event_kind}.{incident.revision}"
        )
        if len(source_event_id) > 200:
            raise ContractViolation("source_event_id 超 200 字符")
        payload_sha256 = hashlib.sha256(body_bytes).hexdigest()
        existing = self._outbox.get(source_event_id)
        if existing is not None:
            if existing.immutable_body_bytes != body_bytes:
                raise ContractViolation(
                    f"同 source_event_id 事件字节冲突: {source_event_id}（需新 revision，不得改内容）"
                )
            return existing
        event = OutboxEvent(
            source_event_id=source_event_id,
            incident_id=incident.incident_id,
            revision=incident.revision,
            event_kind=event_kind,
            severity=severity,
            title=title,
            immutable_body_bytes=body_bytes,
            payload_sha256=payload_sha256,
            metadata=dict(metadata or {}),
            source_id=source_id,
            secret_ref=secret_ref,
        )
        self._outbox[source_event_id] = event
        incident.last_event_source_id = source_event_id
        if event_kind == "RECOVERED":
            incident.state = "RECOVERED"
        elif severity in ("red",) and event_kind == "ESCALATED":
            incident.state = "ESCALATED"
        return event

    def get_outbox_event(self, source_event_id: str) -> OutboxEvent | None:
        return self._outbox.get(source_event_id)

    def queued_outbox(self) -> list[OutboxEvent]:
        """已入队（202/duplicate）且未 DELIVERED 的事件：轮询候选。"""
        return [
            e for e in self._outbox.values()
            if e.acceptance_state in ("ACK_QUEUED", "DUPLICATE")
            and e.delivery_state != "DELIVERED"
        ]

    def pending_outbox(self) -> list[OutboxEvent]:
        """待 POST 派发的事件：排除已送达、已入队（转轮询）、401 暂停、
        待人工、永久拒绝。"""
        now = self._now()
        return [
            e for e in self._outbox.values()
            if e.delivery_state not in ("DELIVERED", "PAUSED_AUTH", "NEEDS_ATTENTION")
            and e.acceptance_state not in ("REJECTED_PERMANENT", "ACK_QUEUED", "DUPLICATE")
            and (e.next_attempt_at is None or e.next_attempt_at <= now)
        ]

    def update_outbox_delivery(
        self,
        source_event_id: str,
        *,
        acceptance_state: str | None = None,
        delivery_state: str | None = None,
        relay_event_id: str | None = None,
        target_status_summary: dict | None = None,
        attempts_increment: int = 0,
        next_attempt_at: datetime | None = None,
        last_error_class: str | None = None,
        last_http_code: int | None = None,
        retry_after_seconds: int | None = None,
        poll_increment: int = 0,
        needs_attention_reason: str | None = None,
    ) -> OutboxEvent:
        event = self._outbox.get(source_event_id)
        if event is None:
            raise ContractViolation(f"outbox 事件不存在: {source_event_id}")
        if acceptance_state is not None:
            event.acceptance_state = acceptance_state
        if delivery_state is not None:
            event.delivery_state = delivery_state
        if relay_event_id is not None:
            event.relay_event_id = relay_event_id
        if target_status_summary is not None:
            event.target_status_summary = target_status_summary
        event.attempts += attempts_increment
        if next_attempt_at is not None:
            event.next_attempt_at = next_attempt_at
        if last_error_class is not None:
            event.last_error_class = last_error_class
        if last_http_code is not None:
            event.last_http_code = last_http_code
        if retry_after_seconds is not None:
            event.retry_after_seconds = retry_after_seconds
        event.poll_count += poll_increment
        if needs_attention_reason is not None:
            event.needs_attention_reason = needs_attention_reason
        event.updated_at = self._now()
        return event

    # -- 导出（报表/测试断言用） -------------------------------------------

    def snapshot(self) -> dict:
        return {
            "batches": {
                bid: {
                    "task": r.task_id,
                    "state": r.state.value,
                    "feedback": r.feedback_state.value,
                    "attempts": sorted(r.attempts),
                    "selected_attempt": r.manifest.attempt_id if r.manifest else None,
                }
                for bid, r in self._batches.items()
            },
            "watermarks": {
                t: {
                    "capture_h": w.capture_h.isoformat() if w.capture_h else None,
                    "apply_cursor": w.apply_cursor.isoformat() if w.apply_cursor else None,
                    "delivery_cursor": w.delivery_cursor.isoformat() if w.delivery_cursor else None,
                }
                for t, w in self._watermarks.items()
            },
            "open_gaps": [
                {
                    "gap_id": g.gap_id,
                    "task": g.task_id,
                    "window": g.window.fingerprint(),
                    "reason": g.reason,
                }
                for g in self._gaps if g.state == "OPEN"
            ],
            "month_coverage": [
                {
                    "table": r.table,
                    "month": r.business_month,
                    "origin": r.route_or_origin,
                    "reconciled": r.last_reconciled_at.isoformat()
                    if r.last_reconciled_at else None,
                    "pending": r.pending_slices,
                    "failed": r.failed_slices,
                }
                for r in self._month_coverage.values()
            ],
            "incidents": [
                {
                    "id": i.incident_id,
                    "key": i.incident_key,
                    "state": i.state,
                    "revision": i.revision,
                }
                for i in self._incidents.values()
            ],
            "outbox": [
                {
                    "source_event_id": e.source_event_id,
                    "acceptance": e.acceptance_state,
                    "delivery": e.delivery_state,
                    "attempts": e.attempts,
                }
                for e in self._outbox.values()
            ],
        }
