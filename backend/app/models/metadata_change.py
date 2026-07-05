from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetMetadataColumnSnapshot(Base):
    __tablename__ = "asset_metadata_column_snapshots"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    snapshot_id = Column(BigInteger, nullable=False)
    system_code = Column(Text, nullable=False)
    source_code = Column(Text, nullable=False)
    namespace_name = Column(Text)
    table_name = Column(Text, nullable=False)
    column_name = Column(Text, nullable=False)
    data_type = Column(Text)
    length = Column(Integer)
    nullable = Column(Text)
    column_default = Column(Text)
    comment = Column(Text)
    is_primary_key = Column(Boolean, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetMetadataChangeEvent(Base):
    __tablename__ = "asset_metadata_change_events"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    snapshot_id_from = Column(BigInteger)
    snapshot_id_to = Column(BigInteger, nullable=False)
    system_code = Column(Text, nullable=False)
    source_code = Column(Text, nullable=False)
    namespace_name = Column(Text)
    table_name = Column(Text, nullable=False)
    column_name = Column(Text)
    change_type = Column(Text, nullable=False)
    before_value = Column(JSONB)
    after_value = Column(JSONB)
    severity = Column(Text, server_default="info")
    status = Column(Text, server_default="open")
    assigned_to = Column(Text)
    reviewed_by = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
