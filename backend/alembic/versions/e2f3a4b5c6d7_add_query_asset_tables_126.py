"""126 P1: asset_query_* tables for query definition/version/run/result.

Hand-written. No privilege grants. Only exercise against APP_TEST_DB_URL first.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_query_definitions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("query_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text()),
        sa.Column("business_domain", sa.Text()),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("namespace_name", sa.Text()),
        sa.Column("owner_name", sa.Text()),
        sa.Column("sensitivity", sa.Text(), server_default="aggregate"),
        sa.Column("current_version_id", sa.BigInteger()),
        sa.Column("ai_readable", sa.Boolean(), server_default="true"),
        sa.Column("allow_schedule", sa.Boolean(), server_default="false"),
        sa.Column("allow_data_product", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.Text(), server_default="active"),
        sa.Column("created_by", sa.Text()),
        sa.Column("updated_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("query_code", name="uq_asset_query_definitions_code"),
        schema="asset",
    )

    op.create_table(
        "asset_query_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.BigInteger(), nullable=False),
        sa.Column("query_code", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_version_id", sa.BigInteger()),
        sa.Column("status", sa.Text(), nullable=False, server_default="captured"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dialect", sa.Text()),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("sql_normalized", sa.Text()),
        sa.Column("sql_sha256", sa.Text(), nullable=False),
        sa.Column("semantic_fingerprint", sa.Text()),
        sa.Column("parameter_schema", JSONB()),
        sa.Column("output_schema", JSONB()),
        sa.Column("grain", sa.Text()),
        sa.Column("period_field", sa.Text()),
        sa.Column("include_rules", sa.Text()),
        sa.Column("exclude_rules", sa.Text()),
        sa.Column("dedup_rules", sa.Text()),
        sa.Column("limitations", JSONB()),
        sa.Column("risk_flags", JSONB()),
        sa.Column("recipe_refs", JSONB()),
        sa.Column("metric_refs", JSONB()),
        sa.Column("source_path", sa.Text()),
        sa.Column("ai_source", JSONB()),
        sa.Column("session_key", sa.Text()),
        sa.Column("revision_reason", sa.Text()),
        sa.Column("diff_summary", sa.Text()),
        sa.Column("effective_from", sa.TIMESTAMP(timezone=True)),
        sa.Column("effective_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("validated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("query_id", "version", name="uq_asset_query_versions_qid_ver"),
        schema="asset",
    )
    op.create_index("ix_asset_query_versions_code_status", "asset_query_versions", ["query_code", "status"], schema="asset")
    op.create_index("ix_asset_query_versions_sql_hash", "asset_query_versions", ["sql_sha256"], schema="asset")
    op.create_index("ix_asset_query_versions_query_id", "asset_query_versions", ["query_id"], schema="asset")

    # Partial unique: only one active version per query_code
    op.execute(
        """
        CREATE UNIQUE INDEX uq_asset_query_versions_one_active
        ON asset.asset_query_versions (query_code)
        WHERE is_active = true
        """
    )

    op.create_table(
        "asset_query_dependencies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("query_version_id", sa.BigInteger(), nullable=False),
        sa.Column("dep_type", sa.Text(), nullable=False),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("schema_name", sa.Text()),
        sa.Column("object_name", sa.Text()),
        sa.Column("column_name", sa.Text()),
        sa.Column("relation_id", sa.BigInteger()),
        sa.Column("recipe_id", sa.Text()),
        sa.Column("recipe_version", sa.Integer()),
        sa.Column("is_formal", sa.Boolean(), server_default="false"),
        sa.Column("evidence", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        schema="asset",
    )
    op.create_index("ix_asset_query_deps_version", "asset_query_dependencies", ["query_version_id"], schema="asset")

    op.create_table(
        "asset_query_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("query_version_id", sa.BigInteger(), nullable=False),
        sa.Column("query_code", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("dialect", sa.Text()),
        sa.Column("parameters", JSONB()),
        sa.Column("parameters_hash", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("row_count", sa.Integer()),
        sa.Column("truncated", sa.Boolean(), server_default="false"),
        sa.Column("result_storage", sa.Text(), server_default="none"),
        sa.Column("result_hash", sa.Text()),
        sa.Column("sql_sha256", sa.Text()),
        sa.Column("warnings", JSONB()),
        sa.Column("error_class", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("triggered_by", sa.Text()),
        sa.Column("session_key", sa.Text()),
        sa.Column("correlation_id", sa.Text()),
        sa.Column("data_as_of", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        schema="asset",
    )
    op.create_index("ix_asset_query_runs_version", "asset_query_runs", ["query_version_id"], schema="asset")
    op.create_index("ix_asset_query_runs_code", "asset_query_runs", ["query_code"], schema="asset")

    op.create_table(
        "asset_query_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("storage", sa.Text(), nullable=False, server_default="none"),
        sa.Column("summary_json", JSONB()),
        sa.Column("file_ref", sa.Text()),
        sa.Column("file_sha256", sa.Text()),
        sa.Column("file_format", sa.Text()),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("sensitivity", sa.Text(), server_default="aggregate"),
        sa.Column("retention_days", sa.Integer()),
        sa.Column("truncated", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        schema="asset",
    )
    op.create_index("ix_asset_query_results_run", "asset_query_results", ["run_id"], schema="asset")


def downgrade() -> None:
    op.drop_table("asset_query_results", schema="asset")
    op.drop_table("asset_query_runs", schema="asset")
    op.drop_table("asset_query_dependencies", schema="asset")
    op.execute("DROP INDEX IF EXISTS asset.uq_asset_query_versions_one_active")
    op.drop_table("asset_query_versions", schema="asset")
    op.drop_table("asset_query_definitions", schema="asset")
