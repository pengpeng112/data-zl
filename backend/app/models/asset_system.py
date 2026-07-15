from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
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
    target_host = Column(Text)
    system_identity_key = Column(Text, unique=True)
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
    target_host = Column(Text)
    connection_identity_key = Column(Text, unique=True)
    identity_source = Column(Text, server_default="manual")
    port = Column(Integer)
    service_name = Column(Text)
    database_name = Column(Text)
    service_mode = Column(Text)
    default_schema = Column(Text)
    display_order = Column(Integer, server_default="0")
    connection_mode = Column(Text)
    environment = Column(Text)
    collect_mode = Column(Text, server_default="metadata_only")
    credential_ref = Column(Text)
    credential_status = Column(Text, server_default="unconfigured")
    credential_username_masked = Column(Text)
    credential_updated_at = Column(TIMESTAMP(timezone=True))
    credential_updated_by = Column(Text)
    connection_options = Column(JSONB)
    write_policy = Column(Text, server_default="readonly")
    write_credential_ref = Column(Text)
    description_cn = Column(Text)
    enabled = Column(Boolean, server_default="true")
    last_check_status = Column(Text)
    last_check_at = Column(TIMESTAMP(timezone=True))
    # plan 76: physical endpoint / alias normalization
    endpoint_key = Column(Text)
    database_key = Column(Text)
    canonical_source_code = Column(Text)
    source_kind = Column(Text, server_default="physical_connection")
    business_labels = Column(JSONB)
    metadata_origin = Column(Text)
    last_test_status = Column(Text)
    last_test_at = Column(TIMESTAMP(timezone=True))
    last_test_latency_ms = Column(Integer)
    last_test_error_code = Column(Text)
    last_test_error_masked = Column(Text)
    last_collect_status = Column(Text)
    last_collect_at = Column(TIMESTAMP(timezone=True))
    last_collect_snapshot_id = Column(BigInteger)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetSourceSchema(Base):
    """Schema/Owner inventory under a physical data source connection."""

    __tablename__ = "asset_source_schemas"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    source_code = Column(Text, nullable=False)
    schema_name = Column(Text, nullable=False)
    business_labels = Column(JSONB)
    table_count = Column(Integer, server_default="0")
    column_count = Column(Integer, server_default="0")
    last_collect_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
