"""add_systems_sources_and_extend_asset_columns

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    s = "asset"

    op.create_table(
        "asset_systems",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("system_code", sa.Text(), unique=True, nullable=False),
        sa.Column("system_name_cn", sa.Text(), nullable=False),
        sa.Column("system_name_en", sa.Text()),
        sa.Column("system_type", sa.Text()),
        sa.Column("owner_department", sa.Text()),
        sa.Column("description_cn", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )

    op.create_table(
        "asset_data_sources",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), unique=True, nullable=False),
        sa.Column("source_name_cn", sa.Text(), nullable=False),
        sa.Column("db_type", sa.Text()),
        sa.Column("host_masked", sa.Text()),
        sa.Column("port", sa.Integer()),
        sa.Column("service_name", sa.Text()),
        sa.Column("database_name", sa.Text()),
        sa.Column("connection_mode", sa.Text()),
        sa.Column("environment", sa.Text()),
        sa.Column("collect_mode", sa.Text(), server_default="metadata_only"),
        sa.Column("credential_ref", sa.Text()),
        sa.Column("write_credential_ref", sa.Text()),
        sa.Column("description_cn", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_check_status", sa.Text()),
        sa.Column("last_check_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )

    # extend asset_tables
    for col, type_ in [
        ("system_code", sa.Text()),
        ("source_code", sa.Text()),
        ("namespace_name", sa.Text()),
        ("table_name_cn", sa.Text()),
        ("business_desc_cn", sa.Text()),
        ("table_role", sa.Text()),
        ("include_status", sa.Text()),
        ("review_status", sa.Text()),
        ("reviewed_by", sa.Text()),
        ("reviewed_at", sa.TIMESTAMP(timezone=True)),
        ("created_at", sa.TIMESTAMP(timezone=True)),
        ("updated_at", sa.TIMESTAMP(timezone=True)),
    ]:
        op.add_column("asset_tables", sa.Column(col, type_), schema=s)

    # extend asset_columns
    for col, type_ in [
        ("system_code", sa.Text()),
        ("source_code", sa.Text()),
        ("namespace_name", sa.Text()),
        ("column_name_cn", sa.Text()),
        ("business_desc_cn", sa.Text()),
        ("value_desc_cn", sa.Text()),
        ("semantic_type", sa.Text()),
        ("is_sensitive", sa.Boolean()),
        ("review_status", sa.Text()),
    ]:
        op.add_column("asset_columns", sa.Column(col, type_), schema=s)


def downgrade() -> None:
    s = "asset"

    # drop extended columns from asset_columns
    for col in [
        "system_code", "source_code", "namespace_name",
        "column_name_cn", "business_desc_cn", "value_desc_cn",
        "semantic_type", "is_sensitive", "review_status",
    ]:
        op.drop_column("asset_columns", col, schema=s)

    # drop extended columns from asset_tables
    for col in [
        "system_code", "source_code", "namespace_name",
        "table_name_cn", "business_desc_cn", "table_role",
        "include_status", "review_status", "reviewed_by", "reviewed_at",
        "created_at", "updated_at",
    ]:
        op.drop_column("asset_tables", col, schema=s)

    op.drop_table("asset_data_sources", schema=s)
    op.drop_table("asset_systems", schema=s)
