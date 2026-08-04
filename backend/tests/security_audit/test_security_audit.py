"""111 号 S5：写接口显式动作授权 + 连接测试防 SSRF。

子进程纯逻辑测试：
  1) 连接测试防 SSRF —— validate_ssrf_target 拒绝回环/链路本地/云元数据/组播/广播/
     未指定地址、非标准端口、不受支持 db_type；放行合法内网地址与标准端口。
  2) 权限一致性 —— 111 S5 为写端点新增的 require_permission 资源码必须已登记在
     RESOURCE_CATALOG，避免"加了依赖却无资源导致全员 403"。
不连接数据库。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_SNIPPET = r"""
import sys
sys.path.insert(0, r"{BACKEND_DIR}")

from app.services.connection_identity import (
    MAX_CONNECTIVITY_TIMEOUT_MS,
    validate_ssrf_target,
)

# ---- 合法目标 ----
assert validate_ssrf_target("oracle", "10.10.8.216", 1521) == []
assert validate_ssrf_target("postgresql", "10.20.1.153", 5432) == []
assert validate_ssrf_target("mysql", "db.internal.example.com", 3306) == []

# ---- 禁止网段 ----
assert any("禁止" in e for e in validate_ssrf_target("oracle", "127.0.0.1", 1521))
assert any("禁止" in e for e in validate_ssrf_target("oracle", "169.254.169.254", 1521))
assert any("禁止" in e for e in validate_ssrf_target("postgresql", "::1", 5432))
assert any("禁止" in e for e in validate_ssrf_target("mysql", "224.0.0.1", 3306))
assert any("禁止" in e for e in validate_ssrf_target("oracle", "0.0.0.0", 1521))
assert any("禁止" in e for e in validate_ssrf_target("oracle", "255.255.255.255", 1521))

# ---- 非标准端口（协议限制）----
assert any("端口" in e for e in validate_ssrf_target("oracle", "10.10.8.216", 1522))
assert any("端口" in e for e in validate_ssrf_target("mysql", "10.10.8.216", 3307))

# ---- 不受支持 db_type ----
assert any("db_type" in e for e in validate_ssrf_target("redis", "10.10.8.216", 6379))

# ---- 非法主机名 ----
assert any("非法" in e for e in validate_ssrf_target("oracle", "a..b", 1521))
# 整数/十六进制形式的 IP（2130706433==127.0.0.1，0x7f000001 同义）可被驱动解析，
# 必须拒绝，防止绕过回环网段检查。
assert any("非法" in e for e in validate_ssrf_target("oracle", "2130706433", 1521))
assert any("非法" in e for e in validate_ssrf_target("oracle", "0x7f000001", 1521))
assert any("非法" in e for e in validate_ssrf_target("oracle", "0X7F000001", 1521))

# ---- 超时上限 ----
assert MAX_CONNECTIVITY_TIMEOUT_MS == 10000

# ---- 111 S5 写端点权限码已登记 ----
import re
from pathlib import Path
src = Path(r"{BACKEND_DIR}") / "app/api/v1/permissions.py"
cat = src.read_text(encoding="utf-8-sig")
codes = set(re.findall(r'\{"code": "([^"]+)"', cat))
for code in ("asset.relation.review", "metadata.snapshot.collect", "asset.annotation", "source.manage"):
    assert code in codes, f"权限资源未登记: {code}"

print("SECURITY_AUDIT_OK")
"""


def _clean_env() -> dict:
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("APP_") and not k.startswith("PYTEST_")
    }
    return env


def test_ssrf_guard_and_permission_codes():
    env = _clean_env()
    snippet = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "SECURITY_AUDIT_OK" in proc.stdout
