from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func

from ..core.db import Base


class AssetSystem(Base):
    __tablename__ = "asset_systems"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    system_code = Column(Text, unique=True, nullable=False)
    system_name_cn = Column(Text, nullable=False)
    system_name_en = Column(Text)
    system_type = Column(Text)
    owner_department = Column(Text)
    description_cn = Column(Text)
    status = Column(Text, server_default="active")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetDataSource(Base):
    __tablename__ = "asset_data_sources"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    system_code = Column(Text, nullable=False)
    source_code = Column(Text, unique=True, nullable=False)
    source_name_cn = Column(Text, nullable=False)
    db_type = Column(Text)
    host_masked = Column(Text)
    port = Column(Integer)
    service_name = Column(Text)
    database_name = Column(Text)
    connection_mode = Column(Text)
    environment = Column(Text)
    collect_mode = Column(Text, server_default="metadata_only")
    credential_ref = Column(Text)
    write_credential_ref = Column(Text)
    description_cn = Column(Text)
    enabled = Column(Boolean, server_default="true")
    last_check_status = Column(Text)
    last_check_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
