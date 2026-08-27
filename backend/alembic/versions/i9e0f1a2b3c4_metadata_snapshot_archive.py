"""plan146 E9: protected soft-archive for metadata snapshots.

Revision ID: i9e0f1a2b3c4
Revises: h8d9e0f1a2b3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i9e0f1a2b3c4"
down_revision: Union[str, None] = "h8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "asset_metadata_snapshots"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True), schema="asset")
    op.add_column(TABLE, sa.Column("archived_by", sa.Text(), nullable=True), schema="asset")


def downgrade() -> None:
    op.drop_column(TABLE, "archived_by", schema="asset")
    op.drop_column(TABLE, "archived_at", schema="asset")
