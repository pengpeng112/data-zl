from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func

from ..core.db import Base


class ApiKey(Base):
    __tablename__ = "asset_api_keys"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    key_name = Column(Text, nullable=False)
    token = Column(Text, unique=True, nullable=False)
    enabled = Column(Boolean, server_default="true")
    user_identifier = Column(Text)
    expires_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_used_at = Column(TIMESTAMP(timezone=True))


class TableOwner(Base):
    __tablename__ = "asset_table_owners"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    full_table_name = Column(Text, unique=True, nullable=False)
    owner_name = Column(Text)
    department = Column(Text)
    contact = Column(Text)
    note = Column(Text)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class BusinessTerm(Base):
    __tablename__ = "asset_business_terms"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    term = Column(Text, nullable=False)
    mapping_type = Column(Text, server_default="column")
    mapping_target = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class MetadataSnapshot(Base):
    __tablename__ = "asset_metadata_snapshots"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    label = Column(Text)
    snapshot_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    scope = Column(Text)
    table_count = Column(Integer)
    column_count = Column(Integer)
    relation_count = Column(Integer)
    data = Column(Text)
