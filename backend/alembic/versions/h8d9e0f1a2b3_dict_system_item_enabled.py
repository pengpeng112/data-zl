"""plan146 C2: platform-level enable switch for dictionary system items.

Revision ID: h8d9e0f1a2b3
Revises: g7b8c9d0e1f2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h8d9e0f1a2b3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "asset_dict_system_items"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"), schema="asset")


def downgrade() -> None:
    op.drop_column(TABLE, "enabled", schema="asset")
