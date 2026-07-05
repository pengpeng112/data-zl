"""add_business_terms

Revision ID: e18fc3ec89ac
Revises: 27ceb159a477
Create Date: 2026-07-04 13:56:07.211243

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e18fc3ec89ac'
down_revision: Union[str, Sequence[str], None] = '27ceb159a477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_business_terms',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('term', sa.Text(), nullable=False),
    sa.Column('mapping_type', sa.Text(), server_default='column', nullable=True),
    sa.Column('mapping_target', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )


def downgrade() -> None:
    op.drop_table('asset_business_terms', schema='asset')
