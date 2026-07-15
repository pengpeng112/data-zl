"""extend data sources, ops templates/runs, and medical dict import runs.

Revision ID: x0e1f2a3b4c5
Revises: w9d0e1f2a3b4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "x0e1f2a3b4c5"
down_revision: Union[str, None] = "w9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    # ── asset_data_sources connection fields ──
    op.add_column(
        "asset_data_sources",
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("service_mode", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("default_schema", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("credential_username_masked", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("credential_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("credential_updated_by", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("connection_options", postgresql.JSONB(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_data_sources",
        sa.Column("write_policy", sa.Text(), server_default="readonly", nullable=False),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            """
            UPDATE asset.asset_data_sources
            SET service_mode = CASE
                WHEN lower(coalesce(db_type, '')) = 'oracle'
                     AND service_name IS NOT NULL AND service_name <> '' THEN 'service_name'
                WHEN lower(coalesce(db_type, '')) = 'oracle'
                     AND database_name IS NOT NULL AND database_name <> '' THEN 'sid'
                WHEN lower(coalesce(db_type, '')) IN ('mysql', 'sqlserver', 'vastbase', 'postgresql')
                     THEN 'database'
                ELSE service_mode
            END
            WHERE service_mode IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE asset.asset_data_sources
            SET write_policy = CASE
                WHEN upper(system_code) IN ('ASSET_PLATFORM', 'PLATFORM') THEN 'platform_controlled'
                ELSE 'readonly'
            END
            """
        )
    )

    # ── ops tool templates versioning ──
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("sql_hash", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("created_by", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("updated_by", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("max_affected_rows", sa.Integer(), server_default="100", nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("target_scope", sa.Text(), server_default="platform_asset", nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_templates",
        sa.Column("immutable_after_approval", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            """
            UPDATE asset.asset_ops_tool_templates
            SET status = CASE WHEN enabled IS TRUE THEN 'approved' ELSE 'draft' END
            WHERE status IS NULL OR status = 'draft'
            """
        )
    )

    # ── ops tool runs tracking ──
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("template_version", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("sql_hash", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("preview_count", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("confirmation_digest", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("transaction_id", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("error_code", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_ops_tool_runs",
        sa.Column("error_summary_masked", sa.Text(), nullable=True),
        schema=SCHEMA,
    )

    # ── medical dict import batch ──
    op.create_table(
        "asset_dict_medical_import_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("batch_code", sa.Text(), nullable=False),
        sa.Column("source_dir", sa.Text(), nullable=True),
        sa.Column("diagnosis_file_name", sa.Text(), nullable=True),
        sa.Column("operation_file_name", sa.Text(), nullable=True),
        sa.Column("diagnosis_sha256", sa.Text(), nullable=True),
        sa.Column("operation_sha256", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("mode", sa.Text(), server_default="dry_run", nullable=False),
        sa.Column("operator", sa.Text(), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("batch_code", name="uq_dict_medical_import_batch_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_dict_medical_import_sha",
        "asset_dict_medical_import_runs",
        ["diagnosis_sha256", "operation_sha256"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_dict_medical_import_sha", table_name="asset_dict_medical_import_runs", schema=SCHEMA)
    op.drop_table("asset_dict_medical_import_runs", schema=SCHEMA)

    for col in (
        "error_summary_masked",
        "error_code",
        "transaction_id",
        "confirmation_digest",
        "preview_count",
        "sql_hash",
        "template_version",
    ):
        op.drop_column("asset_ops_tool_runs", col, schema=SCHEMA)

    for col in (
        "immutable_after_approval",
        "target_scope",
        "max_affected_rows",
        "reviewed_at",
        "reviewed_by",
        "updated_by",
        "created_by",
        "sql_hash",
        "status",
        "version",
    ):
        op.drop_column("asset_ops_tool_templates", col, schema=SCHEMA)

    for col in (
        "write_policy",
        "connection_options",
        "credential_updated_by",
        "credential_updated_at",
        "credential_username_masked",
        "default_schema",
        "service_mode",
        "display_order",
    ):
        op.drop_column("asset_data_sources", col, schema=SCHEMA)
