"""add hashed API token storage

Revision ID: q3d4e5f6a7b8
Revises: p2c3d4e5f6a7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q3d4e5f6a7b8"
down_revision: Union[str, None] = "p2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("asset_api_keys", sa.Column("token_hash", sa.Text()), schema="asset")
    op.create_index("ix_asset_api_keys_token_hash", "asset_api_keys", ["token_hash"], unique=True, schema="asset")
    op.alter_column("asset_api_keys", "token", nullable=True, schema="asset")


def downgrade() -> None:
    # A hash cannot be converted back to its raw secret. Preserve a non-secret
    # placeholder so the legacy NOT NULL constraint can be restored safely.
    op.execute(
        "UPDATE asset.asset_api_keys "
        "SET token = 'migrated:' || COALESCE(token_hash, id::text) "
        "WHERE token IS NULL"
    )
    op.alter_column("asset_api_keys", "token", existing_type=sa.Text(), nullable=False, schema="asset")
    op.drop_index("ix_asset_api_keys_token_hash", table_name="asset_api_keys", schema="asset")
    op.drop_column("asset_api_keys", "token_hash", schema="asset")
