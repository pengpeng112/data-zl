from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class SchedulerJob(Base):
    __tablename__ = "asset_scheduler_jobs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    job_type = Column(Text, nullable=False)
    source_code = Column(Text)
    trigger_mode = Column(Text, nullable=False, server_default="scheduled")
    schedule_cron = Column(Text)
    status = Column(Text, server_default="pending")
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    result_ref = Column(Text)
    total_processed = Column(Integer)
    total_changes = Column(Integer)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class GovernEvent(Base):
    __tablename__ = "asset_govern_events"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    event_type = Column(Text, nullable=False)
    module = Column(Text, nullable=False)
    entity_type = Column(Text)
    entity_ref = Column(Text)
    severity = Column(Text, server_default="info")
    title = Column(Text)
    detail = Column(JSONB)
    status = Column(Text, server_default="open")
    assigned_to = Column(Text)
    acknowledged_at = Column(TIMESTAMP(timezone=True))
    resolved_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class ChangeRule(Base):
    __tablename__ = "asset_change_rules"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    rule_code = Column(Text, unique=True, nullable=False)
    rule_name_cn = Column(Text, nullable=False)
    system_code = Column(Text)
    source_code = Column(Text)
    db_type = Column(Text)
    change_type = Column(Text, nullable=False)
    severity_override = Column(Text)
    ignore_enabled = Column(Boolean, server_default="false")
    description = Column(Text)
    enabled = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
