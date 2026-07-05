"""add_ops_tool_tables

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-04 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    s = "asset"

    op.create_table(
        "asset_ops_tool_templates",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tool_code", sa.Text(), unique=True, nullable=False),
        sa.Column("tool_name_cn", sa.Text(), nullable=False),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("tool_type", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), server_default="medium"),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False),
        sa.Column("execution_mode", sa.Text(), nullable=False),
        sa.Column("sql_or_endpoint_ref", sa.Text()),
        sa.Column("require_approval", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("require_second_confirm", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("description_cn", sa.Text()),
        sa.Column("rollback_note_cn", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )

    op.create_table(
        "asset_ops_tool_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tool_code", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text()),
        sa.Column("approved_by", sa.Text()),
        sa.Column("approval_status", sa.Text(), server_default="draft"),
        sa.Column("input_params_masked", postgresql.JSONB()),
        sa.Column("execution_summary", sa.Text()),
        sa.Column("result_ref", sa.Text()),
        sa.Column("affected_count", sa.Integer()),
        sa.Column("risk_scan", postgresql.JSONB()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )


def downgrade() -> None:
    s = "asset"
    op.drop_table("asset_ops_tool_runs", schema=s)
    op.drop_table("asset_ops_tool_templates", schema=s)
