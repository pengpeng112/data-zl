"""149 P1a: 字段值域知识库三表 + 值域权限码 RBAC 种子。

手写迁移（禁 autogenerate）。三表：
  asset_column_value_domains            主表（一字段一码一现行语义，六元组唯一约束）
  asset_column_value_domain_evidences   证据一对多（多来源各留一条）
  asset_column_value_domain_versions    版本时间线（串行采纳，非并行假说）

权限码（149 §3）：value_domain.read / value_domain.submit / value_domain.confirm。
AI 协作角色 ai_user 仅授予 read+submit，绝不授予 confirm（AI 不得自行确认值域）。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b0c1d2e3f4a5"
down_revision = "i9e0f1a2b3c4"
branch_labels = None
depends_on = None

SCHEMA = "asset"

_PERMISSION_RESOURCES = [
    ("value_domain.read", "值域知识库查看", "value_domain", "read"),
    ("value_domain.submit", "值域候选提交", "value_domain", "submit"),
    ("value_domain.confirm", "值域人工确认", "value_domain", "confirm"),
]

# role_code -> 授权资源（action 固定 access，与 permissions.py 种子端点一致）
_ROLE_GRANTS = {
    "asset_viewer": ["value_domain.read"],
    "asset_editor": ["value_domain.read", "value_domain.submit", "value_domain.confirm"],
    "quality_admin": ["value_domain.read"],
    # ai_user 是 AI 协作角色：仅可提交 pending，禁止 confirm
    "ai_user": ["value_domain.read", "value_domain.submit"],
}


def upgrade() -> None:
    op.create_table(
        "asset_column_value_domains",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.Text(), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("column_name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("domain_kind", sa.Text(), nullable=False, server_default="enum"),
        sa.Column("scope_condition", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("conflict_status", sa.Text(), nullable=False, server_default="none"),
        sa.Column("confirmed_by", sa.Text()),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("current_version_id", sa.BigInteger()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "system_code",
            "source_code",
            "schema_name",
            "table_name",
            "column_name",
            "code",
            name="uq_asset_column_value_domains_key",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_column_value_domains_locate",
        "asset_column_value_domains",
        ["system_code", "schema_name", "table_name", "column_name"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_column_value_domains_status",
        "asset_column_value_domains",
        ["status", "conflict_status"],
        schema=SCHEMA,
    )

    op.create_table(
        "asset_column_value_domain_evidences",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_system", sa.Text()),
        sa.Column("observed_meaning", sa.Text()),
        sa.Column("method", sa.Text()),
        sa.Column("sample_count", sa.Integer()),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("actor", sa.Text()),
        sa.Column("snippet_ref", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_column_value_domain_evidences_domain",
        "asset_column_value_domain_evidences",
        ["domain_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "asset_column_value_domain_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("change_reason", sa.Text()),
        sa.Column("evidence_ref", sa.Text()),
        sa.Column("actor", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("domain_id", "version_no", name="uq_asset_value_domain_versions"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_column_value_domain_versions_domain",
        "asset_column_value_domain_versions",
        ["domain_id"],
        schema=SCHEMA,
    )

    # --- 权限码 RBAC 种子（幂等） ---
    for code, name_cn, module, action in _PERMISSION_RESOURCES:
        op.execute(
            sa.text(
                "INSERT INTO asset.asset_permission_resources "
                "(resource_code, resource_name_cn, module_code, action_code, enabled, sort_order) "
                "VALUES (:code, :name, :module, :action, true, 900) "
                "ON CONFLICT (resource_code) DO NOTHING"
            ).bindparams(code=code, name=name_cn, module=module, action=action)
        )
    for role_code, resources in _ROLE_GRANTS.items():
        for resource in resources:
            op.execute(
                sa.text(
                    "INSERT INTO asset.asset_role_permissions (role_code, resource, action) "
                    "VALUES (:role, :resource, 'access') "
                    "ON CONFLICT (role_code, resource, action) DO NOTHING"
                ).bindparams(role=role_code, resource=resource)
            )


def downgrade() -> None:
    # 先撤种子授权再删表（资源行保留至最后，避免中途残留孤儿授权）
    for role_code, resources in _ROLE_GRANTS.items():
        for resource in resources:
            op.execute(
                sa.text(
                    "DELETE FROM asset.asset_role_permissions "
                    "WHERE role_code = :role AND resource = :resource"
                ).bindparams(role=role_code, resource=resource)
            )
    op.execute(
        sa.text(
            "DELETE FROM asset.asset_permission_resources WHERE resource_code IN "
            "('value_domain.read', 'value_domain.submit', 'value_domain.confirm')"
        )
    )
    op.drop_index(
        "ix_asset_column_value_domain_versions_domain",
        table_name="asset_column_value_domain_versions",
        schema=SCHEMA,
    )
    op.drop_table("asset_column_value_domain_versions", schema=SCHEMA)
    op.drop_index(
        "ix_asset_column_value_domain_evidences_domain",
        table_name="asset_column_value_domain_evidences",
        schema=SCHEMA,
    )
    op.drop_table("asset_column_value_domain_evidences", schema=SCHEMA)
    op.drop_index(
        "ix_asset_column_value_domains_status",
        table_name="asset_column_value_domains",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_asset_column_value_domains_locate",
        table_name="asset_column_value_domains",
        schema=SCHEMA,
    )
    op.drop_table("asset_column_value_domains", schema=SCHEMA)
