"""extend quality_rule/finding/check_run with hospital-grade QC fields

Revision ID: k8d9e0f1a2b3
Revises: j7c8d9e0f1a2
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "k8d9e0f1a2b3"
down_revision: Union[str, None] = "j7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # asset_quality_rules - 18 new columns
    rule_cols = [
        ("rule_name", sa.Text()),
        ("rule_category", sa.Text()),
        ("check_scope", sa.Text()),
        ("constraint_level", sa.Text()),
        ("business_domain", sa.Text()),
        ("system_code", sa.Text()),
        ("source_code", sa.Text()),
        ("namespace_name", sa.Text()),
        ("target_table", sa.Text()),
        ("target_field", sa.Text()),
        ("related_table", sa.Text()),
        ("related_field", sa.Text()),
        ("check_sql", sa.Text()),
        ("error_condition", sa.Text()),
        ("error_level", sa.Text()),
        ("sample_limit", sa.Integer()),
        ("version", sa.Integer()),
        ("remark", sa.Text()),
    ]
    rule_defaults = {
        "constraint_level": "WARN",
        "error_level": "minor",
        "sample_limit": "20",
        "version": "1",
    }
    for col_name, col_type in rule_cols:
        kwargs = {}
        if col_name in rule_defaults:
            kwargs["server_default"] = rule_defaults[col_name]
        op.add_column("asset_quality_rules", sa.Column(col_name, col_type, **kwargs), schema="asset")

    # Backfill existing 10 seed rules
    op.execute("""
        UPDATE asset.asset_quality_rules SET
            rule_category = CASE rule_code
                WHEN 'REL_ORPHAN_RATE' THEN 'RELATION'
                WHEN 'TABLE_NO_DOMAIN' THEN 'COMPLETE'
                WHEN 'COL_NULL_COMMENT' THEN 'COMPLETE'
                WHEN 'REL_NOT_VERIFIED' THEN 'COMPLETE'
                WHEN 'CANDIDATE_NOT_REVIEWED' THEN 'COMPLETE'
                WHEN 'TABLE_ZERO_COLUMNS' THEN 'COMPLETE'
                WHEN 'TABLE_NO_CN_NAME' THEN 'STANDARD'
                WHEN 'COLUMN_NO_CN_NAME' THEN 'STANDARD'
                WHEN 'SOURCE_CONNECTIVITY' THEN 'COMPLETE'
                WHEN 'SOURCE_METADATA_STALE' THEN 'COMPLETE'
            END,
            check_scope = CASE rule_code
                WHEN 'REL_ORPHAN_RATE' THEN 'TABLE_RELATION'
                WHEN 'SOURCE_CONNECTIVITY' THEN 'SYSTEM_CROSS'
                WHEN 'SOURCE_METADATA_STALE' THEN 'SYSTEM_CROSS'
                ELSE 'TABLE_INNER'
            END,
            constraint_level = CASE rule_code
                WHEN 'TABLE_ZERO_COLUMNS' THEN 'HARD'
                WHEN 'SOURCE_CONNECTIVITY' THEN 'HARD'
                WHEN 'CANDIDATE_NOT_REVIEWED' THEN 'INFO'
                WHEN 'COL_NULL_COMMENT' THEN 'WARN'
                WHEN 'TABLE_NO_CN_NAME' THEN 'WARN'
                WHEN 'COLUMN_NO_CN_NAME' THEN 'WARN'
                WHEN 'SOURCE_METADATA_STALE' THEN 'WARN'
                ELSE 'SOFT'
            END,
            error_level = CASE rule_code
                WHEN 'TABLE_ZERO_COLUMNS' THEN 'major'
                WHEN 'SOURCE_CONNECTIVITY' THEN 'major'
                WHEN 'REL_ORPHAN_RATE' THEN 'major'
                WHEN 'TABLE_NO_DOMAIN' THEN 'minor'
                ELSE 'minor'
            END,
            version = 1
        WHERE rule_category IS NULL
    """)

    # asset_quality_findings - 13 new columns
    finding_cols = [
        ("run_id", sa.BigInteger()),
        ("system_code", sa.Text()),
        ("source_code", sa.Text()),
        ("namespace_name", sa.Text()),
        ("table_name", sa.Text()),
        ("column_name", sa.Text()),
        ("total_cnt", sa.Integer()),
        ("error_cnt", sa.Integer()),
        ("error_rate", sa.Integer()),
        ("sample_data", postgresql.JSONB()),
        ("assigned_to", sa.Text()),
        ("confirmed_by", sa.Text()),
        ("rectification_status", sa.Text()),
    ]
    finding_defaults = {"rectification_status": "open"}
    for col_name, col_type in finding_cols:
        kwargs = {}
        if col_name in finding_defaults:
            kwargs["server_default"] = finding_defaults[col_name]
        op.add_column("asset_quality_findings", sa.Column(col_name, col_type, **kwargs), schema="asset")

    # asset_quality_check_runs - 7 new columns
    run_cols = [
        ("task_id", sa.BigInteger()),
        ("system_code", sa.Text()),
        ("source_code", sa.Text()),
        ("total_records", sa.Integer()),
        ("error_records", sa.Integer()),
        ("pass_rate", sa.Integer()),
        ("failed_reason", sa.Text()),
    ]
    for col_name, col_type in run_cols:
        op.add_column("asset_quality_check_runs", sa.Column(col_name, col_type), schema="asset")


def downgrade() -> None:
    rule_cols = ["rule_name","rule_category","check_scope","constraint_level","business_domain",
                 "system_code","source_code","namespace_name","target_table","target_field",
                 "related_table","related_field","check_sql","error_condition","error_level",
                 "sample_limit","version","remark"]
    finding_cols = ["run_id","system_code","source_code","namespace_name","table_name",
                    "column_name","total_cnt","error_cnt","error_rate","sample_data",
                    "assigned_to","confirmed_by","rectification_status"]
    run_cols = ["task_id","system_code","source_code","total_records","error_records",
                "pass_rate","failed_reason"]
    for c in rule_cols:
        op.drop_column("asset_quality_rules", c, schema="asset")
    for c in finding_cols:
        op.drop_column("asset_quality_findings", c, schema="asset")
    for c in run_cols:
        op.drop_column("asset_quality_check_runs", c, schema="asset")
