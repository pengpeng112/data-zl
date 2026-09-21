"""186 I2/I3: dual-source account state decisions and target attempts.

Adds asset.asset_identity_account_state_decisions (per-person dual-source
truth-table captures with transition ordinals) and
asset.asset_identity_account_state_attempts (per-target disable/enable
attempts with lock attribution and idempotent transition identity).

Handwritten upgrade/downgrade (no autogenerate). Old rows do not exist yet;
nothing is backfilled — legacy lock history stays unverified by design.
"""

from alembic import op
import sqlalchemy as sa

revision: str = "c6d7e8f9a0b1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def _portable_json():
    return sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "asset_identity_account_state_decisions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("person_code", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Text(), nullable=False, server_default="dual_source_v1"),
        sa.Column("employee_state", sa.Text(), nullable=False),
        sa.Column("employee_state_reason", sa.Text(), nullable=True),
        sa.Column("user_state", sa.Text(), nullable=False),
        sa.Column("user_state_reason", sa.Text(), nullable=True),
        sa.Column("desired_state", sa.Text(), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("execution_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("employee_evidence", _portable_json(), nullable=True),
        sa.Column("user_evidence", _portable_json(), nullable=True),
        sa.Column("evidence_fingerprint", sa.Text(), nullable=False),
        sa.Column("transition_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "person_code", "rule_version", "evidence_fingerprint",
            name="uq_account_state_decision",
        ),
        schema="asset",
    )
    op.create_index(
        "ix_account_state_decision_person",
        "asset_identity_account_state_decisions",
        ["person_code", "created_at"],
        schema="asset",
    )

    op.create_table(
        "asset_identity_account_state_attempts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("batch_id", sa.Text(), nullable=True),
        sa.Column("decision_id", sa.BigInteger(), nullable=True),
        sa.Column("person_code", sa.Text(), nullable=False),
        sa.Column("target_system", sa.Text(), nullable=False),
        sa.Column("target_account_fingerprint", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("before_state", sa.Text(), nullable=True),
        sa.Column("desired_state", sa.Text(), nullable=False),
        sa.Column("after_state", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_code_masked", sa.Text(), nullable=True),
        sa.Column("lock_attribution", sa.Text(), nullable=True),
        sa.Column("attribution_evidence", _portable_json(), nullable=True),
        sa.Column("rule_version", sa.Text(), nullable=False, server_default="dual_source_v1"),
        sa.Column("transition_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "target_account_fingerprint", "action", "transition_seq", "rule_version",
            name="uq_account_state_attempt_idempotency",
        ),
        schema="asset",
    )
    op.create_index(
        "ix_account_state_attempt_run",
        "asset_identity_account_state_attempts",
        ["run_id"],
        schema="asset",
    )
    op.create_index(
        "ix_account_state_attempt_person",
        "asset_identity_account_state_attempts",
        ["person_code"],
        schema="asset",
    )


def downgrade() -> None:
    op.drop_index("ix_account_state_attempt_person", table_name="asset_identity_account_state_attempts", schema="asset")
    op.drop_index("ix_account_state_attempt_run", table_name="asset_identity_account_state_attempts", schema="asset")
    op.drop_table("asset_identity_account_state_attempts", schema="asset")
    op.drop_index("ix_account_state_decision_person", table_name="asset_identity_account_state_decisions", schema="asset")
    op.drop_table("asset_identity_account_state_decisions", schema="asset")
