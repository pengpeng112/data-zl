"""207 A1: 质量治理执行闭环四表 + 清单/台账增量列 + 事件类型约束扩展 + 权限种子。

手写迁移（禁 autogenerate）。新增（207 §4.1 最小扩展，不另造第二套台账）：
  asset_quality_control_revisions  清单版本不可变快照（(control_id,version) 唯一）
  asset_quality_runs               持久运行单（幂等键 coalesce 控制；父/子运行）
  asset_quality_vendors            厂商台账（首期院内代录，不存凭据）
  asset_quality_notifications      站内待办（idempotency_key 唯一，重试不重复发）
增量列：
  controls  source_code/schedule_enabled/next_run_at/last_run_at/freshness_hours/
            recheck_policy/sla_hours/execution_plan；verification_policy 扩为 String(32)
  issues    主责厂商/督办人/承诺日期/下次跟进/原截止/整改提交时间/最新复测运行/
            复测子状态/连续通过次数/升级级别
约束扩展：
  asset_quality_issue_events 的 event_type CHECK 增加 followup_added/reminded/
  recheck_passed/recheck_failed/recheck_blocked/run_linked（服务层 EVENT_TYPES 同步）
回退保护：downgrade 在新表已有业务数据时拒绝执行（207 §8.2：有数据的生产回退
采用保留表/数据的兼容方案，不做无条件删表）。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c4d5e6f7b8a9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None

SCHEMA = "asset"

_PERMISSION_RESOURCES = [
    ("quality.run.read", "质量运行查看", "quality", "read"),
    ("quality.run.manage", "质量运行管理（取消/重试）", "quality", "manage"),
    ("quality.vendor.manage", "质量厂商维护", "quality", "manage"),
    ("quality.notification.read", "站内质量待办查看", "quality", "read"),
]

# 平台管理员/质量线全量；运行与厂商管理不下放查看类角色
_ROLE_GRANTS = {
    "platform_admin": [code for code, *_ in _PERMISSION_RESOURCES],
    "quality_admin": [code for code, *_ in _PERMISSION_RESOURCES],
}

_NEW_EVENT_TYPES = (
    "created", "acknowledged", "assigned", "status_changed", "action_plan_updated",
    "fields_updated", "comment_added", "observation_linked", "verification_requested",
    "verification_passed", "verification_failed", "reopened", "resolved", "risk_accepted",
    "suppression_set", "duplicate_marked",
    "followup_added", "reminded", "recheck_passed", "recheck_failed", "recheck_blocked",
    "run_linked",
)


def _table_row_count(table: str) -> int:
    conn = op.get_bind()
    return conn.execute(sa.text(f"SELECT count(*) FROM {SCHEMA}.{table}")).scalar_one()


def upgrade() -> None:
    # ── 1. 清单版本快照 ──
    op.create_table(
        "asset_quality_control_revisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "control_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition_snapshot", JSONB(), nullable=False),
        sa.Column("scope_json", JSONB()),
        sa.Column("source_code", sa.String(64)),
        sa.Column("object_key", sa.String(512)),
        sa.Column("detector_versions", JSONB()),
        sa.Column("origin", sa.String(16), nullable=False, server_default="current"),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("version > 0", name="ck_asset_quality_control_revisions_version"),
        sa.CheckConstraint(
            "origin IN ('current','backfill')",
            name="ck_asset_quality_control_revisions_origin",
        ),
        sa.UniqueConstraint("control_id", "version", name="uq_asset_quality_control_revisions"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_control_revisions_control",
        "asset_quality_control_revisions", ["control_id"], schema=SCHEMA,
    )

    # ── 2. 持久运行单 ──
    op.create_table(
        "asset_quality_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_code", sa.String(64), nullable=False),
        sa.Column(
            "control_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "revision_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_control_revisions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "parent_run_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_runs.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "issue_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_issues.id", ondelete="SET NULL"),
        ),
        sa.Column("purpose", sa.String(16), nullable=False, server_default="check"),
        sa.Column("trigger_kind", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("requested_by", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("detector_id", sa.BigInteger()),
        sa.Column("detector_kind", sa.String(16)),
        sa.Column("detector_ref", sa.String(64)),
        sa.Column("scope_key", sa.String(256)),
        sa.Column("scope_json", JSONB()),
        sa.Column("system_code", sa.String(64)),
        sa.Column("source_code", sa.String(64)),
        sa.Column("object_key", sa.String(512)),
        sa.Column("window_start", sa.Date()),
        sa.Column("window_end", sa.Date()),
        sa.Column("scheduled_for", sa.TIMESTAMP(timezone=True)),
        sa.Column("next_window_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("heartbeat_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("lease_owner", sa.String(64)),
        sa.Column("lease_expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("result_summary", JSONB()),
        sa.Column("error_code", sa.String(32)),
        sa.Column("error_message_sanitized", sa.Text()),
        sa.Column("cancel_requested", sa.String(8), nullable=False, server_default="false"),
        sa.Column("cancelled_reason", sa.Text()),
        sa.Column("budget_json", JSONB()),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('queued','waiting_window','running','succeeded','partial',"
            "'failed','cancelled','blocked')",
            name="ck_asset_quality_runs_status",
        ),
        sa.CheckConstraint(
            "purpose IN ('check','recheck')", name="ck_asset_quality_runs_purpose",
        ),
        sa.CheckConstraint(
            "trigger_kind IN ('manual','schedule','recheck')", name="ck_asset_quality_runs_trigger",
        ),
        sa.UniqueConstraint("run_code", name="uq_asset_quality_runs_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_asset_quality_runs_idem", "asset_quality_runs",
        ["control_id", sa.text("COALESCE(NULLIF(idempotency_key, ''), 'row:' || id)")],
        unique=True, schema=SCHEMA,
    )
    for ix, cols in (
        ("ix_asset_quality_runs_status", ["status"]),
        ("ix_asset_quality_runs_control", ["control_id"]),
        ("ix_asset_quality_runs_issue", ["issue_id"]),
        ("ix_asset_quality_runs_parent", ["parent_run_id"]),
    ):
        op.create_index(ix, "asset_quality_runs", cols, schema=SCHEMA)

    # ── 3. 厂商台账 ──
    op.create_table(
        "asset_quality_vendors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("vendor_code", sa.String(64), nullable=False),
        sa.Column("vendor_name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("contact_note", sa.Text()),
        sa.Column("related_system_codes", JSONB()),
        sa.Column("remark", sa.Text()),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('active','disabled')", name="ck_asset_quality_vendors_status",
        ),
        sa.UniqueConstraint("vendor_code", name="uq_asset_quality_vendors_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_vendors_status", "asset_quality_vendors", ["status"], schema=SCHEMA,
    )

    # ── 4. 站内待办 ──
    op.create_table(
        "asset_quality_notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "issue_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_issues.id", ondelete="SET NULL"),
        ),
        sa.Column("run_id", sa.BigInteger()),
        sa.Column("recipient", sa.String(64), nullable=False),
        sa.Column("notify_type", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("payload", JSONB()),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("handled_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("handled_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("idempotency_key", name="uq_asset_quality_notifications_idem"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_notifications_recipient", "asset_quality_notifications",
        ["recipient"], schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_notifications_issue", "asset_quality_notifications",
        ["issue_id"], schema=SCHEMA,
    )

    # ── 5. 清单增量列 + verification_policy 扩长 ──
    op.alter_column(
        "asset_quality_controls", "verification_policy",
        type_=sa.String(32), existing_type=sa.String(16), existing_nullable=False,
        schema=SCHEMA,
    )
    for col, coltype in (
        ("source_code", sa.String(64)),
        ("schedule_enabled", sa.String(8)),
        ("next_run_at", sa.TIMESTAMP(timezone=True)),
        ("last_run_at", sa.TIMESTAMP(timezone=True)),
        ("freshness_hours", sa.Integer()),
        ("recheck_policy", sa.String(16)),
        ("sla_hours", sa.Integer()),
        ("execution_plan", JSONB()),
    ):
        op.add_column(
            "asset_quality_controls",
            sa.Column(col, coltype, **(
                {"server_default": "false"} if col == "schedule_enabled"
                else {"server_default": "auto"} if col == "recheck_policy"
                else {}
            )),
            schema=SCHEMA,
        )
    op.create_check_constraint(
        "ck_asset_quality_controls_recheck_policy",
        "asset_quality_controls",
        "recheck_policy IS NULL OR recheck_policy IN ('auto','manual')",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_asset_quality_controls_verification_policy",
        "asset_quality_controls",
        "verification_policy IN ('manual','auto_recheck_manual_close')",
        schema=SCHEMA,
    )

    # ── 6. 台账增量列 ──
    for col, coltype in (
        ("primary_vendor_code", sa.String(64)),
        ("supervisor_user_identifier", sa.String(64)),
        ("vendor_promised_at", sa.Date()),
        ("next_followup_at", sa.Date()),
        ("original_due_at", sa.Date()),
        ("remediation_submitted_at", sa.TIMESTAMP(timezone=True)),
        ("last_verification_run_id", sa.BigInteger()),
        ("recheck_substatus", sa.String(16)),
        ("recheck_note", sa.Text()),
        ("recheck_pass_streak", sa.Integer()),
        ("escalation_level", sa.Integer()),
    ):
        op.add_column(
            "asset_quality_issues",
            sa.Column(col, coltype, **(
                {"server_default": "none"} if col == "recheck_substatus"
                else {"server_default": "0"} if col in ("recheck_pass_streak", "escalation_level")
                else {}
            )),
            schema=SCHEMA,
        )
    op.create_check_constraint(
        "ck_asset_quality_issues_recheck_substatus",
        "asset_quality_issues",
        "recheck_substatus IN ('none','pending','passed','failed','blocked')",
        schema=SCHEMA,
    )

    # ── 7. 事件类型 CHECK 扩展（207 新增 6 类事件） ──
    op.drop_constraint(
        "ck_asset_quality_issue_events_type", "asset_quality_issue_events", schema=SCHEMA,
    )
    quoted = ",".join(f"'{t}'" for t in _NEW_EVENT_TYPES)
    op.create_check_constraint(
        "ck_asset_quality_issue_events_type",
        "asset_quality_issue_events",
        f"event_type IN ({quoted})",
        schema=SCHEMA,
    )
    # 观测历史精度枚举扩展：HTTP 外部上传标记 external_upload（F06：与可信通道区分）
    op.drop_constraint(
        "ck_asset_quality_observations_precision", "asset_quality_observations", schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_asset_quality_observations_precision",
        "asset_quality_observations",
        "historical_precision IN ('exact','latest_snapshot','summary_backfill','external_upload')",
        schema=SCHEMA,
    )

    # ── 8. 权限码种子（幂等） ──
    for code, name_cn, module, action in _PERMISSION_RESOURCES:
        op.execute(
            sa.text(
                "INSERT INTO asset.asset_permission_resources "
                "(resource_code, resource_name_cn, module_code, action_code, enabled, sort_order) "
                "VALUES (:code, :name, :module, :action, true, 925) "
                "ON CONFLICT (resource_code) DO NOTHING"
            ).bindparams(code=code, name=name_cn, module=module, action=action)
        )
    for role_code, resources in _ROLE_GRANTS.items():
        for resource in resources:
            op.execute(
                sa.text(
                    "INSERT INTO asset.asset_role_permissions (role_code, resource, action) "
                    "VALUES (:role, :resource, 'access') "
                    "ON CONFLICT (role_code, resource, action) DO NOTHING"
                ).bindparams(role=role_code, resource=resource)
            )


def downgrade() -> None:
    # 有数据即拒绝（207 §8.2：新业务数据已产生时禁止无条件 downgrade 删表）
    for table in (
        "asset_quality_notifications", "asset_quality_vendors",
        "asset_quality_runs", "asset_quality_control_revisions",
    ):
        cnt = _table_row_count(table)
        if cnt:
            raise RuntimeError(
                f"{SCHEMA}.{table} 已有 {cnt} 行业务数据，拒绝 downgrade 删表；"
                "生产回退请保留表/数据并回退代码，或先人工导出证据后再执行"
            )

    # 权限种子回收（对称；不触碰其他角色自定义授权）
    for role_code, resources in _ROLE_GRANTS.items():
        for resource in resources:
            op.execute(
                sa.text(
                    "DELETE FROM asset.asset_role_permissions "
                    "WHERE role_code = :role AND resource = :resource"
                ).bindparams(role=role_code, resource=resource)
            )
    codes = tuple(code for code, *_ in _PERMISSION_RESOURCES)
    op.execute(
        sa.text(
            "DELETE FROM asset.asset_permission_resources "
            f"WHERE resource_code IN ({','.join(':c%d' % i for i in range(len(codes)))})"
        ).bindparams(**{f"c{i}": c for i, c in enumerate(codes)})
    )

    # 事件类型 CHECK 回退为 174 原集
    op.drop_constraint(
        "ck_asset_quality_issue_events_type", "asset_quality_issue_events", schema=SCHEMA,
    )
    legacy = (
        "created","acknowledged","assigned","status_changed","action_plan_updated",
        "fields_updated","comment_added","observation_linked","verification_requested",
        "verification_passed","verification_failed","reopened","resolved","risk_accepted",
        "suppression_set","duplicate_marked",
    )
    op.create_check_constraint(
        "ck_asset_quality_issue_events_type", "asset_quality_issue_events",
        "event_type IN (" + ",".join(f"'{t}'" for t in legacy) + ")", schema=SCHEMA,
    )
    op.drop_constraint(
        "ck_asset_quality_observations_precision", "asset_quality_observations", schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_asset_quality_observations_precision", "asset_quality_observations",
        "historical_precision IN ('exact','latest_snapshot','summary_backfill')", schema=SCHEMA,
    )

    for col in (
        "primary_vendor_code", "supervisor_user_identifier", "vendor_promised_at",
        "next_followup_at", "original_due_at", "remediation_submitted_at",
        "last_verification_run_id", "recheck_substatus", "recheck_note",
        "recheck_pass_streak", "escalation_level",
    ):
        op.drop_column("asset_quality_issues", col, schema=SCHEMA)

    op.drop_constraint(
        "ck_asset_quality_controls_verification_policy", "asset_quality_controls", schema=SCHEMA,
    )
    op.drop_constraint(
        "ck_asset_quality_controls_recheck_policy", "asset_quality_controls", schema=SCHEMA,
    )
    for col in (
        "source_code", "schedule_enabled", "next_run_at", "last_run_at", "freshness_hours",
        "recheck_policy", "sla_hours", "execution_plan",
    ):
        op.drop_column("asset_quality_controls", col, schema=SCHEMA)
    op.alter_column(
        "asset_quality_controls", "verification_policy",
        type_=sa.String(16), existing_type=sa.String(32), existing_nullable=False,
        schema=SCHEMA,
    )

    op.drop_table("asset_quality_notifications", schema=SCHEMA)
    op.drop_table("asset_quality_vendors", schema=SCHEMA)
    op.drop_table("asset_quality_runs", schema=SCHEMA)
    op.drop_table("asset_quality_control_revisions", schema=SCHEMA)
