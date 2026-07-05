"""add_scheduler_events_rules_tables

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-04 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    s = "asset"

    op.create_table(
        "asset_scheduler_jobs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("trigger_mode", sa.Text(), server_default="scheduled"),
        sa.Column("schedule_cron", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("result_ref", sa.Text()),
        sa.Column("total_processed", sa.Integer()),
        sa.Column("total_changes", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )

    op.create_table(
        "asset_govern_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text()),
        sa.Column("entity_ref", sa.Text()),
        sa.Column("severity", sa.Text(), server_default="info"),
        sa.Column("title", sa.Text()),
        sa.Column("detail", postgresql.JSONB()),
        sa.Column("status", sa.Text(), server_default="open"),
        sa.Column("assigned_to", sa.Text()),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )

    op.create_table(
        "asset_change_rules",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("rule_code", sa.Text(), unique=True, nullable=False),
        sa.Column("rule_name_cn", sa.Text(), nullable=False),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("db_type", sa.Text()),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("severity_override", sa.Text()),
        sa.Column("ignore_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("description", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )


def downgrade() -> None:
    s = "asset"
    op.drop_table("asset_change_rules", schema=s)
    op.drop_table("asset_govern_events", schema=s)
    op.drop_table("asset_scheduler_jobs", schema=s)
