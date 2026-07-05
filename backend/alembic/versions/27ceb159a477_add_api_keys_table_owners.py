"""add_api_keys_table_owners

Revision ID: 27ceb159a477
Revises: 5d18fbad28ca
Create Date: 2026-07-04 13:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '27ceb159a477'
down_revision: Union[str, Sequence[str], None] = '5d18fbad28ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_api_keys',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('key_name', sa.Text(), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token'),
    schema='asset'
    )
    op.create_table('asset_table_owners',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('full_table_name', sa.Text(), nullable=False),
    sa.Column('owner_name', sa.Text(), nullable=True),
    sa.Column('department', sa.Text(), nullable=True),
    sa.Column('contact', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('full_table_name'),
    schema='asset'
    )


def downgrade() -> None:
    op.drop_table('asset_table_owners', schema='asset')
    op.drop_table('asset_api_keys', schema='asset')
