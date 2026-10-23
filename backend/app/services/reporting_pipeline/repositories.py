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
from typing import Callable, Mapping, Protocol, Sequence

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
    # 最后连续完成日（R05/RT1-025）：与捕获水位分开——中间有缺口时，
    # 后续成功窗可先落地（capture_h 前进），但连续完成游标不越过缺口。
    continuous_through: datetime | None = None


class ControlRepository(Protocol):
    """控制状态仓储协议（R02）：生产 PG 实现与内存模拟共用同一契约。

    语义要点（实现必须遵守，测试按此验收）：
    - 批次/attempt/水位/缺口/月覆盖/租约/incident/outbox 全部持久化，
      进程重启后可恢复；内存实现仅供单进程模拟。
    - acquire_lease 跨进程原子（两工作者同时领取只有一个成功）；
      fencing_token 单调，旧 token 续期/提交被拒。
    - advance_capture_watermark 不得越过 OPEN 缺口；
      advance_continuous_completion 同样受缺口门禁。
    - append_incident_event 同 source_event_id 重试要求字节不变。
    """

    def save_task(self, task_id: str, spec_dict: dict) -> None: ...
    def get_task(self, task_id: str) -> dict | None: ...
    def create_batch(
        self,
        batch_id: str,
        task_id: str,
        business_day: str,
        *,
        target_instance: str | None = None,
        tenant: str | None = None,
        target_table: str | None = None,
    ) -> BatchRecord: ...
    def get_batch(self, batch_id: str) -> BatchRecord: ...
    def attach_attempt_manifest(self, batch_id: str, manifest: BatchManifest) -> None: ...
    def select_manifest(self, batch_id: str) -> BatchManifest: ...
    def transition_batch(
        self, batch_id: str, target: BatchState, *, reason: str, evidence: str | None = None
    ) -> BatchState: ...
    def transition_feedback(
        self, batch_id: str, target: FeedbackState, *, reason: str, evidence: str | None = None
    ) -> FeedbackState: ...
    def list_batches(self) -> list[BatchRecord]: ...
    def get_watermarks(self, task_id: str) -> Watermarks: ...
    def advance_capture_watermark(self, task_id: str, new_h: datetime) -> Watermarks: ...
    def advance_apply_cursor(self, task_id: str, new_cursor: datetime) -> Watermarks: ...
    def advance_delivery_cursor(self, task_id: str, new_cursor: datetime) -> Watermarks: ...
    def advance_continuous_completion(self, task_id: str, through: datetime) -> Watermarks: ...
    def record_gap(self, task_id: str, window: TimeWindow, reason: str) -> GapRecord: ...
    def open_gaps(self, task_id: str) -> list[GapRecord]: ...
    def close_gap(self, gap_id: int, evidence: str) -> GapRecord: ...
    def upsert_month_coverage(self, record: MonthCoverageRecord) -> MonthCoverageRecord: ...
    def month_coverage(self, table: str) -> list[MonthCoverageRecord]: ...
    def overdue_months(self, table: str) -> list[MonthCoverageRecord]: ...
    def acquire_lease(self, resource: str, holder: str, ttl_seconds: int) -> Lease: ...
    def renew_lease(
        self,
        resource: str,
        holder: str,
        fencing_token: int,
        *,
        ttl_seconds: int = 3600,
    ) -> Lease: ...
    def validate_fencing(
        self, resource: str, fencing_token: int, *, holder: str | None = None
    ) -> None: ...
    def release_lease(
        self, resource: str, holder: str, *, fencing_token: int | None = None
    ) -> None: ...
    def create_incident(
        self, incident_key: str, category: str, affected_tables: Sequence[str] | None = None
    ) -> AlertIncident: ...
    def find_open_incident(self, incident_key: str) -> AlertIncident | None: ...
    def append_incident_event(
        self, incident: AlertIncident, *, event_kind: str, severity: str,
        title: str, body_bytes: bytes, metadata: Mapping[str, object] | None = None,
        source_id: str | None = None, secret_ref: str | None = None,
    ) -> OutboxEvent: ...
    def get_outbox_event(self, source_event_id: str) -> OutboxEvent | None: ...
    def queued_outbox(self) -> list[OutboxEvent]: ...
    def pending_outbox(self) -> list[OutboxEvent]: ...
    def update_outbox_delivery(self, source_event_id: str, **kwargs) -> OutboxEvent: ...
    def record_quarantine_group(
        self,
        *,
        batch_id: str,
        canonical_table: str,
        group_key: str,
        reason: str,
        error_code: str | None = None,
        rows_quarantined: int = 0,
        detail_ref: str | None = None,
    ) -> None: ...
    def resolve_quarantine_group(
        self, batch_id: str, group_key: str, *, evidence: str
    ) -> None: ...
    def open_quarantine_groups(self, batch_id: str) -> list[dict]: ...
    def outbox_overview(self, *, limit: int = 20) -> dict: ...
    def snapshot(self) -> dict: ...


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
    # K02：批次的目标绑定（实例/机构/表）。COMMIT_UNKNOWN 的冻结范围按此
    # 结构化判定；未绑定的批次只能全局保护并产生需人工定位的告警。
    target_instance: str | None = None
    tenant: str | None = None
    target_table: str | None = None

    def target_scope_fingerprint(self) -> str | None:
        """结构化冻结范围键；任一成分缺失返回 None（范围不可判定）。"""
        if not (self.target_instance and self.tenant and self.target_table):
            return None
        return f"{self.target_instance}|{self.tenant}|{self.target_table}"


class InMemoryControlRepository:
    """模拟控制存储：单进程确定性实现，时钟可注入；不含任何凭据/患者数据。

    K03 语义（与 PG 实现一致，测试按此验收）：
    - fencing token 序列（_fencing_seq）独立于租约行持久：释放后重获
      token 严格递增，历史 token 永不重用；
    - validate_fencing 校验 token + 有效期（+可选 holder）；
    - release_lease 可绑定 token，旧进程晚到释放不得撤销新租约。
    """

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
        self._quarantine_groups: dict[tuple[str, str], dict] = {}

    # -- 任务配置 -------------------------------------------------------

    def save_task(self, task_id: str, spec_dict: dict) -> None:
        self._tasks[task_id] = dict(spec_dict)

    def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    # -- 批次与 manifest（attempt 隔离） --------------------------------

    def create_batch(
        self,
        batch_id: str,
        task_id: str,
        business_day: str,
        *,
        target_instance: str | None = None,
        tenant: str | None = None,
        target_table: str | None = None,
    ) -> BatchRecord:
        if batch_id in self._batches:
            raise ContractViolation(f"batch_id 已存在: {batch_id}")
        record = BatchRecord(
            batch_id=batch_id,
            task_id=task_id,
            business_day=business_day,
            state=BatchState.PLANNED,
            target_instance=target_instance,
            tenant=tenant,
            target_table=target_table,
        )
        self._batches[batch_id] = record
        return record

    def get_batch(self, batch_id: str) -> BatchRecord:
        """公共批次读取（K04）：恢复层不得依赖仓储私有方法。"""
        return self._require_batch(batch_id)

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

    def advance_continuous_completion(
        self, task_id: str, through: datetime
    ) -> Watermarks:
        """推进最后连续完成日：不越过 OPEN 缺口（RT1-025）。

        与捕获水位分离：H0 之后的日常捕获可以先落地（capture_h 前进），
        但 2026 基线到 H0 之间的历史缺口未补齐前，连续完成游标停在缺口
        之前——日报不得用捕获水位冒充连续完成。
        """
        wm = self.get_watermarks(task_id)
        if wm.continuous_through is not None and through < wm.continuous_through:
            raise ContractViolation("连续完成游标不能后退")
        for gap in self.open_gaps(task_id):
            if gap.window.start < through:
                raise ContractViolation(
                    f"存在未闭合缺口 {gap.window.fingerprint()}（起点 "
                    f"{gap.window.start.isoformat()}），连续完成游标不得推进到 "
                    f"{through.isoformat()}"
                )
        wm.continuous_through = through
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

    def renew_lease(
        self,
        resource: str,
        holder: str,
        fencing_token: int,
        *,
        ttl_seconds: int = 3600,
    ) -> Lease:
        lease = self._leases.get(resource)
        if lease is None or lease.holder != holder:
            raise LeaseDenied(f"租约不存在或持有者不符: {resource}")
        if lease.fencing_token != fencing_token:
            raise LeaseDenied(
                f"围栏不匹配: 持有 {fencing_token} < 当前 {lease.fencing_token}（旧 worker 不得续期）"
            )
        if lease.expires_at <= self._now():
            raise LeaseDenied(f"租约已过期，不能续期: {resource}")
        lease.expires_at = self._now() + timedelta(seconds=ttl_seconds)
        return lease

    def validate_fencing(
        self, resource: str, fencing_token: int, *, holder: str | None = None
    ) -> None:
        """K03：围栏校验含有效期；过期租约的 token 不得再通过提交门。"""
        lease = self._leases.get(resource)
        if lease is None or lease.fencing_token != fencing_token:
            raise LeaseDenied(
                f"围栏校验失败: {resource} 期望 token={lease.fencing_token if lease else None}"
            )
        if lease.expires_at <= self._now():
            raise LeaseDenied(f"租约已过期，token 不再有效: {resource}")
        if holder is not None and lease.holder != holder:
            raise LeaseDenied(f"围栏持有者不符: {resource} {lease.holder} != {holder}")

    def release_lease(
        self, resource: str, holder: str, *, fencing_token: int | None = None
    ) -> None:
        """K03：释放绑定 token——旧进程晚到释放不得撤销新租约。

        token 省略时按持有者释放（兼容旧调用方）；给了 token 则必须与当前
        租约一致才生效（持有者已换也拒绝，防同名旧进程误撤新租约）。token
        序列独立持久（_fencing_seq），释放后重获 token 严格递增。
        """
        lease = self._leases.get(resource)
        if lease is None:
            return
        if fencing_token is not None and lease.fencing_token != fencing_token:
            raise LeaseDenied(
                f"释放被拒（token 不属于当前租约）: {resource} "
                f"释放 token={fencing_token} 当前={lease.fencing_token}"
            )
        if lease.holder != holder:
            return  # 持有者已被顶替：晚到的同名/旧进程释放不生效
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

    def find_open_incident(self, incident_key: str) -> AlertIncident | None:
        for inc in self._incidents.values():
            if inc.incident_key == incident_key and inc.state != "RECOVERED":
                return inc
        return None

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

    # -- 隔离组账（批1-4：坏组/缺父留痕，独立合法组继续） --------------------

    def record_quarantine_group(
        self,
        *,
        batch_id: str,
        canonical_table: str,
        group_key: str,
        reason: str,
        error_code: str | None = None,
        rows_quarantined: int = 0,
        detail_ref: str | None = None,
    ) -> None:
        key = (batch_id, group_key)
        if key in self._quarantine_groups:
            raise ContractViolation(f"隔离组已登记: {batch_id}/{group_key}")
        self._quarantine_groups[key] = {
            "batch_id": batch_id,
            "canonical_table": canonical_table,
            "group_key": group_key,
            "reason": reason,
            "error_code": error_code,
            "rows_quarantined": rows_quarantined,
            "detail_ref": detail_ref,
            "state": "OPEN",
            "created_at": self._now(),
            "resolved_at": None,
            "resolution_evidence": None,
        }

    def resolve_quarantine_group(
        self, batch_id: str, group_key: str, *, evidence: str
    ) -> None:
        record = self._quarantine_groups.get((batch_id, group_key))
        if record is None:
            raise ContractViolation(f"隔离组不存在: {batch_id}/{group_key}")
        record["state"] = "RESOLVED"
        record["resolved_at"] = self._now()
        record["resolution_evidence"] = evidence

    def open_quarantine_groups(self, batch_id: str) -> list[dict]:
        return [
            dict(record)
            for (bid, _), record in sorted(self._quarantine_groups.items())
            if bid == batch_id and record["state"] == "OPEN"
        ]

    def outbox_overview(self, *, limit: int = 20) -> dict:
        """全量投递状态分组统计 + 近期事件（巡检用，含暂停/待人工/退避中）。"""
        events = sorted(
            self._outbox.values(), key=lambda e: (e.updated_at, e.source_event_id)
        )
        groups: dict[str, list] = {}
        for event in events:
            state = event.delivery_state
            if state == "NOT_SENT" and event.acceptance_state in ("ACK_QUEUED", "DUPLICATE"):
                state = "ACK_QUEUED"
            elif state == "NOT_SENT" and event.next_attempt_at is not None:
                state = "BACKOFF_RETRYING"
            groups.setdefault(state, []).append(event)
        def view(e: OutboxEvent) -> dict:
            return {
                "source_event_id": e.source_event_id,
                "event_kind": e.event_kind,
                "delivery_state": e.delivery_state,
                "acceptance_state": e.acceptance_state,
                "attempts": e.attempts,
                "next_attempt_at": (
                    e.next_attempt_at.isoformat() if e.next_attempt_at else None
                ),
                "needs_attention_reason": e.needs_attention_reason,
            }
        return {
            "counts": {state: len(items) for state, items in sorted(groups.items())},
            "recent": [view(e) for e in events[-limit:]],
        }

    # -- 导出（报表/测试断言用） -------------------------------------------

    def snapshot(self) -> dict:
        per_table: dict[str, dict] = {}
        for bid, r in sorted(self._batches.items()):
            row = per_table.setdefault(
                r.task_id,
                {
                    "task": r.task_id,
                    "batches": 0,
                    "by_state": {},
                    "quarantined": 0,
                    "pending_parent": 0,
                    "applied": 0,
                    "commit_unknown": 0,
                    "earliest_open_gap": None,
                },
            )
            row["batches"] += 1
            row["by_state"][r.state.value] = row["by_state"].get(r.state.value, 0) + 1
            if r.state == BatchState.QUARANTINED:
                row["quarantined"] += 1
            elif r.state == BatchState.BLOCKED_DEPENDENCY:
                row["pending_parent"] += 1
            elif r.state == BatchState.APPLIED:
                row["applied"] += 1
            elif r.state == BatchState.COMMIT_UNKNOWN:
                row["commit_unknown"] += 1
        open_by_task: dict[str, list[GapRecord]] = {}
        for g in self._gaps:
            if g.state == "OPEN":
                open_by_task.setdefault(g.task_id, []).append(g)
        for task, gaps in open_by_task.items():
            row = per_table.setdefault(
                task,
                {
                    "task": task, "batches": 0, "by_state": {}, "quarantined": 0,
                    "pending_parent": 0, "applied": 0, "commit_unknown": 0,
                    "earliest_open_gap": None,
                },
            )
            earliest = min(gaps, key=lambda g: g.window.start)
            row["earliest_open_gap"] = {
                "gap_id": earliest.gap_id,
                "window": earliest.window.fingerprint(),
                "reason": earliest.reason,
                "open_gap_count": len(gaps),
            }
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
            "per_table": per_table,
            "watermarks": {
                t: {
                    "capture_h": w.capture_h.isoformat() if w.capture_h else None,
                    "apply_cursor": w.apply_cursor.isoformat() if w.apply_cursor else None,
                    "delivery_cursor": w.delivery_cursor.isoformat() if w.delivery_cursor else None,
                    "continuous_through": (
                        w.continuous_through.isoformat() if w.continuous_through else None
                    ),
                }
                for t, w in self._watermarks.items()
            },
            "open_gaps": [
                {
                    "gap_id": g.gap_id,
                    "task": g.task_id,
                    "window": g.window.fingerprint(),
                    "reason": g.reason,
                    "created_at": g.created_at.isoformat(),
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
                    "created_at": e.created_at.isoformat(),
                    "next_attempt_at": (
                        e.next_attempt_at.isoformat()
                        if e.next_attempt_at else None
                    ),
                    "needs_attention": e.needs_attention_reason,
                }
                for e in self._outbox.values()
            ],
        }
