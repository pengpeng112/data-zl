# -*- coding: utf-8 -*-
"""R212 S3/B07: 创建受限角色浏览器测试身份（隔离库专用，密码经环境变量传入）。

用法（Git Bash，隧道与 APP_TEST_DB_URL 由 tools/dev_env.sh 推导）：
  R212_USER_PW='...' backend/.venv/Scripts/python.exe backend/scripts/create_role_user_r212.py \
      --username r212-viewer --role asset_viewer

- 复用 auth_service.create_local_user + AssetUserRole 绑定（与 create_local_admin 同法）。
- 不发 API token；must_change_password=False（浏览器测试直接用，避免每轮改密）。
- 幂等：已存在则只确保角色绑定并返回（不动密码）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal  # noqa: E402
from app.models.auth import AuthUser  # noqa: E402
from app.models.governance_base import AssetUserRole  # noqa: E402
from app.services import auth_service  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--role", required=True, help="builtin role_code，如 asset_viewer")
    ap.add_argument("--force", action="store_true", help="已存在时重置密码")
    args = ap.parse_args()

    pw = os.environ.get("R212_USER_PW", "").strip()
    if not pw:
        raise SystemExit("缺少 R212_USER_PW 环境变量（不接收 argv 密码）")
    err = auth_service.validate_password_policy(pw)
    if err:
        raise SystemExit(f"密码不符合策略: {err}")

    identifier = args.username
    db = SessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.username == args.username).first()
        if user and not args.force:
            action = "exists"
        elif user and args.force:
            auth_service.change_password(db, user, old_password=None, new_password=pw, force=True)
            user.must_change_password = False
            user.enabled = True
            action = "reset"
        else:
            user = auth_service.create_local_user(
                db,
                username=args.username,
                password=pw,
                user_identifier=identifier,
                must_change_password=False,
                enabled=True,
            )
            action = "created"

        binding = (
            db.query(AssetUserRole)
            .filter(
                AssetUserRole.user_identifier == identifier,
                AssetUserRole.role_code == args.role,
            )
            .first()
        )
        if not binding:
            db.add(
                AssetUserRole(
                    user_identifier=identifier,
                    role_code=args.role,
                    granted_by="r212_test_seed",
                )
            )
        db.commit()
        print(f"{action}: {args.username} role={args.role} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
