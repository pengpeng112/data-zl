"""r200: auth account_type + dict push plan execution_status.

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2

200 号一次性整改（手写，未用 autogenerate）：
- asset_auth_users.account_type：显式账号类型（human/service/emergency），
  新 human 账号强制人员绑定（R05），既有账号默认 human 不受锁死；
- asset_dict_medical_push_plans.execution_status：执行状态轴（D06），
  与既有 status（授权状态轴）分离，兼容字段保留。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE asset.asset_auth_users "
        "ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'human'"
    ))
    op.execute(sa.text(
        "ALTER TABLE asset.asset_dict_medical_push_plans "
        "ADD COLUMN IF NOT EXISTS execution_status TEXT"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE asset.asset_dict_medical_push_plans "
        "DROP COLUMN IF EXISTS execution_status"
    ))
    op.execute(sa.text(
        "ALTER TABLE asset.asset_auth_users "
        "DROP COLUMN IF EXISTS account_type"
    ))
