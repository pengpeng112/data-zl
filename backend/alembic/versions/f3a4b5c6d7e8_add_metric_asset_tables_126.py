"""126 P2: asset_metric_definitions / versions / results.

Hand-written. Test on APP_TEST_DB_URL before production.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_metric_definitions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metric_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("meaning", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("unit", sa.Text()),
        sa.Column("frequency", sa.Text()),
        sa.Column("grain", sa.Text()),
        sa.Column("owner_dept", sa.Text()),
        sa.Column("current_version_id", sa.BigInteger()),
        sa.Column("allow_dashboard", sa.Boolean(), server_default="true"),
        sa.Column("allow_export", sa.Boolean(), server_default="false"),
        sa.Column("allow_data_product", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.Text(), server_default="active"),
        sa.Column("created_by", sa.Text()),
        sa.Column("updated_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("metric_code", name="uq_asset_metric_definitions_code"),
        schema="asset",
    )

    op.create_table(
        "asset_metric_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metric_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_code", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_version_id", sa.BigInteger()),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("definition_text", sa.Text()),
        sa.Column("numerator_desc", sa.Text()),
        sa.Column("denominator_desc", sa.Text()),
        sa.Column("formula", sa.Text()),
        sa.Column("query_code", sa.Text()),
        sa.Column("query_version", sa.Integer()),
        sa.Column("numerator_query_code", sa.Text()),
        sa.Column("numerator_query_version", sa.Integer()),
        sa.Column("denominator_query_code", sa.Text()),
        sa.Column("denominator_query_version", sa.Integer()),
        sa.Column("period_field", sa.Text()),
        sa.Column("include_rules", sa.Text()),
        sa.Column("exclude_rules", sa.Text()),
        sa.Column("dedup_rules", sa.Text()),
        sa.Column("limitations", JSONB()),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("revision_reason", sa.Text()),
        sa.Column("content_hash", sa.Text()),
        sa.Column("effective_from", sa.TIMESTAMP(timezone=True)),
        sa.Column("effective_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("metric_id", "version", name="uq_asset_metric_versions_mid_ver"),
        schema="asset",
    )
    op.create_index("ix_asset_metric_versions_code_status", "asset_metric_versions", ["metric_code", "status"], schema="asset")
    op.create_index("ix_asset_metric_versions_metric_id", "asset_metric_versions", ["metric_id"], schema="asset")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_asset_metric_versions_one_active
        ON asset.asset_metric_versions (metric_code)
        WHERE is_active = true
        """
    )

    op.create_table(
        "asset_metric_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metric_version_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_code", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("dimensions", JSONB()),
        sa.Column("numerator_value", sa.Text()),
        sa.Column("denominator_value", sa.Text()),
        sa.Column("metric_value", sa.Text()),
        sa.Column("status", sa.Text(), server_default="ok"),
        sa.Column("quality_status", sa.Text()),
        sa.Column("data_as_of", sa.TIMESTAMP(timezone=True)),
        sa.Column("query_run_id", sa.BigInteger()),
        sa.Column("run_batch", sa.Text()),
        sa.Column("limitations_note", sa.Text()),
        sa.Column("is_recalc", sa.Boolean(), server_default="false"),
        sa.Column("prev_result_id", sa.BigInteger()),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        schema="asset",
    )
    op.create_index(
        "ix_asset_metric_results_code_period",
        "asset_metric_results",
        ["metric_code", "period_key"],
        schema="asset",
    )
    op.create_index("ix_asset_metric_results_version", "asset_metric_results", ["metric_version_id"], schema="asset")


def downgrade() -> None:
    op.drop_table("asset_metric_results", schema="asset")
    op.execute("DROP INDEX IF EXISTS asset.uq_asset_metric_versions_one_active")
    op.drop_table("asset_metric_versions", schema="asset")
    op.drop_table("asset_metric_definitions", schema="asset")
