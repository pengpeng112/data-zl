"""174 S1: 数据质量主动治理台账五表 + 序列 + 部分唯一索引 + 权限种子。

手写迁移（禁 autogenerate）。表（174 §5 定稿）：
  asset_quality_controls           质控清单（control_code 唯一 + version 版本化）
  asset_quality_control_detectors  检测来源绑定（唯一 control+kind+ref+version）
  asset_quality_observations       不可变观测（幂等键 control+coalesce(detector,0)+run_key+scope）
  asset_quality_issues             整改台账（issue_code 唯一；活动问题部分唯一索引）
  asset_quality_issue_events       不可变业务时间线
  序列 asset_quality_issue_code_seq  issue_code 并发安全生成器（禁止 MAX(id)+1）

权限码（174 §7）：quality.issue.* 8 码 + quality.control.* 3 码 + quality.observation.read。
迁移种子沿用 149/165 先例（ON CONFLICT DO NOTHING）；permissions.py 静态目录同步维护。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d5e6f7a8b9c0"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

SCHEMA = "asset"

_PERMISSION_RESOURCES = [
    ("quality.issue.read", "质量问题查看（本人/本科室）", "quality", "read"),
    ("quality.issue.read_all", "质量问题查看（全院）", "quality", "read"),
    ("quality.issue.create", "质量问题手工登记", "quality", "create"),
    ("quality.issue.assign", "质量问题分派", "quality", "assign"),
    ("quality.issue.handle", "质量问题处理", "quality", "handle"),
    ("quality.issue.verify", "质量问题复测验证", "quality", "verify"),
    ("quality.issue.accept_risk", "质量问题风险接受", "quality", "accept_risk"),
    ("quality.issue.export", "质量问题导出", "quality", "export"),
    ("quality.control.read", "质控清单查看", "quality", "read"),
    ("quality.control.manage", "质控清单管理", "quality", "manage"),
    ("quality.control.run", "质控执行", "quality", "run"),
    ("quality.observation.read", "质量观测查看", "quality", "read"),
]

# 角色授予矩阵（174 §7）：质量线全量；查看类角色只读；platform_admin 走 require_permission
# 的 platform_admin 直通，无需显式授予（165 迁移先例同样保留 platform_admin 行以对齐
# permissions.py 静态矩阵，这里同样授予，幂等无害）。
_ROLE_GRANTS = {
    "platform_admin": [code for code, *_ in _PERMISSION_RESOURCES],
    "quality_admin": [code for code, *_ in _PERMISSION_RESOURCES],
    "asset_viewer": ["quality.issue.read", "quality.control.read", "quality.observation.read"],
    "ai_user": ["quality.issue.read", "quality.control.read", "quality.observation.read"],
}

_ISSUE_ACTIVE_WHERE = (
    "status NOT IN ('resolved','accepted_risk','false_positive','duplicate','cancelled') "
    "AND control_id IS NOT NULL AND archived_at IS NULL"
)


def upgrade() -> None:
    op.create_table(
        "asset_quality_controls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("control_code", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("lifecycle_status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("dimension", sa.String(32)),
        sa.Column("category", sa.String(16)),
        sa.Column("primary_system_code", sa.String(64)),
        sa.Column("related_system_codes", JSONB()),
        sa.Column("object_key", sa.String(512)),
        sa.Column("object_name_snapshot", sa.String(512)),
        sa.Column("metric_name", sa.String(128)),
        sa.Column("metric_unit", sa.String(32)),
        sa.Column("comparator", sa.String(8)),
        sa.Column("threshold_value", sa.Numeric(18, 6)),
        sa.Column("no_data_policy", sa.String(8), nullable=False, server_default="blocked"),
        sa.Column("default_severity", sa.String(8), server_default="medium"),
        sa.Column("default_priority", sa.String(2), server_default="P3"),
        sa.Column("default_dept_code", sa.String(64)),
        sa.Column("default_person_code", sa.String(64)),
        sa.Column("schedule_expr", sa.String(64)),
        sa.Column("timezone", sa.String(64)),
        sa.Column("verification_policy", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("required_pass_count", sa.Integer(), server_default="1"),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "lifecycle_status IN ('draft','active','blocked','deprecated')",
            name="ck_asset_quality_controls_lifecycle",
        ),
        sa.CheckConstraint("version > 0", name="ck_asset_quality_controls_version"),
        sa.CheckConstraint(
            "no_data_policy IN ('pass','fail','blocked')",
            name="ck_asset_quality_controls_no_data_policy",
        ),
        sa.CheckConstraint(
            "comparator IS NULL OR comparator IN ('gt','gte','lt','lte','eq')",
            name="ck_asset_quality_controls_comparator",
        ),
        sa.UniqueConstraint("control_code", name="uq_asset_quality_controls_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_controls_status", "asset_quality_controls", ["lifecycle_status"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_controls_system", "asset_quality_controls", ["primary_system_code"], schema=SCHEMA
    )

    op.create_table(
        "asset_quality_control_detectors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "control_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("detector_kind", sa.String(16), nullable=False),
        sa.Column("detector_ref", sa.String(64), nullable=False),
        sa.Column("detector_version", sa.String(32), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("scope_mapping", JSONB()),
        sa.Column("result_mapping", JSONB()),
        sa.Column("last_bound_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "detector_kind IN ('probe_template','quality_rule','manual','external')",
            name="ck_asset_quality_detectors_kind",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','blocked','disabled')",
            name="ck_asset_quality_detectors_status",
        ),
        sa.UniqueConstraint(
            "control_id", "detector_kind", "detector_ref", "detector_version",
            name="uq_asset_quality_control_detectors_binding",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_detectors_status", "asset_quality_control_detectors", ["status"], schema=SCHEMA
    )

    # 先建 controls/detectors；issues 被 observations 以 FK 引用，必须在 observations 之前建
    op.create_table(
        "asset_quality_issues",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("issue_code", sa.String(32), nullable=False),
        sa.Column(
            "control_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_controls.id", ondelete="SET NULL"),
        ),
        sa.Column("issue_type", sa.String(16), nullable=False, server_default="data_defect"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("primary_system_code", sa.String(64)),
        sa.Column("related_system_codes", JSONB()),
        sa.Column("object_key", sa.String(512)),
        sa.Column("object_name_snapshot", sa.String(512)),
        sa.Column("scope_key", sa.String(256)),
        sa.Column("severity", sa.String(8)),
        sa.Column("priority", sa.String(2)),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("responsible_dept_code", sa.String(64)),
        sa.Column("responsible_person_code", sa.String(64)),
        sa.Column("assignee_user_identifier", sa.String(64)),
        sa.Column("responsible_dept_name_snapshot", sa.String(256)),
        sa.Column("responsible_person_name_snapshot", sa.String(128)),
        sa.Column("assignee_name_snapshot", sa.String(128)),
        sa.Column("action_plan", sa.Text()),
        sa.Column("due_at", sa.Date()),
        sa.Column("wait_kind", sa.String(32)),
        sa.Column("wait_note", sa.Text()),
        sa.Column("external_ticket_ref", sa.String(128)),
        sa.Column("latest_observation_id", sa.BigInteger()),
        sa.Column("latest_metric_value", sa.Numeric(18, 6)),
        sa.Column("latest_result_status", sa.String(16)),
        sa.Column("opened_control_version", sa.Integer()),
        sa.Column("first_seen_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("recurrence_of_issue_id", sa.BigInteger()),
        sa.Column("recurrence_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_of_issue_id", sa.BigInteger()),
        sa.Column("resolution_summary", sa.Text()),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("resolved_by", sa.String(64)),
        sa.Column("risk_reason", sa.Text()),
        sa.Column("risk_approver", sa.String(64)),
        sa.Column("risk_review_at", sa.Date()),
        sa.Column("false_positive_reason", sa.Text()),
        sa.Column("suppressed_until", sa.Date()),
        sa.Column("suppressed_control_version", sa.Integer()),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('new','acknowledged','assigned','in_progress','waiting_external',"
            "'waiting_verify','resolved','accepted_risk','false_positive','duplicate','cancelled')",
            name="ck_asset_quality_issues_status",
        ),
        sa.CheckConstraint(
            "issue_type IN ('data_defect','monitoring_gap','manual')",
            name="ck_asset_quality_issues_type",
        ),
        sa.CheckConstraint("lock_version >= 0", name="ck_asset_quality_issues_lock"),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('critical','high','medium','low','info')",
            name="ck_asset_quality_issues_severity",
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority IN ('P1','P2','P3','P4')",
            name="ck_asset_quality_issues_priority",
        ),
        sa.UniqueConstraint("issue_code", name="uq_asset_quality_issues_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_issues_status", "asset_quality_issues", ["status"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_issues_control", "asset_quality_issues", ["control_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_issues_scope", "asset_quality_issues", ["control_id", "scope_key"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_issues_dept", "asset_quality_issues", ["responsible_dept_code"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_issues_assignee", "asset_quality_issues", ["assignee_user_identifier"], schema=SCHEMA
    )
    op.create_index("ix_asset_quality_issues_due", "asset_quality_issues", ["due_at"], schema=SCHEMA)
    # 部分唯一索引：同一 control+scope 只允许一条非终态活动问题（174 §4.3，数据库层兜底）
    op.create_index(
        "uq_asset_quality_issues_active",
        "asset_quality_issues",
        ["control_id", "scope_key"],
        unique=True,
        postgresql_where=sa.text(_ISSUE_ACTIVE_WHERE),
        schema=SCHEMA,
    )

    op.create_table(
        "asset_quality_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "control_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "detector_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_control_detectors.id", ondelete="CASCADE"),
        ),
        sa.Column("control_version", sa.Integer(), nullable=False),
        sa.Column(
            "issue_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_issues.id", ondelete="SET NULL"),
        ),
        sa.Column("run_key", sa.String(128), nullable=False),
        sa.Column("scope_key", sa.String(256), nullable=False),
        sa.Column("window_start", sa.Date()),
        sa.Column("window_end", sa.Date()),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("result_status", sa.String(16), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6)),
        sa.Column("metric_unit", sa.String(32)),
        sa.Column("threshold_snapshot", JSONB()),
        sa.Column("control_definition_snapshot", JSONB()),
        sa.Column("numerator", sa.Numeric(18, 6)),
        sa.Column("denominator", sa.Numeric(18, 6)),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_record_ref", sa.String(128)),
        sa.Column("evidence_digest", sa.String(128)),
        sa.Column("evidence_ref", sa.String(512)),
        sa.Column("historical_precision", sa.String(16), nullable=False, server_default="exact"),
        sa.Column("error_code", sa.String(32)),
        sa.Column("error_message_sanitized", sa.Text()),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "result_status IN ('pass','fail','error','blocked','skipped','no_data')",
            name="ck_asset_quality_observations_result",
        ),
        sa.CheckConstraint(
            "source_kind IN ('probe_finding','probe_run','quality_finding','manual','external')",
            name="ck_asset_quality_observations_source",
        ),
        sa.CheckConstraint(
            "historical_precision IN ('exact','latest_snapshot','summary_backfill')",
            name="ck_asset_quality_observations_precision",
        ),
        schema=SCHEMA,
    )
    # 幂等唯一键：COALESCE 让 manual 来源（detector_id NULL）同样参与唯一判定
    op.create_index(
        "uq_asset_quality_observations_idem",
        "asset_quality_observations",
        ["control_id", sa.text("COALESCE(detector_id, 0)"), "run_key", "scope_key"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_observations_control", "asset_quality_observations", ["control_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_observations_issue", "asset_quality_observations", ["issue_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_observations_result", "asset_quality_observations", ["result_status"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_observations_window",
        "asset_quality_observations",
        ["window_start", "window_end"],
        schema=SCHEMA,
    )

    op.create_table(
        "asset_quality_issue_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "issue_id",
            sa.BigInteger(),
            sa.ForeignKey("asset.asset_quality_issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(16)),
        sa.Column("to_status", sa.String(16)),
        sa.Column("before_json", JSONB()),
        sa.Column("after_json", JSONB()),
        sa.Column("reason", sa.Text()),
        sa.Column("observation_id", sa.BigInteger()),
        sa.Column("actor_user_identifier", sa.String(64)),
        sa.Column("actor_name_snapshot", sa.String(128)),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "event_type IN ('created','acknowledged','assigned','status_changed',"
            "'action_plan_updated','fields_updated','comment_added','observation_linked',"
            "'verification_requested','verification_passed','verification_failed',"
            "'reopened','resolved','risk_accepted','suppression_set','duplicate_marked')",
            name="ck_asset_quality_issue_events_type",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_quality_issue_events_issue", "asset_quality_issue_events", ["issue_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_quality_issue_events_type", "asset_quality_issue_events", ["event_type"], schema=SCHEMA
    )

    # issue_code 并发安全生成器（174 §5.4：禁止 MAX(id)+1）
    op.execute("CREATE SEQUENCE asset.asset_quality_issue_code_seq START 1")

    # --- 权限码种子（幂等，149/165 先例） ---
    for code, name_cn, module, action in _PERMISSION_RESOURCES:
        op.execute(
            sa.text(
                "INSERT INTO asset.asset_permission_resources "
                "(resource_code, resource_name_cn, module_code, action_code, enabled, sort_order) "
                "VALUES (:code, :name, :module, :action, true, 920) "
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
    # 权限种子回收（与 upgrade 对称；不触碰其他角色的自定义授权）
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

    op.execute("DROP SEQUENCE IF EXISTS asset.asset_quality_issue_code_seq")
    op.drop_index(
        "ix_asset_quality_issue_events_type", table_name="asset_quality_issue_events", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_quality_issue_events_issue", table_name="asset_quality_issue_events", schema=SCHEMA
    )
    op.drop_table("asset_quality_issue_events", schema=SCHEMA)
    op.drop_index(
        "ix_asset_quality_observations_window", table_name="asset_quality_observations", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_quality_observations_result", table_name="asset_quality_observations", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_quality_observations_issue", table_name="asset_quality_observations", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_quality_observations_control", table_name="asset_quality_observations", schema=SCHEMA
    )
    op.drop_index(
        "uq_asset_quality_observations_idem", table_name="asset_quality_observations", schema=SCHEMA
    )
    op.drop_table("asset_quality_observations", schema=SCHEMA)
    op.drop_index("uq_asset_quality_issues_active", table_name="asset_quality_issues", schema=SCHEMA)
    op.drop_index("ix_asset_quality_issues_due", table_name="asset_quality_issues", schema=SCHEMA)
    op.drop_index(
        "ix_asset_quality_issues_assignee", table_name="asset_quality_issues", schema=SCHEMA
    )
    op.drop_index("ix_asset_quality_issues_dept", table_name="asset_quality_issues", schema=SCHEMA)
    op.drop_index("ix_asset_quality_issues_scope", table_name="asset_quality_issues", schema=SCHEMA)
    op.drop_index("ix_asset_quality_issues_control", table_name="asset_quality_issues", schema=SCHEMA)
    op.drop_index("ix_asset_quality_issues_status", table_name="asset_quality_issues", schema=SCHEMA)
    op.drop_table("asset_quality_issues", schema=SCHEMA)
    op.drop_index(
        "ix_asset_quality_detectors_status", table_name="asset_quality_control_detectors", schema=SCHEMA
    )
    op.drop_table("asset_quality_control_detectors", schema=SCHEMA)
    op.drop_index(
        "ix_asset_quality_controls_system", table_name="asset_quality_controls", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_quality_controls_status", table_name="asset_quality_controls", schema=SCHEMA
    )
    op.drop_table("asset_quality_controls", schema=SCHEMA)
