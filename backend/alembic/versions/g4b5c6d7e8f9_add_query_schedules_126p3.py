"""126 P3: asset_query_schedules (default disabled).

Hand-written. Production schedule enable requires separate authorization.
"""

from alembic import op
import sqlalchemy as sa

revision = "g4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_query_schedules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("query_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text()),
        sa.Column("schedule_cron", sa.Text(), nullable=False, server_default="0 3 * * *"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("result_storage", sa.Text(), server_default="none"),
        sa.Column("max_rows", sa.Integer(), server_default="1000"),
        sa.Column("timeout_seconds", sa.Integer(), server_default="300"),
        sa.Column("max_retries", sa.Integer(), server_default="1"),
        sa.Column("last_run_id", sa.BigInteger()),
        sa.Column("last_status", sa.Text()),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("query_code", name="uq_asset_query_schedules_code"),
        schema="asset",
    )


def downgrade() -> None:
    op.drop_table("asset_query_schedules", schema="asset")
