"""Shared status, exit-code and redaction rules for identity sync (plan 122).

This module is deliberately side-effect free so the runner and isolated tests
use exactly the same aggregation rules.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Mapping

SYNC_STATUSES = frozenset({
    "success", "partial_success", "failed", "skipped", "running",
    "overdue", "misconfigured",
})
SUBTASK_CODES = ("main_account_sync", "jhemr_signature_sync")
EXIT_CODES = {
    "success": 0,
    "skipped": 0,
    "running": 0,
    "partial_success": 2,
    "failed": 1,
    "misconfigured": 1,
    "overdue": 1,
}

_SENSITIVE_WORDS = re.compile(
    r"(?i)(password|passwd|token|secret|signature_(?:image|content|data)|sql|param|employee|emp_no|name|phone|id_no)"
)


def normalize_status(value: Any, *, default: str = "failed") -> str:
    status = str(value or "").strip().lower()
    # Legacy statuses are normalized at the boundary and never exposed by the
    # new status API.
    aliases = {"circuit_open": "failed", "threshold_exceeded": "failed", "lock_held": "skipped"}
    status = aliases.get(status, status)
    return status if status in SYNC_STATUSES else default


def aggregate_overall_status(
    main_status: Any,
    signature_status: Any,
    *,
    signature_required: bool = True,
    lock_reason: str | None = None,
) -> str:
    """Aggregate two durable subtasks without hiding required failures."""
    main = normalize_status(main_status)
    signature = normalize_status(signature_status)
    if lock_reason == "lock_held" or main == "skipped":
        return "skipped"
    if main in {"failed", "misconfigured", "overdue"}:
        return main
    if main == "running" or signature == "running":
        return "running"
    if signature_required and signature in {"failed", "misconfigured", "overdue"}:
        return "partial_success" if main == "success" else signature
    if main == "success" and (not signature_required or signature in {"success", "skipped"}):
        return "success"
    if main == "skipped" and signature in {"skipped", "success"}:
        return "skipped"
    return "partial_success" if main == "success" else "failed"


def runner_exit_code(status: Any) -> int:
    return EXIT_CODES.get(normalize_status(status), 1)


def short_fingerprint(value: str | None) -> str | None:
    """Return at most 12 chars for stdout/logs; storage keeps full HMAC."""
    if not value:
        return None
    return str(value)[:12]


def error_code_masked(exc: BaseException | str | None) -> str:
    """Keep only a stable, non-sensitive exception class/code token."""
    if exc is None:
        return "unknown"
    if isinstance(exc, BaseException):
        name = type(exc).__name__
    else:
        match_name = re.match(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", str(exc).strip())
        name = match_name.group(0) if match_name else "UnknownError"
    # Preserve common database error numbers without messages or SQL text.
    text = str(exc)
    if re.search(r"(?i)(password|passwd|token|secret|signature|sql|param|employee|emp_no|name|phone|id_no)", text):
        return "SensitiveError"
    match = re.search(r"(?:SQLSTATE|ORA-|error code|code)\s*[:=]?\s*([A-Z0-9_-]{3,16})", text, re.I)
    suffix = match.group(1).upper() if match else ""
    return f"{name}:{suffix}"[:64] if suffix else name[:64]


def increment_error(errors: dict[str, dict[str, int]], category: str, exc: BaseException | str | None) -> None:
    code = error_code_masked(exc)
    bucket = errors.setdefault(category, {})
    bucket[code] = int(bucket.get(code, 0)) + 1


def redacted_summary(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Recursively remove sensitive keys and cap list output for reports."""
    if not data:
        return {}
    output: dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_WORDS.search(str(key)):
            continue
        if re.search(r"(?i)(error_message|^error$|exception)", str(key)):
            output["error_code_masked"] = error_code_masked(value)
            continue
        if isinstance(value, Mapping):
            output[str(key)] = redacted_summary(value)
        elif isinstance(value, (list, tuple)):
            output[str(key)] = [redacted_summary(v) if isinstance(v, Mapping) else v for v in value[:3]]
        else:
            output[str(key)] = value
    return output


def config_fingerprint(provider: str, cron: str, timezone: str, enabled: bool) -> str:
    raw = f"{provider}|{cron}|{timezone}|{bool(enabled)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def tie_breaker_after(create_date: Any, employee_key: str | None, candidate_date: Any, candidate_key: str | None) -> bool:
    """Composite timestamp + stable employee key ordering for watermarks."""
    if candidate_date is None:
        return False
    if create_date is None:
        return True
    if create_date > candidate_date:
        return True
    if create_date < candidate_date:
        return False
    return str(employee_key or "") > str(candidate_key or "")


def summarize_counts(statuses: list[str]) -> dict[str, int]:
    counts = Counter(normalize_status(s) for s in statuses)
    return {key: int(counts.get(key, 0)) for key in ("success", "partial_success", "failed", "skipped", "running", "overdue", "misconfigured")}


def stdout_summary(*, overall_status: str, run_id: str | None, main: Mapping[str, Any], signature: Mapping[str, Any]) -> dict[str, Any]:
    """Strict one-shot stdout contract: no free-form report or identifiers."""
    return {
        "status": normalize_status(overall_status),
        "run_id": run_id,
        "counts": {
            "main_planned": int(main.get("candidates") or main.get("candidates_total") or 0),
            "main_success": int(main.get("success_count") or main.get("success") or 0),
            "main_failed": int(main.get("failed_count") or main.get("failed") or 0),
            "main_skipped": int(main.get("skipped_count") or main.get("skipped") or 0),
            "signature_planned": int(signature.get("planned_count") or signature.get("source_signatures") or 0),
            "signature_inserted": int(signature.get("inserted") or 0),
            "signature_failed": int(signature.get("failed") or 0),
            "signature_skipped": int(signature.get("skipped_existing") or 0) + int(signature.get("skipped_no_user") or 0),
        },
        "error_classes": signature.get("error_classes") or main.get("error_classes") or {},
        "failed_fingerprints": list(signature.get("failed_fingerprints") or [])[:3],
    }
