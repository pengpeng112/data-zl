from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, Boolean, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class DictCategory(Base):
    __tablename__ = "asset_dict_categories"
    __table_args__ = (
        UniqueConstraint("category_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    category_name_cn = Column(Text, nullable=False)
    standard_system = Column(Text)
    description_cn = Column(Text)
    enabled = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictStandardItem(Base):
    __tablename__ = "asset_dict_standard_items"
    __table_args__ = (
        UniqueConstraint("category_code", "standard_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    standard_code = Column(Text, nullable=False)
    standard_name_cn = Column(Text, nullable=False)
    standard_name_en = Column(Text)
    parent_code = Column(Text)
    pinyin_code = Column(Text)
    wubi_code = Column(Text)
    status = Column(Text, server_default="active")
    effective_from = Column(Date)
    effective_to = Column(Date)
    description_cn = Column(Text)
    extra = Column(JSONB)


class DictSystemItem(Base):
    __tablename__ = "asset_dict_system_items"
    __table_args__ = (
        UniqueConstraint("category_code", "system_code", "system_item_code"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    system_code = Column(Text, nullable=False)
    source_code = Column(Text)
    namespace_name = Column(Text)
    source_table = Column(Text)
    source_key_column = Column(Text)
    source_name_column = Column(Text)
    system_item_code = Column(Text, nullable=False)
    system_item_name_cn = Column(Text, nullable=False)
    raw_status = Column(Text)
    raw_extra = Column(JSONB)
    last_sync_at = Column(TIMESTAMP(timezone=True))


class DictItemMapping(Base):
    __tablename__ = "asset_dict_item_mappings"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    standard_code = Column(Text)
    system_code = Column(Text, nullable=False)
    system_item_code = Column(Text, nullable=False)
    mapping_type = Column(Text, server_default="manual")
    confidence = Column(Text)
    review_status = Column(Text, server_default="draft")
    reviewer = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DictVersion(Base):
    __tablename__ = "asset_dict_versions"
    __table_args__ = (
        UniqueConstraint("category_code", "version_no"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    category_code = Column(Text, nullable=False)
    version_no = Column(Text, nullable=False)
    version_name_cn = Column(Text)
    publish_status = Column(Text, server_default="draft")
    published_by = Column(Text)
    published_at = Column(TIMESTAMP(timezone=True))
    note = Column(Text)
