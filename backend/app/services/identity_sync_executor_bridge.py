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
    # 112 B1/B2 fail-closed boundary
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    if (gate := _require_cdms_semantics_confirmed()) is not None:
        return gate
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
    # 112 B1/B2 fail-closed boundary
    if (gate := _require_identity_sync_enabled()) is not None:
        return gate
    if (gate := _require_phase_d_approval()) is not None:
        return gate
    if (gate := _require_password_write_enabled()) is not None:
        return gate
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
