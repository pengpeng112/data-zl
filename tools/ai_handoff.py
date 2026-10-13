#!/usr/bin/env python3
"""Advisory local file-scope claims for coordinating AI sessions.

Claims are coordination hints only. They are not task status authority and do
not grant access to databases, production systems, or Git operations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterator


DEFAULT_TTL_MINUTES = 120
MAX_TTL_MINUTES = 7 * 24 * 60
SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z", re.ASCII)
WILDCARDS = set("*?[]")


class HandoffError(Exception):
    """Safe-to-display validation or coordination error."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_stamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _safe_text(value: str, label: str, limit: int, required: bool = True) -> str:
    value = value.strip()
    if required and not value:
        raise HandoffError(f"{label} must not be empty")
    if len(value) > limit or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise HandoffError(f"{label} is invalid or too long")
    return value


def _repo_path(repo_arg: str | None) -> Path:
    try:
        root = Path(repo_arg or os.getcwd()).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise HandoffError("repository path is unavailable") from None
    if not root.is_dir():
        raise HandoffError("repository path must be a directory")
    return root


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _claims_dir(root: Path, create: bool = False) -> Path:
    claims = root / ".agents" / "collaboration" / "claims"
    try:
        if not _inside(claims.resolve(strict=False), root):
            raise HandoffError("claims directory resolves outside the repository")
        if create:
            claims.mkdir(parents=True, exist_ok=True)
        resolved = claims.resolve(strict=True)
    except HandoffError:
        raise
    except (OSError, RuntimeError):
        raise HandoffError("claims directory is unavailable") from None
    if not _inside(resolved, root) or not resolved.is_dir():
        raise HandoffError("claims directory resolves outside the repository")
    return resolved


def _scope_path(root: Path, raw: str) -> tuple[str, tuple[str, ...]]:
    raw = raw.strip()
    if not raw or any(char in WILDCARDS for char in raw) or ":" in raw:
        raise HandoffError("scope must be a repository-relative file or directory")
    # Accept either separator in a cross-platform CLI, then validate both path
    # grammars so Windows drive/UNC paths are rejected even on POSIX.
    windows = PureWindowsPath(raw)
    posix = PurePosixPath(raw.replace("\\", "/"))
    if windows.is_absolute() or windows.drive or posix.is_absolute():
        raise HandoffError("scope must be repository-relative")
    pieces = raw.replace("\\", "/").split("/")
    if any(piece in ("", ".", "..") for piece in pieces):
        raise HandoffError("scope contains an invalid path component")
    candidate = root.joinpath(*pieces)
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        raise HandoffError("scope path cannot be resolved") from None
    if not _inside(resolved, root):
        raise HandoffError("scope resolves outside the repository")
    relative = resolved.relative_to(root)
    canonical = unicodedata.normalize("NFC", relative.as_posix())
    if not canonical or canonical == ".":
        raise HandoffError("the repository root cannot be claimed")
    folded_parts = tuple(unicodedata.normalize("NFC", part).casefold() for part in canonical.split("/"))
    return canonical, folded_parts


def _scopes_conflict(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    shared = min(len(left), len(right))
    return left[:shared] == right[:shared]


def _read_claim(path: Path) -> dict[str, Any] | None:
    if path.is_symlink():
        raise HandoffError("a claim record is a symbolic link")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise HandoffError("a claim record is unreadable") from None
    if not isinstance(data, dict):
        raise HandoffError("a claim record is malformed")
    session = data.get("session")
    try:
        if not isinstance(session, str) or _session(session) != path.stem:
            raise HandoffError("a claim record has invalid ownership")
        scopes = data.get("scopes")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(scope, str) for scope in scopes):
            raise HandoffError("a claim record has invalid scopes")
        if any(not scope or len(scope) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in scope) for scope in scopes):
            raise HandoffError("a claim record has invalid scopes")
        ttl = data.get("ttl_minutes")
        if isinstance(ttl, bool) or not isinstance(ttl, int) or not 1 <= ttl <= MAX_TTL_MINUTES:
            raise HandoffError("a claim record has invalid TTL")
        for key, limit in (("tool", 80), ("model", 120), ("task", 240)):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise HandoffError("a claim record has invalid metadata")
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise HandoffError("a claim record has invalid metadata")
        checkpoint = data.get("checkpoint")
        if checkpoint is not None and (
            not isinstance(checkpoint, str)
            or len(checkpoint) > 500
            or any(ord(char) < 32 or ord(char) == 127 for char in checkpoint)
        ):
            raise HandoffError("a claim record has invalid metadata")
        created = _parse_stamp(data.get("created_at"))
        heartbeat = _parse_stamp(data.get("heartbeat_at"))
        expires = _parse_stamp(data.get("expires_at"))
        if created > heartbeat or expires <= heartbeat:
            raise HandoffError("a claim record has invalid timestamps")
    except (TypeError, ValueError, OverflowError):
        raise HandoffError("a claim record has invalid timestamps") from None
    return data


def _all_claims(claims_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        paths = sorted(claims_dir.glob("*.json"), key=lambda item: item.name.casefold())
    except OSError:
        raise HandoffError("cannot list claim records") from None
    for path in paths:
        data = _read_claim(path)
        if data is not None:
            records.append(data)
    return records


@contextmanager
def _guard(claims_dir: Path) -> Iterator[None]:
    guard_path = claims_dir / ".guard"
    token = uuid.uuid4().hex
    try:
        fd = os.open(guard_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise HandoffError("claim store is busy (guard exists); retry after the owner clears it") from None
    except OSError:
        raise HandoffError("cannot acquire claim store guard") from None
    try:
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(token)
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        # Remove only the guard created by this process. A replaced/foreign
        # guard is never removed as a recovery shortcut.
        try:
            if guard_path.read_text(encoding="ascii") == token:
                guard_path.unlink()
        except (OSError, UnicodeError):
            pass


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temp_path: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".claim-", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError:
        raise HandoffError("could not write claim record") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _session(value: str) -> str:
    if not SESSION_RE.fullmatch(value):
        raise HandoffError("session must be a unique ASCII identifier (letters, digits, dot, underscore, hyphen)")
    return value


def status(repo_arg: str | None = None) -> list[dict[str, Any]]:
    root = _repo_path(repo_arg)
    if not (root / ".agents" / "collaboration" / "claims").exists():
        return []
    claims_dir = _claims_dir(root)
    now = _now()
    results = []
    for claim in _all_claims(claims_dir):
        try:
            expired = _parse_stamp(claim["expires_at"]) <= now
        except (KeyError, TypeError, ValueError):
            expired = True
        record = dict(claim)
        record["expired"] = expired
        results.append(record)
    return results


def claim(args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_path(args.repo)
    session = _session(args.session)
    tool = _safe_text(args.tool, "tool", 80)
    model = _safe_text(args.model, "model", 120)
    task = _safe_text(args.task, "task", 240)
    checkpoint = _safe_text(args.checkpoint or "", "checkpoint", 500, required=False)
    if not 1 <= args.ttl_minutes <= MAX_TTL_MINUTES:
        raise HandoffError(f"ttl-minutes must be between 1 and {MAX_TTL_MINUTES}")
    if not args.scopes:
        raise HandoffError("at least one --scope is required")
    scope_pairs = [_scope_path(root, item) for item in args.scopes]
    for index, (_, parts) in enumerate(scope_pairs):
        if any(_scopes_conflict(parts, other) for _, other in scope_pairs[:index]):
            raise HandoffError("scopes in one claim overlap")
    scopes = sorted({path for path, _ in scope_pairs}, key=lambda value: value.casefold())
    claims_dir = _claims_dir(root, create=True)
    target = claims_dir / f"{session}.json"
    now = _now()
    with _guard(claims_dir):
        previous = _read_claim(target)
        if previous is not None and previous.get("session") != session:
            raise HandoffError("claim ownership does not match the requested session")
        existing = _all_claims(claims_dir)
        if any(
            other.get("session", "").casefold() == session.casefold()
            and other.get("session") != session
            for other in existing
        ):
            raise HandoffError("session identifier conflicts with an existing session")
        requested = [parts for _, parts in scope_pairs]
        for other in existing:
            if other.get("session") == session:
                continue
            for existing_scope in other.get("scopes", []):
                try:
                    _, existing_parts = _scope_path(root, existing_scope)
                except HandoffError:
                    raise HandoffError("an existing claim has an invalid scope") from None
                if any(_scopes_conflict(wanted, existing_parts) for wanted in requested):
                    raise HandoffError("requested scope conflicts with another session claim")
        record = {
            "session": session,
            "tool": tool,
            "model": model,
            "task": task,
            "checkpoint": checkpoint or None,
            "scopes": scopes,
            "created_at": (previous or {}).get("created_at", _stamp(now)),
            "heartbeat_at": _stamp(now),
            "ttl_minutes": args.ttl_minutes,
            "expires_at": _stamp(now + timedelta(minutes=args.ttl_minutes)),
        }
        _atomic_write(target, record)
    return record


def heartbeat(args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_path(args.repo)
    session = _session(args.session)
    try:
        claims_dir = _claims_dir(root)
    except HandoffError:
        raise HandoffError("claim does not exist") from None
    target = claims_dir / f"{session}.json"
    with _guard(claims_dir):
        record = _read_claim(target)
        if record is None:
            raise HandoffError("claim does not exist; heartbeat cannot create one")
        if record.get("session") != session:
            raise HandoffError("claim ownership does not match the requested session")
        try:
            ttl = int(args.ttl_minutes) if args.ttl_minutes is not None else int(record["ttl_minutes"])
        except (KeyError, TypeError, ValueError):
            raise HandoffError("claim TTL is invalid") from None
        if not 1 <= ttl <= MAX_TTL_MINUTES:
            raise HandoffError(f"ttl-minutes must be between 1 and {MAX_TTL_MINUTES}")
        now = _now()
        record["ttl_minutes"] = ttl
        record["heartbeat_at"] = _stamp(now)
        record["expires_at"] = _stamp(now + timedelta(minutes=ttl))
        if args.checkpoint is not None:
            record["checkpoint"] = _safe_text(args.checkpoint, "checkpoint", 500, required=False) or None
        _atomic_write(target, record)
    return record


def release(args: argparse.Namespace) -> None:
    root = _repo_path(args.repo)
    session = _session(args.session)
    try:
        claims_dir = _claims_dir(root)
    except HandoffError:
        raise HandoffError("claim does not exist") from None
    target = claims_dir / f"{session}.json"
    with _guard(claims_dir):
        record = _read_claim(target)
        if record is None:
            raise HandoffError("claim does not exist")
        if record.get("session") != session:
            raise HandoffError("claim ownership does not match the requested session")
        try:
            target.unlink()
        except OSError:
            raise HandoffError("could not release claim") from None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Advisory local file-scope claims for AI collaboration")
    parser.add_argument("--repo", help="repository root (defaults to current directory)")
    commands = parser.add_subparsers(dest="command", required=True)

    claim_parser = commands.add_parser("claim", help="create or update this session's claim")
    claim_parser.add_argument("--session", required=True)
    claim_parser.add_argument("--tool", required=True)
    claim_parser.add_argument("--model", required=True)
    claim_parser.add_argument("--task", required=True, help="short non-sensitive task summary")
    claim_parser.add_argument(
        "--scope", dest="scopes", action="append", required=True,
        help="repo-relative file or directory; repeatable",
    )
    claim_parser.add_argument("--checkpoint", default="", help="short non-sensitive checkpoint")
    claim_parser.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)
    claim_parser.set_defaults(handler=claim)

    heartbeat_parser = commands.add_parser("heartbeat", help="renew this session's claim")
    heartbeat_parser.add_argument("--session", required=True)
    heartbeat_parser.add_argument("--ttl-minutes", type=int)
    heartbeat_parser.add_argument("--checkpoint")
    heartbeat_parser.set_defaults(handler=heartbeat)

    release_parser = commands.add_parser("release", help="release this session's claim")
    release_parser.add_argument("--session", required=True)
    release_parser.set_defaults(handler=release)

    status_parser = commands.add_parser("status", help="show claims without changing files")
    status_parser.set_defaults(handler=lambda args: status(args.repo))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        result = args.handler(args)
    except HandoffError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print("error: handoff operation failed", file=sys.stderr)
        return 2
    if args.command == "release":
        print(json.dumps({"released": args.session}, ensure_ascii=True))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
