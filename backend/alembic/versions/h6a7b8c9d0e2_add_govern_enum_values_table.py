"""add_govern_enum_values_table

Revision ID: h6a7b8c9d0e2
Revises: g6a7b8c9d0e1
Create Date: 2026-07-04 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h6a7b8c9d0e2"
down_revision: Union[str, Sequence[str], None] = "g6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUM_SEEDS = [
    ("approval_status", "draft", "草稿"),
    ("approval_status", "pending", "待审批"),
    ("approval_status", "approved", "已通过"),
    ("approval_status", "rejected", "已拒绝"),
    ("approval_status", "executed", "已执行"),
    ("approval_status", "failed", "执行失败"),
    ("approval_status", "cancelled", "已取消"),
    ("review_status", "draft", "草稿"),
    ("review_status", "reviewing", "审核中"),
    ("review_status", "approved", "已通过"),
    ("review_status", "rejected", "已拒绝"),
    ("review_status", "deprecated", "已废弃"),
    ("review_status", "unreviewed", "未审核"),
    ("validation_status", "verified", "已验证"),
    ("validation_status", "manual_reviewed", "人工复核"),
    ("validation_status", "rejected", "已拒绝"),
    ("validation_status", "needs_check", "需检查"),
    ("account_status", "active", "活跃"),
    ("account_status", "disabled", "已停用"),
    ("account_status", "locked", "已锁定"),
    ("account_status", "unknown", "未知"),
    ("execution_mode", "readonly_sql", "只读SQL"),
    ("execution_mode", "whitelist_dml", "白名单DML"),
    ("execution_mode", "stored_procedure", "存储过程"),
    ("execution_mode", "http_api", "HTTP接口"),
    ("execution_mode", "sync_executor", "同步执行器"),
    ("execution_mode", "manual_step", "人工步骤"),
    ("severity", "info", "信息"),
    ("severity", "low", "低"),
    ("severity", "medium", "中"),
    ("severity", "high", "高"),
    ("severity", "critical", "严重"),
]


def upgrade() -> None:
    s = "asset"

    op.create_table(
        "asset_govern_enum_values",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("enum_code", sa.Text(), nullable=False),
        sa.Column("value_code", sa.Text(), nullable=False),
        sa.Column("value_name_cn", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("description", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("enum_code", "value_code"),
        schema=s,
    )

    # seed enum values
    op.execute(
        "INSERT INTO asset.asset_govern_enum_values (enum_code, value_code, value_name_cn) VALUES "
        + ", ".join(f"('{ec}', '{vc}', '{vn}')" for ec, vc, vn in ENUM_SEEDS)
    )


def downgrade() -> None:
    op.drop_table("asset_govern_enum_values", schema="asset")
