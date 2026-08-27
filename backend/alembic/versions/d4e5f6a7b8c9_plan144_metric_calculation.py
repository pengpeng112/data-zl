"""plan144 S4: metric calculation contract, numeric results, metric runs, product pins.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # metric version: deterministic calculation contract + certification decoupling
    op.add_column("asset_metric_versions", sa.Column("calculation_type", sa.Text(), server_default="ratio", nullable=False), schema="asset")
    op.add_column("asset_metric_versions", sa.Column("precision", sa.Integer(), server_default="2", nullable=False), schema="asset")
    op.add_column("asset_metric_versions", sa.Column("rounding_mode", sa.Text(), server_default="half_up", nullable=False), schema="asset")
    op.add_column("asset_metric_versions", sa.Column("certification_status", sa.Text(), server_default="legacy_unverified", nullable=False), schema="asset")
    op.add_column("asset_metric_versions", sa.Column("dimension_schema", postgresql.JSONB(), nullable=True), schema="asset")

    # metric result: real numeric columns + provenance + business key
    op.add_column("asset_metric_results", sa.Column("dimensions_hash", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("parameter_hash", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("numerator_num", sa.Numeric(20, 6), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("denominator_num", sa.Numeric(20, 6), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("metric_num", sa.Numeric(20, 6), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("result_digest", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("source_snapshot_id", sa.BigInteger(), nullable=True), schema="asset")
    op.add_column("asset_metric_results", sa.Column("recalc_reason", sa.Text(), nullable=True), schema="asset")
    op.create_index(
        "uq_asset_metric_results_business_key",
        "asset_metric_results",
        ["metric_code", "version", "period_key", "dimensions_hash", "parameter_hash", "run_batch"],
        unique=True,
        schema="asset",
    )

    # metric run provenance table (144 §7.2)
    op.create_table(
        "asset_metric_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("metric_code", sa.Text(), nullable=False),
        sa.Column("metric_version_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("parameters_hash", sa.Text(), nullable=True),
        sa.Column("calculation_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("main_run_id", sa.BigInteger(), nullable=True),
        sa.Column("numerator_run_id", sa.BigInteger(), nullable=True),
        sa.Column("denominator_run_id", sa.BigInteger(), nullable=True),
        sa.Column("numerator_error", sa.Text(), nullable=True),
        sa.Column("denominator_error", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("engine_version", sa.Text(), nullable=True),
        sa.Column("result_digest", sa.Text(), nullable=True),
        sa.Column("data_as_of", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="asset",
    )
    op.create_index("ix_asset_metric_runs_code_version", "asset_metric_runs", ["metric_code", "version"], schema="asset")

    # data product: publish revision + validated pin + concurrency quota (144 §7.1)
    # (rate_limit_per_min already exists from 126 P4 and stays the per-minute quota)
    op.add_column("asset_data_products", sa.Column("revision", sa.Integer(), server_default="1", nullable=False), schema="asset")
    op.add_column("asset_data_products", sa.Column("pin_validated_at", sa.TIMESTAMP(timezone=True), nullable=True), schema="asset")
    op.add_column("asset_data_products", sa.Column("pin_validation_status", sa.Text(), nullable=True), schema="asset")
    op.add_column("asset_data_products", sa.Column("max_concurrency", sa.Integer(), nullable=True), schema="asset")


def downgrade() -> None:
    op.drop_column("asset_data_products", "max_concurrency", schema="asset")
    op.drop_column("asset_data_products", "pin_validation_status", schema="asset")
    op.drop_column("asset_data_products", "pin_validated_at", schema="asset")
    op.drop_column("asset_data_products", "revision", schema="asset")
    op.drop_index("ix_asset_metric_runs_code_version", table_name="asset_metric_runs", schema="asset")
    op.drop_table("asset_metric_runs", schema="asset")
    op.drop_index("uq_asset_metric_results_business_key", table_name="asset_metric_results", schema="asset")
    op.drop_column("asset_metric_results", "recalc_reason", schema="asset")
    op.drop_column("asset_metric_results", "source_snapshot_id", schema="asset")
    op.drop_column("asset_metric_results", "result_digest", schema="asset")
    op.drop_column("asset_metric_results", "metric_num", schema="asset")
    op.drop_column("asset_metric_results", "denominator_num", schema="asset")
    op.drop_column("asset_metric_results", "numerator_num", schema="asset")
    op.drop_column("asset_metric_results", "parameter_hash", schema="asset")
    op.drop_column("asset_metric_results", "dimensions_hash", schema="asset")
    op.drop_column("asset_metric_versions", "dimension_schema", schema="asset")
    op.drop_column("asset_metric_versions", "certification_status", schema="asset")
    op.drop_column("asset_metric_versions", "rounding_mode", schema="asset")
    op.drop_column("asset_metric_versions", "precision", schema="asset")
    op.drop_column("asset_metric_versions", "calculation_type", schema="asset")
