"""215 E5: AI context build cache table.

Revision ID: d3e5f6a7b8c9
Revises: c0d1e2f3a4b5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d3e5f6a7b8c9"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    op.create_table(
        "asset_ai_context_cache",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column(
            "built_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.UniqueConstraint("cache_key", name="uq_asset_ai_context_cache_key"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("asset_ai_context_cache", schema=SCHEMA)
