"""drop legacy recipe_id-only unique index.

Revision ID: z2f3a4b5c6d7
Revises: y1f2a3b4c5d6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z2f3a4b5c6d7"
down_revision: Union[str, None] = "y1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # v8 removed a legacy UNIQUE constraint, but older installations created
    # recipe_id uniqueness as a standalone index.  It must also be replaced
    # so version 2+ rows can be inserted.
    op.execute(sa.text("DROP INDEX IF EXISTS asset.ix_asset_asset_relation_recipes_recipe_id"))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_asset_asset_relation_recipes_recipe_id "
        "ON asset.asset_relation_recipes (recipe_id)"
    ))


def downgrade() -> None:
    op.execute(sa.text("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM asset.asset_relation_recipes
                GROUP BY recipe_id HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'cannot downgrade: multiple recipe versions exist';
            END IF;
        END $$;
    """))
    op.execute(sa.text("DROP INDEX IF EXISTS asset.ix_asset_asset_relation_recipes_recipe_id"))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX ix_asset_asset_relation_recipes_recipe_id "
        "ON asset.asset_relation_recipes (recipe_id)"
    ))
