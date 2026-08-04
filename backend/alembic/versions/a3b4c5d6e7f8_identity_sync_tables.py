"""identity sync tables for HIS->CDMS/JHEMR grayscale.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- asset_identity_sync_watermarks ---
    op.create_table(
        "asset_identity_sync_watermarks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_code", sa.Text, nullable=False),
        sa.Column("watermark_key", sa.Text, nullable=False),
        sa.Column("last_create_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_emp_no", sa.Text),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("rows_collected", sa.Integer, server_default="0"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_code", "watermark_key"),
        schema="asset",
    )

    # --- asset_identity_sync_batches ---
    op.create_table(
        "asset_identity_sync_batches",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.Text, nullable=False, unique=True),
        sa.Column("batch_type", sa.Text, nullable=False),
        sa.Column("emp_no_masked", sa.Text),
        sa.Column("person_classification", sa.Text),
        sa.Column("status", sa.Text, server_default="pending"),
        sa.Column("confirmation_token_hash", sa.Text),
        sa.Column("action_hash", sa.Text),
        sa.Column("cdms_status", sa.Text),
        sa.Column("jhemr_status", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )

    # --- asset_identity_sync_actions ---
    op.create_table(
        "asset_identity_sync_actions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.Text, nullable=False),
        sa.Column("action_seq", sa.Integer, nullable=False),
        sa.Column("target_system", sa.Text, nullable=False),
        sa.Column("action_type", sa.Text, nullable=False),
        sa.Column("target_table", sa.Text, nullable=False),
        sa.Column("emp_no_masked", sa.Text),
        sa.Column("params_summary", JSONB),
        sa.Column("status", sa.Text, server_default="planned"),
        sa.Column("rows_affected", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="asset",
    )
    op.create_index("ix_identity_sync_actions_batch", "asset_identity_sync_actions", ["batch_id"], schema="asset")

    # --- asset_identity_role_mappings ---
    op.create_table(
        "asset_identity_role_mappings",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("target_system", sa.Text, nullable=False),
        sa.Column("person_classification", sa.Text, nullable=False),
        sa.Column("mapping_key", sa.Text, nullable=False),
        sa.Column("role_code", sa.Text),
        sa.Column("role_name_cn", sa.Text),
        sa.Column("extra_config", JSONB),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("rule_version", sa.Text, server_default="v1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("target_system", "person_classification", "mapping_key"),
        schema="asset",
    )

    # --- asset_identity_protected_accounts ---
    op.create_table(
        "asset_identity_protected_accounts",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("target_system", sa.Text, nullable=False),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("protected_by", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("target_system", "account_id"),
        schema="asset",
    )

    # --- asset_identity_managed_relations ---
    op.create_table(
        "asset_identity_managed_relations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.Text, nullable=False),
        sa.Column("target_system", sa.Text, nullable=False),
        sa.Column("emp_no_masked", sa.Text),
        sa.Column("relation_type", sa.Text, nullable=False),
        sa.Column("target_table", sa.Text, nullable=False),
        sa.Column("target_key", sa.Text),
        sa.Column("relation_data", JSONB),
        sa.Column("status", sa.Text, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("compensated_at", sa.TIMESTAMP(timezone=True)),
        schema="asset",
    )
    op.create_index("ix_identity_managed_relations_batch", "asset_identity_managed_relations", ["batch_id"], schema="asset")

    # --- asset_identity_sync_compensations ---
    op.create_table(
        "asset_identity_sync_compensations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.Text, nullable=False),
        sa.Column("target_system", sa.Text, nullable=False),
        sa.Column("compensation_type", sa.Text, nullable=False),
        sa.Column("target_table", sa.Text),
        sa.Column("target_key", sa.Text),
        sa.Column("status", sa.Text, server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True)),
        schema="asset",
    )

    # --- asset_identity_classifications ---
    op.create_table(
        "asset_identity_classifications",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("emp_no", sa.Text, nullable=False),
        sa.Column("emp_no_masked", sa.Text),
        sa.Column("raw_job", sa.Text),
        sa.Column("raw_title", sa.Text),
        sa.Column("classification", sa.Text, nullable=False),
        sa.Column("matched_rule", sa.Text),
        sa.Column("rule_version", sa.Text, nullable=False, server_default="v1"),
        sa.Column("conflict_detail", JSONB),
        sa.Column("source_create_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("classified_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("emp_no", "rule_version"),
        schema="asset",
    )

    # --- asset_identity_sync_locks ---
    op.create_table(
        "asset_identity_sync_locks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("lock_key", sa.Text, nullable=False, unique=True),
        sa.Column("lock_holder", sa.Text),
        sa.Column("acquired_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("released_at", sa.TIMESTAMP(timezone=True)),
        schema="asset",
    )

    # --- Add columns to existing asset_identity_persons ---
    op.add_column("asset_identity_persons", sa.Column("source_create_date", sa.TIMESTAMP(timezone=True)), schema="asset")
    op.add_column("asset_identity_persons", sa.Column("raw_job", sa.Text), schema="asset")
    op.add_column("asset_identity_persons", sa.Column("raw_title", sa.Text), schema="asset")
    op.add_column("asset_identity_persons", sa.Column("classification", sa.Text), schema="asset")
    op.add_column("asset_identity_persons", sa.Column("classification_rule_version", sa.Text), schema="asset")
    op.add_column("asset_identity_persons", sa.Column("is_managed", sa.Boolean, server_default="false"), schema="asset")
    op.add_column("asset_identity_persons", sa.Column("conflict_flag", sa.Text), schema="asset")

    # --- Seed role mappings ---
    role_mappings = sa.table(
        "asset_identity_role_mappings",
        sa.column("target_system", sa.Text),
        sa.column("person_classification", sa.Text),
        sa.column("mapping_key", sa.Text),
        sa.column("role_code", sa.Text),
        sa.column("role_name_cn", sa.Text),
        sa.column("extra_config", JSONB),
        sa.column("is_active", sa.Boolean),
        sa.column("rule_version", sa.Text),
        schema="asset",
    )
    op.bulk_insert(role_mappings, [
        {
            "target_system": "CDMS",
            "person_classification": "doctor",
            "mapping_key": "role_ftype0",
            "role_code": "a1c9192fbe31423fab2dce6f81791b88",
            "role_name_cn": "医疗质控角色",
            "extra_config": {"ftype": "0"},
            "is_active": True,
            "rule_version": "v1",
        },
        {
            "target_system": "CDMS",
            "person_classification": "pharmacist",
            "mapping_key": "role_ftype0",
            "role_code": "a1c9192fbe31423fab2dce6f81791b88",
            "role_name_cn": "医疗质控角色",
            "extra_config": {"ftype": "0"},
            "is_active": True,
            "rule_version": "v1",
        },
        {
            "target_system": "CDMS",
            "person_classification": "nurse",
            "mapping_key": "role_ftype0",
            "role_code": "e09c6b5410ed4eefbb5bb57cea51ab0a",
            "role_name_cn": "护理质控角色",
            "extra_config": {"ftype": "0"},
            "is_active": True,
            "rule_version": "v1",
        },
        {
            "target_system": "JHEMR",
            "person_classification": "doctor",
            "mapping_key": "role_group",
            "role_code": "001",
            "role_name_cn": "医师组",
            "extra_config": {"hospital_no": "49557032X", "role_chain": "001->25->DOCTOR/0"},
            "is_active": True,
            "rule_version": "v1",
        },
        {
            "target_system": "JHEMR",
            "person_classification": "pharmacist",
            "mapping_key": "role_group",
            "role_code": "001",
            "role_name_cn": "医师组",
            "extra_config": {"hospital_no": "49557032X", "role_chain": "001->25->DOCTOR/0"},
            "is_active": True,
            "rule_version": "v1",
        },
        {
            "target_system": "JHEMR",
            "person_classification": "nurse",
            "mapping_key": "role_group",
            "role_code": "002",
            "role_name_cn": "护士组",
            "extra_config": {"hospital_no": "49557032X", "role_chain": "002->101->NURSE/1"},
            "is_active": True,
            "rule_version": "v1",
        },
    ])


def downgrade() -> None:
    # Remove added columns from asset_identity_persons
    op.drop_column("asset_identity_persons", "conflict_flag", schema="asset")
    op.drop_column("asset_identity_persons", "is_managed", schema="asset")
    op.drop_column("asset_identity_persons", "classification_rule_version", schema="asset")
    op.drop_column("asset_identity_persons", "classification", schema="asset")
    op.drop_column("asset_identity_persons", "raw_title", schema="asset")
    op.drop_column("asset_identity_persons", "raw_job", schema="asset")
    op.drop_column("asset_identity_persons", "source_create_date", schema="asset")

    # Drop new tables in reverse order
    op.drop_table("asset_identity_sync_locks", schema="asset")
    op.drop_table("asset_identity_classifications", schema="asset")
    op.drop_table("asset_identity_sync_compensations", schema="asset")
    op.drop_index("ix_identity_managed_relations_batch", table_name="asset_identity_managed_relations", schema="asset")
    op.drop_table("asset_identity_managed_relations", schema="asset")
    op.drop_table("asset_identity_protected_accounts", schema="asset")
    op.drop_table("asset_identity_role_mappings", schema="asset")
    op.drop_index("ix_identity_sync_actions_batch", table_name="asset_identity_sync_actions", schema="asset")
    op.drop_table("asset_identity_sync_actions", schema="asset")
    op.drop_table("asset_identity_sync_batches", schema="asset")
    op.drop_table("asset_identity_sync_watermarks", schema="asset")
