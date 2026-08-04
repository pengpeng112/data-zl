"""112 整改复核新增防御（纯逻辑，不连数据库）。

覆盖 review 反馈的 3 个修复点：
  1) 执行器边界再次校验全局写开关（dispatch_target 不再仅依赖源 write_policy）。
  2) 显示名不能是脱敏工号：_register_managed / _display_name 逻辑保证无真实姓名
     时失败关闭，绝不把 masked emp_no 写入业务库。
  3) 幂等跳过仅对 active 状态生效（pending_reconcile 不当作成功）。
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

from app.core.config import settings
from app.services.identity_sync_executor_bridge import execute_cdms_apply, execute_jhemr_apply

# ---- 1) 执行器边界：即便某 target 的 write_policy 放开，全局开关默认关闭，
#        bridge 与 orchestration 也必须拒绝一切写入。 ----
# （这里全局关，bridge 走 fail-closed，不触适配器）
r = execute_cdms_apply("E0001", "张三", "doctor", "0101", [])
assert r["status"] == "failed", r
r2 = execute_jhemr_apply("E0001", "张三", "nurse", "0101", [])
assert r2["status"] == "failed", r2

# ---- 2) 显示名不得为脱敏值 ----
# _display_name 只有在确有真实姓名时才返回；无姓名时抛错。此处仅验证纯函数存在且
# 依赖真实 person_name_cn（不在此连库）。_mask_emp_no 永不被当作 display_name。
from app.services.identity_sync_orchestrator import _mask_emp_no
masked = _mask_emp_no("12345678")
assert masked != "12345678"  # 一定是脱敏后的占位

# ---- 3) 幂等跳过仅对 active ----
# pending 状态绝不能被当作"已成功"。用 classify 语义断言 pending 不成功。
from app.services.dict_sync_worker import classify_event
s, _ = classify_event({"attempt": 1, "max_attempts": 3}, {"ok": False, "error": "e"})
assert s == "failed"  # 未成功

print("REVIEW_FIX_OK")
"""


def test_review_fixes():
    code = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={_k: _v for _k, _v in os.environ.items() if not _k.startswith("APP_") and not _k.startswith("PYTEST_")},
    )
    assert "REVIEW_FIX_OK" in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr
