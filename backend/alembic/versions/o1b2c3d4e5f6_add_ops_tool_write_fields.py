"""add ops tool write fields

Revision ID: o1b2c3d4e5f6
Revises: n0a1b2c3d4e5
Create Date: 2026-07-08 02:30:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "o1b2c3d4e5f6"
down_revision: Union[str, None] = "n0a1b2c3d4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("asset_ops_tool_templates", sa.Column("allowed_tables", postgresql.JSONB()), schema="asset")
    op.add_column("asset_ops_tool_templates", sa.Column("allowed_operations", postgresql.JSONB()), schema="asset")
    op.add_column("asset_ops_tool_templates", sa.Column("require_audit", sa.Boolean(), server_default=sa.text("true")), schema="asset")
    op.add_column("asset_ops_tool_templates", sa.Column("dry_run_sql", sa.Text()), schema="asset")


def downgrade() -> None:
    op.drop_column("asset_ops_tool_templates", "dry_run_sql", schema="asset")
    op.drop_column("asset_ops_tool_templates", "require_audit", schema="asset")
    op.drop_column("asset_ops_tool_templates", "allowed_operations", schema="asset")
    op.drop_column("asset_ops_tool_templates", "allowed_tables", schema="asset")