"""126 P3: query schedule definitions (default disabled)."""
from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func

from ..core.db import Base


class AssetQuerySchedule(Base):
    __tablename__ = "asset_query_schedules"
    __table_args__ = (
        UniqueConstraint("query_code", name="uq_asset_query_schedules_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    query_code = Column(Text, nullable=False)
    source_code = Column(Text)
    schedule_cron = Column(Text, nullable=False, server_default="0 3 * * *")
    enabled = Column(Boolean, nullable=False, server_default="false")
    result_storage = Column(Text, server_default="none")
    max_rows = Column(Integer, server_default="1000")
    timeout_seconds = Column(Integer, server_default="300")
    max_retries = Column(Integer, server_default="1")
    last_run_id = Column(BigInteger)
    last_status = Column(Text)
    last_error = Column(Text)
    last_run_at = Column(TIMESTAMP(timezone=True))
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
