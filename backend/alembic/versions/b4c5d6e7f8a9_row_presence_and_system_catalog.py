"""row presence status + system catalog fields for plan 90.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    op.add_column(
        "asset_tables",
        sa.Column("row_presence_status", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_tables",
        sa.Column("row_presence_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_tables",
        sa.Column("row_presence_method", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_tables",
        sa.Column("row_presence_error_code", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_tables_row_presence_status",
        "asset_tables",
        ["row_presence_status"],
        schema=SCHEMA,
    )
    # optional: relations mark when endpoint excluded as empty
    op.add_column(
        "asset_relations",
        sa.Column("endpoint_excluded_empty", sa.Boolean(), server_default=sa.text("false")),
        schema=SCHEMA,
    )
    # systems: canonical alias tracking
    op.add_column(
        "asset_systems",
        sa.Column("canonical_system_code", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_systems_canonical",
        "asset_systems",
        ["canonical_system_code"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_asset_systems_canonical", table_name="asset_systems", schema=SCHEMA)
    op.drop_column("asset_systems", "canonical_system_code", schema=SCHEMA)
    op.drop_column("asset_relations", "endpoint_excluded_empty", schema=SCHEMA)
    op.drop_index("ix_asset_tables_row_presence_status", table_name="asset_tables", schema=SCHEMA)
    op.drop_column("asset_tables", "row_presence_error_code", schema=SCHEMA)
    op.drop_column("asset_tables", "row_presence_method", schema=SCHEMA)
    op.drop_column("asset_tables", "row_presence_checked_at", schema=SCHEMA)
    op.drop_column("asset_tables", "row_presence_status", schema=SCHEMA)
