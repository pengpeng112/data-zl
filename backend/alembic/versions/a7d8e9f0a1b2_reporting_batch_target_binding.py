"""R189-T1 A03/K02: batch target binding for scoped COMMIT_UNKNOWN freeze.

Additive change only, in asset schema:
- asset_reporting_batches.target_instance / tenant / target_table（可空）：
  批次的目标绑定。COMMIT_UNKNOWN 的冻结范围按（实例+机构+表）结构化判定，
  单表提交不明只冻结同目标表的重叠写，不再冻结全批；三列为空的批次视为
  范围不可判定，走全局保护+人工定位告警（recovery 层语义）。

Does not modify any published migration text; chains after f4a5b6c7d8e9.
Isolated-DB verification pending until a cleanable isolated PG is confirmed;
do NOT run against production.

Revision ID: a7d8e9f0a1b2
Revises: f4a5b6c7d8e9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7d8e9f0a1b2"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    op.add_column(
        "asset_reporting_batches",
        sa.Column("target_instance", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_reporting_batches",
        sa.Column("tenant", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_reporting_batches",
        sa.Column("target_table", sa.Text(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("asset_reporting_batches", "target_table", schema=SCHEMA)
    op.drop_column("asset_reporting_batches", "tenant", schema=SCHEMA)
    op.drop_column("asset_reporting_batches", "target_instance", schema=SCHEMA)
