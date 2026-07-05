"""add_metadata_column_snapshots_and_change_events

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-04 19:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    s = "asset"

    op.create_table(
        "asset_metadata_column_snapshots",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("namespace_name", sa.Text()),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("column_name", sa.Text(), nullable=False),
        sa.Column("data_type", sa.Text()),
        sa.Column("length", sa.Integer()),
        sa.Column("nullable", sa.Text()),
        sa.Column("column_default", sa.Text()),
        sa.Column("comment", sa.Text()),
        sa.Column("is_primary_key", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "system_code", "source_code", "namespace_name", "table_name", "column_name"),
        schema=s,
    )

    op.create_table(
        "asset_metadata_change_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot_id_from", sa.BigInteger()),
        sa.Column("snapshot_id_to", sa.BigInteger(), nullable=False),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("namespace_name", sa.Text()),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("column_name", sa.Text()),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("before_value", postgresql.JSONB()),
        sa.Column("after_value", postgresql.JSONB()),
        sa.Column("severity", sa.Text(), server_default="info"),
        sa.Column("status", sa.Text(), server_default="open"),
        sa.Column("assigned_to", sa.Text()),
        sa.Column("reviewed_by", sa.Text()),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )


def downgrade() -> None:
    s = "asset"
    op.drop_table("asset_metadata_change_events", schema=s)
    op.drop_table("asset_metadata_column_snapshots", schema=s)
