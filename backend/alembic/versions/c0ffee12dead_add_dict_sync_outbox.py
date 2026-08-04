"""add dict sync outbox events

Revision ID: c0ffee12dead
Revises: f8a9b0c1d2e3
Create Date: 2026-08-03

Hand-written migration per AGENTS.md constraint (no --autogenerate).

Adds asset_dict_sync_outbox: durable per-target dispatch queue for
cross-system dictionary writes (112 A1/A5). Written in full prior to the
worker so the table exists for lease-based replay.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c0ffee12dead"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_dict_sync_outbox",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("business_key", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("target_system", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("plan_id", sa.BigInteger),
        sa.Column("plan_hash", sa.Text),
        sa.Column("batch_id", sa.Text),
        sa.Column("payload", JSONB),
        sa.Column("status", sa.Text, server_default="pending"),
        sa.Column("attempt", sa.Integer, server_default="0"),
        sa.Column("max_attempts", sa.Integer, server_default="3"),
        sa.Column("next_retry_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("lease_expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("lease_holder", sa.Text),
        sa.Column("last_error_masked", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("business_key", name="uq_asset_dict_sync_outbox_business_key"),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_dict_sync_outbox", schema="asset")
