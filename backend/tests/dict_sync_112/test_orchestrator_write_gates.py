"""112 B1：编排器写入门禁默认全红（fail-closed）纯逻辑测试。

子进程验证 check_write_gates 在默认配置下 all_passed=False，且
blocked_gates 列表完整；保证任何未人工确认的配置都无法触发业务库写入。
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

from app.services.identity_sync_orchestrator import check_write_gates

# 默认配置：所有写开关必须为关（fail-closed）
g = check_write_gates(None)  # 纯配置检查，不依赖 db session
assert g["all_passed"] is False, "default config must NOT pass write gates"

by_name = {x["gate"]: x["passed"] for x in g["gates"]}
# 关键 gate 必须存在且默认关闭
for required in [
    "identity_sync_enabled",
    "password_write_enabled",
    "cdms_fid_semantics_confirmed",
    "no_delete_actions",
]:
    assert required in by_name, f"missing gate {required}"
assert by_name["identity_sync_enabled"] is False
assert by_name["password_write_enabled"] is False
assert by_name["cdms_fid_semantics_confirmed"] is False
assert by_name["no_delete_actions"] is True  # 代码永不发 DELETE

print("ORCH_GATES_OK")
"""


def test_orchestrator_gates_default_fail_closed():
    code = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={_k: _v for _k, _v in os.environ.items() if not _k.startswith("APP_") and not _k.startswith("PYTEST_")},
    )
    assert "ORCH_GATES_OK" in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr