"""Identity sync executor bridge for Phase D controlled execution.

This module connects the orchestrator's planned actions to the actual
CDMS/JHEMR adapters. It is ONLY invoked by the asset_action_executors
white-listed sync service during Phase D controlled execution.

Development/review AI MUST NOT call this module directly against
production CDMS/JHEMR databases.

Per plan 107 section 9.2:
- Real writes only by asset_action_executors white-listed sync service
- Each target is an independent transaction
- Pre-commit read-back before COMMIT
- Full rollback on any failure
- Platform registration failure -> pending_reconcile, not blind retry
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.config import settings

logger = logging.getLogger(__name__)

# 112 B2：CDMS FTYPE 8/32 账户（接口/日志类）永远禁止写入。
CDMS_FORBIDDEN_FTYPE = {8, 32}


def _bridge_fail_closed(reason: str) -> dict[str, Any]:
    """Central fail-closed guard used by every adapter entry point."""
    logger.warning("identity bridge fail-closed: %s", reason)
    return {"status": "failed", "error": f"fail_closed: {reason}"}


def _bridge_blocked(reason: str, gate: dict[str, Any] | None = None) -> dict[str, Any]:
    """186 v1.10 P0-11：门禁阻断 ≠ 目标写失败——零目标连接，仅平台侧记录。"""
    logger.warning("identity bridge gate blocked: %s", reason)
    return {"status": "blocked", "reason": reason, "gate": gate or {}}


def _re_gate_state_action(
    action_code: str,
    person_code: str,
    approval_ref: str | None,
    credential_ref: str | None,
    gate_decision: Any = None,
) -> dict[str, Any] | None:
    """P0-11 defense-in-depth：即使被直接调用（绕过 dispatch），四类状态
    动作仍必须再次通过完整门禁；失败返回 blocked dict（零目标连接）。

    dispatch 传入已验证的 gate_decision 时复验其动作一致性（完整门禁已由
    dispatch 在调用方会话内完成——bridge 不再另开会话，避免跨会话读到
    不同的注册状态）；无 gate_decision 的直接调用走完整门禁。
    """
    if gate_decision is not None:
        if getattr(gate_decision, "executor_code", None) != action_code:
            return _bridge_blocked("gate_decision_mismatch")
        if not getattr(gate_decision, "allowed", False):
            return _bridge_blocked("gate_decision_not_allowed")
        if credential_ref and gate_decision.credential_ref and credential_ref != gate_decision.credential_ref:
            return _bridge_blocked("credential_ref_mismatch")
        return None

    from .identity_sync_action_gate import evaluate_identity_action_gate
    from ..core.db import SessionLocal

    db = SessionLocal()
    try:
        decision = evaluate_identity_action_gate(
            db,
            action_code=action_code,
            person_code=person_code,
            approval_ref=approval_ref,
            reserve_budget=False,  # 名额由 dispatch 预留；此处仅复验
        )
        if not decision.allowed:
            return _bridge_blocked(decision.reason, decision.as_dict())
        if credential_ref and decision.credential_ref and credential_ref != decision.credential_ref:
            return _bridge_blocked("credential_ref_mismatch", decision.as_dict())
        return None
    finally:
        db.close()


def _gate_legacy(kind: str) -> dict[str, Any] | None:
    """186 v1.10 P0-19：旧身份写入口的运行模式总门禁（observe/disable_only
    全部阻断；full 放行后仍受既有 112 B1/B2 门禁约束）。"""
    from .identity_sync_action_gate import gate_legacy_identity_write

    decision = gate_legacy_identity_write(None, kind)
    if not decision.allowed:
        return _bridge_blocked(decision.reason, decision.as_dict())
    return None


def _require_identity_sync_enabled() -> dict[str, Any] | None:
    """Identity writes are globally OFF unless explicitly enabled."""
    if not settings.identity_sync_enabled:
        return _bridge_fail_closed("APP_IDENTITY_SYNC_ENABLED is false")
    return None


def _require_phase_d_approval() -> dict[str, Any] | None:
    if not (settings.identity_phase_d_approval_version or "").strip():
        return _bridge_fail_closed("Phase D approval version is not configured")
    return None


def _require_password_write_enabled() -> dict[str, Any] | None:
    """JHEMR password write (SM4) is OFF until cross-validated (107 §5.2)."""
    if not settings.identity_jhemr_password_write_enabled:
        return _bridge_fail_closed("APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED is false")
    return None


def _require_cdms_semantics_confirmed() -> dict[str, Any] | None:
    """CDMS FID/FUSER/FUPDATEUSER semantics must be vendor/DB confirmed."""
    if not settings.identity_cdms_fid_semantics_confirmed:
        return _bridge_fail_closed("CDMS FID/FUSER/FUPDATEUSER semantics not confirmed")
    return None


def _load_role_mapping(target_system: str, classification: str) -> dict[str, Any]:
    """Load the configured role mapping from the platform DB.

    Role codes are configuration (seeded by migration e7f8a9b0c1d2), never
    hardcoded placeholders.
    """
    from sqlalchemy import select
    from ..core.db import SessionLocal
    from ..models.identity_sync import IdentityRoleMapping

    db = SessionLocal()
    try:
        row = db.scalar(
            select(IdentityRoleMapping).where(
                IdentityRoleMapping.target_system == target_system,
                IdentityRoleMapping.person_classification == classification,
                IdentityRoleMapping.is_active.is_(True),
            )
        )
        if row is None or not row.role_code:
            raise RuntimeError(f"role mapping not configured for {target_system}/{classification}")
        return {"role_code": row.role_code, "role_name_cn": row.role_name_cn}
    finally:
        db.close()


def execute_cdms_apply(
    emp_no: str,
    display_name: str,
    classification: str,
    primary_dept: str,
    additional_depts: list[str],
    job_title: str | None = None,
) -> dict[str, Any]:
    """Execute CDMS account creation via the CDMS adapter.

    Called ONLY by the controlled sync executor in Phase D.
    Returns adapter result dict with status/actions/error.
    """
    # 112 B1/B2 fail-closed boundary（旧契约优先：全局关闭→fail_closed）
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    if (gate := _require_cdms_semantics_confirmed()) is not None:
        return gate
    # 186 v1.10 P0-19：旧入口运行模式门禁（observe/disable_only 全阻断）。
    if (blocked := _gate_legacy("cdms_apply")) is not None:
        return blocked
    if classification is not None and classification not in {"doctor", "nurse", "pharmacist"}:
        return _bridge_fail_closed(f"unsupported classification: {classification}")
    from .cdms_identity_adapter import CdmsIdentityAdapter

    adapter = CdmsIdentityAdapter(
        credential_ref=settings.identity_sync_cdms_credential_ref,
        cdms_host=settings.identity_sync_cdms_host,
        cdms_port=settings.identity_sync_cdms_port,
        cdms_service=settings.identity_sync_cdms_service,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
    )
    try:
        adapter.connect()
        # 初始密码策略（104 E8 裁决）：复用全院默认 FPWD 密文，仅内存传递
        fpwd_template = adapter.fetch_mode_fpwd_ciphertext()
        if not fpwd_template:
            return {"status": "failed", "error": "CDMS password template unavailable"}

        role_mapping = _load_role_mapping("CDMS", classification)

        if adapter.snapshot_user(emp_no):
            return adapter.align_existing_user(
                emp_no=emp_no,
                dept_code=primary_dept,
                dept_codes=[primary_dept] + additional_depts,
                role_mapping=role_mapping,
            )

        result = adapter.apply_single_user(
            emp_no=emp_no,
            person_name=display_name,
            dept_code=primary_dept,
            classification=classification,
            dept_codes=[primary_dept] + additional_depts,
            role_mapping=role_mapping,
            fpwd_template=fpwd_template,
        )
        return result
    except Exception as exc:
        logger.error("CDMS apply failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_jhemr_apply(
    emp_no: str,
    display_name: str,
    classification: str,
    primary_dept: str,
    additional_depts: list[str],
    date_str: str | None = None,
    job_title: str | None = None,
) -> dict[str, Any]:
    """Execute JHEMR full user creation via the JHEMR adapter.

    Called ONLY by the controlled sync executor in Phase D.
    Creates user across 6 tables in ONE transaction with SM4 password.
    Returns adapter result dict with status/actions/error.
    """
    # 112 B1/B2 fail-closed boundary（旧契约优先：全局关闭→fail_closed）
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    if (gate := _require_password_write_enabled()) is not None:
        return gate
    # 186 v1.10 P0-19：旧入口运行模式门禁（observe/disable_only 全阻断）。
    if (blocked := _gate_legacy("jhemr_apply")) is not None:
        return blocked
    if classification is not None and classification not in {"doctor", "nurse", "pharmacist"}:
        return _bridge_fail_closed(f"unsupported classification: {classification}")
    from .jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter(
        credential_ref=settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
        password_secret_ref=settings.identity_jhemr_default_password_ref,
        password_write_enabled=settings.identity_jhemr_password_write_enabled,
    )
    try:
        adapter.connect()
        # Check if user already exists (idempotent)
        if adapter.user_exists(emp_no):
            # Align existing user instead of creating
            from .jhemr_identity_adapter import ROLE_GROUP_MAP
            role_group = ROLE_GROUP_MAP.get(classification, "001")
            result = adapter.align_existing_user(
                emp_no=emp_no,
                classification=classification,
                dept_codes=[primary_dept] + additional_depts,
                role_group_code=role_group,
                job_title=job_title,
            )
            return result
        # Create new user (6-table transaction)
        result = adapter.create_user_full(
            emp_no=emp_no,
            display_name=display_name,
            classification=classification,
            primary_dept=primary_dept,
            additional_depts=additional_depts,
            date_str=date_str,
            job_title=job_title,
        )
        return result
    except Exception as exc:
        logger.error("JHEMR apply failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_jhemr_lock(
    emp_no: str,
    *,
    credential_ref: str | None = None,
    approval_ref: str | None = None,
    gate_decision: Any = None,
) -> dict[str, Any]:
    """Lock one existing JHEMR login. Does not create users or write passwords.

    186 v1.10 P0-11：JHEMR_ACCOUNT_DISABLE 执行器动作；凭据从 source
    purpose 绑定解析（credential_ref），直接调用也复过完整门禁。
    """
    if (blocked := _re_gate_state_action(
        "JHEMR_ACCOUNT_DISABLE", emp_no, approval_ref, credential_ref, gate_decision
    )) is not None:
        return blocked
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    from .jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter(
        credential_ref=credential_ref or settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
    )
    try:
        adapter.connect()
        result = adapter.lock_account(emp_no)
        # P0-4：成功停用保留目标原始时间/类型（恢复归因基准），由调用方持久化。
        return result
    except Exception as exc:
        logger.error("JHEMR lock failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_jhemr_state_read(emp_no: str) -> dict[str, Any]:
    """186 I3：只读 JHEMR 账号状态（无门禁——只读，不写）。"""
    from .jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter(
        credential_ref=settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
    )
    try:
        adapter.connect()
        state = adapter.read_account_state(emp_no)
        if state is None:
            return {"status": "missing_target"}
        return {"status": "ok", "state": state}
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_jhemr_enable(
    emp_no: str,
    *,
    origin_disable: dict[str, Any] | None = None,
    credential_ref: str | None = None,
    approval_ref: str | None = None,
    gate_decision: Any = None,
) -> dict[str, Any]:
    """186 I3：受控恢复 JHEMR 8→0（JHEMR_ACCOUNT_ENABLE 执行器动作）。

    §13.3：恢复必须引用本规则前一 executed 停用的持久证据（origin_disable：
    attempt_id/target_raw_time/指纹/规则版本）；适配器只做状态 CAS 与目标
    raw 时间变更检测，不做 ±容差推定。不重设密码/角色，只改状态。
    """
    if (blocked := _re_gate_state_action(
        "JHEMR_ACCOUNT_ENABLE", emp_no, approval_ref, credential_ref, gate_decision
    )) is not None:
        return blocked
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    from .jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter(
        credential_ref=credential_ref or settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
    )
    try:
        adapter.connect()
        return adapter.unlock_account(emp_no, origin_disable=origin_disable)
    except Exception as exc:
        logger.error("JHEMR enable failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_cdms_disable(
    emp_no: str,
    *,
    credential_ref: str | None = None,
    approval_ref: str | None = None,
    gate_decision: Any = None,
) -> dict[str, Any]:
    """186 I3：CDMS 停用（FUSERSTATE '0'→'1'，CDMS_ACCOUNT_DISABLE 执行器
    动作；条件更新+提交前回读，凭据从 source purpose 绑定解析）。"""
    if (blocked := _re_gate_state_action(
        "CDMS_ACCOUNT_DISABLE", emp_no, approval_ref, credential_ref, gate_decision
    )) is not None:
        return blocked
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    from .cdms_identity_adapter import CdmsIdentityAdapter

    adapter = CdmsIdentityAdapter(
        credential_ref=credential_ref or settings.identity_sync_cdms_credential_ref,
        cdms_host=settings.identity_sync_cdms_host,
        cdms_port=settings.identity_sync_cdms_port,
        cdms_service=settings.identity_sync_cdms_service,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
    )
    try:
        adapter.connect()
        return adapter.lock_user(emp_no)
    except Exception as exc:
        logger.error("CDMS disable failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_cdms_state_read(emp_no: str) -> dict[str, Any]:
    """186 I3：只读 CDMS 账号状态（无门禁——只读，不写）。"""
    from .cdms_identity_adapter import CdmsIdentityAdapter

    adapter = CdmsIdentityAdapter(
        credential_ref=settings.identity_sync_cdms_credential_ref,
        cdms_host=settings.identity_sync_cdms_host,
        cdms_port=settings.identity_sync_cdms_port,
        cdms_service=settings.identity_sync_cdms_service,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
    )
    try:
        adapter.connect()
        state = adapter.read_account_state(emp_no)
        if state is None:
            return {"status": "missing_target"}
        return {"status": "ok", "state": state}
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_cdms_enable(
    emp_no: str,
    *,
    origin_disable: dict[str, Any] | None = None,
    credential_ref: str | None = None,
    approval_ref: str | None = None,
    gate_decision: Any = None,
) -> dict[str, Any]:
    """186 I3：受控恢复 CDMS '1'→'0'（CDMS_ACCOUNT_ENABLE 执行器动作；
    FCHANGEDATE CAS 变更检测 + §13.3 origin_disable 证据）。"""
    if (blocked := _re_gate_state_action(
        "CDMS_ACCOUNT_ENABLE", emp_no, approval_ref, credential_ref, gate_decision
    )) is not None:
        return blocked
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    from .cdms_identity_adapter import CdmsIdentityAdapter

    adapter = CdmsIdentityAdapter(
        credential_ref=credential_ref or settings.identity_sync_cdms_credential_ref,
        cdms_host=settings.identity_sync_cdms_host,
        cdms_port=settings.identity_sync_cdms_port,
        cdms_service=settings.identity_sync_cdms_service,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
    )
    try:
        adapter.connect()
        return adapter.unlock_user(emp_no, origin_disable=origin_disable)
    except Exception as exc:
        logger.error("CDMS enable failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_jhemr_readback(emp_no: str) -> dict[str, Any]:
    """Read back JHEMR user state after apply for verification.

    Returns desensitized snapshot of all 6 tables for the user.
    """
    from .jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter(
        credential_ref=settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
    )
    try:
        adapter.connect()
        snapshot = {
            "user": adapter.snapshot_user(emp_no),
            "depts": adapter.snapshot_user_dept(emp_no),
            "role_groups": adapter.snapshot_role_groups(emp_no),
            "control_mode": adapter.snapshot_control_mode(emp_no),
            "sublogin": adapter.snapshot_sublogin(emp_no),
            "subsign": adapter.snapshot_subsign(emp_no),
        }
        if not snapshot["user"] or not snapshot["depts"] or not snapshot["role_groups"] or not snapshot["control_mode"]:
            return {"error": "jhemr readback incomplete"}
        return snapshot
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_jhemr_password_reset(emp_no: str, date_str: str | None = None) -> dict[str, Any]:
    """Reset one existing JHEMR account through the approved password path."""
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    if (gate := _require_password_write_enabled()) is not None:
        return gate
    if (blocked := _gate_legacy("jhemr_password_reset")) is not None:
        return blocked

    from .jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter(
        credential_ref=settings.identity_sync_jhemr_credential_ref,
        hospital_no=settings.identity_sync_jhemr_hospital_no,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        db_host=settings.identity_sync_jhemr_host,
        db_port=settings.identity_sync_jhemr_port,
        db_name=settings.identity_sync_jhemr_dbname,
        password_secret_ref=settings.identity_jhemr_default_password_ref,
        password_write_enabled=settings.identity_jhemr_password_write_enabled,
    )
    try:
        adapter.connect()
        return adapter.reset_existing_password(emp_no, date_str=date_str)
    except Exception as exc:
        logger.error("JHEMR password reset failed for masked emp: %s", type(exc).__name__)
        return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()


def execute_cdms_readback(emp_no: str) -> dict[str, Any]:
    """Read back CDMS user state after apply for verification."""
    from .cdms_identity_adapter import CdmsIdentityAdapter

    adapter = CdmsIdentityAdapter(
        credential_ref=settings.identity_sync_cdms_credential_ref,
        cdms_host=settings.identity_sync_cdms_host,
        cdms_port=settings.identity_sync_cdms_port,
        cdms_service=settings.identity_sync_cdms_service,
        jump_host=settings.his_source_jump_host,
        jump_port=settings.his_source_jump_port,
        jump_user=settings.his_source_jump_user,
        jump_key=settings.his_source_jump_key or None,
        oracle_client_lib=settings.his_source_oracle_client_lib or "/opt/oracle",
    )
    try:
        adapter.connect()
        snapshot = {
            "user": adapter.snapshot_user(emp_no),
            "auth": adapter.snapshot_auth(emp_no),
        }
        if not snapshot["user"] or not snapshot["auth"]:
            return {"error": "cdms readback incomplete"}
        return snapshot
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        adapter.close()
