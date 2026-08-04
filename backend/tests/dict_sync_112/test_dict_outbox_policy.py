"""112 A1/A5：outbox worker 纯逻辑策略（不连数据库）。

子进程测试 `dict_sync_worker` 的纯策略函数：
  - 重试退避（指数、封顶）
  - 死信判定（attempt 达 max 即 dead_letter）
  - 状态分类（成功/失败重试/死信）
  - 审批入队幂等键（business_key 稳定、不可重复产生不同键）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_SNIPPET = r"""
import sys
sys.path.insert(0, r"{BACKEND_DIR}")

from app.services.dict_sync_worker import (
    business_key_for_plan,
    business_key_for_batch,
    retry_after_seconds,
    should_dead_letter,
    classify_event,
    MAX_ATTEMPTS,
)

# ---- 业务幂等键稳定 ----
assert business_key_for_plan(12, "HIS_SOURCE") == "plan:12:HIS_SOURCE"
assert business_key_for_plan(12, "JHEMR_VASTBASE") == "plan:12:JHEMR_VASTBASE"
assert business_key_for_batch("VALB-abc", "CDMS") == "batch:VALB-abc:CDMS"

# ---- 退避：base * 2^(attempt-1)，封顶 ----
from app.services.dict_sync_worker import BASE_RETRY_DELAY_SECONDS, MAX_RETRY_DELAY_SECONDS
assert retry_after_seconds(1) == BASE_RETRY_DELAY_SECONDS
assert retry_after_seconds(2) == BASE_RETRY_DELAY_SECONDS * 2
assert retry_after_seconds(3) == BASE_RETRY_DELAY_SECONDS * 4
assert retry_after_seconds(100) <= MAX_RETRY_DELAY_SECONDS

# ---- 死信判定 ----
assert should_dead_letter(1, 3) is False
assert should_dead_letter(2, 3) is False
assert should_dead_letter(3, 3) is True
assert should_dead_letter(0, MAX_ATTEMPTS) is False
assert should_dead_letter(MAX_ATTEMPTS, MAX_ATTEMPTS) is True

# ---- 状态分类 ----
# 成功
s, e = classify_event({"attempt": 2, "max_attempts": 3}, {"ok": True})
assert s == "succeeded" and e is None

# 失败但仍可重试（attempt < max）
s, e = classify_event({"attempt": 2, "max_attempts": 3}, {"ok": False, "error": "boom"})
assert s == "failed" and "boom" in e

# 第 3 次失败 -> dead_letter（attempt==max）
s, e = classify_event({"attempt": 3, "max_attempts": 3}, {"ok": False, "error": "boom"})
assert s == "dead_letter" and "boom" in e

# 未知错误同样被脱敏截断到 400 字符内
s, e = classify_event({"attempt": 1, "max_attempts": 3}, {"ok": False, "error": "x" * 1000})
assert s == "failed" and len(e) <= 400

print("OUTBOX_POLICY_OK")
"""


def test_outbox_policy():
    code = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={_k: _v for _k, _v in __import__("os").environ.items() if not _k.startswith("APP_") and not _k.startswith("PYTEST_")},
    )
    assert "OUTBOX_POLICY_OK" in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr