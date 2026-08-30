"""165 E1: 探查数据模型（asset_probe_runs / asset_probe_findings）。

字段与迁移 c1d2e3f4a5b6 一一对应；问题身份唯一键见 165 §2（round-4 A1）。
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from .governance_base import Base


class AssetProbeRun(Base):
    __tablename__ = "asset_probe_runs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    status = Column(String(16), nullable=False, server_default="running")
    probe_count = Column(Integer, nullable=False, server_default="0")
    finding_new = Column(Integer, nullable=False, server_default="0")
    finding_updated = Column(Integer, nullable=False, server_default="0")
    relapse_count = Column(Integer, nullable=False, server_default="0")
    metrics_summary = Column(JSONB)
    error_summary = Column(Text)
    created_by = Column(String(64))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetProbeFinding(Base):
    __tablename__ = "asset_probe_findings"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    probe_type = Column(String(16), nullable=False)
    system_pair = Column(String(64), nullable=False)
    object_desc = Column(String(512), nullable=False)
    object_key_digest = Column(String(32), nullable=False)
    metric_name = Column(String(128), nullable=False)
    metric_value = Column(Numeric(18, 6))
    metric_unit = Column(String(16))
    threshold = Column(Numeric(18, 6))
    window_start = Column(Date)
    window_end = Column(Date)
    severity = Column(String(4))
    status = Column(String(16), nullable=False, server_default="open")
    first_seen_run = Column(String(64))
    last_seen_run = Column(String(64))
    relapse_count = Column(Integer, nullable=False, server_default="0")
    evidence_sql = Column(Text)
    evidence_digest = Column(String(64))
    resolved_by = Column(String(64))
    resolved_at = Column(TIMESTAMP(timezone=True))
    note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
