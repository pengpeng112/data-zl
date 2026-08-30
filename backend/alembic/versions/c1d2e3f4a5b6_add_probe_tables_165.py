"""165 E1: 数据问题 AI 探查两表 + probe.finding.read 权限种子。

手写迁移（禁 autogenerate）。两表（round-4 A1/A2 裁决定稿）：
  asset_probe_runs      每轮探查执行（run_id 唯一，metrics_summary 含未越阈全指标）
  asset_probe_findings  问题身份一行（唯一键=probe_type+system_pair+object_key_digest
                        +metric_name，**不含 window**——同窗重跑幂等更新、新窗重跑
                        更新观测并触发复发判定；object_key_digest=sha256(object_desc)
                        前 32 hex 防 btree 超限）

权限码（A8 裁决，149 迁移种子先例）：probe.finding.read——platform_admin/
quality_admin/ai_user/asset_viewer 均授 read（探查域归质量线；probe.finding.manage
由 166 F7 补）。security_audit 硬编码清单（test_security_audit.py）同步。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None

SCHEMA = "asset"

_PERMISSION_RESOURCES = [
    ("probe.finding.read", "探查问题查看", "probe", "read"),
]

# A8 裁决角色集：探查发现只读面向质量线与 AI 协作
_ROLE_GRANTS = {
    "platform_admin": ["probe.finding.read"],
    "quality_admin": ["probe.finding.read"],
    "ai_user": ["probe.finding.read"],
    "asset_viewer": ["probe.finding.read"],
}


def upgrade() -> None:
    op.create_table(
        "asset_probe_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("probe_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finding_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finding_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relapse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics_summary", JSONB()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    op.create_table(
        "asset_probe_findings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("probe_type", sa.String(16), nullable=False),
        sa.Column("system_pair", sa.String(64), nullable=False),
        sa.Column("object_desc", sa.String(512), nullable=False),
        sa.Column("object_key_digest", sa.String(32), nullable=False),
        sa.Column("metric_name", sa.String(128), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6)),
        sa.Column("metric_unit", sa.String(16)),
        sa.Column("threshold", sa.Numeric(18, 6)),
        sa.Column("window_start", sa.Date()),
        sa.Column("window_end", sa.Date()),
        sa.Column("severity", sa.String(4)),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("first_seen_run", sa.String(64)),
        sa.Column("last_seen_run", sa.String(64)),
        sa.Column("relapse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_sql", sa.Text()),
        sa.Column("evidence_digest", sa.String(64)),
        sa.Column("resolved_by", sa.String(64)),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "probe_type", "system_pair", "object_key_digest", "metric_name",
            name="uq_asset_probe_findings_identity",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_probe_findings_status", "asset_probe_findings", ["status"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_probe_findings_severity", "asset_probe_findings", ["severity"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_probe_findings_probe_type", "asset_probe_findings", ["probe_type"], schema=SCHEMA
    )
    op.create_index(
        "ix_asset_probe_findings_last_seen_run", "asset_probe_findings", ["last_seen_run"], schema=SCHEMA
    )

    # --- 权限码种子（幂等，149 先例） ---
    for code, name_cn, module, action in _PERMISSION_RESOURCES:
        op.execute(
            sa.text(
                "INSERT INTO asset.asset_permission_resources "
                "(resource_code, resource_name_cn, module_code, action_code, enabled, sort_order) "
                "VALUES (:code, :name, :module, :action, true, 910) "
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
            "DELETE FROM asset.asset_permission_resources "
            "WHERE resource_code = 'probe.finding.read'"
        )
    )
    op.drop_index(
        "ix_asset_probe_findings_last_seen_run", table_name="asset_probe_findings", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_probe_findings_probe_type", table_name="asset_probe_findings", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_probe_findings_severity", table_name="asset_probe_findings", schema=SCHEMA
    )
    op.drop_index(
        "ix_asset_probe_findings_status", table_name="asset_probe_findings", schema=SCHEMA
    )
    op.drop_table("asset_probe_findings", schema=SCHEMA)
    op.drop_table("asset_probe_runs", schema=SCHEMA)
