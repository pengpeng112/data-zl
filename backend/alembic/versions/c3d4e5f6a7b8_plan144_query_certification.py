"""plan144 S3: query version certification + dependency typed evidence.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # certification decoupled from lifecycle (144 §12): existing active assets
    # default to legacy_unverified until evaluated — no sudden deactivation.
    op.add_column(
        "asset_query_versions",
        sa.Column("certification_status", sa.Text(), server_default="legacy_unverified", nullable=False),
        schema="asset",
    )
    op.add_column("asset_query_versions", sa.Column("metadata_snapshot_id", sa.BigInteger(), nullable=True), schema="asset")
    op.add_column("asset_query_versions", sa.Column("lineage_snapshot_id", sa.BigInteger(), nullable=True), schema="asset")
    op.add_column("asset_query_versions", sa.Column("validation_digest", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_versions", sa.Column("parser_version", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_versions", sa.Column("unresolved_reason", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_versions", sa.Column("semantic_contract", postgresql.JSONB(), nullable=True), schema="asset")
    op.create_index(
        "ix_asset_query_versions_certification",
        "asset_query_versions",
        ["certification_status"],
        schema="asset",
    )

    # typed evidence for dependency rows (144 §7.1)
    op.add_column("asset_query_dependencies", sa.Column("object_key", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_dependencies", sa.Column("column_key", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_dependencies", sa.Column("evidence_type", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_query_dependencies", sa.Column("evidence_ref", sa.Text(), nullable=True), schema="asset")
    op.add_column(
        "asset_query_dependencies",
        sa.Column("resolution_status", sa.Text(), server_default="unresolved", nullable=False),
        schema="asset",
    )
    op.create_index(
        "ix_asset_query_deps_resolution",
        "asset_query_dependencies",
        ["resolution_status"],
        schema="asset",
    )

    # legacy migration (144 §12): every pre-144 active/current version is
    # explicitly legacy_unverified — column default already covers new rows.
    op.execute(
        "UPDATE asset.asset_query_versions "
        "SET certification_status = 'legacy_unverified' "
        "WHERE certification_status IS NULL OR certification_status = 'legacy_unverified'"
    )


def downgrade() -> None:
    op.drop_index("ix_asset_query_deps_resolution", table_name="asset_query_dependencies", schema="asset")
    op.drop_column("asset_query_dependencies", "resolution_status", schema="asset")
    op.drop_column("asset_query_dependencies", "evidence_ref", schema="asset")
    op.drop_column("asset_query_dependencies", "evidence_type", schema="asset")
    op.drop_column("asset_query_dependencies", "column_key", schema="asset")
    op.drop_column("asset_query_dependencies", "object_key", schema="asset")
    op.drop_index("ix_asset_query_versions_certification", table_name="asset_query_versions", schema="asset")
    op.drop_column("asset_query_versions", "semantic_contract", schema="asset")
    op.drop_column("asset_query_versions", "unresolved_reason", schema="asset")
    op.drop_column("asset_query_versions", "parser_version", schema="asset")
    op.drop_column("asset_query_versions", "validation_digest", schema="asset")
    op.drop_column("asset_query_versions", "lineage_snapshot_id", schema="asset")
    op.drop_column("asset_query_versions", "metadata_snapshot_id", schema="asset")
    op.drop_column("asset_query_versions", "certification_status", schema="asset")
