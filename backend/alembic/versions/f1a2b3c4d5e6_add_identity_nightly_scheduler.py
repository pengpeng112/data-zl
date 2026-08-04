"""add identity nightly scheduler tables and columns

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-08-01

Hand-written migration per AGENTS.md constraint (no --autogenerate).
Adds:
- asset_identity_scheduler_runs table
- asset_identity_circuit_breaker table
- New columns on asset_identity_sync_batches (validation_mode, scheduler_run_id,
  account_fingerprint, template_version, idempotency_key)
- New columns on asset_identity_sync_actions (account_fingerprint)
- New columns on asset_identity_managed_relations (account_fingerprint,
  composite_business_key, template_version, action_hash, idempotency_key)
- Unique constraint on managed_relations (target_system, idempotency_key)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f1a2b3c4d5e6"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New table: asset_identity_scheduler_runs
    op.create_table(
        "asset_identity_scheduler_runs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("run_id", sa.Text, nullable=False, unique=True),
        sa.Column("triggered_by", sa.Text, nullable=False),
        sa.Column("status", sa.Text, server_default="running"),
        sa.Column("lock_holder", sa.Text),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("candidates_total", sa.Integer, server_default="0"),
        sa.Column("candidates_new", sa.Integer, server_default="0"),
        sa.Column("candidates_update", sa.Integer, server_default="0"),
        sa.Column("candidates_deactivate", sa.Integer, server_default="0"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("failed_count", sa.Integer, server_default="0"),
        sa.Column("skipped_count", sa.Integer, server_default="0"),
        sa.Column("change_ratio", JSONB),
        sa.Column("circuit_breaker_triggered", sa.Boolean, server_default="false"),
        sa.Column("circuit_breaker_dimension", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("report_summary", JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    # New table: asset_identity_circuit_breaker
    op.create_table(
        "asset_identity_circuit_breaker",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("breaker_key", sa.Text, nullable=False, unique=True),
        sa.Column("consecutive_failures", sa.Integer, server_default="0"),
        sa.Column("last_failure_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_success_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("is_open", sa.Boolean, server_default="false"),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("threshold", sa.Integer, server_default="3"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    # Add columns to asset_identity_sync_batches
    op.add_column("asset_identity_sync_batches", sa.Column("validation_mode", sa.Text), schema="asset")
    op.add_column("asset_identity_sync_batches", sa.Column("scheduler_run_id", sa.Text), schema="asset")
    op.add_column("asset_identity_sync_batches", sa.Column("account_fingerprint", sa.Text), schema="asset")
    op.add_column("asset_identity_sync_batches", sa.Column("template_version", sa.Text, server_default="jhemr-login-v1"), schema="asset")
    op.add_column("asset_identity_sync_batches", sa.Column("idempotency_key", sa.Text), schema="asset")
    op.create_unique_constraint("uq_sync_batches_idempotency", "asset_identity_sync_batches", ["idempotency_key"], schema="asset")

    # Add columns to asset_identity_sync_actions
    op.add_column("asset_identity_sync_actions", sa.Column("account_fingerprint", sa.Text), schema="asset")

    # Add columns to asset_identity_managed_relations
    op.add_column("asset_identity_managed_relations", sa.Column("account_fingerprint", sa.Text), schema="asset")
    op.add_column("asset_identity_managed_relations", sa.Column("composite_business_key", sa.Text), schema="asset")
    op.add_column("asset_identity_managed_relations", sa.Column("template_version", sa.Text, server_default="jhemr-login-v1"), schema="asset")
    op.add_column("asset_identity_managed_relations", sa.Column("action_hash", sa.Text), schema="asset")
    op.add_column("asset_identity_managed_relations", sa.Column("idempotency_key", sa.Text), schema="asset")
    op.create_unique_constraint("uq_managed_relation_idempotency", "asset_identity_managed_relations", ["target_system", "idempotency_key"], schema="asset")


def downgrade() -> None:
    # Remove constraints
    op.drop_constraint("uq_managed_relation_idempotency", "asset_identity_managed_relations", schema="asset", type_="unique")
    op.drop_constraint("uq_sync_batches_idempotency", "asset_identity_sync_batches", schema="asset", type_="unique")

    # Remove columns from managed_relations
    op.drop_column("asset_identity_managed_relations", "idempotency_key", schema="asset")
    op.drop_column("asset_identity_managed_relations", "action_hash", schema="asset")
    op.drop_column("asset_identity_managed_relations", "template_version", schema="asset")
    op.drop_column("asset_identity_managed_relations", "composite_business_key", schema="asset")
    op.drop_column("asset_identity_managed_relations", "account_fingerprint", schema="asset")

    # Remove columns from actions
    op.drop_column("asset_identity_sync_actions", "account_fingerprint", schema="asset")

    # Remove columns from batches
    op.drop_column("asset_identity_sync_batches", "idempotency_key", schema="asset")
    op.drop_column("asset_identity_sync_batches", "template_version", schema="asset")
    op.drop_column("asset_identity_sync_batches", "account_fingerprint", schema="asset")
    op.drop_column("asset_identity_sync_batches", "scheduler_run_id", schema="asset")
    op.drop_column("asset_identity_sync_batches", "validation_mode", schema="asset")

    # Drop new tables
    op.drop_table("asset_identity_circuit_breaker", schema="asset")
    op.drop_table("asset_identity_scheduler_runs", schema="asset")
