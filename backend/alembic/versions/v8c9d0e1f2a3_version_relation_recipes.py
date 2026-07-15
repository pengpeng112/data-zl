"""version relation recipes and add recipe governance fields.

Revision ID: v8c9d0e1f2a3
Revises: u7b8c9d0e1f2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "v8c9d0e1f2a3"
down_revision: Union[str, None] = "u7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema = "asset"
    additions = [
        ("version", sa.Integer(), "1"), ("recipe_name", sa.Text(), None),
        ("is_active", sa.Boolean(), "false"), ("parent_version_id", sa.BigInteger(), None),
        ("recipe_json", postgresql.JSONB(), None), ("evidence_summary", postgresql.JSONB(), None),
        ("risk_summary", postgresql.JSONB(), None), ("generated_sql", sa.Text(), None),
        ("sql_dialect", sa.Text(), None), ("content_hash", sa.Text(), None),
        ("created_by", sa.Text(), None), ("updated_by", sa.Text(), None),
        ("reviewed_by", sa.Text(), None), ("reviewed_at", sa.TIMESTAMP(timezone=True), None),
        ("review_reason", sa.Text(), None),
    ]
    for name, type_, default in additions:
        op.add_column("asset_relation_recipes", sa.Column(name, type_, server_default=default), schema=schema)

    op.execute(sa.text("""
        UPDATE asset.asset_relation_recipes
        SET recipe_json = jsonb_build_object(
            'primary_tables', COALESCE(primary_tables, '[]'::jsonb),
            'joins', COALESCE(joins, '[]'::jsonb),
            'description', description
        ),
        content_hash = md5(COALESCE(recipe_id, '') || ':' || COALESCE(primary_tables::text, '') || ':' || COALESCE(joins::text, '')),
        status = CASE
            WHEN status IN ('formal', 'user_confirmed', 'verified') THEN 'active'
            WHEN status = 'rejected' THEN 'deprecated'
            ELSE 'draft'
        END,
        is_active = CASE WHEN status IN ('formal', 'user_confirmed', 'verified') THEN true ELSE false END,
        ai_readable = CASE WHEN status IN ('formal', 'user_confirmed', 'verified') THEN true ELSE false END
    """))
    op.alter_column("asset_relation_recipes", "content_hash", nullable=False, schema=schema)

    # Drop the legacy recipe_id-only unique constraint without assuming its generated name.
    op.execute(sa.text("""
        DO $$ DECLARE c record; BEGIN
            FOR c IN SELECT conname FROM pg_constraint
            WHERE conrelid = 'asset.asset_relation_recipes'::regclass
              AND contype = 'u'
              AND pg_get_constraintdef(oid) LIKE '%(recipe_id)%'
              AND pg_get_constraintdef(oid) NOT LIKE '%version%'
            LOOP EXECUTE format('ALTER TABLE asset.asset_relation_recipes DROP CONSTRAINT %I', c.conname); END LOOP;
        END $$;
    """))
    op.create_unique_constraint("uq_asset_relation_recipes_recipe_version", "asset_relation_recipes", ["recipe_id", "version"], schema=schema)
    op.create_index("uq_asset_relation_recipes_active", "asset_relation_recipes", ["recipe_id"], unique=True, schema=schema, postgresql_where=sa.text("is_active = true"))


def downgrade() -> None:
    schema = "asset"
    op.execute(sa.text("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM asset.asset_relation_recipes WHERE version > 1) THEN
                RAISE EXCEPTION 'cannot downgrade: export or remove recipe versions greater than 1 first';
            END IF;
        END $$;
    """))
    op.drop_index("uq_asset_relation_recipes_active", table_name="asset_relation_recipes", schema=schema)
    op.drop_constraint("uq_asset_relation_recipes_recipe_version", "asset_relation_recipes", schema=schema, type_="unique")
    op.create_unique_constraint("uq_asset_relation_recipes_recipe_id", "asset_relation_recipes", ["recipe_id"], schema=schema)
    for name in ["review_reason", "reviewed_at", "reviewed_by", "updated_by", "created_by", "content_hash", "sql_dialect", "generated_sql", "risk_summary", "evidence_summary", "recipe_json", "parent_version_id", "is_active", "recipe_name", "version"]:
        op.drop_column("asset_relation_recipes", name, schema=schema)
