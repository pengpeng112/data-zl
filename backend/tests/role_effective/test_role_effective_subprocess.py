"""111 号 S3：统一有效角色判定。

子进程纯逻辑验证 auth_service.lookup_roles 与 main._lookup_roles 均委托
core.security._effective_role_codes（该查询含 valid_from/expires_at/status 过滤），
防止回退到"只按 user_identifier 拉全量角色"的越权实现。
不连接数据库：用捕获 SQL 的 fake Session 校验查询条件。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_SNIPPET = r"""
import os, sys
sys.path.insert(0, r"{BACKEND_DIR}")
import inspect
from app.services import auth_service
from app import main
from app.main import _lookup_roles

# _effective_role_codes 内部构造 select(AssetUserRole).where(...)
from app.core.security import _effective_role_codes
src = inspect.getsource(_effective_role_codes)
assert "valid_from" in src and "expires_at" in src and "status" in src, (
    "有效角色查询必须过滤 valid_from/expires_at/status"
)

# lookup_roles 必须委托 _effective_role_codes，不得自行拉全量角色
assert "from app.core.security import _effective_role_codes" in inspect.getsource(auth_service.lookup_roles) or \
       "_effective_role_codes" in inspect.getsource(auth_service.lookup_roles), (
    "auth_service.lookup_roles 必须复用 _effective_role_codes"
)
assert "_effective_role_codes" in inspect.getsource(_lookup_roles), (
    "main._lookup_roles 必须复用 _effective_role_codes"
)

# 无 user_identifier 时返回空，不触发查询
assert auth_service.lookup_roles(None, None) == []
assert _lookup_roles(None, None) == []

# 旧 JWT 声明高权限时，数据库空角色必须立即覆盖为 []。
main._lookup_roles = lambda db, user_identifier: []
assert main._resolve_jwt_roles(None, {{
    "user_identifier": "revoked-user", "roles": ["platform_admin"]
}}) == []

# 数据库查询异常不得回退 JWT roles，异常必须向外传播并由中间件失败关闭。
def fail_lookup(db, user_identifier):
    raise RuntimeError("role store unavailable")
main._lookup_roles = fail_lookup
try:
    main._resolve_jwt_roles(None, {{
        "user_identifier": "user-1", "roles": ["platform_admin"]
    }})
except RuntimeError:
    pass
else:
    raise AssertionError("角色库异常时不得回退 JWT roles")
print("ROLE_EFFECTIVE_OK")
"""


def _clean_env() -> dict:
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("APP_") and not k.startswith("PYTEST_")
    }
    env["APP_ENV"] = "test"
    return env


def test_role_lookup_delegates_to_effective_role_codes():
    env = _clean_env()
    # 需要合法测试 URL 才能通过 db.py 门禁 import app.main
    env["APP_TEST_DB_URL"] = "postgresql://u:p@127.0.0.1:5432/asset_test"
    env["APP_DB_URL"] = env["APP_TEST_DB_URL"]
    proc = subprocess.run(
        [sys.executable, "-c", _SNIPPET.format(BACKEND_DIR=str(BACKEND_DIR))],
        capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "ROLE_EFFECTIVE_OK" in proc.stdout
