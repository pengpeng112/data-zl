from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func

from ..core.db import Base


class AssetCandidateRelation(Base):
    __tablename__ = "asset_candidate_relations"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    domain = Column(Text)
    from_table = Column(Text, nullable=False)
    from_columns = Column(Text)
    to_table = Column(Text, nullable=False)
    to_columns = Column(Text)
    join_condition = Column(Text)
    source_view = Column(Text)
    source_file = Column(Text)
    confidence = Column(Text)
    status = Column(Text, server_default="candidate")
    reviewed_by = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
