"""plan144 S5 / 138 first-phase: static lineage edges.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_lineage_edges",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("edge_key", sa.Text(), nullable=False),
        sa.Column("from_object_key", sa.Text(), nullable=False),
        sa.Column("to_object_key", sa.Text(), nullable=False),
        sa.Column("from_object_type", sa.Text(), nullable=False),
        sa.Column("to_object_type", sa.Text(), nullable=False),
        sa.Column("edge_type", sa.Text(), nullable=False),
        sa.Column("granularity", sa.Text(), nullable=False, server_default="table"),
        sa.Column("process_key", sa.Text(), nullable=True),
        sa.Column("transform_type", sa.Text(), nullable=True),
        sa.Column("field_mapping", postgresql.JSONB(), nullable=True),
        sa.Column("expression_hash", sa.Text(), nullable=True),
        sa.Column("evidence_type", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("evidence_hash", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Text(), server_default="auto", nullable=False),
        sa.Column("logic_version", sa.Text(), nullable=False, server_default="1"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("batch_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("unresolved_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("edge_key", name="uq_asset_lineage_edges_key"),
        schema="asset",
    )
    op.create_index("ix_asset_lineage_edges_from", "asset_lineage_edges", ["from_object_key"], schema="asset")
    op.create_index("ix_asset_lineage_edges_to", "asset_lineage_edges", ["to_object_key"], schema="asset")
    # deterministic business key per 138 §4.1
    op.create_index(
        "uq_asset_lineage_edges_business",
        "asset_lineage_edges",
        ["from_object_key", "to_object_key", "edge_type", "process_key", "logic_version"],
        unique=True,
        schema="asset",
    )


def downgrade() -> None:
    op.drop_index("uq_asset_lineage_edges_business", table_name="asset_lineage_edges", schema="asset")
    op.drop_index("ix_asset_lineage_edges_to", table_name="asset_lineage_edges", schema="asset")
    op.drop_index("ix_asset_lineage_edges_from", table_name="asset_lineage_edges", schema="asset")
    op.drop_table("asset_lineage_edges", schema="asset")
