"""Identity sync alert dispatch and DBA privilege recommendation (plan 107).

Alert dispatch: desensitized daily report + anomaly alerts.
DBA recommendation: generates minimum-privilege GRANT suggestions without executing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def dispatch_nightly_report(report: dict[str, Any]) -> None:
    """Dispatch desensitized nightly report.

    In production this would send to configured alert channels (email/webhook).
    Currently logs at INFO level. No sensitive data in report.
    """
    status = report.get("status", "unknown")
    total = report.get("total", 0)
    success = report.get("success", 0)
    failed = report.get("failed", 0)
    skipped = report.get("skipped", 0)

    logger.info(
        "Identity nightly report: status=%s total=%d success=%d failed=%d skipped=%d",
        status, total, success, failed, skipped,
    )

    if failed > 0:
        logger.warning(
            "Identity nightly ALERT: %d failures detected. Review isolated candidates.",
            failed,
        )


def dispatch_circuit_breaker_alert(target: str, dimension: str, value: Any, limit: Any) -> None:
    """Alert when circuit breaker opens."""
    logger.error(
        "Identity circuit breaker OPEN: target=%s dimension=%s value=%s limit=%s",
        target, dimension, value, limit,
    )


def generate_dba_privilege_recommendation() -> dict[str, Any]:
    """Return a review-only minimum-privilege and revoke matrix.

    No executable GRANT/REVOKE statements are returned or run by the app.
    """
    return {
        "note": "DBA reviews and applies separately; AI/scheduler never executes GRANT/REVOKE.",
        "minimum_privilege_matrix": {
            "CDMS": {"read": ["T_MSS_EMP_DICT", "T_MSS_DEPT_DICT"], "write": ["T_MSS_EMP_DICT", "T_MSS_EMP_DEPT"], "forbidden": ["DELETE", "DDL", "DBA", "RESOURCE"]},
            "JHEMR": {"read": ["users", "users_pic", "jhauth_user_vs_role_group", "users_sublogin", "users_subsign"], "write": ["users_pic:INSERT", "users_pic:UPDATE"], "forbidden": ["DELETE", "dictionary writes", "DDL", "SUPERUSER"]},
            "platform": {"read": ["identity sync audit tables"], "write": ["audit rows only"], "forbidden": ["arbitrary SQL", "credential tables"]},
        },
        "revoke_rollback_matrix": [
            {"target": "JHEMR", "privilege": "DELETE", "objects": ["users", "users_pic", "users_sublogin", "users_subsign"], "rollback": "revoke before nightly enablement; verify effective privileges"},
            {"target": "JHEMR", "privilege": "WRITE", "objects": ["diagnosis_dict", "operation_dict", "operation_dict_code"], "rollback": "revoke dictionary writes and keep identity role separate"},
            {"target": "CDMS", "privilege": "DELETE/DDL", "objects": ["identity tables"], "rollback": "revoke and verify session privileges"},
        ],
        "single_account_verification": [
            "Use one synthetic/non-production account in an approved isolated transaction.",
            "Verify only listed SELECT/INSERT/UPDATE capabilities; record boolean/count/error_class.",
            "Perform one controlled write and target readback, then ROLLBACK or use the approved fixture.",
            "Keep nightly disabled until platform release and production write gates are separately authorized.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
