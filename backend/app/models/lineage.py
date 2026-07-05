from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP
from sqlalchemy.sql import func

from ..core.db import Base


class AssetViewDependency(Base):
    __tablename__ = "asset_view_dependencies"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    view_name = Column(Text, nullable=False)
    referenced_schema = Column(Text)
    referenced_table = Column(Text, nullable=False)
    alias = Column(Text)
    source_file = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
