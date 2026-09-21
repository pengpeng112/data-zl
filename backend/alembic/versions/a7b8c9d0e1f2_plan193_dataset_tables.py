"""plan193 B03: dataset core tables (classifications/grants/datasets/versions/
batches/identity maps/facts/quality assertions/exports).

Revision ID: a7b8c9d0e1f2
Revises: e8f9a0b1c2d3
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a7b8c9d0e1f2"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None

_TABLES = [
    ("asset_ds_classifications", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_ref", sa.Text(), nullable=False),
        sa.Column("labels", JSONB(), nullable=False, server_default="{}"),
        sa.Column("protection_level", sa.Text(), nullable=False, server_default="P4"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prev_version", sa.Integer()),
        sa.Column("classified_by", sa.Text()),
        sa.Column("legal_basis_ref", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    ], [
        sa.UniqueConstraint("object_type", "object_ref", "version", name="uq_ds_cls_object_version"),
        sa.CheckConstraint("protection_level in ('P1','P2','P3','P4')", name="ck_ds_cls_level"),
    ], [
        ("ix_ds_cls_object", ["object_type", "object_ref", "status"]),
    ]),
    ("asset_ds_grants", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("principal", sa.Text(), nullable=False),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_ref", sa.Text(), nullable=False),
        sa.Column("row_scope", JSONB(), server_default="{}"),
        sa.Column("column_scope", JSONB(), server_default="{}"),
        sa.Column("operations", JSONB(), nullable=False),
        sa.Column("legal_basis_ref", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("revoke_reason", sa.Text()),
        sa.Column("grant_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approved_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    ], [
        sa.UniqueConstraint("principal", "purpose_code", "resource_type", "resource_ref",
                            name="uq_ds_grant_scope"),
    ], []),
    ("asset_ds_datasets", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("dataset_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("queue_definition", JSONB(), server_default="{}"),
        sa.Column("grain", sa.Text(), nullable=False, server_default="patient"),
        sa.Column("latest_version_id", sa.BigInteger()),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    ], [
        sa.UniqueConstraint("dataset_code", name="uq_ds_dataset_code"),
    ], []),
    ("asset_ds_dataset_versions", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("source_batch_ids", JSONB(), server_default="[]"),
        sa.Column("identity_version", sa.Integer()),
        sa.Column("rule_versions", JSONB(), server_default="{}"),
        sa.Column("cutoff_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("manifest", JSONB()),
        sa.Column("manifest_sha256", sa.Text()),
        sa.Column("quality_conclusion", JSONB()),
        sa.Column("security_conclusion", JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("validated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("approved_by", sa.Text()),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("deprecated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
    ], [
        sa.UniqueConstraint("dataset_id", "version", name="uq_ds_version"),
        sa.CheckConstraint(
            "status in ('draft','validated','approved','published','deprecated','revoked')",
            name="ck_ds_version_status"),
    ], []),
    ("asset_ds_batches", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("object_name", sa.Text(), nullable=False),
        sa.Column("shard_window", JSONB(), server_default="{}"),
        sa.Column("watermark", JSONB()),
        sa.Column("snapshot_capable", sa.Text(), server_default="false"),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("counters", JSONB(), server_default="{}"),
        sa.Column("checkpoints", JSONB(), server_default="{}"),
        sa.Column("error_class", sa.Text()),
        sa.Column("error_detail", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
    ], [
        sa.UniqueConstraint("run_id", name="uq_ds_batch_run"),
    ], []),
    ("asset_ds_identity_maps", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("internal_patient_id", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("match_rule_version", sa.Text(), nullable=False),
        sa.Column("match_evidence", JSONB()),
        sa.Column("confidence", sa.Text(), nullable=False, server_default="deterministic"),
        sa.Column("review_status", sa.Text(), nullable=False, server_default="auto"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True)),
        sa.Column("merged_into", sa.Text()),
        sa.Column("split_from", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    ], [
        sa.UniqueConstraint("internal_patient_id", "source_code", "source_key",
                            name="uq_ds_identity_map"),
    ], [
        ("ix_ds_identity_internal", ["internal_patient_id"]),
    ]),
    ("asset_ds_facts", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_kind", sa.Text(), nullable=False),
        sa.Column("internal_patient_id", sa.Text(), nullable=False),
        sa.Column("internal_visit_id", sa.Text()),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("original_value_ref", sa.Text(), nullable=False),
        sa.Column("standard_value", sa.Text()),
        sa.Column("standard_code_system", sa.Text()),
        sa.Column("unit", sa.Text()),
        sa.Column("rule_version", sa.Text(), nullable=False),
        sa.Column("quality_flag", sa.Text(), server_default="ok"),
        sa.Column("business_time", sa.TIMESTAMP(timezone=True)),
        sa.Column("available_time", sa.TIMESTAMP(timezone=True)),
        sa.Column("ingested_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("batch_run_id", sa.Text()),
        sa.Column("deleted", sa.Text(), server_default="false"),
    ], [
        sa.UniqueConstraint("fact_key", "rule_version", name="uq_ds_fact_rule"),
    ], [
        ("ix_ds_fact_patient", ["internal_patient_id"]),
    ]),
    ("asset_ds_quality_assertions", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_ref", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("metric_name", sa.Text(), nullable=False),
        sa.Column("numerator", sa.BigInteger()),
        sa.Column("denominator", sa.BigInteger()),
        sa.Column("threshold", JSONB()),
        sa.Column("result", sa.Text(), server_default="pending"),
        sa.Column("detail", JSONB()),
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    ], [
        sa.UniqueConstraint("scope_type", "scope_ref", "dimension", name="uq_ds_qa_scope_dim"),
    ], []),
    ("asset_ds_exports", [
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("export_code", sa.Text(), nullable=False),
        sa.Column("grant_id", sa.BigInteger(), nullable=False),
        sa.Column("dataset_version_id", sa.BigInteger(), nullable=False),
        sa.Column("field_whitelist", JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="requested"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("download_count", sa.Integer(), server_default="0"),
        sa.Column("row_count", sa.BigInteger()),
        sa.Column("file_sha256", sa.Text()),
        sa.Column("masking_applied", JSONB()),
        sa.Column("audit_ref", sa.Text()),
        sa.Column("created_by", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    ], [
        sa.UniqueConstraint("export_code", name="uq_ds_export_code"),
    ], []),
]


def upgrade() -> None:
    for name, cols, consts, idxs in _TABLES:
        op.create_table(
            name,
            *cols,
            *consts,
            schema="asset",
        )
        for idx_name, idx_cols in idxs:
            op.create_index(idx_name, name, idx_cols, schema="asset", unique=False)


def downgrade() -> None:
    for name, _cols, _consts, idxs in reversed(_TABLES):
        for idx_name, _idx_cols in idxs:
            op.drop_index(idx_name, table_name=name, schema="asset")
        op.drop_table(name, schema="asset")
