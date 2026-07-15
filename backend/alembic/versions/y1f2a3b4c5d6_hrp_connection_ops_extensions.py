"""HRP connection normalization and ops target/log extensions.

Revision ID: y1f2a3b4c5d6
Revises: x0e1f2a3b4c5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "y1f2a3b4c5d6"
down_revision: Union[str, None] = "x0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    # ── data sources: physical endpoint / alias / test-collect state ──
    for name, col in [
        ("endpoint_key", sa.Column("endpoint_key", sa.Text(), nullable=True)),
        ("database_key", sa.Column("database_key", sa.Text(), nullable=True)),
        ("canonical_source_code", sa.Column("canonical_source_code", sa.Text(), nullable=True)),
        ("source_kind", sa.Column("source_kind", sa.Text(), server_default="physical_connection", nullable=False)),
        ("business_labels", sa.Column("business_labels", postgresql.JSONB(), nullable=True)),
        ("metadata_origin", sa.Column("metadata_origin", sa.Text(), nullable=True)),
        ("last_test_status", sa.Column("last_test_status", sa.Text(), nullable=True)),
        ("last_test_at", sa.Column("last_test_at", sa.TIMESTAMP(timezone=True), nullable=True)),
        ("last_test_latency_ms", sa.Column("last_test_latency_ms", sa.Integer(), nullable=True)),
        ("last_test_error_code", sa.Column("last_test_error_code", sa.Text(), nullable=True)),
        ("last_test_error_masked", sa.Column("last_test_error_masked", sa.Text(), nullable=True)),
        ("last_collect_status", sa.Column("last_collect_status", sa.Text(), nullable=True)),
        ("last_collect_at", sa.Column("last_collect_at", sa.TIMESTAMP(timezone=True), nullable=True)),
        ("last_collect_snapshot_id", sa.Column("last_collect_snapshot_id", sa.BigInteger(), nullable=True)),
    ]:
        op.add_column("asset_data_sources", col, schema=SCHEMA)

    # backfill endpoint/database keys from existing identity fields
    op.execute(
        sa.text(
            """
            UPDATE asset.asset_data_sources
            SET
              endpoint_key = lower(coalesce(db_type, 'unknown')) || '://' ||
                             lower(coalesce(nullif(target_host, ''), nullif(host_masked, ''), 'unknown-host')) ||
                             ':' || coalesce(port::text, '0'),
              database_key = lower(coalesce(db_type, 'unknown')) || '://' ||
                             lower(coalesce(nullif(target_host, ''), nullif(host_masked, ''), 'unknown-host')) ||
                             ':' || coalesce(port::text, '0') || '/' ||
                             lower(coalesce(nullif(service_mode, ''),
                                   CASE WHEN lower(coalesce(db_type,'')) = 'oracle' THEN 'service_name' ELSE 'database' END)) ||
                             '/' || lower(coalesce(nullif(service_name, ''), nullif(database_name, ''), ''))
            WHERE endpoint_key IS NULL OR database_key IS NULL
            """
        )
    )
    # mark known ODS peripheral aliases
    op.execute(
        sa.text(
            """
            UPDATE asset.asset_data_sources
            SET source_kind = 'legacy_alias',
                canonical_source_code = 'ods_8_216',
                business_labels = CASE source_code
                  WHEN 'ods_lis' THEN '["LIS","检验"]'::jsonb
                  WHEN 'ods_pacs' THEN '["PACS","影像"]'::jsonb
                  WHEN 'ods_emr' THEN '["EMR","病历"]'::jsonb
                  WHEN 'ods_ydhl' THEN '["YDHL","移动护理"]'::jsonb
                  WHEN 'ods_sm' THEN '["SM","手麻"]'::jsonb
                  ELSE business_labels
                END
            WHERE source_code IN ('ods_lis','ods_pacs','ods_emr','ods_ydhl','ods_sm')
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE asset.asset_data_sources
            SET source_kind = 'physical_connection',
                business_labels = coalesce(business_labels, '["DATA_CENTER","数据中心"]'::jsonb)
            WHERE source_code = 'ods_8_216'
            """
        )
    )
    op.create_index("ix_asset_data_sources_endpoint_key", "asset_data_sources", ["endpoint_key"], schema=SCHEMA)
    op.create_index("ix_asset_data_sources_database_key", "asset_data_sources", ["database_key"], schema=SCHEMA)
    op.create_index("ix_asset_data_sources_canonical", "asset_data_sources", ["canonical_source_code"], schema=SCHEMA)

    # ── schema inventory per connection ──
    op.create_table(
        "asset_source_schemas",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.Text(), nullable=False),
        sa.Column("business_labels", postgresql.JSONB(), nullable=True),
        sa.Column("table_count", sa.Integer(), server_default="0"),
        sa.Column("column_count", sa.Integer(), server_default="0"),
        sa.Column("last_collect_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("source_code", "schema_name", name="uq_asset_source_schemas_src_schema"),
        schema=SCHEMA,
    )
    op.create_index("ix_asset_source_schemas_source", "asset_source_schemas", ["source_code"], schema=SCHEMA)

    # ── ops template / run target snapshots ──
    for col in [
        sa.Column("target_connection_id", sa.BigInteger(), nullable=True),
        sa.Column("target_source_code", sa.Text(), nullable=True),
        sa.Column("target_database_key", sa.Text(), nullable=True),
        sa.Column("target_schema", sa.Text(), nullable=True),
    ]:
        op.add_column("asset_ops_tool_templates", col, schema=SCHEMA)

    for col in [
        sa.Column("target_connection_id", sa.BigInteger(), nullable=True),
        sa.Column("target_source_code", sa.Text(), nullable=True),
        sa.Column("target_database_key", sa.Text(), nullable=True),
        sa.Column("target_schema", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("confirmation_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("preview_params_hash", sa.Text(), nullable=True),
    ]:
        op.add_column("asset_ops_tool_runs", col, schema=SCHEMA)
    op.create_index("ix_ops_tool_runs_correlation", "asset_ops_tool_runs", ["correlation_id"], schema=SCHEMA)

    # ── medical import run extras ──
    op.add_column(
        "asset_dict_medical_import_runs",
        sa.Column("correlation_id", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_dict_medical_import_runs",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

    # ── optional unified ops event log (queryable without dumping audit JSON) ──
    op.create_table(
        "asset_ops_event_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_ref", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("operator", sa.Text(), nullable=True),
        sa.Column("target_connection_id", sa.BigInteger(), nullable=True),
        sa.Column("target_database_key", sa.Text(), nullable=True),
        sa.Column("target_source_code", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("batch_code", sa.Text(), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("summary_masked", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("event_id", name="uq_asset_ops_event_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_ops_event_module_action", "asset_ops_event_logs", ["module", "action"], schema=SCHEMA)
    op.create_index("ix_ops_event_correlation", "asset_ops_event_logs", ["correlation_id"], schema=SCHEMA)
    op.create_index("ix_ops_event_created", "asset_ops_event_logs", ["created_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_ops_event_created", table_name="asset_ops_event_logs", schema=SCHEMA)
    op.drop_index("ix_ops_event_correlation", table_name="asset_ops_event_logs", schema=SCHEMA)
    op.drop_index("ix_ops_event_module_action", table_name="asset_ops_event_logs", schema=SCHEMA)
    op.drop_table("asset_ops_event_logs", schema=SCHEMA)

    op.drop_column("asset_dict_medical_import_runs", "duration_ms", schema=SCHEMA)
    op.drop_column("asset_dict_medical_import_runs", "correlation_id", schema=SCHEMA)

    op.drop_index("ix_ops_tool_runs_correlation", table_name="asset_ops_tool_runs", schema=SCHEMA)
    for col in (
        "preview_params_hash",
        "confirmation_expires_at",
        "correlation_id",
        "target_schema",
        "target_database_key",
        "target_source_code",
        "target_connection_id",
    ):
        op.drop_column("asset_ops_tool_runs", col, schema=SCHEMA)
    for col in ("target_schema", "target_database_key", "target_source_code", "target_connection_id"):
        op.drop_column("asset_ops_tool_templates", col, schema=SCHEMA)

    op.drop_index("ix_asset_source_schemas_source", table_name="asset_source_schemas", schema=SCHEMA)
    op.drop_table("asset_source_schemas", schema=SCHEMA)

    op.drop_index("ix_asset_data_sources_canonical", table_name="asset_data_sources", schema=SCHEMA)
    op.drop_index("ix_asset_data_sources_database_key", table_name="asset_data_sources", schema=SCHEMA)
    op.drop_index("ix_asset_data_sources_endpoint_key", table_name="asset_data_sources", schema=SCHEMA)
    for col in (
        "last_collect_snapshot_id",
        "last_collect_at",
        "last_collect_status",
        "last_test_error_masked",
        "last_test_error_code",
        "last_test_latency_ms",
        "last_test_at",
        "last_test_status",
        "metadata_origin",
        "business_labels",
        "source_kind",
        "canonical_source_code",
        "database_key",
        "endpoint_key",
    ):
        op.drop_column("asset_data_sources", col, schema=SCHEMA)
