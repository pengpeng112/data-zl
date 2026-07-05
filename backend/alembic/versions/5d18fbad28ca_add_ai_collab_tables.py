"""add_ai_collab_tables

Revision ID: 5d18fbad28ca
Revises: 9a7ed532710c
Create Date: 2026-07-04 13:24:56.907122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '5d18fbad28ca'
down_revision: Union[str, Sequence[str], None] = '9a7ed532710c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_ai_sessions',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('session_key', sa.Text(), nullable=False),
    sa.Column('purpose', sa.Text(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_key'),
    schema='asset'
    )
    op.create_table('asset_ai_tool_calls',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('session_key', sa.Text(), nullable=True),
    sa.Column('tool_name', sa.Text(), nullable=True),
    sa.Column('request', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('response_summary', sa.Text(), nullable=True),
    sa.Column('called_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )
    op.create_table('asset_view_drafts',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('session_key', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('sql_text', sa.Text(), nullable=True),
    sa.Column('purpose', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default='draft', nullable=True),
    sa.Column('risk_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('reviewed_by', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('feedback', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )


def downgrade() -> None:
    op.drop_table('asset_view_drafts', schema='asset')
    op.drop_table('asset_ai_tool_calls', schema='asset')
    op.drop_table('asset_ai_sessions', schema='asset')
