from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy.sql import func

from ..core.db import Base


class GraphSyncBatch(Base):
    """图分析层同步批次记录（98号 S0 / 100号修复）。"""
    __tablename__ = "asset_graph_sync_batches"
    __table_args__ = {"schema": "asset"}

    batch_id = Column(Text, primary_key=True)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))
    status = Column(Text, nullable=False)
    mode = Column(Text, nullable=False)
    node_count = Column(Integer, server_default="0")
    edge_count = Column(Integer, server_default="0")
    upsert_count = Column(Integer, server_default="0")
    delete_count = Column(Integer, server_default="0")
    unresolved_count = Column(Integer, server_default="0")
    skipped_count = Column(Integer, server_default="0")
    checksum = Column(Text)
    error_masked = Column(Text)