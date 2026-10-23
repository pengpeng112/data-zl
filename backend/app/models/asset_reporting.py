"""R189-T1 报送管道控制状态模型候选（asset schema，asset_reporting_ 前缀）。

E02 仅提供表结构候选：与 dict_sync_outbox/quality_governance 的 outbox、
租约、幂等模式对齐，但不复用其业务表（报送管道状态语义独立）。真实迁移
手写在 E08 隔离验收后进入 alembic/versions；本文件未注册进 models/__init__，
未进入当前任何迁移链。

所有列不存明文凭据/患者数据：secret 只存 secret_ref；告警 body 为脱敏
UTF-8 文本；指纹为 sha256hex。
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from ..core.db import Base


class AssetReportingTaskConfig(Base):
    """77项任务配置：spec_json 为 TaskSpec 序列化；enabled 默认 false。"""

    __tablename__ = "asset_reporting_task_configs"
    __table_args__ = (
        UniqueConstraint("canonical_table", name="uq_asset_reporting_task_table"),
        Index("ix_asset_reporting_task_enabled", "enabled"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    canonical_table = Column(Text, nullable=False)
    business_name = Column(Text)
    config_version = Column(String(32), nullable=False, server_default="v0-seed")
    spec_json = Column(JSONB, nullable=False)
    definition_fingerprint = Column(String(64))
    enabled = Column(Boolean, nullable=False, server_default="false")
    lock_version = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingBatch(Base):
    """批次主记录：状态机历史、反馈链、选中 attempt。"""

    __tablename__ = "asset_reporting_batches"
    __table_args__ = (
        UniqueConstraint("batch_id", name="uq_asset_reporting_batch_id"),
        Index("ix_asset_reporting_batch_task_day", "canonical_table", "business_day"),
        Index("ix_asset_reporting_batch_state", "state"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(Text, nullable=False)
    canonical_table = Column(Text, nullable=False)
    business_day = Column(Date, nullable=False)
    mode = Column(String(24), nullable=False, server_default="T1")
    state = Column(String(24), nullable=False, server_default="PLANNED")
    feedback_state = Column(String(24), nullable=False, server_default="NOT_SUBMITTED")
    state_history = Column(JSONB, nullable=False, server_default="[]")
    selected_attempt_id = Column(Text)
    # K02：目标绑定（实例/机构/表）——COMMIT_UNKNOWN 冻结范围按此结构化，
    # 单表提交不明不得冻结全批；全部可空（历史行未绑定=范围不可判定）。
    target_instance = Column(Text, nullable=True)
    tenant = Column(Text, nullable=True)
    target_table = Column(Text, nullable=True)
    lock_version = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingBatchAttempt(Base):
    """attempt 隔离：每次尝试的 manifest 独立归档，不互相覆盖。"""

    __tablename__ = "asset_reporting_batch_attempts"
    __table_args__ = (
        UniqueConstraint("batch_id", "attempt_id", name="uq_asset_reporting_attempt"),
        Index("ix_asset_reporting_attempt_batch", "batch_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(Text, nullable=False)
    attempt_id = Column(Text, nullable=False)
    engine = Column(String(16))
    pagination_complete = Column(Boolean, nullable=False, server_default="false")
    manifest_json = Column(JSONB, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    total_bytes = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingWatermark(Base):
    """三游标分离：capture_h / apply_cursor / delivery_cursor。

    R02 增列 continuous_through：最后连续完成日（与捕获水位分开，
    中间有缺口时不推进；RT1-025）。
    """

    __tablename__ = "asset_reporting_watermarks"
    __table_args__ = (
        UniqueConstraint("canonical_table", name="uq_asset_reporting_wm_table"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    canonical_table = Column(Text, nullable=False)
    capture_h = Column(TIMESTAMP(timezone=True))
    apply_cursor = Column(TIMESTAMP(timezone=True))
    delivery_cursor = Column(TIMESTAMP(timezone=True))
    continuous_through = Column(TIMESTAMP(timezone=True))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingGapLedger(Base):
    """失败缺口账本：捕获水位不得越过 OPEN 缺口。"""

    __tablename__ = "asset_reporting_gap_ledger"
    __table_args__ = (
        Index("ix_asset_reporting_gap_task_state", "canonical_table", "state"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    canonical_table = Column(Text, nullable=False)
    window_start = Column(TIMESTAMP(timezone=True), nullable=False)
    window_end = Column(TIMESTAMP(timezone=True), nullable=False)
    window_fingerprint = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    error_class = Column(String(64))
    state = Column(String(16), nullable=False, server_default="OPEN")
    attempt = Column(Integer, nullable=False, server_default="0")
    next_retry_at = Column(TIMESTAMP(timezone=True))
    manual_condition = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    closed_at = Column(TIMESTAMP(timezone=True))
    close_evidence = Column(Text)


class AssetReportingMonthCoverage(Base):
    """历史业务月覆盖账：业务月×来源归属；RESCAN_OVERDUE 数据源。"""

    __tablename__ = "asset_reporting_month_coverage"
    __table_args__ = (
        UniqueConstraint(
            "canonical_table", "business_month", "route_or_origin",
            name="uq_asset_reporting_month_cover",
        ),
        Index("ix_asset_reporting_month_next_due", "next_due"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    canonical_table = Column(Text, nullable=False)
    business_month = Column(String(7), nullable=False)  # YYYY-MM
    route_or_origin = Column(Text, nullable=False)
    last_complete_snapshot_cutoff = Column(TIMESTAMP(timezone=True))
    last_reconciled_at = Column(TIMESTAMP(timezone=True))
    cycle_days = Column(Integer)
    next_due = Column(TIMESTAMP(timezone=True))
    pending_slices = Column(Integer, nullable=False, server_default="0")
    failed_slices = Column(Integer, nullable=False, server_default="0")
    unresolved_quality = Column(Integer, nullable=False, server_default="0")
    overdue_reason = Column(Text)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingLease(Base):
    """幂等租约 + 单调 fencing token（同表单写者的控制面侧凭据）。"""

    __tablename__ = "asset_reporting_leases"
    __table_args__ = (
        UniqueConstraint("resource", name="uq_asset_reporting_lease_resource"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    resource = Column(Text, nullable=False)  # 如 target:DBOPER.EMR_X 或 ctrl:scheduler
    holder = Column(Text, nullable=False)
    fencing_token = Column(BigInteger, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingAlertIncident(Base):
    """告警 incident：同 key 聚合，revision 单调，RECOVERED 用新事件。"""

    __tablename__ = "asset_reporting_alert_incidents"
    __table_args__ = (
        UniqueConstraint("incident_key", name="uq_asset_reporting_incident_key"),
        Index("ix_asset_reporting_incident_state", "state"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    incident_id = Column(Text, nullable=False, unique=True)
    incident_key = Column(Text, nullable=False)
    category = Column(String(64), nullable=False)
    state = Column(String(16), nullable=False, server_default="OPEN")
    revision = Column(Integer, nullable=False, server_default="0")
    affected_tables = Column(JSONB)
    last_event_source_id = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingAlertOutbox(Base):
    """告警 outbox：不可变请求字节（UTF-8 JSON）+ 投递状态跟踪。

    immutable_body 存确切 UTF-8 请求字节（LargeBinary），重试原字节不变、
    仅换时间戳/签名（签名在发送时计算，不入库）。secret 只存 secret_ref。
    """

    __tablename__ = "asset_reporting_alert_outbox"
    __table_args__ = (
        UniqueConstraint("source_event_id", name="uq_asset_reporting_outbox_sid"),
        Index("ix_asset_reporting_outbox_delivery", "delivery_state", "next_attempt_at"),
        Index("ix_asset_reporting_outbox_incident", "incident_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_event_id = Column(Text, nullable=False)
    incident_id = Column(Text, nullable=False)
    revision = Column(Integer, nullable=False)
    event_kind = Column(String(24), nullable=False)
    severity = Column(String(16), nullable=False)
    title = Column(Text, nullable=False)
    immutable_body = Column(LargeBinary, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    metadata_json = Column(JSONB)
    source_id = Column(Text)
    secret_ref = Column(Text)
    acceptance_state = Column(String(32), nullable=False, server_default="PENDING")
    delivery_state = Column(String(32), nullable=False, server_default="NOT_SENT")
    relay_event_id = Column(Text)
    target_status_summary = Column(JSONB)
    attempts = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(TIMESTAMP(timezone=True))
    last_error_class = Column(String(64))
    last_http_code = Column(Integer)
    retry_after_seconds = Column(Integer)
    poll_count = Column(Integer, nullable=False, server_default="0")
    needs_attention_reason = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingVersionEvidence(Base):
    """R02 版本证据账：键含目标实例/租户/表，跨表同 ID 不互污染（RT1-014）。

    version_value 为已核版本序字符串凭据；version_kind 声明 int/decimal/
    timestamp；applied_operation_id 关联同事务提交凭据。内存账仅模拟。
    """

    __tablename__ = "asset_reporting_version_evidence"
    __table_args__ = (
        UniqueConstraint(
            "target_instance", "tenant", "canonical_table", "stable_key",
            name="uq_asset_reporting_version_key",
        ),
        Index(
            "ix_asset_reporting_version_table",
            "canonical_table",
        ),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    target_instance = Column(Text, nullable=False)
    tenant = Column(Text, nullable=False)
    canonical_table = Column(Text, nullable=False)
    stable_key = Column(Text, nullable=False)  # JSON 编码的业务稳定键元组
    version_value = Column(Text, nullable=False)
    version_kind = Column(String(16))
    applied_operation_id = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetReportingQuarantineGroup(Base):
    """R02 隔离组账：坏行/组的工单化留痕（独立合法组继续的依据）。"""

    __tablename__ = "asset_reporting_quarantine_groups"
    __table_args__ = (
        UniqueConstraint("batch_id", "group_key", name="uq_asset_reporting_quarantine"),
        Index("ix_asset_reporting_quarantine_state", "canonical_table", "state"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(Text, nullable=False)
    canonical_table = Column(Text, nullable=False)
    group_key = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    error_code = Column(String(64))
    rows_quarantined = Column(Integer, nullable=False, server_default="0")
    state = Column(String(16), nullable=False, server_default="OPEN")
    detail_ref = Column(Text)  # 受权限保护的工单/日志引用（不含患者明细）
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True))
    resolution_evidence = Column(Text)


class AssetReportingApprovalRef(Base):
    """T+1 正式装载的耐久批准登记（批1-2c）。

    管道自身永远不写本表：只有运维经 reporting_ctl approval-register
    （显式管理动作，对应用户会话内批准）登记；装载时由
    PlatformApprovalVerifier 只读核验。JSON 里的字符串不是生产批准，
    本表是唯一耐久批准源。
    """

    __tablename__ = "asset_reporting_approval_refs"
    __table_args__ = (
        UniqueConstraint("approval_ref", "executor_code", name="uq_asset_reporting_approval"),
        Index("ix_asset_reporting_approval_ref", "approval_ref"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    approval_ref = Column(Text, nullable=False)
    executor_code = Column(Text, nullable=False)
    target_scope = Column(Text, nullable=False)  # target:{instance}.{tenant}.{table}
    allowed_operations = Column(Text, nullable=False, server_default="INSERT,UPDATE")
    valid_from = Column(TIMESTAMP(timezone=True), nullable=False)
    valid_until = Column(TIMESTAMP(timezone=True), nullable=False)
    registered_by = Column(Text, nullable=False)
    note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
