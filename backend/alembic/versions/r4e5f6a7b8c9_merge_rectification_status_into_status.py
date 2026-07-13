"""merge rectification_status into status

Revision ID: r4e5f6a7b8c9
Revises: q3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r4e5f6a7b8c9"
down_revision: Union[str, None] = "q3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE asset.asset_quality_findings "
        "SET status = rectification_status "
        "WHERE rectification_status IS NOT NULL "
        "AND rectification_status <> '' "
        "AND rectification_status <> status"
    )
    op.drop_column("asset_quality_findings", "rectification_status", schema="asset")


def downgrade() -> None:
    op.add_column(
        "asset_quality_findings",
        sa.Column("rectification_status", sa.Text(), server_default="open"),
        schema="asset",
    )
