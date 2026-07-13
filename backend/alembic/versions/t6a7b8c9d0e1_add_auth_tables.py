"""add asset_auth_users/sessions/login_events tables

Revision ID: t6a7b8c9d0e1
Revises: s5f6a7b8c9d0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t6a7b8c9d0e1"
down_revision: Union[str, None] = "s5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_auth_users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("user_identifier", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )
    op.create_index("ix_asset_auth_users_username", "asset_auth_users", ["username"], unique=True, schema="asset")
    op.create_index("ix_asset_auth_users_user_identifier", "asset_auth_users", ["user_identifier"], schema="asset")

    op.create_table(
        "asset_auth_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("client_ip_masked", sa.Text()),
        sa.Column("user_agent", sa.Text()),
        schema="asset",
    )
    op.create_index(
        "ix_asset_auth_sessions_refresh_token_hash",
        "asset_auth_sessions",
        ["refresh_token_hash"],
        unique=True,
        schema="asset",
    )
    op.create_index(
        "ix_asset_auth_sessions_user_expires",
        "asset_auth_sessions",
        ["user_id", "expires_at"],
        schema="asset",
    )
    op.create_index("ix_asset_auth_sessions_user_id", "asset_auth_sessions", ["user_id"], schema="asset")

    op.create_table(
        "asset_auth_login_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.Text()),
        sa.Column("user_identifier", sa.Text()),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text()),
        sa.Column("client_ip_masked", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )
    op.create_index(
        "ix_asset_auth_login_events_created",
        "asset_auth_login_events",
        ["created_at"],
        schema="asset",
    )
    op.create_index(
        "ix_asset_auth_login_events_username",
        "asset_auth_login_events",
        ["username"],
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_auth_login_events", schema="asset")
    op.drop_table("asset_auth_sessions", schema="asset")
    op.drop_table("asset_auth_users", schema="asset")
