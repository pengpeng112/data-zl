from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP
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
