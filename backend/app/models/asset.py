from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetTable(Base):
    __tablename__ = "asset_tables"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    system_code = Column(Text)
    source_code = Column(Text)
    namespace_name = Column(Text)
    schema_name = Column(Text)
    table_name = Column(Text)
    table_name_cn = Column(Text)
    business_desc_cn = Column(Text)
    table_role = Column(Text)
    comment = Column(Text)
    row_count_stats = Column(Text)
    column_count = Column(Integer)
    domain = Column(Text)
    grain = Column(Text)
    pk = Column(Text)
    confidence = Column(Text)
    include_status = Column(Text, server_default="candidate")
    review_status = Column(Text, server_default="unreviewed")
    reviewed_by = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    note = Column(Text)
    source = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AssetColumn(Base):
    __tablename__ = "asset_columns"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    system_code = Column(Text)
    source_code = Column(Text)
    namespace_name = Column(Text)
    schema_name = Column(Text)
    table_name = Column(Text)
    column_id = Column(Integer)
    column_name = Column(Text)
    column_name_cn = Column(Text)
    business_desc_cn = Column(Text)
    value_desc_cn = Column(Text)
    data_type = Column(Text)
    length = Column(Integer)
    nullable = Column(Text)
    comment = Column(Text)
    semantic_type = Column(Text)
    is_sensitive = Column(Boolean, server_default="false")
    review_status = Column(Text, server_default="unreviewed")


class AssetRelation(Base):
    __tablename__ = "asset_relations"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    rel_id = Column(Integer)
    domain = Column(Text)
    from_table = Column(Text)
    from_columns = Column(Text)
    to_table = Column(Text)
    to_columns = Column(Text)
    join_condition = Column(Text)
    cardinality = Column(Text)
    confidence = Column(Text)
    validation_level = Column(Text)
    validation_status = Column(Text)
    validation_metrics = Column(Text)
    note = Column(Text)
    validation_note = Column(Text)


class AssetRelationReview(Base):
    __tablename__ = "asset_relation_reviews"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    relation_scope = Column(Text, nullable=False, server_default="formal")
    source_relation_table = Column(Text)
    source_relation_id = Column(BigInteger)
    from_system_code = Column(Text)
    from_source_code = Column(Text)
    from_table = Column(Text, nullable=False)
    from_columns = Column(Text)
    to_system_code = Column(Text)
    to_source_code = Column(Text)
    to_table = Column(Text, nullable=False)
    to_columns = Column(Text)
    join_condition = Column(Text)
    relation_desc_cn = Column(Text)
    business_logic_cn = Column(Text)
    confidence = Column(Text)
    validation_status = Column(Text)
    review_status = Column(Text, server_default="draft")
    reviewer = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_note = Column(Text)
    source_evidence = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
