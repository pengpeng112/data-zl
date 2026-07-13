"""asset_relation_recipes - relationship recipe/knowledge base model."""
from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AssetRelationRecipe(Base):
    __tablename__ = "asset_relation_recipes"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    recipe_id = Column(Text, unique=True, nullable=False, index=True)
    status = Column(Text, nullable=False, server_default="candidate")
    domain = Column(Text)
    source_system = Column(Text)
    recommended_view_name = Column(Text)
    description = Column(Text)
    business_domain = Column(Text)
    primary_tables = Column(JSONB)
    joins = Column(JSONB)
    ai_readable = Column(Boolean, server_default="true")
    imported_from = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True))
