"""126 P4: asset_data_products catalog for published query/metric APIs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "h5c6d7e8f9a0"
down_revision = "g4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_data_products",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("product_type", sa.Text(), nullable=False),
        sa.Column("query_code", sa.Text()),
        sa.Column("metric_code", sa.Text()),
        sa.Column("pin_version", sa.Integer()),
        sa.Column("source_code", sa.Text()),
        sa.Column("parameter_schema", JSONB()),
        sa.Column("max_rows", sa.Integer(), server_default="1000"),
        sa.Column("result_storage", sa.Text(), server_default="none"),
        sa.Column("owner_name", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("ai_readable", sa.Boolean(), server_default="true"),
        sa.Column("rate_limit_per_min", sa.Integer(), server_default="30"),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("product_code", name="uq_asset_data_products_code"),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_data_products", schema="asset")
