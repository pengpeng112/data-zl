"""R189-T1 E08: reporting pipeline control-state tables (candidates verified on
isolated test DB).

Nine additive tables in asset schema, asset_reporting_ prefix. No changes to
existing tables. See backend/app/models/asset_reporting.py for column semantics.

Revision ID: e3f4a5b6c7d8
Revises: d3e5f6a7b8c9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d3e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    op.create_table(
        "asset_reporting_task_configs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("config_version", sa.String(32), nullable=False,
                  server_default="v0-seed"),
        sa.Column("spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("definition_fingerprint", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("canonical_table", name="uq_asset_reporting_task_table"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_task_enabled", "asset_reporting_task_configs",
        ["enabled"], schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_batches",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("business_day", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False, server_default="T1"),
        sa.Column("state", sa.String(24), nullable=False, server_default="PLANNED"),
        sa.Column("feedback_state", sa.String(24), nullable=False,
                  server_default="NOT_SUBMITTED"),
        sa.Column("state_history", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("selected_attempt_id", sa.Text(), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("batch_id", name="uq_asset_reporting_batch_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_batch_task_day", "asset_reporting_batches",
        ["canonical_table", "business_day"], schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_batch_state", "asset_reporting_batches",
        ["state"], schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_batch_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("engine", sa.String(16), nullable=True),
        sa.Column("pagination_complete", sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("manifest_json", postgresql.JSONB(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("batch_id", "attempt_id", name="uq_asset_reporting_attempt"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_attempt_batch", "asset_reporting_batch_attempts",
        ["batch_id"], schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_watermarks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("capture_h", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("apply_cursor", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivery_cursor", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("canonical_table", name="uq_asset_reporting_wm_table"),
        schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_gap_ledger",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_fingerprint", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("error_class", sa.String(64), nullable=True),
        sa.Column("state", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("manual_condition", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("close_evidence", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_gap_task_state", "asset_reporting_gap_ledger",
        ["canonical_table", "state"], schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_month_coverage",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("business_month", sa.String(7), nullable=False),
        sa.Column("route_or_origin", sa.Text(), nullable=False),
        sa.Column("last_complete_snapshot_cutoff", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_reconciled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cycle_days", sa.Integer(), nullable=True),
        sa.Column("next_due", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pending_slices", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_slices", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unresolved_quality", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "canonical_table", "business_month", "route_or_origin",
            name="uq_asset_reporting_month_cover",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_month_next_due", "asset_reporting_month_coverage",
        ["next_due"], schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_leases",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("holder", sa.Text(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("resource", name="uq_asset_reporting_lease_resource"),
        schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_alert_incidents",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("incident_id", sa.Text(), nullable=False, unique=True),
        sa.Column("incident_key", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_tables", postgresql.JSONB(), nullable=True),
        sa.Column("last_event_source_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("incident_key", name="uq_asset_reporting_incident_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_incident_state", "asset_reporting_alert_incidents",
        ["state"], schema=SCHEMA,
    )

    op.create_table(
        "asset_reporting_alert_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_event_id", sa.Text(), nullable=False),
        sa.Column("incident_id", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_kind", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("immutable_body", sa.LargeBinary(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("secret_ref", sa.Text(), nullable=True),
        sa.Column("acceptance_state", sa.String(32), nullable=False,
                  server_default="PENDING"),
        sa.Column("delivery_state", sa.String(32), nullable=False,
                  server_default="NOT_SENT"),
        sa.Column("relay_event_id", sa.Text(), nullable=True),
        sa.Column("target_status_summary", postgresql.JSONB(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error_class", sa.String(64), nullable=True),
        sa.Column("last_http_code", sa.Integer(), nullable=True),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column("poll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("needs_attention_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("source_event_id", name="uq_asset_reporting_outbox_sid"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_outbox_delivery", "asset_reporting_alert_outbox",
        ["delivery_state", "next_attempt_at"], schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_outbox_incident", "asset_reporting_alert_outbox",
        ["incident_id"], schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("asset_reporting_alert_outbox", schema=SCHEMA)
    op.drop_table("asset_reporting_alert_incidents", schema=SCHEMA)
    op.drop_table("asset_reporting_leases", schema=SCHEMA)
    op.drop_table("asset_reporting_month_coverage", schema=SCHEMA)
    op.drop_table("asset_reporting_gap_ledger", schema=SCHEMA)
    op.drop_table("asset_reporting_watermarks", schema=SCHEMA)
    op.drop_table("asset_reporting_batch_attempts", schema=SCHEMA)
    op.drop_table("asset_reporting_batches", schema=SCHEMA)
    op.drop_table("asset_reporting_task_configs", schema=SCHEMA)
