"""add_lineage_candidate_quality_tables

Revision ID: 9a7ed532710c
Revises: 8453cb52458a
Create Date: 2026-07-04 11:17:59.323322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9a7ed532710c'
down_revision: Union[str, Sequence[str], None] = '8453cb52458a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_candidate_relations',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('domain', sa.Text(), nullable=True),
    sa.Column('from_table', sa.Text(), nullable=False),
    sa.Column('from_columns', sa.Text(), nullable=True),
    sa.Column('to_table', sa.Text(), nullable=False),
    sa.Column('to_columns', sa.Text(), nullable=True),
    sa.Column('join_condition', sa.Text(), nullable=True),
    sa.Column('source_view', sa.Text(), nullable=True),
    sa.Column('source_file', sa.Text(), nullable=True),
    sa.Column('confidence', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default='candidate', nullable=True),
    sa.Column('reviewed_by', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )
    op.create_table('asset_quality_check_runs',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('triggered_by', sa.Text(), nullable=True),
    sa.Column('total_rules', sa.Integer(), nullable=True),
    sa.Column('total_findings', sa.Integer(), nullable=True),
    sa.Column('status', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )
    op.create_table('asset_quality_findings',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('rule_code', sa.Text(), nullable=True),
    sa.Column('target_type', sa.Text(), nullable=True),
    sa.Column('target_ref', sa.Text(), nullable=True),
    sa.Column('severity', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default='open', nullable=True),
    sa.Column('metric_value', sa.Text(), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('found_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('resolved_by', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )
    op.create_table('asset_quality_rules',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('rule_code', sa.Text(), nullable=False),
    sa.Column('rule_type', sa.Text(), nullable=True),
    sa.Column('target_type', sa.Text(), nullable=True),
    sa.Column('execution_mode', sa.Text(), server_default='metadata_only', nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('threshold_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('rule_code'),
    schema='asset'
    )
    op.create_table('asset_view_dependencies',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('view_name', sa.Text(), nullable=False),
    sa.Column('referenced_schema', sa.Text(), nullable=True),
    sa.Column('referenced_table', sa.Text(), nullable=False),
    sa.Column('alias', sa.Text(), nullable=True),
    sa.Column('source_file', sa.Text(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='asset'
    )
    op.create_index('idx_asset_view_deps_view', 'asset_view_dependencies', ['view_name'], schema='asset')
    op.create_index('idx_asset_view_deps_table', 'asset_view_dependencies', ['referenced_table'], schema='asset')
    op.create_index('idx_asset_candidate_status', 'asset_candidate_relations', ['status'], schema='asset')
    op.create_index('idx_asset_quality_findings_status', 'asset_quality_findings', ['status'], schema='asset')
    op.create_index('idx_asset_quality_findings_target', 'asset_quality_findings', ['target_ref'], schema='asset')


def downgrade() -> None:
    op.drop_index('idx_asset_quality_findings_target', table_name='asset_quality_findings', schema='asset')
    op.drop_index('idx_asset_quality_findings_status', table_name='asset_quality_findings', schema='asset')
    op.drop_index('idx_asset_candidate_status', table_name='asset_candidate_relations', schema='asset')
    op.drop_index('idx_asset_view_deps_table', table_name='asset_view_dependencies', schema='asset')
    op.drop_index('idx_asset_view_deps_view', table_name='asset_view_dependencies', schema='asset')
    op.drop_table('asset_view_dependencies', schema='asset')
    op.drop_table('asset_quality_rules', schema='asset')
    op.drop_table('asset_quality_findings', schema='asset')
    op.drop_table('asset_quality_check_runs', schema='asset')
    op.drop_table('asset_candidate_relations', schema='asset')
