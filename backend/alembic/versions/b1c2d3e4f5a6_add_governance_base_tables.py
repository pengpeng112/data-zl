"""add_governance_base_tables

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    asset_schema = "asset"

    op.create_table(
        "asset_roles",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("role_code", sa.Text(), unique=True, nullable=False),
        sa.Column("role_name_cn", sa.Text(), nullable=False),
        sa.Column("role_type", sa.Text(), server_default="platform"),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=asset_schema,
    )

    op.create_table(
        "asset_user_roles",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_identifier", sa.Text(), nullable=False),
        sa.Column("role_code", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.Text()),
        sa.Column("granted_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        schema=asset_schema,
    )

    op.create_table(
        "asset_role_permissions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("role_code", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=asset_schema,
    )

    op.create_table(
        "asset_govern_change_requests",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_ref", sa.Text()),
        sa.Column("request_type", sa.Text(), nullable=False),
        sa.Column("request_payload", postgresql.JSONB()),
        sa.Column("before_data", postgresql.JSONB()),
        sa.Column("after_data", postgresql.JSONB()),
        sa.Column("approval_status", sa.Text(), server_default="draft"),
        sa.Column("requested_by", sa.Text()),
        sa.Column("approved_by", sa.Text()),
        sa.Column("executed_by", sa.Text()),
        sa.Column("execution_result", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=asset_schema,
    )

    op.create_table(
        "asset_govern_audit_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_ref", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("before_data", postgresql.JSONB()),
        sa.Column("after_data", postgresql.JSONB()),
        sa.Column("operator", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=asset_schema,
    )

    op.create_table(
        "asset_action_executors",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("executor_code", sa.Text(), unique=True, nullable=False),
        sa.Column("executor_name_cn", sa.Text(), nullable=False),
        sa.Column("execution_mode", sa.Text(), nullable=False),
        sa.Column("tool_code", sa.Text()),
        sa.Column("sql_or_endpoint_ref", sa.Text()),
        sa.Column("target_system_code", sa.Text()),
        sa.Column("target_source_code", sa.Text()),
        sa.Column("risk_level", sa.Text(), server_default="medium"),
        sa.Column("require_approval", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("require_second_confirm", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=asset_schema,
    )


def downgrade() -> None:
    asset_schema = "asset"
    op.drop_table("asset_action_executors", schema=asset_schema)
    op.drop_table("asset_govern_audit_logs", schema=asset_schema)
    op.drop_table("asset_govern_change_requests", schema=asset_schema)
    op.drop_table("asset_role_permissions", schema=asset_schema)
    op.drop_table("asset_user_roles", schema=asset_schema)
    op.drop_table("asset_roles", schema=asset_schema)
