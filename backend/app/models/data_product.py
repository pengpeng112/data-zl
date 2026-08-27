"""126 P4: published data product catalog (query/metric based, no arbitrary SQL)."""
from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetDataProduct(Base):
    __tablename__ = "asset_data_products"
    __table_args__ = (
        UniqueConstraint("product_code", name="uq_asset_data_products_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    product_code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    product_type = Column(Text, nullable=False)  # query | metric
    # refs
    query_code = Column(Text)
    metric_code = Column(Text)
    # pin version or use active
    pin_version = Column(Integer)
    source_code = Column(Text)
    parameter_schema = Column(JSONB)  # {name: {type, required}}
    max_rows = Column(Integer, server_default="1000")
    result_storage = Column(Text, server_default="none")
    owner_name = Column(Text)
    enabled = Column(Boolean, nullable=False, server_default="true")
    ai_readable = Column(Boolean, server_default="true")
    rate_limit_per_min = Column(Integer, server_default="30")
    # 144 S4: publish revision + validated pin + concurrency quota
    revision = Column(Integer, nullable=False, server_default="1")
    pin_validated_at = Column(TIMESTAMP(timezone=True))
    pin_validation_status = Column(Text)
    max_concurrency = Column(Integer)
    created_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
