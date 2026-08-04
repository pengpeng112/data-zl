"""临床诊断映射导入暂存、推送计划和执行记录表（101号）。

新增四张表：
- asset_dict_medical_import_rows: OCR/Excel 暂存行
- asset_dict_medical_push_plans: 服务端不可篡改推送计划
- asset_dict_medical_push_actions: 结构化业务动作
- asset_dict_medical_push_runs: 分系统事务包执行记录

禁止 autogenerate，upgrade/downgrade 全手写。

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    op.create_table(
        "asset_dict_medical_import_rows",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("import_run_id", sa.BigInteger(), nullable=False),
        sa.Column("source_file_name", sa.Text()),
        sa.Column("source_file_sha256", sa.Text()),
        sa.Column("source_sheet", sa.Text()),
        sa.Column("source_row_no", sa.Integer(), nullable=False),
        sa.Column("row_hash", sa.Text()),
        sa.Column("raw_dict_attribute", sa.Text()),
        sa.Column("raw_hospital_code", sa.Text()),
        sa.Column("raw_hospital_name", sa.Text()),
        sa.Column("raw_national_clinical_code", sa.Text()),
        sa.Column("raw_national_clinical_name", sa.Text()),
        sa.Column("raw_insurance_code", sa.Text()),
        sa.Column("raw_insurance_name", sa.Text()),
        sa.Column("norm_dict_attribute", sa.Text()),
        sa.Column("norm_hospital_code", sa.Text()),
        sa.Column("norm_hospital_name", sa.Text()),
        sa.Column("norm_national_clinical_code", sa.Text()),
        sa.Column("norm_national_clinical_name", sa.Text()),
        sa.Column("norm_insurance_code", sa.Text()),
        sa.Column("norm_insurance_name", sa.Text()),
        sa.Column("insurance_mapping_status", sa.Text(), server_default="valid"),
        sa.Column("validation_status", sa.Text(), server_default="valid"),
        sa.Column("validation_errors", JSONB()),
        sa.Column("diff_type", sa.Text(), server_default="new"),
        sa.Column("review_status", sa.Text(), server_default="pending"),
        sa.Column("reviewer", sa.Text()),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("merged_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("merged_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_run_id", "source_row_no"),
        schema=SCHEMA,
    )
    op.create_index("ix_dict_import_rows_run", "asset_dict_medical_import_rows",
                    ["import_run_id"], schema=SCHEMA)
    op.create_index("ix_dict_import_rows_review", "asset_dict_medical_import_rows",
                    ["review_status"], schema=SCHEMA)

    op.create_table(
        "asset_dict_medical_push_plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_code", sa.Text(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("target_systems", JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft"),
        sa.Column("platform_data_version", sa.Text()),
        sa.Column("content_hash", sa.Text()),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("item_count", sa.Integer(), server_default="0"),
        sa.Column("created_by", sa.Text()),
        sa.Column("approved_by", sa.Text()),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("approval_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_code"),
        schema=SCHEMA,
    )

    op.create_table(
        "asset_dict_medical_push_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("target_system", sa.Text(), nullable=False),
        sa.Column("target_source_code", sa.Text()),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("item_name_cn", sa.Text()),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB()),
        sa.Column("status", sa.Text(), server_default="planned"),
        sa.Column("diff_type", sa.Text()),
        sa.Column("conflict_detail", JSONB()),
        sa.Column("run_id", sa.BigInteger()),
        sa.Column("error_masked", sa.Text()),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "target_system", "item_code", "action_type"),
        schema=SCHEMA,
    )
    op.create_index("ix_dict_push_actions_plan", "asset_dict_medical_push_actions",
                    ["plan_id"], schema=SCHEMA)

    op.create_table(
        "asset_dict_medical_push_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("target_system", sa.Text(), nullable=False),
        sa.Column("target_source_code", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending"),
        sa.Column("total_actions", sa.Integer(), server_default="0"),
        sa.Column("succeeded_count", sa.Integer(), server_default="0"),
        sa.Column("failed_count", sa.Integer(), server_default="0"),
        sa.Column("skipped_count", sa.Integer(), server_default="0"),
        sa.Column("reconcile_result", JSONB()),
        sa.Column("error_masked", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_dict_push_runs_plan", "asset_dict_medical_push_runs",
                    ["plan_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("asset_dict_medical_push_runs", schema=SCHEMA)
    op.drop_table("asset_dict_medical_push_actions", schema=SCHEMA)
    op.drop_table("asset_dict_medical_push_plans", schema=SCHEMA)
    op.drop_table("asset_dict_medical_import_rows", schema=SCHEMA)