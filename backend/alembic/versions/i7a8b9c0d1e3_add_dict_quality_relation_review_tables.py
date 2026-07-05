"""add dict_general / quality_tasks_metrics / relation_reviews tables

Revision ID: i7a8b9c0d1e3
Revises: h6a7b8c9d0e2
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "i7a8b9c0d1e3"
down_revision: Union[str, None] = "h6a7b8c9d0e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P13 通用字典 5 tables
    op.create_table(
        "asset_dict_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category_code", sa.Text(), unique=True, nullable=False),
        sa.Column("category_name_cn", sa.Text(), nullable=False),
        sa.Column("standard_system", sa.Text()),
        sa.Column("description_cn", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    op.create_table(
        "asset_dict_standard_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("standard_code", sa.Text(), nullable=False),
        sa.Column("standard_name_cn", sa.Text(), nullable=False),
        sa.Column("standard_name_en", sa.Text()),
        sa.Column("parent_code", sa.Text()),
        sa.Column("pinyin_code", sa.Text()),
        sa.Column("wubi_code", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active"),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("description_cn", sa.Text()),
        sa.Column("extra", postgresql.JSONB()),
        sa.UniqueConstraint("category_code", "standard_code"),
        schema="asset",
    )

    op.create_table(
        "asset_dict_system_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("namespace_name", sa.Text()),
        sa.Column("source_table", sa.Text()),
        sa.Column("source_key_column", sa.Text()),
        sa.Column("source_name_column", sa.Text()),
        sa.Column("system_item_code", sa.Text(), nullable=False),
        sa.Column("system_item_name_cn", sa.Text(), nullable=False),
        sa.Column("raw_status", sa.Text()),
        sa.Column("raw_extra", postgresql.JSONB()),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("category_code", "system_code", "system_item_code"),
        schema="asset",
    )

    op.create_table(
        "asset_dict_item_mappings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("standard_code", sa.Text()),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("system_item_code", sa.Text(), nullable=False),
        sa.Column("mapping_type", sa.Text(), server_default="manual"),
        sa.Column("confidence", sa.Text()),
        sa.Column("review_status", sa.Text(), server_default="draft"),
        sa.Column("reviewer", sa.Text()),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    op.create_table(
        "asset_dict_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("version_no", sa.Text(), nullable=False),
        sa.Column("version_name_cn", sa.Text()),
        sa.Column("publish_status", sa.Text(), server_default="draft"),
        sa.Column("published_by", sa.Text()),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("note", sa.Text()),
        sa.UniqueConstraint("category_code", "version_no"),
        schema="asset",
    )

    # P5.4 质量任务/指标 2 tables
    op.create_table(
        "asset_quality_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("target_scope", sa.Text()),
        sa.Column("execution_mode", sa.Text(), server_default="metadata_only"),
        sa.Column("schedule_cron", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("last_run_status", sa.Text()),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    op.create_table(
        "asset_quality_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("namespace_name", sa.Text()),
        sa.Column("table_name", sa.Text()),
        sa.Column("column_name", sa.Text()),
        sa.Column("metric_code", sa.Text()),
        sa.Column("metric_value", sa.Integer()),
        sa.Column("metric_text", sa.Text()),
        sa.Column("measured_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    # P9 关系复核工作台 1 table
    op.create_table(
        "asset_relation_reviews",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("relation_scope", sa.Text(), nullable=False, server_default="formal"),
        sa.Column("source_relation_table", sa.Text()),
        sa.Column("source_relation_id", sa.BigInteger()),
        sa.Column("from_system_code", sa.Text()),
        sa.Column("from_source_code", sa.Text()),
        sa.Column("from_table", sa.Text(), nullable=False),
        sa.Column("from_columns", sa.Text()),
        sa.Column("to_system_code", sa.Text()),
        sa.Column("to_source_code", sa.Text()),
        sa.Column("to_table", sa.Text(), nullable=False),
        sa.Column("to_columns", sa.Text()),
        sa.Column("join_condition", sa.Text()),
        sa.Column("relation_desc_cn", sa.Text()),
        sa.Column("business_logic_cn", sa.Text()),
        sa.Column("confidence", sa.Text()),
        sa.Column("validation_status", sa.Text()),
        sa.Column("review_status", sa.Text(), server_default="draft"),
        sa.Column("reviewer", sa.Text()),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("source_evidence", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_relation_reviews", schema="asset")
    op.drop_table("asset_quality_metrics", schema="asset")
    op.drop_table("asset_quality_tasks", schema="asset")
    op.drop_table("asset_dict_versions", schema="asset")
    op.drop_table("asset_dict_item_mappings", schema="asset")
    op.drop_table("asset_dict_system_items", schema="asset")
    op.drop_table("asset_dict_standard_items", schema="asset")
    op.drop_table("asset_dict_categories", schema="asset")
