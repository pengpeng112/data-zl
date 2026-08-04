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
    """Generate DBA minimum-privilege recommendations for identity sync.

    Returns SQL suggestions ONLY. Does NOT execute GRANT/REVOKE.
    Per plan 107 section 14: generate suggestions, DBA executes manually.
    """
    return {
        "note": "DBA must review and execute manually. AI/scheduler never executes GRANT/REVOKE.",
        "jhemr_recommendations": [
            "GRANT SELECT, INSERT ON jhemr.users TO identity_sync_role;",
            "GRANT SELECT, INSERT ON jhemr.user_dept TO identity_sync_role;",
            "GRANT SELECT, INSERT ON jhemr.jhauth_user_vs_role_group TO identity_sync_role;",
            "GRANT SELECT, INSERT ON jhemr.users_control_mode TO identity_sync_role;",
            "GRANT SELECT, INSERT ON jhemr.users_sublogin TO identity_sync_role;",
            "GRANT SELECT, INSERT ON jhemr.users_subsign TO identity_sync_role;",
            "-- NO DELETE privilege for nightly scheduler",
            "-- NO UPDATE on jhauth_user_vs_role or jhauth_user_vs_permission",
        ],
        "cdms_recommendations": [
            "GRANT SELECT, INSERT ON CDMS.T_MSS_EMP_DICT TO identity_sync_role;",
            "GRANT SELECT, INSERT ON CDMS.T_MSS_AUTHMAPPING TO identity_sync_role;",
            "-- UPDATE only FUSERSTATE for soft-stop:",
            "GRANT UPDATE (FUSERSTATE) ON CDMS.T_MSS_EMP_DICT TO identity_sync_role;",
            "-- NO DELETE privilege for nightly scheduler",
        ],
        "platform_recommendations": [
            "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA asset TO asset_app;",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA asset TO asset_app;",
        ],
        "delete_policy": "DELETE privilege must NOT be granted to daily scheduler. "
                         "Temporary DELETE for one-time repair requires separate DBA approval and time-limited grant.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
