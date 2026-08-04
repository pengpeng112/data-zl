"""add group_class to identity person departments

Revision ID: f8a9b0c1d2e3
Revises: f1a2b3c4d5e6
Create Date: 2026-08-03

Hand-written migration per AGENTS.md constraint (no --autogenerate).

Adds asset_identity_person_departments.group_class: the HIS
STAFF_VS_GROUP.GROUP_CLASS value (e.g. 病区医生/病区护士) for rows collected
from staff groups. Required by the plan-107 additional-department whitelist
(doctor -> 病区医生, nurse -> 病区护士, pharmacist -> primary dept only).
"""

from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "asset_identity_person_departments",
        sa.Column("group_class", sa.Text),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_column("asset_identity_person_departments", "group_class", schema="asset")
