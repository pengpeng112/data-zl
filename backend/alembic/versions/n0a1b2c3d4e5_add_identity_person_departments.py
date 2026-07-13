"""add_identity_person_departments

Revision ID: n0a1b2c3d4e5
Revises: m9f0a1b2c3d5
Create Date: 2026-07-07 21:30:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "n0a1b2c3d4e5"
down_revision: Union[str, None] = "m9f0a1b2c3d5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "asset_identity_person_departments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("person_code", sa.Text(), nullable=False),
        sa.Column("dept_code", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_dept_code", sa.Text()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_code", "dept_code", "source_table"),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_identity_person_departments", schema="asset")
