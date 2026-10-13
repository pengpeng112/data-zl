"""210 S1：数据集安全分类分级闭环——契约增列、版本成员与撤销账本。

对应 210 计划 F01/F05/F07/F08/F10/F11 的模型侧最小迁移（手写，禁 autogenerate）：

1. asset_ds_classifications 增列：classification_schema_version/object_id/
   object_physical_key/label_source/evidence/proposal_hash/effective_at/
   retention_until；新部分唯一索引 uq_ds_cls_single_active（同对象仅一条 active，
   服务层 expected_version CAS 的并发兜底）；label_source CHECK。
2. asset_ds_grants：approved_by 放开为可空（pending 授权审批主体后置），
   增 requested_by/approved_at/project_code（F05 职责分离）；status CHECK 扩
   pending/rejected。
3. asset_ds_dataset_versions 增 frozen_by（冻结执行主体，审批分离对照）。
4. 新表 asset_ds_version_members：版本↔具体 fact 行冻结成员（F07 版本隔离）。
5. 新表 asset_ds_revocation_ledger：撤销事件账本（F11 备份恢复重放）。
6. asset_ds_exports 增列：requested_by/approved_by/approved_at/review_note/
   purpose_code/project_code/approval_hash/artifact_path/artifact_bytes/
   requested_fields/generation_error（F08 真实导出闭环）；status CHECK 扩
   review_pending/generating/failed。

非空降级保护：downgrade 删除 210 增列前须确认无依赖行；对已有 pending 授权回退
approved_by NOT NULL 前，统一以 'migrated' 回填（不丢数据、不破坏旧 active 行）。

Revision ID: c0d1e2f3a4b5
Revises: a9b8c7d6e5f4
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c0d1e2f3a4b5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None

SCHEMA = "asset"

# (列名, 类型, server_default 文本或 None, nullable)
CLS_ADD_COLUMNS = [
    ("classification_schema_version", sa.Text(), "'b02_v1'", False),
    ("object_id", sa.BigInteger(), None, True),
    ("object_physical_key", JSONB(), None, True),
    ("label_source", sa.Text(), "'manual'", False),
    ("evidence", JSONB(), None, True),
    ("proposal_hash", sa.Text(), None, True),
    ("effective_at", sa.TIMESTAMP(timezone=True), None, True),
    ("retention_until", sa.TIMESTAMP(timezone=True), None, True),
]

GRANT_ADD_COLUMNS = [
    ("requested_by", sa.Text(), None, True),
    ("approved_at", sa.TIMESTAMP(timezone=True), None, True),
    ("project_code", sa.Text(), None, True),
]

EXPORT_ADD_COLUMNS = [
    ("requested_by", sa.Text(), None, True),
    ("approved_by", sa.Text(), None, True),
    ("approved_at", sa.TIMESTAMP(timezone=True), None, True),
    ("review_note", sa.Text(), None, True),
    ("purpose_code", sa.Text(), None, True),
    ("project_code", sa.Text(), None, True),
    ("approval_hash", sa.Text(), None, True),
    ("artifact_path", sa.Text(), None, True),
    ("artifact_bytes", sa.BigInteger(), None, True),
    ("requested_fields", JSONB(), None, True),
    ("generation_error", sa.Text(), None, True),
]


def _add_columns(table: str, columns: list) -> None:
    for name, type_, srv_default, nullable in columns:
        op.add_column(
            table,
            sa.Column(name, type_, nullable=nullable,
                      **({"server_default": sa.text(srv_default)} if srv_default else {})),
            schema=SCHEMA,
        )


def upgrade() -> None:
    # 1) 分类表增列 + 约束/索引
    _add_columns("asset_ds_classifications", CLS_ADD_COLUMNS)
    # label_source CHECK（旧行默认 manual，满足约束）
    op.create_check_constraint(
        "ck_ds_cls_source", "asset_ds_classifications",
        "label_source IN ('manual','candidate','confirmed')", schema=SCHEMA)
    # 同对象单 active 部分唯一索引（生产 ds 表 0 行；隔离库由 TRUNCATE 清理后建索引）
    op.create_index(
        "uq_ds_cls_single_active", "asset_ds_classifications",
        ["object_type", "object_ref"], unique=True, schema=SCHEMA,
        postgresql_where=sa.text("status = 'active'"))

    # 2) 授权表：approved_by 可空 + 增列 + status CHECK
    op.alter_column("asset_ds_grants", "approved_by", existing_type=sa.Text(),
                    nullable=True, schema=SCHEMA)
    _add_columns("asset_ds_grants", GRANT_ADD_COLUMNS)
    op.execute(
        f"ALTER TABLE {SCHEMA}.asset_ds_grants DROP CONSTRAINT IF EXISTS ck_ds_grant_status_210")
    op.create_check_constraint(
        "ck_ds_grant_status_210", "asset_ds_grants",
        "status IN ('pending','active','rejected','revoked','expired')", schema=SCHEMA)

    # 3) 版本表：冻结人
    op.add_column("asset_ds_dataset_versions",
                  sa.Column("frozen_by", sa.Text()), schema=SCHEMA)

    # 4) 版本冻结成员表
    op.create_table(
        "asset_ds_version_members",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("dataset_version_id", sa.BigInteger, nullable=False),
        sa.Column("fact_id", sa.BigInteger, nullable=False),
        sa.Column("fact_key", sa.Text, nullable=False),
        sa.Column("content_sha256", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_version_id", "fact_id", name="uq_ds_vm_fact"),
        schema=SCHEMA,
    )
    op.create_index("ix_ds_vm_version", "asset_ds_version_members",
                    ["dataset_version_id"], schema=SCHEMA)

    # 5) 撤销账本表
    op.create_table(
        "asset_ds_revocation_ledger",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("revocation_type", sa.Text, nullable=False),
        sa.Column("target_ref", sa.Text, nullable=False),
        sa.Column("target_id", sa.BigInteger),
        sa.Column("reason", sa.Text),
        sa.Column("revoked_by", sa.Text),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("replayed", sa.Text, nullable=False, server_default="false"),
        sa.Column("replayed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("replay_result", JSONB),
        schema=SCHEMA,
    )
    op.create_index("ix_ds_revocation_target", "asset_ds_revocation_ledger",
                    ["revocation_type", "target_ref"], schema=SCHEMA)
    op.create_index("ix_ds_revocation_pending", "asset_ds_revocation_ledger",
                    ["replayed"], schema=SCHEMA)

    # 6) 导出表增列 + status CHECK（旧枚举全部保留，仅扩新状态）
    _add_columns("asset_ds_exports", EXPORT_ADD_COLUMNS)
    op.execute(
        f"ALTER TABLE {SCHEMA}.asset_ds_exports DROP CONSTRAINT IF EXISTS ck_ds_export_status_210")
    op.create_check_constraint(
        "ck_ds_export_status_210", "asset_ds_exports",
        "status IN ('requested','review_pending','approved','generating','generated',"
        "'downloaded','expired','revoked','failed')", schema=SCHEMA)


def downgrade() -> None:
    # 反向拆除：先约束/索引后列；非空降级保护——approved_by 回 NOT NULL 前回填。
    op.execute(
        f"ALTER TABLE {SCHEMA}.asset_ds_exports DROP CONSTRAINT IF EXISTS ck_ds_export_status_210")
    for name, _, _, _ in reversed(EXPORT_ADD_COLUMNS):
        op.drop_column("asset_ds_exports", name, schema=SCHEMA)

    op.drop_index("ix_ds_revocation_pending", table_name="asset_ds_revocation_ledger", schema=SCHEMA)
    op.drop_index("ix_ds_revocation_target", table_name="asset_ds_revocation_ledger", schema=SCHEMA)
    op.drop_table("asset_ds_revocation_ledger", schema=SCHEMA)

    op.drop_index("ix_ds_vm_version", table_name="asset_ds_version_members", schema=SCHEMA)
    op.drop_table("asset_ds_version_members", schema=SCHEMA)

    op.drop_column("asset_ds_dataset_versions", "frozen_by", schema=SCHEMA)

    op.execute(
        f"ALTER TABLE {SCHEMA}.asset_ds_grants DROP CONSTRAINT IF EXISTS ck_ds_grant_status_210")
    for name, _, _, _ in reversed(GRANT_ADD_COLUMNS):
        op.drop_column("asset_ds_grants", name, schema=SCHEMA)
    op.execute(
        f"UPDATE {SCHEMA}.asset_ds_grants SET approved_by='migrated' WHERE approved_by IS NULL")
    op.alter_column("asset_ds_grants", "approved_by", existing_type=sa.Text(),
                    nullable=False, schema=SCHEMA)

    op.drop_index("uq_ds_cls_single_active", table_name="asset_ds_classifications", schema=SCHEMA)
    op.execute(
        f"ALTER TABLE {SCHEMA}.asset_ds_classifications DROP CONSTRAINT IF EXISTS ck_ds_cls_source")
    for name, _, _, _ in reversed(CLS_ADD_COLUMNS):
        op.drop_column("asset_ds_classifications", name, schema=SCHEMA)
