"""174 S1: 数据质量主动治理台账模型（五表）。

Control（质控清单）→ Observation（不可变观测）→ Issue（整改台账）→ IssueEvent（业务时间线）。
Detector 把检测来源（probe_template / quality_rule / manual / external）绑定到 Control。

字段与迁移 d5e6f7a8b9c0 一一对应；状态/转移矩阵权威定义在
services/quality_governance_service.py（模型层只存值，不复制状态机）。
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from .governance_base import Base

# 非终态谓词（174 §4.3）：与 service 层 ISSUE_TERMINAL_STATUSES 保持一致
_ISSUE_ACTIVE_WHERE = text(
    "status NOT IN ('resolved','accepted_risk','false_positive','duplicate','cancelled') "
    "AND control_id IS NOT NULL AND archived_at IS NULL"
)


class QualityControl(Base):
    """质控清单：稳定 control_code + 递增 version 的版本化规则口径。"""

    __tablename__ = "asset_quality_controls"
    __table_args__ = (
        UniqueConstraint("control_code", name="uq_asset_quality_controls_code"),
        Index("ix_asset_quality_controls_status", "lifecycle_status"),
        Index("ix_asset_quality_controls_system", "primary_system_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    control_code = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, server_default="1")
    title = Column(String(256), nullable=False)
    description = Column(Text)
    lifecycle_status = Column(String(16), nullable=False, server_default="draft")
    blocked_reason = Column(Text)
    dimension = Column(String(32))
    category = Column(String(16))
    primary_system_code = Column(String(64))
    related_system_codes = Column(JSONB)
    object_key = Column(String(512))
    object_name_snapshot = Column(String(512))
    metric_name = Column(String(128))
    metric_unit = Column(String(32))
    comparator = Column(String(8))
    threshold_value = Column(Numeric(18, 6))
    no_data_policy = Column(String(8), nullable=False, server_default="blocked")
    default_severity = Column(String(8), server_default="medium")
    default_priority = Column(String(2), server_default="P3")
    default_dept_code = Column(String(64))
    default_person_code = Column(String(64))
    schedule_expr = Column(String(64))
    timezone = Column(String(64))
    verification_policy = Column(String(16), nullable=False, server_default="manual")
    required_pass_count = Column(Integer, server_default="1")
    # 207 A1 增量：执行计划与调度贯通（缺失必须可解释，不猜测默认执行）
    source_code = Column(String(64))
    schedule_enabled = Column(String(8), nullable=False, server_default="false")
    next_run_at = Column(TIMESTAMP(timezone=True))
    last_run_at = Column(TIMESTAMP(timezone=True))
    freshness_hours = Column(Integer)
    recheck_policy = Column(String(16), server_default="auto")
    sla_hours = Column(Integer)
    execution_plan = Column(JSONB)
    lock_version = Column(Integer, nullable=False, server_default="0")
    created_by = Column(String(64))
    updated_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityControlDetector(Base):
    """检测来源绑定：一条 Control 可绑多个 Detector（含手工来源）。"""

    __tablename__ = "asset_quality_control_detectors"
    __table_args__ = (
        UniqueConstraint(
            "control_id",
            "detector_kind",
            "detector_ref",
            "detector_version",
            name="uq_asset_quality_control_detectors_binding",
        ),
        Index("ix_asset_quality_detectors_status", "status"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    control_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    detector_kind = Column(String(16), nullable=False)
    detector_ref = Column(String(64), nullable=False)
    detector_version = Column(String(32), nullable=False, server_default="1")
    status = Column(String(16), nullable=False, server_default="draft")
    blocked_reason = Column(Text)
    scope_mapping = Column(JSONB)
    result_mapping = Column(JSONB)
    last_bound_at = Column(TIMESTAMP(timezone=True))
    created_by = Column(String(64))
    updated_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityObservation(Base):
    """不可变观测：一次执行在一个窗口/范围的固化结果；禁止业务 UPDATE/DELETE。"""

    __tablename__ = "asset_quality_observations"
    __table_args__ = (
        # 幂等唯一键：COALESCE 处理 manual 来源 detector_id 为 NULL 的场景（Postgres NULL 不参与唯一）
        Index(
            "uq_asset_quality_observations_idem",
            "control_id",
            text("COALESCE(detector_id, 0)"),
            "run_key",
            "scope_key",
            unique=True,
        ),
        Index("ix_asset_quality_observations_control", "control_id"),
        Index("ix_asset_quality_observations_issue", "issue_id"),
        Index("ix_asset_quality_observations_result", "result_status"),
        Index("ix_asset_quality_observations_window", "window_start", "window_end"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    control_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    detector_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_control_detectors.id", ondelete="CASCADE"),
    )
    control_version = Column(Integer, nullable=False)
    issue_id = Column(BigInteger, ForeignKey("asset.asset_quality_issues.id", ondelete="SET NULL"))
    run_key = Column(String(128), nullable=False)
    scope_key = Column(String(256), nullable=False)
    window_start = Column(Date)
    window_end = Column(Date)
    observed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    result_status = Column(String(16), nullable=False)
    metric_value = Column(Numeric(18, 6))
    metric_unit = Column(String(32))
    threshold_snapshot = Column(JSONB)
    control_definition_snapshot = Column(JSONB)
    numerator = Column(Numeric(18, 6))
    denominator = Column(Numeric(18, 6))
    source_kind = Column(String(32), nullable=False)
    source_record_ref = Column(String(128))
    evidence_digest = Column(String(128))
    evidence_ref = Column(String(512))
    historical_precision = Column(String(16), nullable=False, server_default="exact")
    error_code = Column(String(32))
    error_message_sanitized = Column(Text)
    created_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityIssue(Base):
    """整改台账：一次治理事件（issue_code 唯一）；非终态下同一 control+scope 仅一条活动问题。"""

    __tablename__ = "asset_quality_issues"
    __table_args__ = (
        UniqueConstraint("issue_code", name="uq_asset_quality_issues_code"),
        Index("ix_asset_quality_issues_status", "status"),
        Index("ix_asset_quality_issues_control", "control_id"),
        Index("ix_asset_quality_issues_scope", "control_id", "scope_key"),
        Index("ix_asset_quality_issues_dept", "responsible_dept_code"),
        Index("ix_asset_quality_issues_assignee", "assignee_user_identifier"),
        Index("ix_asset_quality_issues_due", "due_at"),
        # 部分唯一索引：同一 control_id + scope_key 只允许一条非终态活动问题（174 §4.3）
        Index(
            "uq_asset_quality_issues_active",
            "control_id",
            "scope_key",
            unique=True,
            postgresql_where=_ISSUE_ACTIVE_WHERE,
        ),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    issue_code = Column(String(32), nullable=False)
    control_id = Column(BigInteger, ForeignKey("asset.asset_quality_controls.id", ondelete="SET NULL"))
    issue_type = Column(String(16), nullable=False, server_default="data_defect")
    title = Column(String(256), nullable=False)
    description = Column(Text)
    primary_system_code = Column(String(64))
    related_system_codes = Column(JSONB)
    object_key = Column(String(512))
    object_name_snapshot = Column(String(512))
    scope_key = Column(String(256))
    severity = Column(String(8))
    priority = Column(String(2))
    status = Column(String(16), nullable=False, server_default="new")
    responsible_dept_code = Column(String(64))
    responsible_person_code = Column(String(64))
    assignee_user_identifier = Column(String(64))
    responsible_dept_name_snapshot = Column(String(256))
    responsible_person_name_snapshot = Column(String(128))
    assignee_name_snapshot = Column(String(128))
    action_plan = Column(Text)
    due_at = Column(Date)
    wait_kind = Column(String(32))
    wait_note = Column(Text)
    external_ticket_ref = Column(String(128))
    latest_observation_id = Column(BigInteger)
    latest_metric_value = Column(Numeric(18, 6))
    latest_result_status = Column(String(16))
    opened_control_version = Column(Integer)
    first_seen_at = Column(TIMESTAMP(timezone=True))
    last_seen_at = Column(TIMESTAMP(timezone=True))
    recurrence_of_issue_id = Column(BigInteger)
    recurrence_no = Column(Integer, nullable=False, server_default="0")
    duplicate_of_issue_id = Column(BigInteger)
    resolution_summary = Column(Text)
    resolved_at = Column(TIMESTAMP(timezone=True))
    resolved_by = Column(String(64))
    risk_reason = Column(Text)
    risk_approver = Column(String(64))
    risk_review_at = Column(Date)
    # 207 A1/B2 增量：厂商督办 + 复测链
    primary_vendor_code = Column(String(64))
    supervisor_user_identifier = Column(String(64))
    vendor_promised_at = Column(Date)
    next_followup_at = Column(Date)
    original_due_at = Column(Date)
    remediation_submitted_at = Column(TIMESTAMP(timezone=True))
    last_verification_run_id = Column(BigInteger)
    recheck_substatus = Column(String(16), server_default="none")
    recheck_note = Column(Text)
    recheck_pass_streak = Column(Integer, nullable=False, server_default="0")
    escalation_level = Column(Integer, nullable=False, server_default="0")
    false_positive_reason = Column(Text)
    suppressed_until = Column(Date)
    suppressed_control_version = Column(Integer)
    lock_version = Column(Integer, nullable=False, server_default="0")
    created_by = Column(String(64))
    updated_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    archived_at = Column(TIMESTAMP(timezone=True))


class QualityControlRevision(Base):
    """207 A1：清单版本不可变快照。

    每个 (control_id, version) 冻结当时完整口径（规则定义、检测器版本、源/对象
    绑定、阈值、窗口/空值/采样/复测口径）；运行单引用快照，编辑清单不影响在途
    任务。origin=current 表示激活/预检时从当前定义生成；backfill 表示 B4 工具
    对既有清单的当前版本补建（不伪造历史版本）。
    """

    __tablename__ = "asset_quality_control_revisions"
    __table_args__ = (
        UniqueConstraint("control_id", "version", name="uq_asset_quality_control_revisions"),
        Index("ix_asset_quality_control_revisions_control", "control_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    control_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    definition_snapshot = Column(JSONB, nullable=False)
    scope_json = Column(JSONB)
    source_code = Column(String(64))
    object_key = Column(String(512))
    detector_versions = Column(JSONB)
    origin = Column(String(16), nullable=False, server_default="current")
    created_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityRun(Base):
    """207 A2：持久运行单（数据库为事实源）。

    多检测器 = 父运行 + 每检测器一个子运行（parent_run_id）；worker 只领取子运行。
    状态：queued/waiting_window/running/succeeded/partial/failed/cancelled/blocked。
    运行成功 ≠ 数据通过：数据结论在 result_summary 与观测六态中。
    """

    __tablename__ = "asset_quality_runs"
    __table_args__ = (
        UniqueConstraint("run_code", name="uq_asset_quality_runs_code"),
        # 幂等唯一：非空 idempotency_key 上唯一；空键回退行自身 id（父子行不冲突）
        Index(
            "uq_asset_quality_runs_idem",
            "control_id",
            text("COALESCE(NULLIF(idempotency_key, ''), 'row:' || id)"),
            unique=True,
        ),
        Index("ix_asset_quality_runs_status", "status"),
        Index("ix_asset_quality_runs_control", "control_id"),
        Index("ix_asset_quality_runs_issue", "issue_id"),
        Index("ix_asset_quality_runs_parent", "parent_run_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_code = Column(String(64), nullable=False)
    control_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_control_revisions.id", ondelete="SET NULL"),
    )
    parent_run_id = Column(BigInteger, ForeignKey("asset.asset_quality_runs.id", ondelete="CASCADE"))
    issue_id = Column(BigInteger, ForeignKey("asset.asset_quality_issues.id", ondelete="SET NULL"))
    purpose = Column(String(16), nullable=False, server_default="check")
    trigger_kind = Column(String(16), nullable=False, server_default="manual")
    requested_by = Column(String(64))
    status = Column(String(16), nullable=False, server_default="queued")
    detector_id = Column(BigInteger)
    detector_kind = Column(String(16))
    detector_ref = Column(String(64))
    scope_key = Column(String(256))
    scope_json = Column(JSONB)
    system_code = Column(String(64))
    source_code = Column(String(64))
    object_key = Column(String(512))
    window_start = Column(Date)
    window_end = Column(Date)
    scheduled_for = Column(TIMESTAMP(timezone=True))
    next_window_at = Column(TIMESTAMP(timezone=True))
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    heartbeat_at = Column(TIMESTAMP(timezone=True))
    lease_owner = Column(String(64))
    lease_expires_at = Column(TIMESTAMP(timezone=True))
    attempt = Column(Integer, nullable=False, server_default="0")
    max_attempts = Column(Integer, nullable=False, server_default="3")
    idempotency_key = Column(String(128))
    result_summary = Column(JSONB)
    error_code = Column(String(32))
    error_message_sanitized = Column(Text)
    cancel_requested = Column(String(8), nullable=False, server_default="false")
    cancelled_reason = Column(Text)
    budget_json = Column(JSONB)
    lock_version = Column(Integer, nullable=False, server_default="0")
    created_by = Column(String(64))
    updated_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityVendor(Base):
    """207 B2：厂商台账（首期院内经办人代录，不做外部门户，不存凭据）。"""

    __tablename__ = "asset_quality_vendors"
    __table_args__ = (
        UniqueConstraint("vendor_code", name="uq_asset_quality_vendors_code"),
        Index("ix_asset_quality_vendors_status", "status"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    vendor_code = Column(String(64), nullable=False)
    vendor_name = Column(String(256), nullable=False)
    status = Column(String(16), nullable=False, server_default="active")
    contact_note = Column(Text)
    related_system_codes = Column(JSONB)
    remark = Column(Text)
    lock_version = Column(Integer, nullable=False, server_default="0")
    created_by = Column(String(64))
    updated_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityNotification(Base):
    """207 B2：站内待办/提醒（幂等；不外发微信/邮件/第三方工单）。"""

    __tablename__ = "asset_quality_notifications"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_asset_quality_notifications_idem"),
        Index("ix_asset_quality_notifications_recipient", "recipient"),
        Index("ix_asset_quality_notifications_issue", "issue_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    issue_id = Column(BigInteger, ForeignKey("asset.asset_quality_issues.id", ondelete="SET NULL"))
    run_id = Column(BigInteger)
    recipient = Column(String(64), nullable=False)
    notify_type = Column(String(32), nullable=False)
    idempotency_key = Column(String(160), nullable=False)
    payload = Column(JSONB)
    read_at = Column(TIMESTAMP(timezone=True))
    handled_at = Column(TIMESTAMP(timezone=True))
    handled_note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityIssueEvent(Base):
    """不可变业务时间线：合规审计仍由 GovernAuditLog 承担，本表承担业务可读时间线。"""

    __tablename__ = "asset_quality_issue_events"
    __table_args__ = (
        Index("ix_asset_quality_issue_events_issue", "issue_id"),
        Index("ix_asset_quality_issue_events_type", "event_type"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    issue_id = Column(
        BigInteger,
        ForeignKey("asset.asset_quality_issues.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(32), nullable=False)
    from_status = Column(String(16))
    to_status = Column(String(16))
    before_json = Column(JSONB)
    after_json = Column(JSONB)
    reason = Column(Text)
    observation_id = Column(BigInteger)
    actor_user_identifier = Column(String(64))
    actor_name_snapshot = Column(String(128))
    occurred_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    correlation_id = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
