"""add permission resources, profile governance fields and data scopes.

Revision ID: u7b8c9d0e1f2
Revises: t6a7b8c9d0e1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "u7b8c9d0e1f2"
down_revision: Union[str, None] = "t6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema = "asset"

    op.create_table(
        "asset_permission_resources",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("resource_code", sa.Text(), nullable=False),
        sa.Column("resource_name_cn", sa.Text(), nullable=False),
        sa.Column("module_code", sa.Text(), nullable=False),
        sa.Column("action_code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("resource_code", name="uq_asset_permission_resources_code"),
        schema=schema,
    )
    op.create_index(
        "ix_asset_permission_resources_module_action",
        "asset_permission_resources",
        ["module_code", "action_code"],
        schema=schema,
    )

    op.create_table(
        "asset_user_data_scopes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_identifier", sa.Text(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("system_code", sa.Text()),
        sa.Column("source_code", sa.Text()),
        sa.Column("schema_name", sa.Text()),
        sa.Column("domain", sa.Text()),
        sa.Column("filter_json", postgresql.JSONB()),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True)),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("request_id", sa.BigInteger()),
        sa.Column("granted_by", sa.Text()),
        sa.Column("revoked_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema=schema,
    )
    op.create_index(
        "ix_asset_user_data_scopes_user_status",
        "asset_user_data_scopes",
        ["user_identifier", "status"],
        schema=schema,
    )

    for name, type_ in [
        ("source", sa.Text()),
        ("request_id", sa.BigInteger()),
        ("status", sa.Text()),
        ("valid_from", sa.TIMESTAMP(timezone=True)),
    ]:
        op.add_column("asset_user_roles", sa.Column(name, type_), schema=schema)
    op.execute(sa.text("UPDATE asset.asset_user_roles SET source='direct', status='active' WHERE source IS NULL OR status IS NULL"))
    op.alter_column("asset_user_roles", "source", nullable=False, server_default="direct", schema=schema)
    op.alter_column("asset_user_roles", "status", nullable=False, server_default="active", schema=schema)
    op.create_index(
        "ix_asset_user_roles_user_status",
        "asset_user_roles",
        ["user_identifier", "status"],
        schema=schema,
    )

    op.execute(sa.text("""
        DELETE FROM asset.asset_role_permissions a
        USING asset.asset_role_permissions b
        WHERE a.id > b.id
          AND a.role_code = b.role_code
          AND a.resource = b.resource
          AND a.action = b.action
    """))
    op.create_unique_constraint(
        "uq_asset_role_permissions_role_resource_action",
        "asset_role_permissions",
        ["role_code", "resource", "action"],
        schema=schema,
    )

    for name, type_, default in [
        ("profile_summary", sa.Text(), None),
        ("profile_tags", postgresql.JSONB(), None),
        ("review_status", sa.Text(), "unreviewed"),
        ("profile_updated_at", sa.TIMESTAMP(timezone=True), None),
        ("created_at", sa.TIMESTAMP(timezone=True), None),
    ]:
        op.add_column("asset_identity_persons", sa.Column(name, type_, server_default=default), schema=schema)


def downgrade() -> None:
    schema = "asset"
    op.drop_column("asset_identity_persons", "created_at", schema=schema)
    op.drop_column("asset_identity_persons", "profile_updated_at", schema=schema)
    op.drop_column("asset_identity_persons", "review_status", schema=schema)
    op.drop_column("asset_identity_persons", "profile_tags", schema=schema)
    op.drop_column("asset_identity_persons", "profile_summary", schema=schema)
    op.drop_constraint("uq_asset_role_permissions_role_resource_action", "asset_role_permissions", schema=schema, type_="unique")
    op.drop_index("ix_asset_user_roles_user_status", table_name="asset_user_roles", schema=schema)
    for name in ["valid_from", "status", "request_id", "source"]:
        op.drop_column("asset_user_roles", name, schema=schema)
    op.drop_index("ix_asset_user_data_scopes_user_status", table_name="asset_user_data_scopes", schema=schema)
    op.drop_table("asset_user_data_scopes", schema=schema)
    op.drop_index("ix_asset_permission_resources_module_action", table_name="asset_permission_resources", schema=schema)
    op.drop_table("asset_permission_resources", schema=schema)
