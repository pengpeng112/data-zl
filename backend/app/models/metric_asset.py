"""126 P2 + 144 S4: metric definition / version / period result / metric run."""
from sqlalchemy import BigInteger, Boolean, Column, Integer, Numeric, Text, TIMESTAMP, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetMetricDefinition(Base):
    __tablename__ = "asset_metric_definitions"
    __table_args__ = (
        UniqueConstraint("metric_code", name="uq_asset_metric_definitions_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    metric_code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    meaning = Column(Text)
    category = Column(Text)
    unit = Column(Text)
    frequency = Column(Text)
    grain = Column(Text)
    owner_dept = Column(Text)
    current_version_id = Column(BigInteger)
    allow_dashboard = Column(Boolean, server_default="true")
    allow_export = Column(Boolean, server_default="false")
    allow_data_product = Column(Boolean, server_default="false")
    status = Column(Text, server_default="active")
    created_by = Column(Text)
    updated_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetMetricVersion(Base):
    __tablename__ = "asset_metric_versions"
    __table_args__ = (
        UniqueConstraint("metric_id", "version", name="uq_asset_metric_versions_mid_ver"),
        Index("ix_asset_metric_versions_code_status", "metric_code", "status"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    metric_id = Column(BigInteger, nullable=False, index=True)
    metric_code = Column(Text, nullable=False, index=True)
    version = Column(Integer, nullable=False, server_default="1")
    parent_version_id = Column(BigInteger)
    status = Column(Text, nullable=False, server_default="draft")
    is_active = Column(Boolean, nullable=False, server_default="false")
    definition_text = Column(Text)
    numerator_desc = Column(Text)
    denominator_desc = Column(Text)
    formula = Column(Text)
    # query version refs: single query or split numerator/denominator
    query_code = Column(Text)
    query_version = Column(Integer)
    numerator_query_code = Column(Text)
    numerator_query_version = Column(Integer)
    denominator_query_code = Column(Text)
    denominator_query_version = Column(Integer)
    period_field = Column(Text)
    include_rules = Column(Text)
    exclude_rules = Column(Text)
    dedup_rules = Column(Text)
    limitations = Column(JSONB)
    system_code = Column(Text)
    source_code = Column(Text)
    revision_reason = Column(Text)
    content_hash = Column(Text)
    # 144 S4: calculation contract (deterministic Decimal engine)
    calculation_type = Column(Text, server_default="ratio")  # single|ratio|sum
    precision = Column(Integer, server_default="2")
    rounding_mode = Column(Text, server_default="half_up")
    certification_status = Column(Text, server_default="legacy_unverified")
    dimension_schema = Column(JSONB)
    effective_from = Column(TIMESTAMP(timezone=True))
    effective_to = Column(TIMESTAMP(timezone=True))
    activated_at = Column(TIMESTAMP(timezone=True))
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetMetricResult(Base):
    __tablename__ = "asset_metric_results"
    __table_args__ = (
        Index("ix_asset_metric_results_code_period", "metric_code", "period_key"),
        # 144 S4/A16: one result per (metric version, period, dimensions,
        # parameters, batch) — same-period different dimensions/batches never
        # overwrite each other; recalc creates a new batch.
        Index(
            "uq_asset_metric_results_business_key",
            "metric_code", "version", "period_key", "dimensions_hash", "parameter_hash", "run_batch",
            unique=True,
        ),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    metric_version_id = Column(BigInteger, nullable=False, index=True)
    metric_code = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    period_key = Column(Text, nullable=False)  # e.g. 2026-01
    dimensions = Column(JSONB)
    dimensions_hash = Column(Text)
    parameter_hash = Column(Text)
    numerator_value = Column(Text)
    denominator_value = Column(Text)
    metric_value = Column(Text)
    # 144 S4: real numeric columns — free-text is display-only legacy
    numerator_num = Column(Numeric(20, 6))
    denominator_num = Column(Numeric(20, 6))
    metric_num = Column(Numeric(20, 6))
    result_digest = Column(Text)
    source_snapshot_id = Column(BigInteger)
    status = Column(Text, server_default="ok")  # ok|partial|unavailable
    quality_status = Column(Text)
    data_as_of = Column(TIMESTAMP(timezone=True))
    query_run_id = Column(BigInteger)
    run_batch = Column(Text)
    limitations_note = Column(Text)
    is_recalc = Column(Boolean, server_default="false")
    recalc_reason = Column(Text)
    prev_result_id = Column(BigInteger)
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetMetricRun(Base):
    """144 S4: provenance of one metric calculation (subqueries + formula)."""

    __tablename__ = "asset_metric_runs"
    __table_args__ = (
        Index("ix_asset_metric_runs_code_version", "metric_code", "version"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    metric_code = Column(Text, nullable=False)
    metric_version_id = Column(BigInteger, nullable=False)
    version = Column(Integer, nullable=False)
    period_key = Column(Text, nullable=False)
    dimensions = Column(JSONB)
    parameters = Column(JSONB)
    parameters_hash = Column(Text)
    calculation_type = Column(Text)
    status = Column(Text, server_default="running")  # running|success|partial|unavailable|failed
    main_run_id = Column(BigInteger)
    numerator_run_id = Column(BigInteger)
    denominator_run_id = Column(BigInteger)
    numerator_error = Column(Text)
    denominator_error = Column(Text)
    formula = Column(Text)
    engine_version = Column(Text)
    result_digest = Column(Text)
    data_as_of = Column(TIMESTAMP(timezone=True))
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))
    triggered_by = Column(Text)
    error_code = Column(Text)
    correlation_id = Column(Text)
