"""add target identity keys for system/source unification.

Revision ID: w9d0e1f2a3b4
Revises: v8c9d0e1f2a3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w9d0e1f2a3b4"
down_revision: Union[str, None] = "v8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema = "asset"
    for table, columns in {
        "asset_systems": [("target_host", sa.Text()), ("system_identity_key", sa.Text())],
        "asset_data_sources": [("target_host", sa.Text()), ("connection_identity_key", sa.Text()), ("identity_source", sa.Text(), "manual"), ("credential_status", sa.Text(), "unconfigured")],
    }.items():
        for item in columns:
            name, type_ = item[0], item[1]
            default = item[2] if len(item) > 2 else None
            op.add_column(table, sa.Column(name, type_, server_default=default), schema=schema)
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id, lower(coalesce(target_host, system_code)) AS base_key,
                   row_number() OVER (PARTITION BY lower(coalesce(target_host, system_code)) ORDER BY id) AS rn
            FROM asset.asset_systems
        )
        UPDATE asset.asset_systems s
        SET system_identity_key = CASE WHEN ranked.rn = 1 THEN ranked.base_key ELSE ranked.base_key || ':' || s.system_code END
        FROM ranked WHERE s.id = ranked.id AND s.system_identity_key IS NULL
    """))
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id, lower(concat_ws(':', coalesce(target_host, host_masked, source_code), coalesce(port::text, ''), coalesce(service_name, database_name, ''))) AS base_key,
                   row_number() OVER (PARTITION BY lower(concat_ws(':', coalesce(target_host, host_masked, source_code), coalesce(port::text, ''), coalesce(service_name, database_name, ''))) ORDER BY id) AS rn
            FROM asset.asset_data_sources
        )
        UPDATE asset.asset_data_sources s
        SET connection_identity_key = CASE WHEN ranked.rn = 1 THEN ranked.base_key ELSE ranked.base_key || ':' || s.source_code END
        FROM ranked WHERE s.id = ranked.id AND s.connection_identity_key IS NULL
    """))
    op.create_unique_constraint("uq_asset_systems_identity_key", "asset_systems", ["system_identity_key"], schema=schema)
    op.create_unique_constraint("uq_asset_data_sources_connection_identity_key", "asset_data_sources", ["connection_identity_key"], schema=schema)
    op.create_index("ix_asset_data_sources_target_host", "asset_data_sources", ["target_host"], schema=schema)


def downgrade() -> None:
    schema = "asset"
    op.drop_index("ix_asset_data_sources_target_host", table_name="asset_data_sources", schema=schema)
    op.drop_constraint("uq_asset_data_sources_connection_identity_key", "asset_data_sources", schema=schema, type_="unique")
    op.drop_constraint("uq_asset_systems_identity_key", "asset_systems", schema=schema, type_="unique")
    for table, names in {"asset_data_sources": ["credential_status", "identity_source", "connection_identity_key", "target_host"], "asset_systems": ["system_identity_key", "target_host"]}.items():
        for name in names: op.drop_column(table, name, schema=schema)
