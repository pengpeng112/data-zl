"""add source_code to metadata snapshots

Revision ID: p2c3d4e5f6a7
Revises: o1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p2c3d4e5f6a7"
down_revision: Union[str, None] = "o1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("asset_metadata_snapshots", sa.Column("source_code", sa.Text()), schema="asset")
    op.execute(
        "UPDATE asset.asset_metadata_snapshots "
        "SET source_code = (data::jsonb ->> 'source') "
        "WHERE source_code IS NULL AND data IS NOT NULL"
    )
    op.create_index(
        "ix_asset_metadata_snapshots_source_code",
        "asset_metadata_snapshots",
        ["source_code"],
        schema="asset",
    )


def downgrade() -> None:
    op.drop_index("ix_asset_metadata_snapshots_source_code", table_name="asset_metadata_snapshots", schema="asset")
    op.drop_column("asset_metadata_snapshots", "source_code", schema="asset")
