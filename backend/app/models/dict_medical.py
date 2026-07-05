from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class DictMedicalCodeSet(Base):
    __tablename__ = "asset_dict_medical_code_sets"
    __table_args__ = (
        UniqueConstraint("code_set_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    code_set_code = Column(Text, nullable=False)
    code_set_type = Column(Text, nullable=False)
    code_set_name_cn = Column(Text, nullable=False)
    standard_system = Column(Text)
    version_no = Column(Text)
    source_system = Column(Text)
    enabled = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictMedicalCodeItem(Base):
    __tablename__ = "asset_dict_medical_code_items"
    __table_args__ = (
        UniqueConstraint("code_set_code", "item_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    code_set_code = Column(Text, nullable=False)
    item_code = Column(Text, nullable=False)
    item_name_cn = Column(Text, nullable=False)
    item_name_alias = Column(Text)
    category_code = Column(Text, nullable=False)
    parent_code = Column(Text)
    status = Column(Text, server_default="active")
    effective_from = Column(TIMESTAMP(timezone=True))
    effective_to = Column(TIMESTAMP(timezone=True))
    extra = Column(JSONB)


class DictMedicalCodeMapping(Base):
    __tablename__ = "asset_dict_medical_code_mappings"
    __table_args__ = (
        UniqueConstraint("category_code", "from_code_set", "from_item_code", "to_code_set", "to_item_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    from_code_set = Column(Text, nullable=False)
    from_item_code = Column(Text, nullable=False)
    to_code_set = Column(Text, nullable=False)
    to_item_code = Column(Text, nullable=False)
    mapping_type = Column(Text, server_default="manual")
    mapping_cardinality = Column(Text)
    confidence = Column(Text, server_default="unknown")
    review_status = Column(Text, server_default="draft")
    reviewer = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictMedicalSyncDiff(Base):
    __tablename__ = "asset_dict_medical_sync_diffs"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    target_system = Column(Text, nullable=False)
    target_source_code = Column(Text)
    diff_type = Column(Text, nullable=False)
    code_set_code = Column(Text)
    item_code = Column(Text)
    before_data = Column(JSONB)
    after_data = Column(JSONB)
    severity = Column(Text, server_default="medium")
    status = Column(Text, server_default="open")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    handled_at = Column(TIMESTAMP(timezone=True))
