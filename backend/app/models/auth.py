"""Local account authentication models (asset_auth_*)."""

from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, TIMESTAMP, Index
from sqlalchemy.sql import func

from ..core.db import Base


class AuthUser(Base):
    __tablename__ = "asset_auth_users"
    __table_args__ = (
        Index("ix_asset_auth_users_user_identifier", "user_identifier"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    username = Column(Text, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    user_identifier = Column(Text)
    enabled = Column(Boolean, nullable=False, server_default="true")
    must_change_password = Column(Boolean, nullable=False, server_default="false")
    failed_login_count = Column(Integer, nullable=False, server_default="0")
    locked_until = Column(TIMESTAMP(timezone=True))
    last_login_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class AuthSession(Base):
    __tablename__ = "asset_auth_sessions"
    __table_args__ = (
        Index("ix_asset_auth_sessions_user_expires", "user_id", "expires_at"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    refresh_token_hash = Column(Text, unique=True, nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_used_at = Column(TIMESTAMP(timezone=True))
    client_ip_masked = Column(Text)
    user_agent = Column(Text)


class AuthLoginEvent(Base):
    __tablename__ = "asset_auth_login_events"
    __table_args__ = (
        Index("ix_asset_auth_login_events_created", "created_at"),
        Index("ix_asset_auth_login_events_username", "username"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    username = Column(Text)
    user_identifier = Column(Text)
    result = Column(Text, nullable=False)  # success | failure
    reason_code = Column(Text)
    client_ip_masked = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
