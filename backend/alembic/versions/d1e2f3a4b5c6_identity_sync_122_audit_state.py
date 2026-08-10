"""plan 122 identity sync run facts, subtasks, alerts and watermarks.

Hand-written migration.  It never grants/revokes privileges and is intended
to be exercised only against an isolated APP_TEST_DB_URL.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d1e2f3a4b5c6"
down_revision = "c0ffee12dead"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asset_identity_sync_watermarks", sa.Column("candidate_create_date", sa.TIMESTAMP(timezone=True)), schema="asset")
    op.add_column("asset_identity_sync_watermarks", sa.Column("candidate_emp_no", sa.Text), schema="asset")
    op.add_column("asset_identity_sync_watermarks", sa.Column("candidate_run_id", sa.Text), schema="asset")
    op.add_column("asset_identity_sync_watermarks", sa.Column("safe_lookback_hours", sa.Integer, server_default="24"), schema="asset")
    op.add_column("asset_identity_sync_watermarks", sa.Column("watermark_status", sa.Text, server_default="committed"), schema="asset")

    for name, typ in (
        ("subtask_code", sa.Text),
        ("reason_code", sa.Text),
        ("error_class", sa.Text),
        ("error_code_masked", sa.Text),
    ):
        op.add_column("asset_identity_sync_actions", sa.Column(name, typ), schema="asset")

    for name, typ in (
        ("provider_code", sa.Text),
        ("provider_config_fingerprint", sa.Text),
        ("provider_heartbeat_at", sa.TIMESTAMP(timezone=True)),
        ("candidate_watermark", JSONB),
        ("committed_watermark", JSONB),
        ("watermark_advanced", sa.Boolean, ),
        ("last_error_class", sa.Text),
        ("duration_ms", sa.Integer),
    ):
        op.add_column("asset_identity_scheduler_runs", sa.Column(name, typ, server_default="false" if name == "watermark_advanced" else None), schema="asset")

    op.create_table(
        "asset_identity_sync_subtasks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("run_id", sa.Text, nullable=False),
        sa.Column("subtask_code", sa.Text, nullable=False),
        sa.Column("target_system", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("planned_count", sa.Integer, server_default="0"),
        sa.Column("succeeded_count", sa.Integer, server_default="0"),
        sa.Column("skipped_count", sa.Integer, server_default="0"),
        sa.Column("failed_count", sa.Integer, server_default="0"),
        sa.Column("error_classes", JSONB),
        sa.Column("report_summary", JSONB),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "subtask_code", name="uq_identity_sync_subtask_run_code"),
        schema="asset",
    )
    op.create_index("ix_identity_sync_subtask_run", "asset_identity_sync_subtasks", ["run_id"], schema="asset")

    op.create_table(
        "asset_identity_sync_alerts",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("run_id", sa.Text),
        sa.Column("alert_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False, server_default="warning"),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("error_class", sa.Text),
        sa.Column("occurrence_count", sa.Integer, server_default="1"),
        sa.Column("detail", JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        schema="asset",
    )
    op.create_index("ix_identity_sync_alert_created", "asset_identity_sync_alerts", ["created_at"], schema="asset")
    op.create_index("ix_identity_sync_alert_status", "asset_identity_sync_alerts", ["status"], schema="asset")


def downgrade() -> None:
    op.drop_index("ix_identity_sync_alert_status", table_name="asset_identity_sync_alerts", schema="asset")
    op.drop_index("ix_identity_sync_alert_created", table_name="asset_identity_sync_alerts", schema="asset")
    op.drop_table("asset_identity_sync_alerts", schema="asset")
    op.drop_index("ix_identity_sync_subtask_run", table_name="asset_identity_sync_subtasks", schema="asset")
    op.drop_table("asset_identity_sync_subtasks", schema="asset")

    for name in ("duration_ms", "last_error_class", "watermark_advanced", "committed_watermark", "candidate_watermark", "provider_heartbeat_at", "provider_config_fingerprint", "provider_code"):
        op.drop_column("asset_identity_scheduler_runs", name, schema="asset")
    for name in ("error_code_masked", "error_class", "reason_code", "subtask_code"):
        op.drop_column("asset_identity_sync_actions", name, schema="asset")
    for name in ("watermark_status", "safe_lookback_hours", "candidate_run_id", "candidate_emp_no", "candidate_create_date"):
        op.drop_column("asset_identity_sync_watermarks", name, schema="asset")
