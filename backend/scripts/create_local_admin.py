"""Create or reset the first local platform admin (deploy-time only).

Password sources (never via CLI args / shell history):
1. Environment variable APP_PLATFORM_ADMIN_PASSWORD
2. Interactive getpass prompt
3. Optional --generate-password (prints once to stdout)

Idempotent:
- Existing username without --force exits non-zero (no duplicate account).
- Role binding is upsert-safe (no duplicate platform_admin rows).
- --force resets password, clears lock, revokes sessions, re-enables account.

Does not write passwords into logs, .env files, or Git.
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal
from app.models.auth import AuthUser
from app.models.governance_base import AssetUserRole
from app.services import auth_service
from scripts.create_admin_token import create_token

DEFAULT_USERNAME = "platform-admin"
DEFAULT_IDENTIFIER = "platform-admin"
ENV_PASSWORD = "APP_PLATFORM_ADMIN_PASSWORD"


def _resolve_password(*, generate: bool, interactive: bool) -> tuple[str, str]:
    """Return (password, source_tag). Never reads from argv."""
    env_pw = os.environ.get(ENV_PASSWORD, "").strip()
    if env_pw:
        err = auth_service.validate_password_policy(env_pw)
        if err:
            raise SystemExit(f"环境变量 {ENV_PASSWORD} 不符合密码策略: {err}")
        return env_pw, "env"

    if generate:
        # 8-18 位，字母+数字+符号（满足前端 8-18 与两类组合）
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
        symbols = "!@#$%*"
        # 固定混入三类各至少 1 个，总长 12（落在 8-18）
        chars = [
            secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ"),
            secrets.choice("abcdefghijkmnopqrstuvwxyz"),
            secrets.choice("23456789"),
            secrets.choice(symbols),
        ]
        chars += [secrets.choice(alphabet + symbols) for _ in range(8)]
        secrets.SystemRandom().shuffle(chars)
        pw = "".join(chars)
        err = auth_service.validate_password_policy(pw)
        if err:
            pw = "Adm9#kP2xQ7"
        return pw, "generated"

    if interactive or sys.stdin.isatty():
        pw1 = getpass.getpass("输入 platform-admin 初始密码（不回显）: ")
        pw2 = getpass.getpass("再次确认密码: ")
        if not pw1 or pw1 != pw2:
            raise SystemExit("两次输入不一致或为空")
        err = auth_service.validate_password_policy(pw1)
        if err:
            raise SystemExit(err)
        return pw1, "interactive"

    raise SystemExit(
        f"未提供密码。请设置 {ENV_PASSWORD}，或在交互终端运行，或使用 --generate-password。"
    )


def create_local_admin(
    *,
    username: str = DEFAULT_USERNAME,
    user_identifier: str = DEFAULT_IDENTIFIER,
    force: bool = False,
    issue_api_token: bool = True,
    key_name: str = "platform-admin",
    password: str | None = None,
    password_source: str = "caller",
    generate_password: bool = False,
    interactive: bool = False,
) -> dict:
    if password is None:
        password, password_source = _resolve_password(
            generate=generate_password, interactive=interactive
        )

    db = SessionLocal()
    try:
        existing = db.query(AuthUser).filter(AuthUser.username == username).first()
        if existing and not force:
            raise SystemExit(
                f"账号 {username!r} 已存在（id={existing.id}）。"
                "重复执行被拒绝（幂等保护）。需要重置时加 --force。"
            )

        if existing and force:
            auth_service.change_password(
                db, existing, old_password=None, new_password=password, force=True
            )
            existing.must_change_password = True
            existing.enabled = True
            existing.user_identifier = user_identifier
            existing.failed_login_count = 0
            existing.locked_until = None
            user = existing
            action = "reset"
        else:
            user = auth_service.create_local_user(
                db,
                username=username,
                password=password,
                user_identifier=user_identifier,
                must_change_password=True,
                enabled=True,
            )
            action = "created"

        role = (
            db.query(AssetUserRole)
            .filter(
                AssetUserRole.user_identifier == user_identifier,
                AssetUserRole.role_code == "platform_admin",
            )
            .first()
        )
        if not role:
            db.add(
                AssetUserRole(
                    user_identifier=user_identifier,
                    role_code="platform_admin",
                    granted_by="create_local_admin",
                )
            )

        db.commit()

        api_token = None
        if issue_api_token:
            api_token = create_token(key_name=key_name, user_identifier=user_identifier)

        return {
            "action": action,
            "username": username,
            "user_identifier": user_identifier,
            "password_source": password_source,
            # Only return plaintext when generated so operator can deliver once.
            "one_time_password": password if password_source == "generated" else None,
            "api_token": api_token,
            "must_change_password": True,
            "auth_user_id": user.id,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create local platform-admin account")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--user-identifier", default=DEFAULT_IDENTIFIER)
    parser.add_argument("--force", action="store_true", help="Reset existing account")
    parser.add_argument("--no-api-token", action="store_true")
    parser.add_argument("--key-name", default="platform-admin")
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="Auto-generate one-time password and print once (avoid if possible)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force getpass prompt even if not a TTY detection path",
    )
    args = parser.parse_args()

    result = create_local_admin(
        username=args.username,
        user_identifier=args.user_identifier,
        force=args.force,
        issue_api_token=not args.no_api_token,
        key_name=args.key_name,
        generate_password=args.generate_password,
        interactive=args.interactive,
    )
    # Safe summary only — never log password from env/interactive
    print("=== local platform admin ===")
    print(f"action={result['action']}")
    print(f"username={result['username']}")
    print(f"user_identifier={result['user_identifier']}")
    print(f"password_source={result['password_source']}")
    print("must_change_password=true")
    if result.get("one_time_password"):
        print("one_time_password=<shown once below>")
        print(result["one_time_password"])
    if result.get("api_token"):
        print("api_token=<shown once below>")
        print(result["api_token"])
    print("Deliver credentials via approved secure channel only.")


if __name__ == "__main__":
    main()
