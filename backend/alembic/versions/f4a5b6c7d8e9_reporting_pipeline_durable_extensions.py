"""R189-T1 R02: reporting pipeline durable-state extensions.

Additive changes only, in asset schema:
- asset_reporting_watermarks.continuous_through (最后连续完成日，与捕获
  水位分开；缺口未闭合不得推进——RT1-025)。
- asset_reporting_version_evidence（耐久版本账：键含目标实例/租户/表，
  跨表同 ID 不互污染——RT1-014）。
- asset_reporting_quarantine_groups（隔离组账：坏组工单化留痕）。

Does not modify any published migration text; chains after e3f4a5b6c7d8.
Isolated-DB verification pending (RT1-003/004/005) until a cleanable
isolated PG is confirmed; do NOT run against production.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"


def upgrade() -> None:
    op.add_column(
        "asset_reporting_watermarks",
        sa.Column("continuous_through", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_table(
        "asset_reporting_version_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("target_instance", sa.Text(), nullable=False),
        sa.Column("tenant", sa.Text(), nullable=False),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("stable_key", sa.Text(), nullable=False),
        sa.Column("version_value", sa.Text(), nullable=False),
        sa.Column("version_kind", sa.String(16), nullable=True),
        sa.Column("applied_operation_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "target_instance", "tenant", "canonical_table", "stable_key",
            name="uq_asset_reporting_version_key",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_version_table", "asset_reporting_version_evidence",
        ["canonical_table"], schema=SCHEMA,
    )
    op.create_table(
        "asset_reporting_quarantine_groups",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("canonical_table", sa.Text(), nullable=False),
        sa.Column("group_key", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("rows_quarantined", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("detail_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolution_evidence", sa.Text(), nullable=True),
        sa.UniqueConstraint("batch_id", "group_key",
                            name="uq_asset_reporting_quarantine"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_reporting_quarantine_state", "asset_reporting_quarantine_groups",
        ["canonical_table", "state"], schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_reporting_quarantine_state",
        table_name="asset_reporting_quarantine_groups", schema=SCHEMA,
    )
    op.drop_table("asset_reporting_quarantine_groups", schema=SCHEMA)
    op.drop_index(
        "ix_asset_reporting_version_table",
        table_name="asset_reporting_version_evidence", schema=SCHEMA,
    )
    op.drop_table("asset_reporting_version_evidence", schema=SCHEMA)
    op.drop_column(
        "asset_reporting_watermarks", "continuous_through", schema=SCHEMA,
    )
