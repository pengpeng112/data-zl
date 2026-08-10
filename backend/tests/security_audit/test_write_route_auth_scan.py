"""123 R3 / 118-U5：写路由权限自动扫描。

扫描 FastAPI 路由表中全部 POST/PUT/PATCH/DELETE：
1) 必须进入显式公开白名单，或
2) 受全局鉴权中间件保护（路径不在 PUBLIC_* 中）。

兼容新版 Starlette/FastAPI 的 _IncludedRouter 嵌套路由表。
缺权写路由直接失败关闭。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_SNIPPET = r"""
import os
import sys

sys.path.insert(0, r"{BACKEND_DIR}")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_RATE_LIMIT_ENABLED", "false")
os.environ.setdefault(
    "APP_TEST_DB_URL",
    os.environ.get("APP_TEST_DB_URL") or "postgresql://u:p@127.0.0.1:5432/asset_test",
)
os.environ["APP_DB_URL"] = os.environ["APP_TEST_DB_URL"]

from app.main import PUBLIC_EXACT, PUBLIC_PREFIXES, app

WRITE = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_WRITE_ALLOWLIST = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


def _iter_api_routes(routes):
    for route in routes:
        name = type(route).__name__
        if name == "_IncludedRouter":
            original = getattr(route, "original_router", None)
            nested = getattr(original, "routes", None) if original is not None else None
            if nested:
                yield from _iter_api_routes(nested)
            continue
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", None)
        if path and methods:
            yield path, {m.upper() for m in methods}


violations = []
protected = 0
public_ok = 0
seen = set()
for path, methods in _iter_api_routes(app.routes):
    for method in methods:
        if method not in WRITE:
            continue
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        if key in PUBLIC_WRITE_ALLOWLIST:
            public_ok += 1
            continue
        if _is_public_path(path):
            # 公开集合里的写方法必须显式列入 allowlist（健康/文档通常无写）
            if path.startswith(("/health", "/docs", "/openapi", "/redoc", "/api/v1/health")):
                public_ok += 1
                continue
            violations.append(f"PUBLIC_WRITE_NOT_ALLOWLISTED {method} {path}")
            continue
        protected += 1

if protected < 20:
    raise SystemExit(f"too few protected write routes: {protected}; total_seen={len(seen)}")
if violations:
    raise SystemExit("WRITE_ROUTE_VIOLATIONS\n" + "\n".join(violations[:50]))
print(f"WRITE_ROUTE_SCAN_OK protected={protected} public_ok={public_ok} total={len(seen)}")
"""


def _clean_env() -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("APP_") and not k.startswith("PYTEST_")
    }
    host_url = os.environ.get("APP_TEST_DB_URL", "")
    if host_url and "test" in host_url.lower():
        env["APP_TEST_DB_URL"] = host_url
        env["APP_DB_URL"] = host_url
    env["APP_ENV"] = "test"
    env["APP_RATE_LIMIT_ENABLED"] = "false"
    env["APP_JWT_SECRET"] = "test-only-jwt-secret-not-for-prod"
    return env


def test_write_routes_require_auth_or_public_allowlist():
    env = _clean_env()
    snippet = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(BACKEND_DIR),
        timeout=180,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "WRITE_ROUTE_SCAN_OK" in proc.stdout
