"""plan144 S6: unified AI context snapshots + answer/feedback/evaluation tables.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_ai_context_snapshots",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("context_id", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default="ai-data-context/v1"),
        sa.Column("question_summary", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("manifest_hash", sa.Text(), nullable=True),
        sa.Column("object_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("relation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("query_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metric_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("product_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("context_id", name="uq_asset_ai_context_snapshots_cid"),
        schema="asset",
    )
    op.create_index(
        "ix_asset_ai_context_snapshots_generated",
        "asset_ai_context_snapshots",
        ["generated_at"],
        schema="asset",
    )


def downgrade() -> None:
    op.drop_index("ix_asset_ai_context_snapshots_generated", table_name="asset_ai_context_snapshots", schema="asset")
    op.drop_table("asset_ai_context_snapshots", schema="asset")
