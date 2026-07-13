"""add asset_relation_recipes table

Revision ID: s5f6a7b8c9d0
Revises: r4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "s5f6a7b8c9d0"
down_revision: Union[str, None] = "r4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_relation_recipes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("recipe_id", sa.Text(), unique=True, nullable=False, index=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("domain", sa.Text()),
        sa.Column("source_system", sa.Text()),
        sa.Column("recommended_view_name", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("business_domain", sa.Text()),
        sa.Column("primary_tables", JSONB()),
        sa.Column("joins", JSONB()),
        sa.Column("ai_readable", sa.Boolean(), server_default="true"),
        sa.Column("imported_from", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_relation_recipes", schema="asset")
