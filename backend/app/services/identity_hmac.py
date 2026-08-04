"""Server-side HMAC account fingerprint for identity sync.

Per plan 107 §9: batches, actions, scheduler runs, and managed relations
are bound to accounts via HMAC fingerprint, NOT emp_no_masked.

The HMAC key is loaded from a secret provider (file/env), never hardcoded.
Fingerprints are irreversible and safe for logs/audit/API output.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class IdentityHmacError(Exception):
    """Raised when HMAC operations fail."""


_key_cache: bytes | None = None


def _load_hmac_key(key_ref: str) -> bytes:
    """Load HMAC key from secret provider. Never logs key material."""
    global _key_cache
    if _key_cache is not None:
        return _key_cache

    import os
    key_ref = key_ref.strip()
    if key_ref.startswith("env:"):
        var_name = key_ref[4:]
        value = os.environ.get(var_name, "")
        if not value:
            raise IdentityHmacError("HMAC key environment variable is empty")
        _key_cache = value.encode("utf-8")
        return _key_cache

    path_str = key_ref[7:] if key_ref.startswith("file://") else key_ref
    try:
        content = Path(path_str).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise IdentityHmacError(
            f"Cannot read HMAC key file: {type(exc).__name__}"
        ) from exc
    if not content:
        raise IdentityHmacError("HMAC key file is empty")
    _key_cache = content.split("\n")[0].strip().encode("utf-8")
    return _key_cache


def reset_key_cache() -> None:
    """Reset cached key (for testing)."""
    global _key_cache
    _key_cache = None


def compute_account_fingerprint(emp_no: str, target_system: str, key_ref: str) -> str:
    """Compute irreversible HMAC-SHA256 fingerprint for an account.

    The fingerprint binds (emp_no, target_system) so the same person has
    different fingerprints per target system. This prevents cross-system
    identity confusion.

    Returns hex string (64 chars). Safe for logs/audit/API.
    """
    if not emp_no:
        raise IdentityHmacError("emp_no must not be empty for fingerprint")
    key = _load_hmac_key(key_ref)
    message = f"{target_system}:{emp_no}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def compute_action_hash(
    account_fingerprint: str,
    target_system: str,
    action_type: str,
    target_table: str,
    template_version: str,
) -> str:
    """Compute a deterministic hash for an action to enable idempotency.

    Same inputs always produce the same hash, enabling duplicate detection.
    """
    raw = f"{account_fingerprint}|{target_system}|{action_type}|{target_table}|{template_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compute_idempotency_key(
    account_fingerprint: str,
    target_system: str,
    relation_type: str,
    target_table: str,
    template_version: str,
) -> str:
    """Compute unique idempotency key for managed relation deduplication.

    Ensures the same logical relation is never created twice.
    """
    raw = f"{account_fingerprint}|{target_system}|{relation_type}|{target_table}|{template_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def compute_batch_fingerprint(
    account_fingerprints: list[str],
    batch_type: str,
    validation_mode: str | None = None,
) -> str:
    """Compute a batch-level fingerprint for scheduler run binding."""
    sorted_fps = sorted(account_fingerprints)
    raw = f"{batch_type}|{validation_mode or ''}|" + "|".join(sorted_fps)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
