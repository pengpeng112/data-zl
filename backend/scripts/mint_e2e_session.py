"""119 号 S4 辅助：为真实浏览器验收铸造短期会话材料（在服务器容器内执行）。

选择第一个拥有 asset.graph.view 权限（或 *:*:*）的启用账号，铸造短期 JWT，
把 {username, nickname, roles, permissions, accessToken, expires} 以 JSON 打到 stdout。
调用方通过 ssh 捕获，禁止落盘/打印到日志。Token TTL 由平台配置决定（短期）。
"""
import json
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.auth import AuthUser  # noqa: E402
from app.services import auth_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        from app.api.v1.permissions import _permission_codes_for_roles

        users = db.scalars(select(AuthUser).where(AuthUser.enabled.is_(True))).all()
        chosen = None
        for user in users:
            roles = auth_service.lookup_roles(db, user.user_identifier or user.username)
            permissions = _permission_codes_for_roles(db, roles)
            if "*:*:*" in permissions or "asset.graph.view" in permissions:
                chosen = (user, roles, permissions)
                break
        if not chosen:
            print(json.dumps({"error": "no user with graph permission"}))
            return
        user, roles, permissions = chosen
        token, expires_at = auth_service.create_access_token(user, roles)
        print(json.dumps({
            "username": user.username,
            "nickname": user.user_identifier or user.username,
            "roles": roles,
            "permissions": permissions,
            "accessToken": token,
            "expires": int(expires_at.timestamp() * 1000),
        }))
    finally:
        db.close()


if __name__ == "__main__":
    main()
