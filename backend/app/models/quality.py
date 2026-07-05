from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class QualityRule(Base):
    __tablename__ = "asset_quality_rules"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    rule_code = Column(Text, unique=True, nullable=False)
    rule_name = Column(Text)
    rule_type = Column(Text)
    rule_category = Column(Text)
    target_type = Column(Text)
    execution_mode = Column(Text, server_default="metadata_only")
    check_scope = Column(Text)
    constraint_level = Column(Text, server_default="WARN")
    business_domain = Column(Text)
    system_code = Column(Text)
    source_code = Column(Text)
    namespace_name = Column(Text)
    target_table = Column(Text)
    target_field = Column(Text)
    related_table = Column(Text)
    related_field = Column(Text)
    check_sql = Column(Text)
    error_condition = Column(Text)
    error_level = Column(Text, server_default="minor")
    description = Column(Text)
    threshold_config = Column(JSONB)
    sample_limit = Column(Integer, server_default="20")
    version = Column(Integer, server_default="1")
    remark = Column(Text)
    enabled = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityFinding(Base):
    __tablename__ = "asset_quality_findings"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    run_id = Column(BigInteger)
    rule_code = Column(Text)
    target_type = Column(Text)
    target_ref = Column(Text)
    system_code = Column(Text)
    source_code = Column(Text)
    namespace_name = Column(Text)
    table_name = Column(Text)
    column_name = Column(Text)
    severity = Column(Text)
    status = Column(Text, server_default="open")
    rectification_status = Column(Text, server_default="open")
    metric_value = Column(Text)
    total_cnt = Column(Integer)
    error_cnt = Column(Integer)
    error_rate = Column(Integer)
    detail = Column(JSONB)
    sample_data = Column(JSONB)
    assigned_to = Column(Text)
    confirmed_by = Column(Text)
    found_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True))
    resolved_by = Column(Text)
    note = Column(Text)


class QualityCheckRun(Base):
    __tablename__ = "asset_quality_check_runs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    task_id = Column(BigInteger)
    system_code = Column(Text)
    source_code = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))
    triggered_by = Column(Text)
    total_rules = Column(Integer)
    total_findings = Column(Integer)
    total_records = Column(Integer)
    error_records = Column(Integer)
    pass_rate = Column(Integer)
    failed_reason = Column(Text)
    status = Column(Text)


class QualityTask(Base):
    __tablename__ = "asset_quality_tasks"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    task_name = Column(Text, nullable=False)
    system_code = Column(Text)
    source_code = Column(Text)
    target_scope = Column(Text)
    execution_mode = Column(Text, server_default="metadata_only")
    schedule_cron = Column(Text)
    enabled = Column(Boolean, server_default="true")
    last_run_status = Column(Text)
    last_run_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class QualityMetric(Base):
    __tablename__ = "asset_quality_metrics"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    system_code = Column(Text)
    source_code = Column(Text)
    namespace_name = Column(Text)
    table_name = Column(Text)
    column_name = Column(Text)
    metric_code = Column(Text)
    metric_value = Column(Integer)
    metric_text = Column(Text)
    measured_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
