"""112 B1/B2：身份同步写入门禁（fail-closed）纯逻辑测试。

子进程验证：
  - 默认配置下 check_write_gates 全红（identity_sync_enabled、密码写、
    CDMS FID 语义确认等全部默认关闭）=> 任何身份写都不会发生。
  - bridge 的 fail-closed 边界：APP_IDENTITY_SYNC_ENABLED=false 时
    execute_cdms_apply / execute_jhemr_apply 直接返回 failed 且不触碰适配器。
  - 分类白名单：非法 classification 拒绝。
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

from app.services.identity_sync_executor_bridge import (
    execute_cdms_apply,
    execute_jhemr_apply,
    _require_identity_sync_enabled,
    _require_password_write_enabled,
    _require_cdms_semantics_confirmed,
)

# ---- fail-closed：全局关闭时 bridge 拒绝一切写入 ----
r = execute_cdms_apply("E0001", "张三", "doctor", "0101", [])
assert r["status"] == "failed" and "fail_closed" in r["error"], r

r2 = execute_jhemr_apply("E0001", "张三", "nurse", "0101", [])
assert r2["status"] == "failed" and "fail_closed" in r2["error"], r2

# 单个 gate 检查函数同样关闭
assert _require_identity_sync_enabled() is not None
assert _require_password_write_enabled() is not None
assert _require_cdms_semantics_confirmed() is not None

# 非法 classification 也必须拒绝（即便 gate 全开——这里全局仍关闭，先拿 fail_closed）
r3 = execute_cdms_apply("E0001", "张三", "evil_role", "0101", [])
assert r3["status"] == "failed", r3

print("IDENTITY_GATES_OK")
"""


def test_identity_write_gates_fail_closed():
    code = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={_k: _v for _k, _v in os.environ.items() if not _k.startswith("APP_") and not _k.startswith("PYTEST_")},
    )
    assert "IDENTITY_GATES_OK" in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr