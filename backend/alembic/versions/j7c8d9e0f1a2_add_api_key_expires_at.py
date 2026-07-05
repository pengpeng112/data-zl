"""add api_key expires_at

Revision ID: j7c8d9e0f1a2
Revises: i7a8b9c0d1e3
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "j7c8d9e0f1a2"
down_revision: Union[str, None] = "i7a8b9c0d1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("asset_api_keys", sa.Column("expires_at", sa.TIMESTAMP(timezone=True)), schema="asset")


def downgrade() -> None:
    op.drop_column("asset_api_keys", "expires_at", schema="asset")
