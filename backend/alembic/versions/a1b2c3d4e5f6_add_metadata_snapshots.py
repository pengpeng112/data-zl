"""add_metadata_snapshots

Revision ID: a1b2c3d4e5f6
Revises: e18fc3ec89ac
Create Date: 2026-07-04 14:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e18fc3ec89ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_metadata_snapshots',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('label', sa.Text(), nullable=True),
    sa.Column('snapshot_time', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('scope', sa.Text(), nullable=True),
    sa.Column('table_count', sa.Integer(), nullable=True),
    sa.Column('column_count', sa.Integer(), nullable=True),
    sa.Column('relation_count', sa.Integer(), nullable=True),
    sa.Column('data', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )


def downgrade() -> None:
    op.drop_table('asset_metadata_snapshots', schema='asset')
