"""add api_key user_identifier for RBAC

Revision ID: l9e0f1a2b3c4
Revises: k8d9e0f1a2b3
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "l9e0f1a2b3c4"
down_revision: Union[str, None] = "k8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("asset_api_keys", sa.Column("user_identifier", sa.Text()), schema="asset")


def downgrade() -> None:
    op.drop_column("asset_api_keys", "user_identifier", schema="asset")
