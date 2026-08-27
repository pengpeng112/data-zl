"""plan144 S7: AI answer events, feedback loop, evaluation cases/runs.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table(name, columns, indexes=(), uniques=()):
    cols = [
        sa.Column("id", sa.BigInteger(), nullable=False),
        *columns,
        sa.PrimaryKeyConstraint("id"),
        *uniques,
    ]
    op.create_table(name, *cols, schema="asset")
    for ix_name, ix_cols in indexes:
        op.create_index(ix_name, name, ix_cols, schema="asset")


def upgrade() -> None:
    _table(
        "asset_ai_answer_events",
        [
            sa.Column("question_digest", sa.Text(), nullable=False),
            sa.Column("question_summary", sa.Text(), nullable=True),
            sa.Column("caller_id", sa.Text(), nullable=False, server_default="unknown"),
            sa.Column("model_version", sa.Text(), nullable=True),
            sa.Column("context_id", sa.Text(), nullable=True),
            sa.Column("query_code", sa.Text(), nullable=True),
            sa.Column("query_version", sa.Integer(), nullable=True),
            sa.Column("metric_code", sa.Text(), nullable=True),
            sa.Column("metric_version", sa.Integer(), nullable=True),
            sa.Column("product_code", sa.Text(), nullable=True),
            sa.Column("run_id", sa.BigInteger(), nullable=True),
            sa.Column("result_digest", sa.Text(), nullable=True),
            sa.Column("data_as_of", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("answer_digest", sa.Text(), nullable=True),
            sa.Column("answer_summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        ],
        indexes=[
            ("ix_asset_ai_answers_run", ["run_id"]),
            ("ix_asset_ai_answers_caller", ["caller_id"]),
        ],
    )
    _table(
        "asset_ai_feedback",
        [
            sa.Column("answer_event_id", sa.BigInteger(), nullable=False),
            sa.Column("rating", sa.Text(), nullable=False),
            sa.Column("error_types", postgresql.JSONB(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("suggested_revision", sa.Text(), nullable=True),
            sa.Column("submitted_by", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
            sa.Column("status", sa.Text(), nullable=False, server_default="submitted"),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("revision_query_code", sa.Text(), nullable=True),
            sa.Column("revision_query_version", sa.Integer(), nullable=True),
            sa.Column("evaluation_case_id", sa.BigInteger(), nullable=True),
            sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        ],
        indexes=[("ix_asset_ai_feedback_status", ["status"])],
    )
    _table(
        "asset_query_evaluation_cases",
        [
            sa.Column("case_code", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("system_code", sa.Text(), nullable=True),
            sa.Column("business_domain", sa.Text(), nullable=True),
            sa.Column("asset_type", sa.Text(), nullable=False, server_default="query"),
            sa.Column("query_code", sa.Text(), nullable=False),
            sa.Column("query_version", sa.Integer(), nullable=True),
            sa.Column("parameters", postgresql.JSONB(), nullable=True),
            sa.Column("assertions", postgresql.JSONB(), nullable=False),
            sa.Column("evidence", sa.Text(), nullable=True),
            sa.Column("evaluation_set_version", sa.Text(), nullable=False, server_default="eval-set-v1"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        ],
        indexes=[("ix_asset_query_eval_cases_target", ["query_code", "query_version"])],
        uniques=[sa.UniqueConstraint("case_code", name="uq_asset_query_eval_cases_code")],
    )
    _table(
        "asset_query_evaluation_runs",
        [
            sa.Column("case_id", sa.BigInteger(), nullable=False),
            sa.Column("case_code", sa.Text(), nullable=False),
            sa.Column("evaluation_set_version", sa.Text(), nullable=False),
            sa.Column("query_code", sa.Text(), nullable=False),
            sa.Column("query_version", sa.Integer(), nullable=False),
            sa.Column("parameters", postgresql.JSONB(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("passed", sa.Boolean(), nullable=False),
            sa.Column("assertion_results", postgresql.JSONB(), nullable=True),
            sa.Column("actual_summary", postgresql.JSONB(), nullable=True),
            sa.Column("result_digest", sa.Text(), nullable=True),
            sa.Column("error_code", sa.Text(), nullable=True),
            sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
            sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("triggered_by", sa.Text(), nullable=True),
        ],
        indexes=[
            ("ix_asset_query_eval_runs_case", ["case_id"]),
            ("ix_asset_query_eval_runs_target", ["query_code", "query_version"]),
        ],
    )


def downgrade() -> None:
    op.drop_table("asset_query_evaluation_runs", schema="asset")
    op.drop_table("asset_query_evaluation_cases", schema="asset")
    op.drop_table("asset_ai_feedback", schema="asset")
    op.drop_table("asset_ai_answer_events", schema="asset")
