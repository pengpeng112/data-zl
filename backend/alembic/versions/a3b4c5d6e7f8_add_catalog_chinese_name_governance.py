"""add catalog Chinese-name governance metadata

Revision ID: a3b4c5d6e7f8
Revises: z2f3a4b5c6d7
"""
from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "z2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asset_tables", sa.Column("name_cn_source", sa.Text()), schema="asset")
    op.add_column("asset_tables", sa.Column("name_cn_status", sa.Text()), schema="asset")
    op.add_column("asset_columns", sa.Column("name_cn_source", sa.Text()), schema="asset")
    op.add_column("asset_columns", sa.Column("name_cn_status", sa.Text()), schema="asset")
    op.add_column("asset_source_schemas", sa.Column("schema_name_cn", sa.Text()), schema="asset")
    op.add_column("asset_source_schemas", sa.Column("name_cn_source", sa.Text()), schema="asset")
    op.add_column("asset_source_schemas", sa.Column("name_cn_status", sa.Text()), schema="asset")


def downgrade() -> None:
    op.drop_column("asset_source_schemas", "name_cn_status", schema="asset")
    op.drop_column("asset_source_schemas", "name_cn_source", schema="asset")
    op.drop_column("asset_source_schemas", "schema_name_cn", schema="asset")
    op.drop_column("asset_columns", "name_cn_status", schema="asset")
    op.drop_column("asset_columns", "name_cn_source", schema="asset")
    op.drop_column("asset_tables", "name_cn_status", schema="asset")
    op.drop_column("asset_tables", "name_cn_source", schema="asset")
