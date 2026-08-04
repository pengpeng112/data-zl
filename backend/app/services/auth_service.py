"""Local account authentication service: password, JWT, refresh sessions."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import _effective_role_codes
from ..models.auth import AuthLoginEvent, AuthSession, AuthUser

_ph = PasswordHasher()

GENERIC_LOGIN_FAILURE = "账号或密码错误"
REASON_BAD_CREDENTIALS = "bad_credentials"
REASON_DISABLED = "disabled"
REASON_LOCKED = "locked"
REASON_SUCCESS = "success"
REASON_MUST_CHANGE = "must_change_password"


class AuthError(Exception):
    def __init__(self, message: str, reason_code: str = REASON_BAD_CREDENTIALS, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        self.status_code = status_code


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def validate_password_policy(password: str) -> str | None:
    """与前端 REGEXP_PWD 对齐：8-18 位；数字/字母/符号至少两类；禁止中文。"""
    min_len = settings.auth_password_min_length
    max_len = settings.auth_password_max_length
    if not password or len(password) < min_len or len(password) > max_len:
        return f"密码长度应为 {min_len}-{max_len} 位"
    if re.search(r"[\u4e00-\u9fa5]", password):
        return "密码不能包含中文"
    has_letter = bool(re.search(r"[A-Za-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))
    if sum([has_letter, has_digit, has_symbol]) < 2:
        return "密码格式应为8-18位数字、字母、符号的任意两种组合"
    # 拒绝单一字符类（与前端正则一致）
    if re.fullmatch(r"[0-9]+", password):
        return "密码格式应为8-18位数字、字母、符号的任意两种组合"
    if re.fullmatch(r"[a-z]+", password) or re.fullmatch(r"[A-Z]+", password):
        return "密码格式应为8-18位数字、字母、符号的任意两种组合"
    if re.fullmatch(r"[^A-Za-z0-9]+", password):
        return "密码格式应为8-18位数字、字母、符号的任意两种组合"
    return None


def mask_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    ip = ip.strip()
    if "." in ip and ":" not in ip:
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:2] + ["*"] * max(0, len(parts) - 2))
    return "***"


def _load_key_material(for_sign: bool) -> str | bytes:
    algo = (settings.jwt_algorithm or "HS256").upper()
    if algo.startswith("HS"):
        secret = settings.jwt_secret or ""
        if not secret or secret == "dev-only-change-me":
            if settings.env not in ("dev", "test", "development"):
                raise AuthError("生产环境必须配置 APP_JWT_SECRET 或 RS256 密钥", "config", 500)
        return secret
    path = settings.jwt_private_key_path if for_sign else settings.jwt_public_key_path
    if not path:
        # RS256 验签也可回退公钥；签名必须私钥
        if not for_sign and settings.jwt_private_key_path:
            path = settings.jwt_private_key_path
        else:
            raise AuthError("未配置 JWT 密钥路径", "config", 500)
    return Path(path).read_text(encoding="utf-8")


def create_access_token(user: AuthUser, roles: list[str] | None = None) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.auth_access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "username": user.username,
        "user_identifier": user.user_identifier or user.username,
        "roles": roles or [],
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": secrets.token_urlsafe(16),
        "typ": "access",
    }
    token = jwt.encode(payload, _load_key_material(for_sign=True), algorithm=settings.jwt_algorithm)
    return token, expires


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify JWT; return payload or None if invalid/expired."""
    if not token or token.count(".") != 2:
        return None
    try:
        payload = jwt.decode(
            token,
            _load_key_material(for_sign=False),
            algorithms=[settings.jwt_algorithm],
            options={"require_exp": True, "require_sub": True},
        )
        if payload.get("typ") and payload.get("typ") != "access":
            return None
        return payload
    except JWTError:
        return None
    except Exception:
        return None


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_refresh_session(
    db: Session,
    user: AuthUser,
    *,
    client_ip_masked: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, AuthSession]:
    raw = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw),
        expires_at=now + timedelta(hours=settings.auth_refresh_token_ttl_hours),
        created_at=now,
        last_used_at=now,
        client_ip_masked=client_ip_masked,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(session)
    db.flush()
    return raw, session


def rotate_refresh_session(
    db: Session,
    raw_refresh: str,
    *,
    client_ip_masked: str | None = None,
    user_agent: str | None = None,
) -> tuple[AuthUser, str, AuthSession, list[str]]:
    """Validate old refresh, revoke it, issue new one. Returns user, new_raw, session, roles."""
    now = datetime.now(timezone.utc)
    token_hash = hash_refresh_token(raw_refresh)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    if not session or session.revoked_at is not None:
        raise AuthError("会话无效或已撤销", "invalid_session", 401)
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise AuthError("会话已过期", "session_expired", 401)

    user = db.get(AuthUser, session.user_id)
    if not user or not user.enabled:
        raise AuthError("账号不可用", REASON_DISABLED, 401)

    session.revoked_at = now
    session.last_used_at = now
    raw_new, new_session = issue_refresh_session(
        db, user, client_ip_masked=client_ip_masked, user_agent=user_agent
    )
    roles = lookup_roles(db, user.user_identifier or user.username)
    return user, raw_new, new_session, roles


def revoke_session(db: Session, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    token_hash = hash_refresh_token(raw_refresh)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)


def revoke_all_user_sessions(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ).all()
    for s in sessions:
        s.revoked_at = now
    return len(sessions)


def record_login_event(
    db: Session,
    *,
    username: str | None,
    user_identifier: str | None,
    result: str,
    reason_code: str | None,
    client_ip_masked: str | None,
) -> None:
    db.add(
        AuthLoginEvent(
            username=username,
            user_identifier=user_identifier,
            result=result,
            reason_code=reason_code,
            client_ip_masked=client_ip_masked,
        )
    )


def lookup_roles(db: Session, user_identifier: str | None) -> list[str]:
    if not user_identifier:
        return []
    return sorted(_effective_role_codes(db, user_identifier))


def _is_locked(user: AuthUser, now: datetime) -> bool:
    if not user.locked_until:
        return False
    locked = user.locked_until
    if locked.tzinfo is None:
        locked = locked.replace(tzinfo=timezone.utc)
    return locked > now


def authenticate_user(
    db: Session,
    username: str,
    password: str,
    *,
    client_ip_masked: str | None = None,
) -> AuthUser:
    """Validate credentials and lockout rules. Raises AuthError on failure."""
    now = datetime.now(timezone.utc)
    user = db.scalar(select(AuthUser).where(AuthUser.username == username))
    if not user:
        record_login_event(
            db,
            username=username,
            user_identifier=None,
            result="failure",
            reason_code=REASON_BAD_CREDENTIALS,
            client_ip_masked=client_ip_masked,
        )
        db.commit()
        raise AuthError(GENERIC_LOGIN_FAILURE, REASON_BAD_CREDENTIALS, 401)

    if not user.enabled:
        record_login_event(
            db,
            username=username,
            user_identifier=user.user_identifier,
            result="failure",
            reason_code=REASON_DISABLED,
            client_ip_masked=client_ip_masked,
        )
        db.commit()
        raise AuthError(GENERIC_LOGIN_FAILURE, REASON_DISABLED, 401)

    if _is_locked(user, now):
        record_login_event(
            db,
            username=username,
            user_identifier=user.user_identifier,
            result="failure",
            reason_code=REASON_LOCKED,
            client_ip_masked=client_ip_masked,
        )
        db.commit()
        raise AuthError(GENERIC_LOGIN_FAILURE, REASON_LOCKED, 401)

    if not verify_password(password, user.password_hash):
        user.failed_login_count = int(user.failed_login_count or 0) + 1
        if user.failed_login_count >= settings.auth_max_failed_login:
            user.locked_until = now + timedelta(minutes=settings.auth_lockout_minutes)
        record_login_event(
            db,
            username=username,
            user_identifier=user.user_identifier,
            result="failure",
            reason_code=REASON_BAD_CREDENTIALS,
            client_ip_masked=client_ip_masked,
        )
        db.commit()
        raise AuthError(GENERIC_LOGIN_FAILURE, REASON_BAD_CREDENTIALS, 401)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    record_login_event(
        db,
        username=username,
        user_identifier=user.user_identifier,
        result="success",
        reason_code=REASON_SUCCESS,
        client_ip_masked=client_ip_masked,
    )
    db.flush()
    return user


def change_password(
    db: Session,
    user: AuthUser,
    *,
    old_password: str | None,
    new_password: str,
    force: bool = False,
) -> None:
    policy_err = validate_password_policy(new_password)
    if policy_err:
        raise AuthError(policy_err, "weak_password", 400)
    if not force:
        if not old_password or not verify_password(old_password, user.password_hash):
            raise AuthError("原密码不正确", "bad_old_password", 400)
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.updated_at = datetime.now(timezone.utc)
    revoke_all_user_sessions(db, user.id)


def create_local_user(
    db: Session,
    *,
    username: str,
    password: str,
    user_identifier: str | None = None,
    must_change_password: bool = True,
    enabled: bool = True,
) -> AuthUser:
    existing = db.scalar(select(AuthUser).where(AuthUser.username == username))
    if existing:
        raise AuthError("用户名已存在", "username_exists", 409)
    policy_err = validate_password_policy(password)
    if policy_err:
        raise AuthError(policy_err, "weak_password", 400)
    user = AuthUser(
        username=username,
        password_hash=hash_password(password),
        user_identifier=user_identifier,
        enabled=enabled,
        must_change_password=must_change_password,
        failed_login_count=0,
    )
    db.add(user)
    db.flush()
    return user


def format_expires(dt: datetime) -> str:
    """pure-admin expects 'yyyy/MM/dd HH:mm:ss' style string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    return local.strftime("%Y/%m/%d %H:%M:%S")
