"""144 S7: AI answer provenance, accuracy feedback, and evaluation cases/runs.

No patient-level content ever lands here: answer events store digests and
version refs only; feedback comments are sanitized text; golden cases use
synthetic parameters and aggregate assertions (144 §7.2, §12).
"""
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetAiAnswerEvent(Base):
    """Provenance of one AI statistical answer (digests, not raw content)."""

    __tablename__ = "asset_ai_answer_events"
    __table_args__ = (
        Index("ix_asset_ai_answers_run", "run_id"),
        Index("ix_asset_ai_answers_caller", "caller_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    question_digest = Column(Text, nullable=False)
    question_summary = Column(Text)  # sanitized short summary, never full PHI
    caller_id = Column(Text, nullable=False, server_default="unknown")
    model_version = Column(Text)
    context_id = Column(Text)
    query_code = Column(Text)
    query_version = Column(Integer)
    metric_code = Column(Text)
    metric_version = Column(Integer)
    product_code = Column(Text)
    run_id = Column(BigInteger)
    result_digest = Column(Text)
    data_as_of = Column(TIMESTAMP(timezone=True))
    answer_digest = Column(Text)
    answer_summary = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetAiFeedback(Base):
    """Correctness feedback bound to answer/run/context; state machine per 144 §7.3."""

    __tablename__ = "asset_ai_feedback"
    __table_args__ = (
        Index("ix_asset_ai_feedback_status", "status"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    answer_event_id = Column(BigInteger, nullable=False)
    # correct | partially_correct | incorrect | insufficient_evidence | ambiguous
    rating = Column(Text, nullable=False)
    # typed error taxonomy (144 §4.7); free text sanitized into comment
    error_types = Column(JSONB)
    comment = Column(Text)
    suggested_revision = Column(Text)
    submitted_by = Column(Text)
    submitted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    # submitted → triaged → accepted|rejected|needs_business_confirmation
    #   → revision_draft → evaluation_running → resolved|regression_failed
    status = Column(Text, nullable=False, server_default="submitted")
    reviewed_by = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_note = Column(Text)
    revision_query_code = Column(Text)
    revision_query_version = Column(Integer)
    evaluation_case_id = Column(BigInteger)
    resolved_at = Column(TIMESTAMP(timezone=True))


class AssetQueryEvaluationCase(Base):
    """Golden case: fixed params + aggregate assertions, versioned set (144 §12)."""

    __tablename__ = "asset_query_evaluation_cases"
    __table_args__ = (
        UniqueConstraint("case_code", name="uq_asset_query_eval_cases_code"),
        Index("ix_asset_query_eval_cases_target", "query_code", "query_version"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    case_code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    system_code = Column(Text)
    business_domain = Column(Text)
    asset_type = Column(Text, nullable=False, server_default="query")  # query|metric|product
    query_code = Column(Text, nullable=False)
    query_version = Column(Integer)  # None → follow current active
    parameters = Column(JSONB)
    # assertions: [{"kind": "row_count_min", "value": 0},
    #              {"kind": "numeric_tolerance", "column": "X", "expected": 1.0, "tolerance": 0.01},
    #              {"kind": "status_success"}]
    assertions = Column(JSONB, nullable=False)
    evidence = Column(Text)
    evaluation_set_version = Column(Text, nullable=False, server_default="eval-set-v1")
    enabled = Column(Boolean, nullable=False, server_default="true")
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetQueryEvaluationRun(Base):
    """One replay of one case against a target version (A25)."""

    __tablename__ = "asset_query_evaluation_runs"
    __table_args__ = (
        Index("ix_asset_query_eval_runs_case", "case_id"),
        Index("ix_asset_query_eval_runs_target", "query_code", "query_version"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    case_id = Column(BigInteger, nullable=False)
    case_code = Column(Text, nullable=False)
    evaluation_set_version = Column(Text, nullable=False)
    query_code = Column(Text, nullable=False)
    query_version = Column(Integer, nullable=False)
    parameters = Column(JSONB)
    status = Column(Text, nullable=False)  # pass|fail|error|skipped
    passed = Column(Boolean, nullable=False)
    assertion_results = Column(JSONB)
    actual_summary = Column(JSONB)
    result_digest = Column(Text)
    error_code = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))
    triggered_by = Column(Text)
