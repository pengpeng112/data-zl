"""126 P1: query definition / version / dependency / run / optional result."""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetQueryDefinition(Base):
    __tablename__ = "asset_query_definitions"
    __table_args__ = (
        UniqueConstraint("query_code", name="uq_asset_query_definitions_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    query_code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    purpose = Column(Text)
    business_domain = Column(Text)
    system_code = Column(Text)
    source_code = Column(Text)
    namespace_name = Column(Text)
    owner_name = Column(Text)
    sensitivity = Column(Text, server_default="aggregate")
    current_version_id = Column(BigInteger)
    ai_readable = Column(Boolean, server_default="true")
    allow_schedule = Column(Boolean, server_default="false")
    allow_data_product = Column(Boolean, server_default="false")
    status = Column(Text, server_default="active")
    created_by = Column(Text)
    updated_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetQueryVersion(Base):
    __tablename__ = "asset_query_versions"
    __table_args__ = (
        UniqueConstraint("query_id", "version", name="uq_asset_query_versions_qid_ver"),
        Index("ix_asset_query_versions_code_status", "query_code", "status"),
        Index("ix_asset_query_versions_sql_hash", "sql_sha256"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    query_id = Column(BigInteger, nullable=False, index=True)
    query_code = Column(Text, nullable=False, index=True)
    version = Column(Integer, nullable=False, server_default="1")
    parent_version_id = Column(BigInteger)
    status = Column(Text, nullable=False, server_default="captured")
    is_active = Column(Boolean, nullable=False, server_default="false")
    dialect = Column(Text)
    sql_text = Column(Text, nullable=False)
    sql_normalized = Column(Text)
    sql_sha256 = Column(Text, nullable=False)
    semantic_fingerprint = Column(Text)
    parameter_schema = Column(JSONB)
    output_schema = Column(JSONB)
    grain = Column(Text)
    period_field = Column(Text)
    include_rules = Column(Text)
    exclude_rules = Column(Text)
    dedup_rules = Column(Text)
    limitations = Column(JSONB)
    risk_flags = Column(JSONB)
    recipe_refs = Column(JSONB)
    metric_refs = Column(JSONB)
    source_path = Column(Text)
    ai_source = Column(JSONB)
    session_key = Column(Text)
    revision_reason = Column(Text)
    diff_summary = Column(Text)
    effective_from = Column(TIMESTAMP(timezone=True))
    effective_to = Column(TIMESTAMP(timezone=True))
    validated_at = Column(TIMESTAMP(timezone=True))
    activated_at = Column(TIMESTAMP(timezone=True))
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetQueryDependency(Base):
    __tablename__ = "asset_query_dependencies"
    __table_args__ = (
        Index("ix_asset_query_deps_version", "query_version_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    query_version_id = Column(BigInteger, nullable=False)
    dep_type = Column(Text, nullable=False)  # table/column/relation/recipe
    system_code = Column(Text)
    source_code = Column(Text)
    schema_name = Column(Text)
    object_name = Column(Text)
    column_name = Column(Text)
    relation_id = Column(BigInteger)
    recipe_id = Column(Text)
    recipe_version = Column(Integer)
    is_formal = Column(Boolean, server_default="false")
    evidence = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetQueryRun(Base):
    __tablename__ = "asset_query_runs"
    __table_args__ = (
        Index("ix_asset_query_runs_version", "query_version_id"),
        Index("ix_asset_query_runs_code", "query_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    query_version_id = Column(BigInteger, nullable=False)
    query_code = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    source_code = Column(Text)
    dialect = Column(Text)
    parameters = Column(JSONB)
    parameters_hash = Column(Text)
    status = Column(Text, server_default="pending")
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    duration_ms = Column(Integer)
    row_count = Column(Integer)
    truncated = Column(Boolean, server_default="false")
    result_storage = Column(Text, server_default="none")  # none|summary|file_ref
    result_hash = Column(Text)
    sql_sha256 = Column(Text)
    warnings = Column(JSONB)
    error_class = Column(Text)
    error_message = Column(Text)
    triggered_by = Column(Text)
    session_key = Column(Text)
    correlation_id = Column(Text)
    data_as_of = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetQueryResult(Base):
    __tablename__ = "asset_query_results"
    __table_args__ = (
        Index("ix_asset_query_results_run", "run_id"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    run_id = Column(BigInteger, nullable=False)
    storage = Column(Text, nullable=False, server_default="none")
    summary_json = Column(JSONB)
    file_ref = Column(Text)
    file_sha256 = Column(Text)
    file_format = Column(Text)
    file_size_bytes = Column(Integer)
    sensitivity = Column(Text, server_default="aggregate")
    retention_days = Column(Integer)
    truncated = Column(Boolean, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
