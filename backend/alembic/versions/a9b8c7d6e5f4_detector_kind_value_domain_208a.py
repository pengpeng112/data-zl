"""208 A3（207 T08 + 207 链缺陷修复）：质量域 CHECK 约束扩展。

背景（浏览器实测发现，sqlite 纯逻辑测不出 DB CHECK）：
1. 174 迁移 d5e6f7a8b9c0 的 ck_asset_quality_detectors_kind 只允许
   probe_template/quality_rule/manual/external；207 T08 新增 value_domain 检测器
   后 API pattern 已扩但 DB 约束未跟 → 创建 value_domain 检测器 500。
2. 174 迁移的 ck_asset_quality_observations_source 不含 'quality_run'——
   207 执行链每轮运行写观测（source_kind=quality_run）在 PG 上必被拒；
   207 隔离库集成测试未覆盖「执行→写观测」路径，故未暴露。本迁移补上。

Revision ID: a9b8c7d6e5f4
Revises: c4d5e6f7b8a9
Create Date: 2026-09-29
"""

from alembic import op

revision = "a9b8c7d6e5f4"
down_revision = "c4d5e6f7b8a9"
branch_labels = None
depends_on = None

SCHEMA = "asset"
KINDS_NEW = "('probe_template','quality_rule','value_domain','manual','external')"
KINDS_OLD = "('probe_template','quality_rule','manual','external')"
SOURCE_NEW = "('probe_finding','probe_run','quality_finding','quality_run','manual','external')"
SOURCE_OLD = "('probe_finding','probe_run','quality_finding','manual','external')"


def _replace_check(table: str, name: str, column: str, allowed: str) -> None:
    op.execute(
        f"ALTER TABLE {SCHEMA}.{table} DROP CONSTRAINT IF EXISTS {name}"
    )
    op.create_check_constraint(name, table, f"{column} IN {allowed}", schema=SCHEMA)


def upgrade() -> None:
    _replace_check(
        "asset_quality_control_detectors", "ck_asset_quality_detectors_kind",
        "detector_kind", KINDS_NEW,
    )
    _replace_check(
        "asset_quality_observations", "ck_asset_quality_observations_source",
        "source_kind", SOURCE_NEW,
    )


def downgrade() -> None:
    # 回退前须确认无 value_domain 检测器 / quality_run 观测残留，否则约束回不去
    # （显式失败优于静默丢数据）
    _replace_check(
        "asset_quality_control_detectors", "ck_asset_quality_detectors_kind",
        "detector_kind", KINDS_OLD,
    )
    _replace_check(
        "asset_quality_observations", "ck_asset_quality_observations_source",
        "source_kind", SOURCE_OLD,
    )
