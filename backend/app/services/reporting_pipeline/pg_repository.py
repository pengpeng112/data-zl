"""PG 耐久控制仓储（R02）：SqlAlchemyControlRepository。

对应整改计划 §R02 与 ControlRepository 协议：
- 批次/attempt/水位/缺口/月覆盖/租约/incident/outbox/版本证据/隔离组
  全部落 asset schema 既有9表 + R02 增量2表；进程重启后状态可恢复。
- acquire_lease / outbox 领取在事务内 SELECT ... FOR UPDATE，跨进程原子：
  两个工作者同时领取同一资源只有一个成功；fencing_token 单调递增，
  旧 token 续期被拒。
- InMemoryControlRepository 仅供单进程模拟；本实现是生产装配的仓储。
- 本模块不含任何业务源库连接；控制面 PG 连接由调用方以 session 工厂
  注入（与业务源库身份分离）。
- 隔离库验收（RT1-003/004/005）依赖 APP_TEST_DB_URL 指向已核实可清理
  隔离库；未配置时本实现只做导入/编译级验证，不连接任何数据库。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset_reporting import (
    AssetReportingAlertIncident,
    AssetReportingAlertOutbox,
    AssetReportingBatch,
    AssetReportingBatchAttempt,
    AssetReportingGapLedger,
    AssetReportingLease,
    AssetReportingMonthCoverage,
    AssetReportingQuarantineGroup,
    AssetReportingTaskConfig,
    AssetReportingVersionEvidence,
    AssetReportingWatermark,
)
from app.services.reporting_pipeline.apply_port import (
    VersionScope,
)
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    BatchState,
    BatchStateMachine,
    ContractViolation,
    EndReason,
    FeedbackState,
    FeedbackStateMachine,
    RowClassification,
)
from app.services.reporting_pipeline.planner import (
    MonthCoverageRecord,
    TimeWindow,
)
from app.services.reporting_pipeline.repositories import (
    AlertIncident,
    BatchRecord,
    GapRecord,
    Lease,
    LeaseDenied,
    OutboxEvent,
    Watermarks,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# BatchManifest 序列化（JSONB 存档）
# ---------------------------------------------------------------------------


def manifest_to_dict(manifest: BatchManifest) -> dict:
    return {
        "batch_id": manifest.batch_id,
        "attempt_id": manifest.attempt_id,
        "task_id": manifest.task_id,
        "config_version": manifest.config_version,
        "definition_fingerprint": manifest.definition_fingerprint,
        "source_identity": manifest.source_identity,
        "window_fingerprint": manifest.window_fingerprint,
        "source_visibility_cutoff": manifest.source_visibility_cutoff,
        "rows": {
            "source_read_rows": manifest.rows.source_read_rows,
            "valid": manifest.rows.valid,
            "duplicate_conflict": manifest.rows.duplicate_conflict,
            "quarantined": manifest.rows.quarantined,
            "pending_apply": manifest.rows.pending_apply,
            "unreadable_partial": manifest.rows.unreadable_partial,
        },
        "pagination_complete": manifest.pagination_complete,
        "end_reason": manifest.end_reason.value,
        "shard_count": manifest.shard_count,
        "file_count": manifest.file_count,
        "total_bytes": manifest.total_bytes,
        "schema_version": manifest.schema_version,
        "type_contract_version": manifest.type_contract_version,
        "payload_sha256": manifest.payload_sha256,
        "source_version_min": manifest.source_version_min,
        "source_version_max": manifest.source_version_max,
        "engine": manifest.engine.value if hasattr(manifest.engine, "value") else str(manifest.engine),
        "created_at": manifest.created_at,
    }


def manifest_from_dict(document: dict) -> BatchManifest:
    from app.services.reporting_pipeline.contracts import Engine

    rows = document["rows"]
    return BatchManifest(
        batch_id=document["batch_id"],
        attempt_id=document["attempt_id"],
        task_id=document["task_id"],
        config_version=document["config_version"],
        definition_fingerprint=document.get("definition_fingerprint"),
        source_identity=document["source_identity"],
        window_fingerprint=document["window_fingerprint"],
        source_visibility_cutoff=document["source_visibility_cutoff"],
        rows=RowClassification(
            source_read_rows=rows["source_read_rows"],
            valid=rows.get("valid", 0),
            duplicate_conflict=rows.get("duplicate_conflict", 0),
            quarantined=rows.get("quarantined", 0),
            pending_apply=rows.get("pending_apply", 0),
            unreadable_partial=rows.get("unreadable_partial", 0),
        ),
        pagination_complete=document["pagination_complete"],
        end_reason=EndReason(document["end_reason"]),
        shard_count=document["shard_count"],
        file_count=document["file_count"],
        total_bytes=document["total_bytes"],
        schema_version=document["schema_version"],
        type_contract_version=document["type_contract_version"],
        payload_sha256=document["payload_sha256"],
        source_version_min=document.get("source_version_min"),
        source_version_max=document.get("source_version_max"),
        engine=Engine(document.get("engine", "UNDECIDED")),
        created_at=document.get("created_at"),
    )


class PgVersionRegistry:
    """耐久版本账（VersionRegistry 的 PG 实现）。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def current_version(self, scope: VersionScope, stable_key: tuple) -> str | None:
        key = json.dumps(list(stable_key), ensure_ascii=False, default=str)
        with self._session_factory() as session:
            row = session.execute(
                select(AssetReportingVersionEvidence).where(
                    AssetReportingVersionEvidence.target_instance == scope.target_instance,
                    AssetReportingVersionEvidence.tenant == scope.tenant,
                    AssetReportingVersionEvidence.canonical_table == scope.table,
                    AssetReportingVersionEvidence.stable_key == key,
                )
            ).scalar_one_or_none()
            return row.version_value if row else None

    def register_version(
        self,
        scope: VersionScope,
        stable_key: tuple,
        version: str,
        *,
        operation_id: str,
    ) -> None:
        key = json.dumps(list(stable_key), ensure_ascii=False, default=str)
        with self._session_factory() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingVersionEvidence)
                    .where(
                        AssetReportingVersionEvidence.target_instance == scope.target_instance,
                        AssetReportingVersionEvidence.tenant == scope.tenant,
                        AssetReportingVersionEvidence.canonical_table == scope.table,
                        AssetReportingVersionEvidence.stable_key == key,
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if row is None:
                    session.add(
                        AssetReportingVersionEvidence(
                            target_instance=scope.target_instance,
                            tenant=scope.tenant,
                            canonical_table=scope.table,
                            stable_key=key,
                            version_value=version,
                            applied_operation_id=operation_id,
                        )
                    )
                else:
                    row.version_value = version
                    row.applied_operation_id = operation_id
                    row.updated_at = _utcnow()


class SqlAlchemyControlRepository:
    """ControlRepository 的 PG 耐久实现（asset schema，asset_reporting_* 表）。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sessions = session_factory

    def version_registry(self) -> PgVersionRegistry:
        return PgVersionRegistry(self._sessions)

    # -- 任务配置 -------------------------------------------------------

    def save_task(self, task_id: str, spec_dict: dict) -> None:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingTaskConfig).where(
                        AssetReportingTaskConfig.canonical_table == task_id
                    )
                ).scalar_one_or_none()
                if row is None:
                    session.add(
                        AssetReportingTaskConfig(
                            canonical_table=task_id, spec_json=spec_dict
                        )
                    )
                else:
                    row.spec_json = spec_dict
                    row.lock_version += 1
                    row.updated_at = _utcnow()

    def get_task(self, task_id: str) -> dict | None:
        with self._sessions() as session:
            row = session.execute(
                select(AssetReportingTaskConfig).where(
                    AssetReportingTaskConfig.canonical_table == task_id
                )
            ).scalar_one_or_none()
            return dict(row.spec_json) if row else None

    # -- 批次与 attempt ---------------------------------------------------

    def _load_batch(self, session: Session, batch_id: str) -> BatchRecord:
        row = session.execute(
            select(AssetReportingBatch).where(AssetReportingBatch.batch_id == batch_id)
        ).scalar_one_or_none()
        if row is None:
            raise ContractViolation(f"批次不存在: {batch_id}")
        record = BatchRecord(
            batch_id=row.batch_id,
            task_id=row.canonical_table,
            business_day=str(row.business_day),
            state=BatchState(row.state),
            feedback_state=FeedbackState(row.feedback_state),
            target_instance=row.target_instance,
            tenant=row.tenant,
            target_table=row.target_table,
        )
        attempts = session.execute(
            select(AssetReportingBatchAttempt).where(
                AssetReportingBatchAttempt.batch_id == batch_id
            )
        ).scalars().all()
        for att in attempts:
            record.attempts[att.attempt_id] = manifest_from_dict(att.manifest_json)
            if row.selected_attempt_id == att.attempt_id:
                record.manifest = record.attempts[att.attempt_id]
        return record

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
        with self._sessions() as session:
            with session.begin():
                exists = session.execute(
                    select(AssetReportingBatch.id).where(
                        AssetReportingBatch.batch_id == batch_id
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    raise ContractViolation(f"batch_id 已存在: {batch_id}")
                session.add(
                    AssetReportingBatch(
                        batch_id=batch_id,
                        canonical_table=task_id,
                        business_day=_parse_date(business_day),
                        state=BatchState.PLANNED.value,
                        feedback_state=FeedbackState.NOT_SUBMITTED.value,
                        state_history=[],
                        target_instance=target_instance,
                        tenant=tenant,
                        target_table=target_table,
                    )
                )
        return BatchRecord(
            batch_id=batch_id,
            task_id=task_id,
            business_day=business_day,
            state=BatchState.PLANNED,
            target_instance=target_instance,
            tenant=tenant,
            target_table=target_table,
        )

    def get_batch(self, batch_id: str) -> BatchRecord:
        """公共批次读取（K04）：恢复层只依赖本公共接口，不触私有方法。"""
        with self._sessions() as session:
            return self._load_batch(session, batch_id)

    def attach_attempt_manifest(self, batch_id: str, manifest: BatchManifest) -> None:
        with self._sessions() as session:
            with session.begin():
                self._require_batch_row(session, batch_id)
                exists = session.execute(
                    select(AssetReportingBatchAttempt.id).where(
                        AssetReportingBatchAttempt.batch_id == batch_id,
                        AssetReportingBatchAttempt.attempt_id == manifest.attempt_id,
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    raise ContractViolation(
                        f"attempt 已存在: {batch_id}/{manifest.attempt_id}"
                    )
                session.add(
                    AssetReportingBatchAttempt(
                        batch_id=batch_id,
                        attempt_id=manifest.attempt_id,
                        engine=(
                            manifest.engine.value
                            if hasattr(manifest.engine, "value")
                            else None
                        ),
                        pagination_complete=manifest.pagination_complete,
                        manifest_json=manifest_to_dict(manifest),
                        payload_sha256=manifest.payload_sha256,
                        total_bytes=manifest.total_bytes,
                    )
                )

    def select_manifest(self, batch_id: str) -> BatchManifest:
        with self._sessions() as session:
            record = self._load_batch(session, batch_id)
            complete = [m for m in record.attempts.values() if m.pagination_complete]
            if not complete:
                raise ContractViolation(
                    f"[{batch_id}] 无完整 attempt manifest（部分 stage 不能当完整批次）"
                )
            chosen = max(complete, key=lambda m: m.attempt_id)
        with self._sessions() as session:
            with session.begin():
                row = self._require_batch_row(session, batch_id)
                row.selected_attempt_id = chosen.attempt_id
                row.updated_at = _utcnow()
        return chosen

    def transition_batch(
        self,
        batch_id: str,
        target: BatchState,
        *,
        reason: str,
        evidence: str | None = None,
    ) -> BatchState:
        with self._sessions() as session:
            with session.begin():
                row = self._require_batch_row(session, batch_id)
                record = self._load_batch(session, batch_id)
                machine = BatchStateMachine()
                machine.transition(
                    target, reason=reason, evidence=evidence, manifest=record.manifest
                )
                history = list(row.state_history or [])
                history.append(
                    {
                        "to": target.value,
                        "reason": reason,
                        "evidence": evidence,
                        "at": _utcnow().isoformat(timespec="seconds"),
                    }
                )
                row.state = machine.state.value
                row.state_history = history
                row.updated_at = _utcnow()
                return machine.state

    def transition_feedback(
        self, batch_id: str, target: FeedbackState, *, reason: str, evidence: str | None = None
    ) -> FeedbackState:
        machine = FeedbackStateMachine()
        machine.transition(target, reason=reason, evidence=evidence)
        with self._sessions() as session:
            with session.begin():
                row = self._require_batch_row(session, batch_id)
                row.feedback_state = machine.state.value
                row.updated_at = _utcnow()
        return machine.state

    def list_batches(self) -> list[BatchRecord]:
        out: list[BatchRecord] = []
        with self._sessions() as session:
            ids = [
                row
                for row in session.execute(
                    select(AssetReportingBatch.batch_id).order_by(
                        AssetReportingBatch.batch_id
                    )
                ).scalars()
            ]
        for batch_id in ids:
            with self._sessions() as session:
                out.append(self._load_batch(session, batch_id))
        return out

    @staticmethod
    def _require_batch_row(session: Session, batch_id: str) -> AssetReportingBatch:
        row = session.execute(
            select(AssetReportingBatch).where(AssetReportingBatch.batch_id == batch_id)
        ).scalar_one_or_none()
        if row is None:
            raise ContractViolation(f"批次不存在: {batch_id}")
        return row

    # -- 水位 ------------------------------------------------------------

    def get_watermarks(self, task_id: str) -> Watermarks:
        with self._sessions() as session:
            row = session.execute(
                select(AssetReportingWatermark).where(
                    AssetReportingWatermark.canonical_table == task_id
                )
            ).scalar_one_or_none()
            if row is None:
                return Watermarks(task_id=task_id)
            return Watermarks(
                task_id=task_id,
                capture_h=row.capture_h,
                apply_cursor=row.apply_cursor,
                delivery_cursor=row.delivery_cursor,
                continuous_through=row.continuous_through,
            )

    def _advance_watermark(
        self,
        task_id: str,
        field: str,
        new_value: datetime,
        *,
        monotonic: bool = True,
        gap_guard: bool = False,
        continuous_guard: bool = False,
    ) -> Watermarks:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingWatermark)
                    .where(AssetReportingWatermark.canonical_table == task_id)
                    .with_for_update()
                ).scalar_one_or_none()
                current = getattr(row, field) if row else None
                if monotonic and current is not None and new_value < current:
                    raise ContractViolation(f"{field} 不能后退")
                if gap_guard:
                    gaps = session.execute(
                        select(AssetReportingGapLedger).where(
                            AssetReportingGapLedger.canonical_table == task_id,
                            AssetReportingGapLedger.state == "OPEN",
                        )
                    ).scalars()
                    for gap in gaps:
                        guard_end = gap.window_end
                        if continuous_guard:
                            if gap.window_start < new_value:
                                raise ContractViolation(
                                    f"存在未闭合缺口 {gap.window_fingerprint}，"
                                    f"连续完成游标不得推进到 {new_value.isoformat()}"
                                )
                        elif guard_end > (current or gap.window_start):
                            raise ContractViolation(
                                f"存在未闭合缺口 {gap.window_fingerprint}，禁止把"
                                f"捕获水位推到 {new_value.isoformat()}"
                            )
                if row is None:
                    row = AssetReportingWatermark(canonical_table=task_id)
                    session.add(row)
                setattr(row, field, new_value)
                row.updated_at = _utcnow()
        return self.get_watermarks(task_id)

    def advance_capture_watermark(self, task_id: str, new_h: datetime) -> Watermarks:
        return self._advance_watermark(
            task_id, "capture_h", new_h, gap_guard=True
        )

    def advance_apply_cursor(self, task_id: str, new_cursor: datetime) -> Watermarks:
        return self._advance_watermark(task_id, "apply_cursor", new_cursor)

    def advance_delivery_cursor(self, task_id: str, new_cursor: datetime) -> Watermarks:
        return self._advance_watermark(task_id, "delivery_cursor", new_cursor)

    def advance_continuous_completion(self, task_id: str, through: datetime) -> Watermarks:
        return self._advance_watermark(
            task_id, "continuous_through", through,
            gap_guard=True, continuous_guard=True,
        )

    # -- 缺口账本 ---------------------------------------------------------

    def record_gap(self, task_id: str, window: TimeWindow, reason: str) -> GapRecord:
        with self._sessions() as session:
            with session.begin():
                row = AssetReportingGapLedger(
                    canonical_table=task_id,
                    window_start=window.start,
                    window_end=window.end_exclusive,
                    window_fingerprint=window.fingerprint(),
                    reason=reason,
                    state="OPEN",
                )
                session.add(row)
                session.flush()
                return GapRecord(
                    gap_id=row.id,
                    task_id=task_id,
                    window=window,
                    reason=reason,
                )

    def open_gaps(self, task_id: str) -> list[GapRecord]:
        with self._sessions() as session:
            rows = (
                session.execute(
                    select(AssetReportingGapLedger)
                    .where(
                        AssetReportingGapLedger.canonical_table == task_id,
                        AssetReportingGapLedger.state == "OPEN",
                    )
                    .order_by(AssetReportingGapLedger.window_start)
                )
                .scalars()
                .all()
            )
            return [
                GapRecord(
                    gap_id=row.id,
                    task_id=task_id,
                    window=TimeWindow(row.window_start, row.window_end),
                    reason=row.reason,
                    state=row.state,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def close_gap(self, gap_id: int, evidence: str) -> GapRecord:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingGapLedger)
                    .where(AssetReportingGapLedger.id == gap_id)
                    .with_for_update()
                ).scalar_one_or_none()
                if row is None:
                    raise ContractViolation(f"缺口不存在: {gap_id}")
                if row.state == "CLOSED":
                    raise ContractViolation(f"缺口 {gap_id} 已闭合")
                row.state = "CLOSED"
                row.closed_at = _utcnow()
                row.close_evidence = evidence
                return GapRecord(
                    gap_id=row.id,
                    task_id=row.canonical_table,
                    window=TimeWindow(row.window_start, row.window_end),
                    reason=row.reason,
                    state="CLOSED",
                    closed_at=row.closed_at,
                )

    # -- 历史月覆盖 -------------------------------------------------------

    def upsert_month_coverage(self, record: MonthCoverageRecord) -> MonthCoverageRecord:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingMonthCoverage).where(
                        AssetReportingMonthCoverage.canonical_table == record.table,
                        AssetReportingMonthCoverage.business_month == record.business_month,
                        AssetReportingMonthCoverage.route_or_origin == record.route_or_origin,
                    )
                ).scalar_one_or_none()
                if row is None:
                    row = AssetReportingMonthCoverage(
                        canonical_table=record.table,
                        business_month=record.business_month,
                        route_or_origin=record.route_or_origin,
                    )
                    session.add(row)
                row.last_complete_snapshot_cutoff = record.last_complete_snapshot_cutoff
                row.last_reconciled_at = record.last_reconciled_at
                row.cycle_days = record.cycle_days
                row.next_due = (
                    record.last_reconciled_at + timedelta(days=record.cycle_days)
                    if record.last_reconciled_at and record.cycle_days
                    else None
                )
                row.pending_slices = record.pending_slices
                row.failed_slices = record.failed_slices
                row.unresolved_quality = record.unresolved_quality
                row.overdue_reason = record.overdue_reason
                row.updated_at = _utcnow()
        return record

    def month_coverage(self, table: str) -> list[MonthCoverageRecord]:
        with self._sessions() as session:
            rows = (
                session.execute(
                    select(AssetReportingMonthCoverage).where(
                        AssetReportingMonthCoverage.canonical_table == table
                    )
                )
                .scalars()
                .all()
            )
            return [self._coverage_from_row(row) for row in rows]

    @staticmethod
    def _coverage_from_row(row) -> MonthCoverageRecord:
        return MonthCoverageRecord(
            table=row.canonical_table,
            business_month=row.business_month,
            route_or_origin=row.route_or_origin,
            last_complete_snapshot_cutoff=row.last_complete_snapshot_cutoff,
            last_reconciled_at=row.last_reconciled_at,
            cycle_days=row.cycle_days,
            pending_slices=row.pending_slices,
            failed_slices=row.failed_slices,
            unresolved_quality=row.unresolved_quality,
            overdue_reason=row.overdue_reason,
        )

    def overdue_months(self, table: str) -> list[MonthCoverageRecord]:
        now = _utcnow()
        return [r for r in self.month_coverage(table) if r.is_overdue(now)]

    # -- 幂等租约 + fencing token（跨进程原子） ---------------------------
    #
    # K03 语义：
    # - release 不删行（软释放：holder 置 released 标记并立刻过期），
    #   fencing_token 随行持久——释放后重获 token 严格递增，历史 token
    #   永不重用；validate_fencing 校验 token + 有效期（+可选 holder）。
    # - 并发首次创建同一资源：唯一约束冲突方重读重试一次，只允许一个合法
    #   领取。
    # - renew 尊重调用方 TTL（默认 3600），不再固定写死。

    _RELEASED_HOLDER_PREFIX = "released:"

    def acquire_lease(self, resource: str, holder: str, ttl_seconds: int) -> Lease:
        from sqlalchemy.exc import IntegrityError

        now = _utcnow()
        try:
            with self._sessions() as session:
                with session.begin():
                    return self._acquire_lease_locked(session, resource, holder, ttl_seconds, now)
        except IntegrityError:
            # 并发首次创建：另一进程先插入唯一行；重读后按既有行竞争一次
            with self._sessions() as session:
                with session.begin():
                    return self._acquire_lease_locked(session, resource, holder, ttl_seconds, now)

    def _acquire_lease_locked(
        self, session: Session, resource: str, holder: str, ttl_seconds: int, now: datetime
    ) -> Lease:
        row = session.execute(
            select(AssetReportingLease)
            .where(AssetReportingLease.resource == resource)
            .with_for_update()
        ).scalar_one_or_none()
        if row is not None and row.expires_at > now and row.holder != holder:
            raise LeaseDenied(
                f"资源 {resource} 被 {row.holder} 持有至 {row.expires_at}"
            )
        # 同一持有者未释放再领取同样推进 token：同身份的旧运行若仍在执行，
        # 其 token 在提交门被顶替失效（防同名双运行同时有效，K03）
        token = (row.fencing_token + 1) if row is not None else 1
        if row is None:
            row = AssetReportingLease(resource=resource)
            session.add(row)
        row.holder = holder
        row.fencing_token = token
        row.expires_at = now + timedelta(seconds=ttl_seconds)
        row.updated_at = now
        return Lease(
            resource=resource,
            holder=holder,
            fencing_token=token,
            expires_at=row.expires_at,
        )

    def renew_lease(
        self,
        resource: str,
        holder: str,
        fencing_token: int,
        *,
        ttl_seconds: int = 3600,
    ) -> Lease:
        now = _utcnow()
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingLease)
                    .where(AssetReportingLease.resource == resource)
                    .with_for_update()
                ).scalar_one_or_none()
                if row is None or row.holder != holder:
                    raise LeaseDenied(f"租约不存在或持有者不符: {resource}")
                if row.fencing_token != fencing_token:
                    raise LeaseDenied(
                        f"围栏不匹配: 持有 {fencing_token} < 当前 {row.fencing_token}"
                        "（旧 worker 不得续期）"
                    )
                if row.expires_at <= now:
                    raise LeaseDenied(f"租约已过期，不能续期: {resource}")
                row.expires_at = now + timedelta(seconds=ttl_seconds)
                row.updated_at = now
                return Lease(
                    resource=resource,
                    holder=holder,
                    fencing_token=row.fencing_token,
                    expires_at=row.expires_at,
                )

    def validate_fencing(
        self, resource: str, fencing_token: int, *, holder: str | None = None
    ) -> None:
        """K03：token + 有效期（+可选 holder）三方校验。

        过期租约的 token 不得通过提交门：过期后即使未被他人重领，本 token
        也不再证明"当前唯一写者"，调用方须重新领取。
        """
        now = _utcnow()
        with self._sessions() as session:
            row = session.execute(
                select(AssetReportingLease).where(
                    AssetReportingLease.resource == resource
                )
            ).scalar_one_or_none()
            if row is None or row.fencing_token != fencing_token:
                raise LeaseDenied(
                    f"围栏校验失败: {resource} 期望 token="
                    f"{row.fencing_token if row else None}"
                )
            if row.expires_at <= now:
                raise LeaseDenied(f"租约已过期，token 不再有效: {resource}")
            if holder is not None and row.holder != holder:
                raise LeaseDenied(f"围栏持有者不符: {resource} {row.holder} != {holder}")

    def release_lease(
        self, resource: str, holder: str, *, fencing_token: int | None = None
    ) -> None:
        """K03：软释放（不删行）+ token 绑定。

        - 不删行保证 fencing_token 序列跨释放/重启单调；
        - 释放把 holder 改为 released 标记并立刻过期；重复释放幂等；
        - 给了 token 则必须与当前行一致：旧进程晚到释放（token 已被新
          领取顶替或持有者已换）不得撤销新租约。
        """
        now = _utcnow()
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingLease)
                    .where(AssetReportingLease.resource == resource)
                    .with_for_update()
                ).scalar_one_or_none()
                if row is None:
                    return
                if row.holder.startswith(self._RELEASED_HOLDER_PREFIX):
                    if (
                        fencing_token is not None
                        and row.fencing_token != fencing_token
                    ):
                        raise LeaseDenied(
                            f"释放被拒（token 不属于当前租约）: {resource} "
                            f"释放 token={fencing_token} 当前={row.fencing_token}"
                        )
                    return  # 已释放：幂等
                if row.holder != holder:
                    # 持有者已被顶替：晚到的同名/旧进程释放不生效
                    if fencing_token is not None:
                        raise LeaseDenied(
                            f"释放被拒（租约已由他人持有）: {resource} 当前持有者"
                            f" {row.holder} != {holder}"
                        )
                    return
                if fencing_token is not None and row.fencing_token != fencing_token:
                    raise LeaseDenied(
                        f"释放被拒（token 不属于当前租约）: {resource} "
                        f"释放 token={fencing_token} 当前={row.fencing_token}"
                    )
                row.holder = f"{self._RELEASED_HOLDER_PREFIX}{holder}@{row.fencing_token}"
                row.expires_at = now
                row.updated_at = now

    # -- 告警 incident / outbox -------------------------------------------

    def create_incident(
        self,
        incident_key: str,
        category: str,
        affected_tables: Iterable[str] | None = None,
    ) -> AlertIncident:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingAlertIncident).where(
                        AssetReportingAlertIncident.incident_key == incident_key,
                        AssetReportingAlertIncident.state != "RECOVERED",
                    )
                ).scalar_one_or_none()
                if row is not None:
                    return self._incident_from_row(row)
                row = AssetReportingAlertIncident(
                    incident_key=incident_key,
                    category=category,
                    affected_tables=list(affected_tables or []),
                    state="OPEN",
                    revision=0,
                )
                session.add(row)
                session.flush()
                return self._incident_from_row(row)

    @staticmethod
    def _incident_from_row(row) -> AlertIncident:
        return AlertIncident(
            incident_id=row.incident_id,
            incident_key=row.incident_key,
            category=row.category,
            state=row.state,
            revision=row.revision,
            affected_tables=list(row.affected_tables or []),
            last_event_source_id=row.last_event_source_id,
            created_at=row.created_at,
        )

    def _incident_row(self, session: Session, incident: AlertIncident):
        row = session.execute(
            select(AssetReportingAlertIncident).where(
                AssetReportingAlertIncident.incident_id == incident.incident_id
            )
        ).scalar_one_or_none()
        if row is None:
            raise ContractViolation(f"incident 不存在: {incident.incident_id}")
        return row

    def append_incident_event(
        self,
        incident: AlertIncident,
        *,
        event_kind: str,
        severity: str,
        title: str,
        body_bytes: bytes,
        metadata: dict | None = None,
        source_id: str | None = None,
        secret_ref: str | None = None,
    ) -> OutboxEvent:
        if not body_bytes:
            raise ContractViolation("事件 body 不能为空")
        with self._sessions() as session:
            with session.begin():
                row = self._incident_row(session, incident)
                candidate_id = (
                    f"r189t1.{incident.incident_id}.{event_kind}.{incident.revision}"
                    if incident.revision > 0 else None
                )
                if candidate_id:
                    existing = session.execute(
                        select(AssetReportingAlertOutbox).where(
                            AssetReportingAlertOutbox.source_event_id == candidate_id
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        if bytes(existing.immutable_body) != body_bytes:
                            raise ContractViolation(
                                f"同 source_event_id 事件字节冲突: {candidate_id}"
                                "（需新 revision，不得改内容）"
                            )
                        return self._event_from_row(existing)
                row.revision += 1
                row.updated_at = _utcnow()
                source_event_id = (
                    f"r189t1.{incident.incident_id}.{event_kind}.{row.revision}"
                )
                if len(source_event_id) > 200:
                    raise ContractViolation("source_event_id 超 200 字符")
                payload_sha256 = hashlib.sha256(body_bytes).hexdigest()
                dup = session.execute(
                    select(AssetReportingAlertOutbox).where(
                        AssetReportingAlertOutbox.source_event_id == source_event_id
                    )
                ).scalar_one_or_none()
                if dup is not None:
                    if bytes(dup.immutable_body) != body_bytes:
                        raise ContractViolation(
                            f"同 source_event_id 事件字节冲突: {source_event_id}"
                        )
                    return self._event_from_row(dup)
                event_row = AssetReportingAlertOutbox(
                    source_event_id=source_event_id,
                    incident_id=incident.incident_id,
                    revision=row.revision,
                    event_kind=event_kind,
                    severity=severity,
                    title=title,
                    immutable_body=body_bytes,
                    payload_sha256=payload_sha256,
                    metadata_json=dict(metadata or {}),
                    source_id=source_id,
                    secret_ref=secret_ref,
                )
                session.add(event_row)
                row.last_event_source_id = source_event_id
                if event_kind == "RECOVERED":
                    row.state = "RECOVERED"
                elif severity in ("red",) and event_kind == "ESCALATED":
                    row.state = "ESCALATED"
                return OutboxEvent(
                    source_event_id=source_event_id,
                    incident_id=incident.incident_id,
                    revision=row.revision,
                    event_kind=event_kind,
                    severity=severity,
                    title=title,
                    immutable_body_bytes=body_bytes,
                    payload_sha256=payload_sha256,
                    metadata=dict(metadata or {}),
                    source_id=source_id,
                    secret_ref=secret_ref,
                )

    @staticmethod
    def _event_from_row(row) -> OutboxEvent:
        return OutboxEvent(
            source_event_id=row.source_event_id,
            incident_id=row.incident_id,
            revision=row.revision,
            event_kind=row.event_kind,
            severity=row.severity,
            title=row.title,
            immutable_body_bytes=bytes(row.immutable_body),
            payload_sha256=row.payload_sha256,
            metadata=dict(row.metadata_json or {}),
            source_id=row.source_id,
            secret_ref=row.secret_ref,
            acceptance_state=row.acceptance_state,
            delivery_state=row.delivery_state,
            relay_event_id=row.relay_event_id,
            target_status_summary=dict(row.target_status_summary or {}),
            attempts=row.attempts,
            next_attempt_at=row.next_attempt_at,
            last_error_class=row.last_error_class,
            last_http_code=row.last_http_code,
            retry_after_seconds=row.retry_after_seconds,
            poll_count=row.poll_count,
            needs_attention_reason=row.needs_attention_reason,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def get_outbox_event(self, source_event_id: str) -> OutboxEvent | None:
        with self._sessions() as session:
            row = session.execute(
                select(AssetReportingAlertOutbox).where(
                    AssetReportingAlertOutbox.source_event_id == source_event_id
                )
            ).scalar_one_or_none()
            return self._event_from_row(row) if row else None

    def queued_outbox(self) -> list[OutboxEvent]:
        with self._sessions() as session:
            rows = (
                session.execute(
                    select(AssetReportingAlertOutbox).where(
                        AssetReportingAlertOutbox.acceptance_state.in_(
                            ("ACK_QUEUED", "DUPLICATE")
                        ),
                        AssetReportingAlertOutbox.delivery_state != "DELIVERED",
                    )
                )
                .scalars()
                .all()
            )
            return [self._event_from_row(r) for r in rows]

    def pending_outbox(self) -> list[OutboxEvent]:
        now = _utcnow()
        with self._sessions() as session:
            rows = (
                session.execute(
                    select(AssetReportingAlertOutbox)
                    .where(
                        AssetReportingAlertOutbox.delivery_state.notin_(
                            ("DELIVERED", "PAUSED_AUTH", "NEEDS_ATTENTION")
                        ),
                        AssetReportingAlertOutbox.acceptance_state.notin_(
                            ("REJECTED_PERMANENT", "ACK_QUEUED", "DUPLICATE")
                        ),
                    )
                    .order_by(AssetReportingAlertOutbox.id)
                )
                .scalars()
                .all()
            )
            return [
                self._event_from_row(r)
                for r in rows
                if r.next_attempt_at is None or r.next_attempt_at <= now
            ]

    def update_outbox_delivery(self, source_event_id: str, **kwargs) -> OutboxEvent:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingAlertOutbox)
                    .where(
                        AssetReportingAlertOutbox.source_event_id == source_event_id
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if row is None:
                    raise ContractViolation(f"outbox 事件不存在: {source_event_id}")
                if kwargs.get("acceptance_state") is not None:
                    row.acceptance_state = kwargs["acceptance_state"]
                if kwargs.get("delivery_state") is not None:
                    row.delivery_state = kwargs["delivery_state"]
                if kwargs.get("relay_event_id") is not None:
                    row.relay_event_id = kwargs["relay_event_id"]
                if kwargs.get("target_status_summary") is not None:
                    row.target_status_summary = kwargs["target_status_summary"]
                row.attempts += kwargs.get("attempts_increment", 0)
                if kwargs.get("next_attempt_at") is not None:
                    row.next_attempt_at = kwargs["next_attempt_at"]
                if kwargs.get("last_error_class") is not None:
                    row.last_error_class = kwargs["last_error_class"]
                if kwargs.get("last_http_code") is not None:
                    row.last_http_code = kwargs["last_http_code"]
                if kwargs.get("retry_after_seconds") is not None:
                    row.retry_after_seconds = kwargs["retry_after_seconds"]
                row.poll_count += kwargs.get("poll_increment", 0)
                if kwargs.get("needs_attention_reason") is not None:
                    row.needs_attention_reason = kwargs["needs_attention_reason"]
                row.updated_at = _utcnow()
                return self._event_from_row(row)

    # -- 隔离组（R02 增量） --------------------------------------------------

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
        with self._sessions() as session:
            with session.begin():
                exists = session.execute(
                    select(AssetReportingQuarantineGroup.id).where(
                        AssetReportingQuarantineGroup.batch_id == batch_id,
                        AssetReportingQuarantineGroup.group_key == group_key,
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    raise ContractViolation(
                        f"隔离组已登记: {batch_id}/{group_key}"
                    )
                session.add(
                    AssetReportingQuarantineGroup(
                        batch_id=batch_id,
                        canonical_table=canonical_table,
                        group_key=group_key,
                        reason=reason,
                        error_code=error_code,
                        rows_quarantined=rows_quarantined,
                        detail_ref=detail_ref,
                    )
                )

    def resolve_quarantine_group(
        self, batch_id: str, group_key: str, *, evidence: str
    ) -> None:
        with self._sessions() as session:
            with session.begin():
                row = session.execute(
                    select(AssetReportingQuarantineGroup).where(
                        AssetReportingQuarantineGroup.batch_id == batch_id,
                        AssetReportingQuarantineGroup.group_key == group_key,
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise ContractViolation(f"隔离组不存在: {batch_id}/{group_key}")
                row.state = "RESOLVED"
                row.resolved_at = _utcnow()
                row.resolution_evidence = evidence

    # -- 导出 ------------------------------------------------------------

    def snapshot(self) -> dict:
        # 与内存实现同构：逐表行、批次、水位、缺口、月覆盖、incident、outbox
        per_table: dict[str, dict] = {}
        with self._sessions() as session:
            batch_rows = (
                session.execute(select(AssetReportingBatch).order_by(AssetReportingBatch.batch_id))
                .scalars()
                .all()
            )
            attempts_by_batch: dict[str, dict] = {}
            for att in (
                session.execute(select(AssetReportingBatchAttempt)).scalars().all()
            ):
                attempts_by_batch.setdefault(att.batch_id, {})[att.attempt_id] = att
            for row in batch_rows:
                entry = per_table.setdefault(
                    row.canonical_table,
                    {
                        "task": row.canonical_table, "batches": 0, "by_state": {},
                        "quarantined": 0, "pending_parent": 0, "applied": 0,
                        "commit_unknown": 0, "earliest_open_gap": None,
                    },
                )
                entry["batches"] += 1
                entry["by_state"][row.state] = entry["by_state"].get(row.state, 0) + 1
                if row.state == BatchState.QUARANTINED.value:
                    entry["quarantined"] += 1
                elif row.state == BatchState.BLOCKED_DEPENDENCY.value:
                    entry["pending_parent"] += 1
                elif row.state == BatchState.APPLIED.value:
                    entry["applied"] += 1
                elif row.state == BatchState.COMMIT_UNKNOWN.value:
                    entry["commit_unknown"] += 1
            gap_rows = (
                session.execute(
                    select(AssetReportingGapLedger).where(
                        AssetReportingGapLedger.state == "OPEN"
                    )
                )
                .scalars()
                .all()
            )
            open_by_task: dict[str, list] = {}
            for gap in gap_rows:
                open_by_task.setdefault(gap.canonical_table, []).append(gap)
            for table, gaps in open_by_task.items():
                entry = per_table.setdefault(
                    table,
                    {
                        "task": table, "batches": 0, "by_state": {}, "quarantined": 0,
                        "pending_parent": 0, "applied": 0, "commit_unknown": 0,
                        "earliest_open_gap": None,
                    },
                )
                earliest = min(gaps, key=lambda g: g.window_start)
                entry["earliest_open_gap"] = {
                    "gap_id": earliest.id,
                    "window": earliest.window_fingerprint,
                    "reason": earliest.reason,
                    "open_gap_count": len(gaps),
                }
            wm_rows = session.execute(select(AssetReportingWatermark)).scalars().all()
            month_rows = session.execute(select(AssetReportingMonthCoverage)).scalars().all()
            inc_rows = session.execute(select(AssetReportingAlertIncident)).scalars().all()
            outbox_rows = session.execute(select(AssetReportingAlertOutbox)).scalars().all()
            batches_section = {
                row.batch_id: {
                    "task": row.canonical_table,
                    "state": row.state,
                    "feedback": row.feedback_state,
                    "attempts": sorted(attempts_by_batch.get(row.batch_id, {})),
                    "selected_attempt": row.selected_attempt_id,
                }
                for row in batch_rows
            }
            return {
                "batches": batches_section,
                "per_table": per_table,
                "watermarks": {
                    row.canonical_table: {
                        "capture_h": row.capture_h.isoformat() if row.capture_h else None,
                        "apply_cursor": row.apply_cursor.isoformat() if row.apply_cursor else None,
                        "delivery_cursor": (
                            row.delivery_cursor.isoformat() if row.delivery_cursor else None
                        ),
                        "continuous_through": (
                            row.continuous_through.isoformat()
                            if row.continuous_through else None
                        ),
                    }
                    for row in wm_rows
                },
                "open_gaps": [
                    {
                        "gap_id": g.id,
                        "task": g.canonical_table,
                        "window": g.window_fingerprint,
                        "reason": g.reason,
                    }
                    for g in gap_rows
                ],
                "month_coverage": [
                    {
                        "table": r.canonical_table,
                        "month": r.business_month,
                        "origin": r.route_or_origin,
                        "reconciled": (
                            r.last_reconciled_at.isoformat() if r.last_reconciled_at else None
                        ),
                        "pending": r.pending_slices,
                        "failed": r.failed_slices,
                    }
                    for r in month_rows
                ],
                "incidents": [
                    {
                        "id": i.incident_id,
                        "key": i.incident_key,
                        "state": i.state,
                        "revision": i.revision,
                    }
                    for i in inc_rows
                ],
                "outbox": [
                    {
                        "source_event_id": o.source_event_id,
                        "acceptance": o.acceptance_state,
                        "delivery": o.delivery_state,
                        "attempts": o.attempts,
                    }
                    for o in outbox_rows
                ],
            }


def _parse_date(value: str):
    from datetime import date

    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
