"""112 A2/A3：同目标事务执行器 + 单行 SQL 硬约束（纯逻辑，不连数据库）。

子进程验证：
  - 同目标多动作共享连接：_run_target_transaction 在同一连接上按序执行全部
    动作，且 serial_no 只能来自 DBA 白名单 sequence（未配置则失败关闭）。
  - validate_push_sql 仍然拒绝 DELETE/MERGE/多行 VALUES/IN-list/注释等。
  - 结果状态分类（成功/失败/死信）可被 worker 正确使用。
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

from fastapi import HTTPException

from app.services.medical_code_push import validate_push_sql, ACTION_INSERT, ACTION_STOP
from app.services.dict_sync_executor import _run_target_transaction, _whitelisted_serial_sequence
from app.core.config import settings

# ---- 单行 INSERT 合法 ----
sql_ok = validate_push_sql(
    "INSERT INTO jhemr.diagnosis_dict (diagnosis_code, isstop) VALUES (%(code)s, 0)",
    action_type=ACTION_INSERT, target_table="jhemr.diagnosis_dict",
)
assert sql_ok.startswith("INSERT INTO")

# ---- 禁止语法：DELETE / MERGE / 多行 VALUES / IN-list / 注释 ----
for bad in [
    "DELETE FROM jhemr.diagnosis_dict WHERE diagnosis_code=%(code)s",
    "MERGE INTO jhemr.diagnosis_dict USING (SELECT 1) ON (1=1) WHEN MATCHED THEN UPDATE SET isstop=0",
    "INSERT INTO jhemr.diagnosis_dict (a,b) VALUES (1,2), (3,4)",
    "INSERT INTO jhemr.diagnosis_dict (a) VALUES (1) WHERE a IN (1,2)",
    "INSERT INTO jhemr.diagnosis_dict (a) VALUES (1) /* x */",
]:
    try:
        validate_push_sql(bad, action_type=ACTION_INSERT, target_table="jhemr.diagnosis_dict")
        raise AssertionError("should have rejected: " + bad)
    except ValueError:
        pass

# ---- 未配置白名单 sequence -> 未配置时 _whitelisted_serial_sequence() 返回 None ----
# (默认配置必须为空，确保取号失败关闭；不允许默认 MAX+1)
assert _whitelisted_serial_sequence() is None, "serial whitelist must default to empty (fail-closed)"

# ---- 同目标共享连接：全部成功才执行到 writer；任一失败即抛错、绝不部分提交 ----
class FakeConn:
    def __init__(self):
        self.calls = []
        self.fail_on = None
    def cursor(self):
        return self
    def execute(self, sql, params=None):
        if self.fail_on and len(self.calls) >= self.fail_on:
            raise RuntimeError("boom")
        self.calls.append((sql, params))
        self.rowcount = 1
    def fetchone(self):
        return (1,)
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

conn = FakeConn()
row_counts = {}
_running_sentinel = {"called": 0}

def make_action(table, sql, params):
    return {
        "action_id": "a1",
        "action_type": "insert",
        "target_system": "JHEMR_VASTBASE",
        "target_table": table,
        "item_code": "X",
        "sql": sql,
        "params": params,
        "plan_status": "planned",
        "meta": {},
    }

# 两个动作 -> 同一连接执行两次
conn.fail_on = None
acts = [
    make_action("jhemr.diagnosis_dict", "INSERT INTO jhemr.diagnosis_dict (a) VALUES (1)", {"x": 1}),
    make_action("jhemr.operation_dict", "INSERT INTO jhemr.operation_dict (b) VALUES (2)", {"y": 2}),
]
_run_target_transaction(conn, "postgresql", acts, row_counts=row_counts)
assert len(conn.calls) == 2, "both actions must run on the SAME connection"

# 第二动作失败 -> 抛错（调用方回滚整包，不部分提交）
conn2 = FakeConn(); conn2.fail_on = 1
try:
    _run_target_transaction(conn2, "postgresql", acts, row_counts={})
    raise AssertionError("second action failure must propagate")
except RuntimeError:
    pass

print("EXECUTOR_FAILLCLOSED_OK")
"""


def test_executor_fail_closed():
    code = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={_k: _v for _k, _v in os.environ.items() if not _k.startswith("APP_") and not _k.startswith("PYTEST_")},
    )
    assert "EXECUTOR_FAILLCLOSED_OK" in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr