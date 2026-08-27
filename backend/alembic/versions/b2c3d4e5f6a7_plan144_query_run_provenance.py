"""plan144 S2: query run provenance columns (digest/schema/data_as_of/safe params).

Revision ID: b2c3d4e5f6a7
Revises: aa11bb22cc33
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "aa11bb22cc33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Content digests (144 §4.5): result_digest supersedes row-count-only hash;
    # schema_digest pins the output column contract.
    op.add_column("asset_query_runs", sa.Column("result_digest", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_runs", sa.Column("schema_digest", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_runs", sa.Column("result_digest_version", sa.Text(), nullable=True), schema="asset")
    # data_as_of provenance so created_at can never masquerade as data currency
    op.add_column("asset_query_runs", sa.Column("data_as_of_source", sa.Text(), nullable=True), schema="asset")
    # masked parameter summary: sensitive ids stored as hashes only (144 §4.1)
    op.add_column("asset_query_runs", sa.Column("safe_parameters_summary", postgresql.JSONB(), nullable=True), schema="asset")
    # explicit historical recalculation audit
    op.add_column("asset_query_runs", sa.Column("recalc_reason", sa.Text(), nullable=True), schema="asset")


def downgrade() -> None:
    op.drop_column("asset_query_runs", "recalc_reason", schema="asset")
    op.drop_column("asset_query_runs", "safe_parameters_summary", schema="asset")
    op.drop_column("asset_query_runs", "data_as_of_source", schema="asset")
    op.drop_column("asset_query_runs", "result_digest_version", schema="asset")
    op.drop_column("asset_query_runs", "schema_digest", schema="asset")
    op.drop_column("asset_query_runs", "result_digest", schema="asset")
