from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class OpsToolTemplate(Base):
    __tablename__ = "asset_ops_tool_templates"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    tool_code = Column(Text, unique=True, nullable=False)
    tool_name_cn = Column(Text, nullable=False)
    system_code = Column(Text, nullable=False)
    source_code = Column(Text)
    tool_type = Column(Text, nullable=False)
    risk_level = Column(Text, nullable=False, server_default="medium")
    input_schema = Column(JSONB, nullable=False)
    execution_mode = Column(Text, nullable=False)
    sql_or_endpoint_ref = Column(Text)
    require_approval = Column(Boolean, server_default="true")
    require_second_confirm = Column(Boolean, server_default="true")
    enabled = Column(Boolean, server_default="false")
    description_cn = Column(Text)
    rollback_note_cn = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class OpsToolRun(Base):
    __tablename__ = "asset_ops_tool_runs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    tool_code = Column(Text, nullable=False)
    requested_by = Column(Text)
    approved_by = Column(Text)
    approval_status = Column(Text, server_default="draft")
    input_params_masked = Column(JSONB)
    execution_summary = Column(Text)
    result_ref = Column(Text)
    affected_count = Column(Integer)
    risk_scan = Column(JSONB)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
