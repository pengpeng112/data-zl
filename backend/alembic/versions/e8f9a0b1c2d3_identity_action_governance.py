"""186 v1.10 P0-11/P0-18/P0-19: identity action governance objects.

Adds:
- asset.asset_source_purpose_bindings — per-(source, purpose) write credential
  binding; the legacy single write_policy on asset_data_sources keeps serving
  dict push and is NOT overwritten (P0-18).
- asset.asset_identity_action_scopes / _scope_members — frozen approved
  action scopes (pilot persons + frozen baseline); approval tokens alone are
  never a scope (P0-19/§13.5).
- asset.asset_identity_window_budgets / _reservations — persistent per-window
  budget shared by pilots, manual reruns and restarts (§13.5).
- asset_identity_account_state_attempts.origin_disable_attempt_id — enable
  attempts reference the executed disable they recover from (P0-4/§13.3).
- Seeds four identity state executors into asset_action_executors, all
  DEFAULT DISABLED; enabling any of them stays a controlled governance action
  (P0-11). Also grants identity_admin the read-only identity.sync_diff:view
  permission (P1-8).

Handwritten upgrade/downgrade (no autogenerate). No existing rows are
rewritten; historical lock attribution is not backfilled.
"""

from alembic import op
import sqlalchemy as sa

revision: str = "e8f9a0b1c2d3"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None

_IDENTITY_EXECUTORS = [
    {
        "executor_code": "JHEMR_ACCOUNT_DISABLE",
        "executor_name_cn": "JHEMR 账号停用（8）",
        "execution_mode": "adapter_method",
        "tool_code": "identity_state_sync",
        "sql_or_endpoint_ref": "jhemr_identity_adapter.lock_account",
        "target_system_code": "JHEMR",
        "target_source_code": "jhemr_vastbase_10_10_8_177",
        "risk_level": "high",
        "require_approval": True,
        "require_second_confirm": False,
        "enabled": False,
        "description": "186 §4.6.4：HIS 双来源任一停用 → JHEMR account_status=8；仅改状态，不动密码/角色/签名。",
    },
    {
        "executor_code": "JHEMR_ACCOUNT_ENABLE",
        "executor_name_cn": "JHEMR 账号恢复（8→0，未批准启用）",
        "execution_mode": "adapter_method",
        "tool_code": "identity_state_sync",
        "sql_or_endpoint_ref": "jhemr_identity_adapter.unlock_account",
        "target_system_code": "JHEMR",
        "target_source_code": "jhemr_vastbase_10_10_8_177",
        "risk_level": "high",
        "require_approval": True,
        "require_second_confirm": True,
        "enabled": False,
        "description": "§13.3：需锁所有权证据+独立 enable 批准；当前目标无审计/版本合同，automatic_enable_supported=false。",
    },
    {
        "executor_code": "CDMS_ACCOUNT_DISABLE",
        "executor_name_cn": "CDMS 账号停用（FUSERSTATE '0'→'1'）",
        "execution_mode": "adapter_method",
        "tool_code": "identity_state_sync",
        "sql_or_endpoint_ref": "cdms_identity_adapter.lock_user",
        "target_system_code": "CDMS",
        "target_source_code": "paperless_cdms_oracle_10_10_10_93",
        "risk_level": "high",
        "require_approval": True,
        "require_second_confirm": False,
        "enabled": False,
        "description": "186 §4.6.4：条件更新+提交前回读；FTYPE 8/32 永禁写入。",
    },
    {
        "executor_code": "CDMS_ACCOUNT_ENABLE",
        "executor_name_cn": "CDMS 账号恢复（'1'→'0'，未批准启用）",
        "execution_mode": "adapter_method",
        "tool_code": "identity_state_sync",
        "sql_or_endpoint_ref": "cdms_identity_adapter.unlock_user",
        "target_system_code": "CDMS",
        "target_source_code": "paperless_cdms_oracle_10_10_10_93",
        "risk_level": "high",
        "require_approval": True,
        "require_second_confirm": True,
        "enabled": False,
        "description": "§13.3：FCHANGEDATE CAS 变更检测+所有权证据；无合同时 automatic_enable_supported=false。",
    },
]


def _pk():
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "asset_source_purpose_bindings",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("write_policy", sa.Text(), nullable=False, server_default="identity_account_sync"),
        sa.Column("write_credential_ref", sa.Text(), nullable=True),
        sa.Column("credential_status", sa.Text(), nullable=False, server_default="unconfigured"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_ref", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_code", "purpose", name="uq_source_purpose_binding"),
        schema="asset",
    )

    op.create_table(
        "asset_identity_action_scopes",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("approval_ref", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False, server_default="disable"),
        sa.Column("scope_fingerprint", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("approval_ref", "action", "scope_type", name="uq_identity_scope_approval"),
        schema="asset",
    )
    op.create_index(
        "ix_identity_scope_status", "asset_identity_action_scopes", ["status"], schema="asset",
    )

    op.create_table(
        "asset_identity_action_scope_members",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("scope_id", _pk(), nullable=False),
        sa.Column("person_code", sa.Text(), nullable=False),
        sa.Column("frozen_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scope_id", "person_code", name="uq_identity_scope_member"),
        schema="asset",
    )
    op.create_index(
        "ix_identity_scope_member_person",
        "asset_identity_action_scope_members",
        ["person_code"],
        schema="asset",
    )

    op.create_table(
        "asset_identity_window_budgets",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("window_key", sa.Text(), nullable=False),
        sa.Column("approval_ref", sa.Text(), nullable=False),
        sa.Column("limit_persons", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("window_key", name="uq_identity_window_key"),
        schema="asset",
    )
    op.create_index(
        "ix_identity_window_open", "asset_identity_window_budgets", ["closed_at"], schema="asset",
    )

    op.create_table(
        "asset_identity_window_reservations",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("window_id", _pk(), nullable=False),
        sa.Column("person_code", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False, server_default="disable"),
        sa.Column("status", sa.Text(), nullable=False, server_default="reserved"),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("window_id", "person_code", name="uq_identity_window_reservation"),
        schema="asset",
    )
    op.create_index(
        "ix_identity_window_reservation_window",
        "asset_identity_window_reservations",
        ["window_id"],
        schema="asset",
    )

    op.add_column(
        "asset_identity_account_state_attempts",
        sa.Column("origin_disable_attempt_id", _pk(), nullable=True),
        schema="asset",
    )

    # P0-11：四类身份状态执行器种子（全部默认 disabled；启用=受控治理动作）。
    conn = op.get_bind()
    for row in _IDENTITY_EXECUTORS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM asset.asset_action_executors WHERE executor_code = :code"),
            {"code": row["executor_code"]},
        ).first()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO asset.asset_action_executors "
                    "(executor_code, executor_name_cn, execution_mode, tool_code, sql_or_endpoint_ref, "
                    "target_system_code, target_source_code, risk_level, require_approval, "
                    "require_second_confirm, enabled, description) VALUES "
                    "(:executor_code, :executor_name_cn, :execution_mode, :tool_code, :sql_or_endpoint_ref, "
                    ":target_system_code, :target_source_code, :risk_level, :require_approval, "
                    ":require_second_confirm, :enabled, :description)"
                ),
                row,
            )

    # P1-8：identity_admin 默认获得只读 identity.sync_diff:view。
    exists_perm = conn.execute(
        sa.text(
            "SELECT 1 FROM asset.asset_role_permissions "
            "WHERE role_code = 'identity_admin' AND resource = 'identity.sync_diff' AND action = 'view'"
        )
    ).first()
    if not exists_perm:
        conn.execute(
            sa.text(
                "INSERT INTO asset.asset_role_permissions (role_code, resource, action) "
                "VALUES ('identity_admin', 'identity.sync_diff', 'view')"
            )
        )

    # P0-11⑥：执行器注册管理权限（默认仅 platform_admin；普通身份用户不可达）。
    exists_res = conn.execute(
        sa.text("SELECT 1 FROM asset.asset_permission_resources WHERE resource_code = 'govern.executor.manage'")
    ).first()
    if not exists_res:
        conn.execute(
            sa.text(
                "INSERT INTO asset.asset_permission_resources "
                "(resource_code, resource_name_cn, module_code, action_code, description, enabled) VALUES "
                "('govern.executor.manage', '治理执行器注册管理', 'govern', 'manage', "
                "'186 P0-11：asset_action_executors 白名单注册的查看与受控变更（含审计）', true)"
            )
        )
    exists_grant = conn.execute(
        sa.text(
            "SELECT 1 FROM asset.asset_role_permissions "
            "WHERE role_code = 'platform_admin' AND resource = 'govern.executor' AND action = 'manage'"
        )
    ).first()
    if not exists_grant:
        conn.execute(
            sa.text(
                "INSERT INTO asset.asset_role_permissions (role_code, resource, action) "
                "VALUES ('platform_admin', 'govern.executor', 'manage')"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM asset.asset_role_permissions WHERE (role_code, resource, action) IN "
            "(('identity_admin', 'identity.sync_diff', 'view'), ('platform_admin', 'govern.executor', 'manage'))"
        )
    )
    conn.execute(
        sa.text("DELETE FROM asset.asset_permission_resources WHERE resource_code = 'govern.executor.manage'")
    )
    conn.execute(
        sa.text(
            "DELETE FROM asset.asset_action_executors WHERE executor_code IN "
            "('JHEMR_ACCOUNT_DISABLE', 'JHEMR_ACCOUNT_ENABLE', 'CDMS_ACCOUNT_DISABLE', 'CDMS_ACCOUNT_ENABLE')"
        )
    )
    op.drop_column(
        "asset_identity_account_state_attempts", "origin_disable_attempt_id", schema="asset",
    )
    op.drop_index(
        "ix_identity_window_reservation_window",
        table_name="asset_identity_window_reservations",
        schema="asset",
    )
    op.drop_table("asset_identity_window_reservations", schema="asset")
    op.drop_index("ix_identity_window_open", table_name="asset_identity_window_budgets", schema="asset")
    op.drop_table("asset_identity_window_budgets", schema="asset")
    op.drop_index(
        "ix_identity_scope_member_person",
        table_name="asset_identity_action_scope_members",
        schema="asset",
    )
    op.drop_table("asset_identity_action_scope_members", schema="asset")
    op.drop_index("ix_identity_scope_status", table_name="asset_identity_action_scopes", schema="asset")
    op.drop_table("asset_identity_action_scopes", schema="asset")
    op.drop_table("asset_source_purpose_bindings", schema="asset")
