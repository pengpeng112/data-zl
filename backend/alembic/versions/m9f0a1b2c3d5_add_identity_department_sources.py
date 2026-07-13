"""add_identity_department_sources

Revision ID: m9f0a1b2c3d5
Revises: l9e0f1a2b3c4
Create Date: 2026-07-07 19:30:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "m9f0a1b2c3d5"
down_revision: Union[str, None] = "l9e0f1a2b3c4"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "asset_identity_department_sources",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("dept_code", sa.Text()),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("source_table", sa.Text()),
        sa.Column("source_dept_id", sa.Text(), nullable=False),
        sa.Column("source_dept_name", sa.Text()),
        sa.Column("source_parent_dept_code", sa.Text()),
        sa.Column("source_dept_type", sa.Text()),
        sa.Column("source_status", sa.Text()),
        sa.Column("match_status", sa.Text(), server_default="unmatched"),
        sa.Column("raw_data", postgresql.JSONB()),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_system", "source_table", "source_dept_id"),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_identity_department_sources", schema="asset")
