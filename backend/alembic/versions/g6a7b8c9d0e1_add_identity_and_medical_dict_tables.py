"""add_identity_and_medical_dict_tables

Revision ID: g6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-04 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    s = "asset"

    # P12 identity tables
    op.create_table(
        "asset_identity_departments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("dept_code", sa.Text(), nullable=False),
        sa.Column("dept_name_cn", sa.Text(), nullable=False),
        sa.Column("dept_type", sa.Text()),
        sa.Column("parent_dept_code", sa.Text()),
        sa.Column("source_system", sa.Text(), server_default="HIS"),
        sa.Column("source_table", sa.Text(), server_default="dept_dict"),
        sa.Column("source_dept_id", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active"),
        sa.Column("last_source_sync_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_status", sa.Text(), server_default="unreviewed"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dept_code"),
        schema=s,
    )

    op.create_table(
        "asset_identity_persons",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("person_code", sa.Text(), nullable=False),
        sa.Column("person_name_cn", sa.Text()),
        sa.Column("dept_code", sa.Text()),
        sa.Column("dept_name_cn", sa.Text()),
        sa.Column("job_title", sa.Text()),
        sa.Column("person_type", sa.Text(), server_default="formal"),
        sa.Column("employment_status", sa.Text()),
        sa.Column("primary_source_system", sa.Text()),
        sa.Column("source_system", sa.Text()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_code"),
        schema=s,
    )

    op.create_table(
        "asset_identity_person_sources",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("person_code", sa.Text()),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("source_table", sa.Text()),
        sa.Column("source_person_id", sa.Text(), nullable=False),
        sa.Column("source_person_name", sa.Text()),
        sa.Column("source_dept_code", sa.Text()),
        sa.Column("source_status", sa.Text()),
        sa.Column("is_temporary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("match_status", sa.Text(), server_default="unmatched"),
        sa.Column("raw_data", postgresql.JSONB()),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_system", "source_table", "source_person_id"),
        schema=s,
    )

    op.create_table(
        "asset_identity_accounts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("person_code", sa.Text()),
        sa.Column("system_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("account_name", sa.Text()),
        sa.Column("account_status", sa.Text()),
        sa.Column("role_codes", sa.Text()),
        sa.Column("role_names_cn", sa.Text()),
        sa.Column("dept_code", sa.Text()),
        sa.Column("dept_name_cn", sa.Text()),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_status", sa.Text(), server_default="unreviewed"),
        sa.Column("note", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_code", "account_id"),
        schema=s,
    )

    op.create_table(
        "asset_identity_sync_diffs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("diff_type", sa.Text(), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("target_system", sa.Text()),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_code", sa.Text()),
        sa.Column("before_data", postgresql.JSONB()),
        sa.Column("after_data", postgresql.JSONB()),
        sa.Column("severity", sa.Text(), server_default="medium"),
        sa.Column("status", sa.Text(), server_default="open"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("handled_at", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )

    # P13 medical dict tables
    op.create_table(
        "asset_dict_medical_code_sets",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("code_set_code", sa.Text(), nullable=False),
        sa.Column("code_set_type", sa.Text(), nullable=False),
        sa.Column("code_set_name_cn", sa.Text(), nullable=False),
        sa.Column("standard_system", sa.Text()),
        sa.Column("version_no", sa.Text()),
        sa.Column("source_system", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_set_code"),
        schema=s,
    )

    op.create_table(
        "asset_dict_medical_code_items",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code_set_code", sa.Text(), nullable=False),
        sa.Column("item_code", sa.Text(), nullable=False),
        sa.Column("item_name_cn", sa.Text(), nullable=False),
        sa.Column("item_name_alias", sa.Text()),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("parent_code", sa.Text()),
        sa.Column("status", sa.Text(), server_default="active"),
        sa.Column("effective_from", sa.TIMESTAMP(timezone=True)),
        sa.Column("effective_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("extra", postgresql.JSONB()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_set_code", "item_code"),
        schema=s,
    )

    op.create_table(
        "asset_dict_medical_code_mappings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("from_code_set", sa.Text(), nullable=False),
        sa.Column("from_item_code", sa.Text(), nullable=False),
        sa.Column("to_code_set", sa.Text(), nullable=False),
        sa.Column("to_item_code", sa.Text(), nullable=False),
        sa.Column("mapping_type", sa.Text(), server_default="manual"),
        sa.Column("mapping_cardinality", sa.Text()),
        sa.Column("confidence", sa.Text(), server_default="unknown"),
        sa.Column("review_status", sa.Text(), server_default="draft"),
        sa.Column("reviewer", sa.Text()),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_code", "from_code_set", "from_item_code", "to_code_set", "to_item_code"),
        schema=s,
    )

    op.create_table(
        "asset_dict_medical_sync_diffs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("target_system", sa.Text(), nullable=False),
        sa.Column("target_source_code", sa.Text()),
        sa.Column("diff_type", sa.Text(), nullable=False),
        sa.Column("code_set_code", sa.Text()),
        sa.Column("item_code", sa.Text()),
        sa.Column("before_data", postgresql.JSONB()),
        sa.Column("after_data", postgresql.JSONB()),
        sa.Column("severity", sa.Text(), server_default="medium"),
        sa.Column("status", sa.Text(), server_default="open"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("handled_at", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        schema=s,
    )


def downgrade() -> None:
    s = "asset"
    op.drop_table("asset_dict_medical_sync_diffs", schema=s)
    op.drop_table("asset_dict_medical_code_mappings", schema=s)
    op.drop_table("asset_dict_medical_code_items", schema=s)
    op.drop_table("asset_dict_medical_code_sets", schema=s)
    op.drop_table("asset_identity_sync_diffs", schema=s)
    op.drop_table("asset_identity_accounts", schema=s)
    op.drop_table("asset_identity_person_sources", schema=s)
    op.drop_table("asset_identity_persons", schema=s)
    op.drop_table("asset_identity_departments", schema=s)
