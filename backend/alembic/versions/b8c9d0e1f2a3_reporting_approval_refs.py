"""T+1 批1-2c：耐久批准登记表（asset_reporting_approval_refs）

revision ID: b8c9d0e1f2a3
Revises: a7d8e9f0a1b2
Create Date: 2026-10-23

管道自身不写本表；仅运维经 reporting_ctl approval-register 显式登记，
装载时由 PlatformApprovalVerifier 只读核验（批1-2c 生产 ApplyPort 组装）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"
TABLE = "asset_reporting_approval_refs"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("approval_ref", sa.Text(), nullable=False),
        sa.Column("executor_code", sa.Text(), nullable=False),
        sa.Column("target_scope", sa.Text(), nullable=False),
        sa.Column(
            "allowed_operations", sa.Text(), nullable=False,
            server_default="INSERT,UPDATE",
        ),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("registered_by", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "approval_ref", "executor_code",
            name="uq_asset_reporting_approval",
        ),
        sa.Index("ix_asset_reporting_approval_ref", "approval_ref"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table(TABLE, schema=SCHEMA)
