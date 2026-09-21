"""Identity sync models for HIS -> CDMS / JHEMR nightly synchronization.

All tables use asset schema with asset_identity_* prefix.
Expanded per plan 107: nightly scheduler, HMAC fingerprint, circuit breaker,
dual-target validation, managed relation idempotency.
"""

from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP, UniqueConstraint, Index

# SQLite requires INTEGER for autoincrement PKs
PortableBigInt = BigInteger().with_variant(Integer, "sqlite")
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Portable JSON: uses JSONB on PostgreSQL, plain JSON on SQLite
PortableJSON = JSON().with_variant(JSONB(), "postgresql")
from sqlalchemy.sql import func

from ..core.db import Base


class IdentitySyncWatermark(Base):
    """Composite watermark for incremental HIS collection."""
    __tablename__ = "asset_identity_sync_watermarks"
    __table_args__ = (
        UniqueConstraint("source_code", "watermark_key"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    source_code = Column(Text, nullable=False)
    watermark_key = Column(Text, nullable=False)
    last_create_date = Column(TIMESTAMP(timezone=True))
    last_emp_no = Column(Text)  # HMAC tie-breaker (legacy column name; never plaintext)
    last_run_at = Column(TIMESTAMP(timezone=True))
    rows_collected = Column(Integer, server_default="0")
    # 122: candidate and committed watermarks are kept separately.  The
    # committed pair is never advanced by a failed run.
    candidate_create_date = Column(TIMESTAMP(timezone=True))
    candidate_emp_no = Column(Text)  # HMAC tie-breaker (legacy column name; never plaintext)
    candidate_run_id = Column(Text)
    safe_lookback_hours = Column(Integer, server_default="24")
    watermark_status = Column(Text, server_default="committed")  # candidate | committed | stalled
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentitySyncBatch(Base):
    """One sync batch (nightly auto, validation, or manual rerun)."""
    __tablename__ = "asset_identity_sync_batches"
    __table_args__ = (
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    batch_id = Column(Text, nullable=False, unique=True)
    batch_type = Column(Text, nullable=False)  # nightly | validation | manual_rerun
    validation_mode = Column(Text)  # doctor_nurse_dual_target_v1 | NULL
    scheduler_run_id = Column(Text)  # FK to IdentitySchedulerRun.run_id
    emp_no_masked = Column(Text)
    account_fingerprint = Column(Text)  # HMAC fingerprint, not emp_no
    person_classification = Column(Text)  # doctor | nurse | pharmacist
    status = Column(Text, server_default="pending")
    # pending | collecting | preflight | planning | applying | readback | reconciling | success | failed | partial_target_success | blocked_no_candidate
    action_hash = Column(Text)
    template_version = Column(Text, server_default="jhemr-login-v1")
    idempotency_key = Column(Text, unique=True)
    cdms_status = Column(Text)  # pending | success | failed | rolled_back | skipped
    jhemr_status = Column(Text)  # pending | success | failed | rolled_back | skipped
    error_message = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentitySyncAction(Base):
    """Individual action within a sync batch."""
    __tablename__ = "asset_identity_sync_actions"
    __table_args__ = (
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    batch_id = Column(Text, nullable=False)
    action_seq = Column(Integer, nullable=False)
    target_system = Column(Text, nullable=False)  # CDMS | JHEMR
    action_type = Column(Text, nullable=False)
    target_table = Column(Text, nullable=False)
    emp_no_masked = Column(Text)
    account_fingerprint = Column(Text)
    params_summary = Column(PortableJSON)
    status = Column(Text, server_default="planned")  # planned | executed | skipped | failed | rolled_back
    subtask_code = Column(Text)  # main_account_sync | jhemr_signature_sync | jhemr_education_title_sync
    reason_code = Column(Text)
    error_class = Column(Text)
    error_code_masked = Column(Text)
    rows_affected = Column(Integer)
    error_message = Column(Text)
    executed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityRoleMapping(Base):
    """Configured role mappings for target systems (not guessed at runtime)."""
    __tablename__ = "asset_identity_role_mappings"
    __table_args__ = (
        UniqueConstraint("target_system", "person_classification", "mapping_key"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    target_system = Column(Text, nullable=False)  # CDMS | JHEMR
    person_classification = Column(Text, nullable=False)  # doctor | nurse | pharmacist
    mapping_key = Column(Text, nullable=False)
    role_code = Column(Text)
    role_name_cn = Column(Text)
    extra_config = Column(PortableJSON)
    is_active = Column(Boolean, server_default="true")
    rule_version = Column(Text, server_default="v1")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityProtectedAccount(Base):
    """Accounts that must never be modified by sync (manual/admin accounts)."""
    __tablename__ = "asset_identity_protected_accounts"
    __table_args__ = (
        UniqueConstraint("target_system", "account_id"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    target_system = Column(Text, nullable=False)
    account_id = Column(Text, nullable=False)
    reason = Column(Text)
    protected_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityManagedRelation(Base):
    """Relations created by sync task; only these can be rolled back.

    Expanded per plan 107 §10: stores target system, irreversible account
    fingerprint, composite business key, creation batch, template version,
    action hash, status, and idempotency unique key.
    """
    __tablename__ = "asset_identity_managed_relations"
    __table_args__ = (
        UniqueConstraint("target_system", "idempotency_key", name="uq_managed_relation_idempotency"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    batch_id = Column(Text, nullable=False)
    target_system = Column(Text, nullable=False)
    account_fingerprint = Column(Text, nullable=False)  # HMAC, not emp_no
    composite_business_key = Column(Text)  # e.g. "CDMS:FLOGINNAME=xxx" or "JHEMR:db_user+hospital_no"
    emp_no_masked = Column(Text)
    relation_type = Column(Text, nullable=False)  # account | role | dept | auth | control_mode | sublogin | subsign | password
    target_table = Column(Text, nullable=False)
    target_key = Column(Text)
    relation_data = Column(PortableJSON)
    template_version = Column(Text, server_default="jhemr-login-v1")
    action_hash = Column(Text)
    status = Column(Text, server_default="active")  # active | compensated | pending_reconcile
    idempotency_key = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    compensated_at = Column(TIMESTAMP(timezone=True))


class IdentitySyncCompensation(Base):
    """Compensation queue for partial-success recovery."""
    __tablename__ = "asset_identity_sync_compensations"
    __table_args__ = (
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    batch_id = Column(Text, nullable=False)
    target_system = Column(Text, nullable=False)
    compensation_type = Column(Text, nullable=False)  # lock_account | remove_managed_relation | reconcile
    target_table = Column(Text)
    target_key = Column(Text)
    status = Column(Text, server_default="pending")  # pending | executed | failed | skipped
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    executed_at = Column(TIMESTAMP(timezone=True))


class IdentityClassificationRecord(Base):
    """Persisted classification result for each person."""
    __tablename__ = "asset_identity_classifications"
    __table_args__ = (
        UniqueConstraint("emp_no", "rule_version"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    emp_no = Column(Text, nullable=False)
    emp_no_masked = Column(Text)
    raw_job = Column(Text)
    raw_title = Column(Text)
    classification = Column(Text, nullable=False)
    matched_rule = Column(Text)
    rule_version = Column(Text, nullable=False, server_default="v1")
    conflict_detail = Column(PortableJSON)
    source_create_date = Column(TIMESTAMP(timezone=True))
    classified_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityDistributedLock(Base):
    """Database-level distributed lock for sync mutual exclusion."""
    __tablename__ = "asset_identity_sync_locks"
    __table_args__ = (
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    lock_key = Column(Text, nullable=False, unique=True)
    lock_holder = Column(Text)
    acquired_at = Column(TIMESTAMP(timezone=True))
    expires_at = Column(TIMESTAMP(timezone=True))
    released_at = Column(TIMESTAMP(timezone=True))


class IdentitySchedulerRun(Base):
    """Nightly scheduler execution record with circuit breaker state."""
    __tablename__ = "asset_identity_scheduler_runs"
    __table_args__ = (
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    run_id = Column(Text, nullable=False, unique=True)
    triggered_by = Column(Text, nullable=False)  # nightly_cron | manual_rerun | validation
    status = Column(Text, server_default="running")
    # success | partial_success | failed | skipped | running | overdue | misconfigured
    lock_holder = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    candidates_total = Column(Integer, server_default="0")
    candidates_new = Column(Integer, server_default="0")
    candidates_update = Column(Integer, server_default="0")
    candidates_deactivate = Column(Integer, server_default="0")
    success_count = Column(Integer, server_default="0")
    failed_count = Column(Integer, server_default="0")
    skipped_count = Column(Integer, server_default="0")
    change_ratio = Column(PortableJSON)  # {"new_ratio": 0.1, "update_ratio": 0.05, ...}
    circuit_breaker_triggered = Column(Boolean, server_default="false")
    circuit_breaker_dimension = Column(Text)  # which threshold was hit
    error_message = Column(Text)
    report_summary = Column(PortableJSON)  # desensitized daily report
    provider_code = Column(Text)
    provider_config_fingerprint = Column(Text)
    provider_heartbeat_at = Column(TIMESTAMP(timezone=True))
    candidate_watermark = Column(PortableJSON)
    committed_watermark = Column(PortableJSON)
    watermark_advanced = Column(Boolean, server_default="false")
    last_error_class = Column(Text)
    duration_ms = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityCircuitBreaker(Base):
    """Circuit breaker state for consecutive failure tracking."""
    __tablename__ = "asset_identity_circuit_breaker"
    __table_args__ = (
        UniqueConstraint("breaker_key"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    breaker_key = Column(Text, nullable=False)  # e.g. "nightly_cdms", "nightly_jhemr"
    consecutive_failures = Column(Integer, server_default="0")
    last_failure_at = Column(TIMESTAMP(timezone=True))
    last_success_at = Column(TIMESTAMP(timezone=True))
    is_open = Column(Boolean, server_default="false")
    opened_at = Column(TIMESTAMP(timezone=True))
    threshold = Column(Integer, server_default="3")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentitySyncSubtask(Base):
    """Durable per-run subtask facts used for status aggregation and audit."""
    __tablename__ = "asset_identity_sync_subtasks"
    __table_args__ = (
        UniqueConstraint("run_id", "subtask_code", name="uq_identity_sync_subtask_run_code"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    run_id = Column(Text, nullable=False)
    subtask_code = Column(Text, nullable=False)  # main_account_sync | jhemr_signature_sync | jhemr_education_title_sync
    target_system = Column(Text)
    status = Column(Text, nullable=False, server_default="running")
    planned_count = Column(Integer, server_default="0")
    succeeded_count = Column(Integer, server_default="0")
    skipped_count = Column(Integer, server_default="0")
    failed_count = Column(Integer, server_default="0")
    error_classes = Column(PortableJSON)
    report_summary = Column(PortableJSON)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentitySyncAlert(Base):
    """Queryable, redacted operational alert; no SQL parameters or identities."""
    __tablename__ = "asset_identity_sync_alerts"
    __table_args__ = (
        Index("ix_identity_sync_alert_created", "created_at"),
        Index("ix_identity_sync_alert_status", "status"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    run_id = Column(Text)
    alert_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False, server_default="warning")
    status = Column(Text, nullable=False, server_default="open")
    error_class = Column(Text)
    occurrence_count = Column(Integer, server_default="1")
    detail = Column(PortableJSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True))


class IdentityAccountStateDecision(Base):
    """186 I2: one dual-source account-state decision per person capture.

    Persists the §4.6.2 truth-table inputs/outcome so SYS_USER-only changes
    (invisible to SYS_EMPLOYEE.MODIFIEDTIME) still drive target actions.
    Employment status stays on IdentityPerson; this row is the *login
    account* state, never a resignation record.
    """
    __tablename__ = "asset_identity_account_state_decisions"
    __table_args__ = (
        UniqueConstraint("person_code", "rule_version", "evidence_fingerprint", name="uq_account_state_decision"),
        Index("ix_account_state_decision_person", "person_code", "created_at"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    person_code = Column(Text, nullable=False)
    rule_version = Column(Text, nullable=False, server_default="dual_source_v1")
    employee_state = Column(Text, nullable=False)  # enabled | disabled | unknown
    employee_state_reason = Column(Text)
    user_state = Column(Text, nullable=False)  # enabled | disabled | unknown
    user_state_reason = Column(Text)
    desired_state = Column(Text, nullable=False)  # enabled | disabled | unknown
    decision_reason = Column(Text)
    execution_allowed = Column(Boolean, nullable=False, server_default="false")
    blocked_reason = Column(Text)
    employee_evidence = Column(PortableJSON)  # allow-listed projection only
    user_evidence = Column(PortableJSON)
    evidence_fingerprint = Column(Text, nullable=False)
    transition_seq = Column(Integer, nullable=False, server_default="1")
    source_complete = Column(Boolean, nullable=False, server_default="true")
    captured_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityAccountStateAttempt(Base):
    """186 I3: one target-system enable/disable attempt with attribution.

    Idempotency identity = (fingerprint, action, transition_seq, rule_version)
    — a repeated same-direction transition replays the same row; a later
    NEW transition (enabled→disabled→enabled→disabled) gets a fresh ordinal
    and is never swallowed by the earlier one.
    """
    __tablename__ = "asset_identity_account_state_attempts"
    __table_args__ = (
        UniqueConstraint(
            "target_account_fingerprint", "action", "transition_seq", "rule_version",
            name="uq_account_state_attempt_idempotency",
        ),
        Index("ix_account_state_attempt_run", "run_id"),
        Index("ix_account_state_attempt_person", "person_code"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    run_id = Column(Text)
    batch_id = Column(Text)
    decision_id = Column(PortableBigInt)
    person_code = Column(Text, nullable=False)
    target_system = Column(Text, nullable=False)  # JHEMR | CDMS
    target_account_fingerprint = Column(Text, nullable=False)  # HMAC, never plaintext
    action = Column(Text, nullable=False)  # disable | enable
    before_state = Column(Text)
    desired_state = Column(Text, nullable=False)
    after_state = Column(Text)
    status = Column(Text, nullable=False, server_default="planned")
    # planned | executed | skipped | failed | blocked | pending_reconcile | cancelled_stale
    reason_code = Column(Text)
    error_class = Column(Text)
    error_code_masked = Column(Text)
    lock_attribution = Column(Text)  # by_this_rule | manual_or_unknown | not_applicable
    attribution_evidence = Column(PortableJSON)
    rule_version = Column(Text, nullable=False, server_default="dual_source_v1")
    transition_seq = Column(Integer, nullable=False, server_default="1")
    # 186 v1.10 P0-4/§13.3：恢复（enable）显式关联本规则前一 executed 停用
    # 动作；attribution_evidence 内保留目标 raw 时间/类型/精度。executed_at
    # 只是平台审计时间，绝不作为恢复归因依据。
    origin_disable_attempt_id = Column(PortableBigInt)
    executed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityApprovedScope(Base):
    """186 v1.10 P0-19/§13.5：冻结的批准动作范围（审批 token 不是名单）。

    scope_type=pilot 为显式试点人员；scope_type=baseline 为冻结基线类
    （成员在 freeze 时从新鲜观测交集生成，写死在 members 表，之后新增
    对象不自动混入）。status: active | closed | superseded。
    """

    __tablename__ = "asset_identity_action_scopes"
    __table_args__ = (
        UniqueConstraint("approval_ref", "action", "scope_type", name="uq_identity_scope_approval"),
        Index("ix_identity_scope_status", "status"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    scope_type = Column(Text, nullable=False)  # pilot | baseline
    approval_ref = Column(Text, nullable=False)  # e.g. 186-20260909-disable-only
    action = Column(Text, nullable=False, server_default="disable")
    scope_fingerprint = Column(Text)  # hash over frozen members (baseline)
    status = Column(Text, nullable=False, server_default="active")
    description = Column(Text)
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityApprovedScopeMember(Base):
    """Frozen member of an approved scope (person-level, never auto-extended)."""

    __tablename__ = "asset_identity_action_scope_members"
    __table_args__ = (
        UniqueConstraint("scope_id", "person_code", name="uq_identity_scope_member"),
        Index("ix_identity_scope_member_person", "person_code"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    scope_id = Column(PortableBigInt, nullable=False)
    person_code = Column(Text, nullable=False)
    frozen_reason = Column(Text)  # decision_reason at freeze time
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityWindowBudget(Base):
    """186 v1.10 §13.5：持久调度窗口预算（试点/人工重跑/重启共享同一窗）。

    窗口身份由持久行决定，不由重启后本地日期重算；8.83 跳时不产生第二份
    额度（超过 window_hours 才允许开新窗）。
    """

    __tablename__ = "asset_identity_window_budgets"
    __table_args__ = (
        UniqueConstraint("window_key", name="uq_identity_window_key"),
        Index("ix_identity_window_open", "closed_at"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    window_key = Column(Text, nullable=False)
    approval_ref = Column(Text, nullable=False)
    limit_persons = Column(Integer, nullable=False, server_default="20")
    opened_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    closed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IdentityWindowReservation(Base):
    """One person's slot in one window; retry of the same object/transition
    never consumes an extra slot (unique per window+person)."""

    __tablename__ = "asset_identity_window_reservations"
    __table_args__ = (
        UniqueConstraint("window_id", "person_code", name="uq_identity_window_reservation"),
        Index("ix_identity_window_reservation_window", "window_id"),
        {"schema": "asset"},
    )

    id = Column(PortableBigInt, primary_key=True)
    window_id = Column(PortableBigInt, nullable=False)
    person_code = Column(Text, nullable=False)
    action = Column(Text, nullable=False, server_default="disable")
    status = Column(Text, nullable=False, server_default="reserved")  # reserved | executed | failed | released
    run_id = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
