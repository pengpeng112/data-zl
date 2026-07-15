"""asset_relation_recipes - relationship recipe/knowledge base model."""
from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetRelationRecipe(Base):
    __tablename__ = "asset_relation_recipes"
    __table_args__ = (
        UniqueConstraint("recipe_id", "version", name="uq_asset_relation_recipes_recipe_version"),
        Index("ix_asset_relation_recipes_recipe_status", "recipe_id", "status"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    recipe_id = Column(Text, nullable=False, index=True)
    version = Column(Integer, nullable=False, server_default="1")
    recipe_name = Column(Text)
    status = Column(Text, nullable=False, server_default="draft")
    is_active = Column(Boolean, nullable=False, server_default="false")
    parent_version_id = Column(BigInteger)
    recipe_json = Column(JSONB)
    domain = Column(Text)
    source_system = Column(Text)
    recommended_view_name = Column(Text)
    description = Column(Text)
    business_domain = Column(Text)
    primary_tables = Column(JSONB)
    joins = Column(JSONB)
    ai_readable = Column(Boolean, server_default="true")
    evidence_summary = Column(JSONB)
    risk_summary = Column(JSONB)
    generated_sql = Column(Text)
    sql_dialect = Column(Text)
    content_hash = Column(Text)
    created_by = Column(Text)
    updated_by = Column(Text)
    reviewed_by = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    review_reason = Column(Text)
    imported_from = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True))
