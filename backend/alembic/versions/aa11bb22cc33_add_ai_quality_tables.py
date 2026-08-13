"""S5 Dify AI quality jobs and reviewed results.

Revision ID: aa11bb22cc33
Revises: h5c6d7e8f9a0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "aa11bb22cc33"
down_revision: Union[str, None] = "h5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Complete the physical identity of existing quality findings.  Schema
    # (Oracle owner) is distinct from an optional database namespace.
    op.add_column("asset_quality_findings", sa.Column("schema_name", sa.Text(), nullable=True), schema="asset")
    op.create_table(
        "asset_ai_quality_jobs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_key", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("input_digest", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("input_summary", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("dify_run_id", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(), nullable=True),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("job_key"), schema="asset",
    )
    op.create_index("ix_ai_quality_jobs_status", "asset_ai_quality_jobs", ["status"], schema="asset")
    op.create_index("ix_ai_quality_jobs_digest", "asset_ai_quality_jobs", ["input_digest"], schema="asset")
    op.create_table(
        "asset_ai_quality_job_findings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("finding_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["asset.asset_ai_quality_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finding_id"], ["asset.asset_quality_findings.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("job_id", "finding_id", name="uq_ai_quality_job_finding"), schema="asset",
    )
    op.create_index("ix_ai_quality_job_findings_finding", "asset_ai_quality_job_findings", ["finding_id"], schema="asset")
    op.create_table(
        "asset_ai_quality_results",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("risk_level", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("structured_result", postgresql.JSONB(), nullable=False),
        sa.Column("output_digest", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("review_by", sa.Text(), nullable=True),
        sa.Column("review_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("accepted_recommendations", postgresql.JSONB(), nullable=True),
        sa.Column("attached_by", sa.Text(), nullable=True),
        sa.Column("attached_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["asset.asset_ai_quality_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("job_id"), schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_ai_quality_results", schema="asset")
    op.drop_index("ix_ai_quality_job_findings_finding", table_name="asset_ai_quality_job_findings", schema="asset")
    op.drop_table("asset_ai_quality_job_findings", schema="asset")
    op.drop_index("ix_ai_quality_jobs_digest", table_name="asset_ai_quality_jobs", schema="asset")
    op.drop_index("ix_ai_quality_jobs_status", table_name="asset_ai_quality_jobs", schema="asset")
    op.drop_table("asset_ai_quality_jobs", schema="asset")
    op.drop_column("asset_quality_findings", "schema_name", schema="asset", if_exists=True)
