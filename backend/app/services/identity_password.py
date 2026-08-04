"""JHEMR SM4 password encoding per plan 106/107.

Algorithm (verified by forward/reverse encryption):
  key16 = (user_id + date_str + "bjgoodwill").encode('utf-8')[:16]
  cipher = SM4/ECB/PKCS7Padding
  output = Base64(ciphertext)

Security constraints:
- Default password ONLY from secret provider (file/env), never in code/git/logs.
- Plaintext, ciphertext, derived key, and algorithm secrets MUST NOT appear in
  logs, audit, API responses, test reports, or Git.
- date_str uses Asia/Shanghai timezone (same set_date for all tables in one tx).
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

SM4_SALT = "bjgoodwill"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

_SENSITIVE_LOG_PATTERNS = ("password", "pwd", "secret", "key16", "plaintext", "ciphertext")


def _resolve_secret(ref: str) -> str:
    """Resolve a secret reference to its string value.

    Supports:
    - file:///path/to/file (reads first line, stripped)
    - env:VAR_NAME (reads environment variable)
    - bare path (treated as file path)
    """
    import os

    ref = ref.strip()
    if ref.startswith("env:"):
        var_name = ref[4:]
        value = os.environ.get(var_name, "")
        if not value:
            raise IdentityPasswordError(f"Environment variable for password ref is empty")
        return value
    path_str = ref[7:] if ref.startswith("file://") else ref
    try:
        content = Path(path_str).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise IdentityPasswordError(
            f"Cannot read password secret file: {type(exc).__name__}"
        ) from exc
    if not content:
        raise IdentityPasswordError("Password secret file is empty")
    return content.split("\n")[0].strip()


class IdentityPasswordError(Exception):
    """Raised when password operations fail."""


def get_shanghai_date_str(dt: datetime | None = None) -> str:
    """Get yyyyMMdd string in Asia/Shanghai timezone."""
    if dt is None:
        dt = datetime.now(SHANGHAI_TZ)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI_TZ)
    else:
        dt = dt.astimezone(SHANGHAI_TZ)
    return dt.strftime("%Y%m%d")


def encode_jhemr_password(user_id: str, plain_pwd: str, date_str: str | None = None) -> str:
    """Generate JHEMR user_pwd_sm ciphertext.

    Args:
        user_id: The user_login_name / user_id (employee number).
        plain_pwd: The plaintext password to encrypt.
        date_str: Override date string (yyyyMMdd). Defaults to today in Asia/Shanghai.

    Returns:
        Base64-encoded SM4/ECB/PKCS7 ciphertext.

    Raises:
        IdentityPasswordError: If gmssl is not available or encryption fails.
    """
    if not user_id or not plain_pwd:
        raise IdentityPasswordError("user_id and plain_pwd must not be empty")

    if date_str is None:
        date_str = get_shanghai_date_str()

    key_material = f"{user_id}{date_str}{SM4_SALT}".encode("utf-8")[:16]
    if len(key_material) < 16:
        key_material = key_material.ljust(16, b"\x00")

    try:
        from gmssl.sm4 import CryptSM4, SM4_ENCRYPT
    except ImportError as exc:
        raise IdentityPasswordError(
            "gmssl package is required for JHEMR password encoding"
        ) from exc

    try:
        sm4 = CryptSM4()
        sm4.set_key(key_material, SM4_ENCRYPT)
        plaintext_bytes = plain_pwd.encode("utf-8")
        ciphertext = sm4.crypt_ecb(plaintext_bytes)
        return base64.b64encode(ciphertext).decode("ascii")
    except Exception as exc:
        raise IdentityPasswordError(f"SM4 encryption failed: {type(exc).__name__}") from exc


def get_default_password(secret_ref: str) -> str:
    """Retrieve the default password from the secret provider.

    The password is NEVER logged, stored in variables beyond this call chain,
    or included in any audit/API output.
    """
    return _resolve_secret(secret_ref)


def compute_password_fields(
    user_id: str,
    secret_ref: str,
    date_str: str | None = None,
) -> dict[str, str]:
    """Compute all password-related fields for a JHEMR user in one call.

    Returns dict with:
    - user_pwd_sm: Base64 SM4 ciphertext
    - pwd_set_date: the date_str used (yyyyMMdd)
    - is_sm: "2" (SM4 mode indicator)

    The plaintext password is resolved internally and never returned or logged.
    """
    plain_pwd = get_default_password(secret_ref)
    if date_str is None:
        date_str = get_shanghai_date_str()

    ciphertext = encode_jhemr_password(user_id, plain_pwd, date_str)

    return {
        "user_pwd_sm": ciphertext,
        "pwd_set_date": date_str,
        "is_sm": "2",
    }
