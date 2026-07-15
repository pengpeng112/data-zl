"""Server-side credential file store for data source connections.

Passwords are never returned by APIs. Platform tables only keep credential_ref
and masked username/status. Default layout:

    /etc/data-asset/credentials/<source_code>.readonly

Local/dev fallback uses APP_CREDENTIAL_DIR or ./var/credentials.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

SOURCE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
DEFAULT_CREDENTIAL_DIR = Path(os.environ.get("APP_CREDENTIAL_DIR", "/etc/data-asset/credentials"))


class CredentialStoreError(ValueError):
    pass


def _safe_source_code(source_code: str) -> str:
    code = (source_code or "").strip()
    if not code or not SOURCE_CODE_RE.match(code):
        raise CredentialStoreError("invalid source_code for credential path")
    if ".." in code or "/" in code or "\\" in code:
        raise CredentialStoreError("source_code path traversal is not allowed")
    return code


def credential_dir() -> Path:
    path = Path(os.environ.get("APP_CREDENTIAL_DIR") or DEFAULT_CREDENTIAL_DIR)
    return path


def credential_path(source_code: str, *, writable: bool = False) -> Path:
    code = _safe_source_code(source_code)
    suffix = ".write" if writable else ".readonly"
    base = credential_dir().resolve()
    path = (base / f"{code}{suffix}").resolve()
    if not str(path).startswith(str(base)):
        raise CredentialStoreError("credential path escaped store directory")
    return path


def mask_username(username: str | None) -> str | None:
    if not username:
        return None
    name = username.strip()
    if not name:
        return None
    if len(name) <= 2:
        return name[0] + "*"
    return name[0] + ("*" * min(3, len(name) - 2)) + name[-1]


def status(source_code: str, *, writable: bool = False) -> str:
    try:
        path = credential_path(source_code, writable=writable)
    except CredentialStoreError:
        return "error"
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "error"
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "error"
    if ":" not in content:
        return "error"
    user, pwd = content.split(":", 1)
    if not user.strip() or not pwd:
        return "error"
    return "configured"


def store(
    source_code: str,
    username: str,
    password: str,
    *,
    writable: bool = False,
    activate: bool = True,
) -> str:
    """Write username:password to the credential file and return file:// ref.

    When activate=False, writes to a temp sibling file and returns its path as
    inactive ref (caller must activate after DB commit).
    """
    code = _safe_source_code(source_code)
    user = (username or "").strip()
    if not user:
        raise CredentialStoreError("username is required")
    if password is None or password == "":
        raise CredentialStoreError("password is required")
    if "\n" in user or "\r" in user or ":" in user:
        raise CredentialStoreError("username contains illegal characters")
    if "\n" in password or "\r" in password:
        raise CredentialStoreError("password contains illegal characters")

    final_path = credential_path(code, writable=writable)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(final_path.parent, 0o700)
    except OSError:
        pass

    payload = f"{user}:{password}".encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{code}.",
        suffix=".tmp",
        dir=str(final_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        if activate:
            os.replace(tmp_path, final_path)
            try:
                os.chmod(final_path, 0o600)
            except OSError:
                pass
            return f"file://{final_path}"
        inactive = final_path.with_suffix(final_path.suffix + ".pending")
        os.replace(tmp_path, inactive)
        try:
            os.chmod(inactive, 0o600)
        except OSError:
            pass
        return f"file://{inactive}"
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def activate(pending_ref: str, source_code: str, *, writable: bool = False) -> str:
    """Atomically promote a pending credential file to the active path."""
    if not pending_ref.startswith("file://"):
        raise CredentialStoreError("pending credential_ref must be file://")
    pending = Path(pending_ref[7:])
    final_path = credential_path(source_code, writable=writable)
    if not pending.exists():
        raise CredentialStoreError("pending credential file is missing")
    os.replace(pending, final_path)
    try:
        os.chmod(final_path, 0o600)
    except OSError:
        pass
    return f"file://{final_path}"


def rotate(source_code: str, username: str, password: str, *, writable: bool = False) -> str:
    return store(source_code, username, password, writable=writable, activate=True)


def delete(source_code: str, *, writable: bool = False) -> None:
    path = credential_path(source_code, writable=writable)
    pending = path.with_suffix(path.suffix + ".pending")
    for target in (path, pending):
        try:
            if target.exists():
                target.unlink()
        except OSError as exc:
            raise CredentialStoreError(f"failed to delete credential file: {exc}") from exc
