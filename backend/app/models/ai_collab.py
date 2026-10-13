from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class AiSession(Base):
    __tablename__ = "asset_ai_sessions"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    session_key = Column(Text, unique=True, nullable=False)
    purpose = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AiToolCall(Base):
    __tablename__ = "asset_ai_tool_calls"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    session_key = Column(Text)
    tool_name = Column(Text)
    request = Column(JSONB)
    response_summary = Column(Text)
    called_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class ViewDraft(Base):
    __tablename__ = "asset_view_drafts"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    session_key = Column(Text)
    title = Column(Text)
    sql_text = Column(Text)
    purpose = Column(Text)
    status = Column(Text, server_default="draft")
    risk_flags = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    reviewed_by = Column(Text)
    reviewed_at = Column(TIMESTAMP(timezone=True))
    feedback = Column(Text)


class AiContextSnapshot(Base):
    """144 S6: versioned unified AI context snapshot (ai-data-context/v1)."""

    __tablename__ = "asset_ai_context_snapshots"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    context_id = Column(Text, nullable=False, unique=True)
    schema_version = Column(Text, nullable=False, server_default="ai-data-context/v1")
    question_summary = Column(Text)
    generated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True))
    manifest_hash = Column(Text)
    object_count = Column(Integer, server_default="0")
    relation_count = Column(Integer, server_default="0")
    query_count = Column(Integer, server_default="0")
    metric_count = Column(Integer, server_default="0")
    product_count = Column(Integer, server_default="0")
    truncated = Column(Boolean, server_default="false")
    # compact manifest of references; large payloads stay in this JSONB as
    # bounded summaries only (no patient data, no full sensitive SQL)
    snapshot_json = Column(JSONB)
    created_by = Column(Text)


class AiContextCacheEntry(Base):
    """215 E5: AI 上下文构建缓存条目。

    缓存键 = system_code + question 归一化 + 全部构建参数 + 权限过滤摘要
    （见 services/ai_context_cache.py）。**禁止**用 manifest_hash 作缓存键——
    它只哈希各类计数，同计数不同题会串快照（round-12 三方实锤）。
    缓存命中不消除留档：每次 resolve 仍会写一条 asset_ai_context_snapshots。
    """

    __tablename__ = "asset_ai_context_cache"
    __table_args__ = {"schema": "asset"}

    id = Column(BigInteger, primary_key=True)
    cache_key = Column(Text, nullable=False, unique=True)
    built_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    hit_count = Column(Integer, nullable=False, server_default="0")
    snapshot_json = Column(JSONB, nullable=False)
    created_by = Column(Text)
