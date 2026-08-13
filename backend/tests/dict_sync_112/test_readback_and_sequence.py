"""112 A3 复核修复：写后回读 + sequence 标识符白名单（纯逻辑，不连数据库）。"""
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
from app.services.medical_code_push import (
    validate_sequence_identifier,
    build_readback_select,
    readback_actions_on_conn,
    _whitelisted_serial_sequence,
    _resolve_serial_from_whitelisted_sequence,
)
from app.core.config import settings

# There is intentionally no MAX+1 fallback or runtime strategy switch. Missing
# sequence configuration must remain fail-closed.
import app.services.medical_code_push as medical_code_push

assert not hasattr(medical_code_push, "_resolve_serial_from_locked_max")
assert not hasattr(settings, "jhemr_serial_strategy")

# ---- sequence identifier whitelist ----
assert validate_sequence_identifier("jhemr.serial_seq") == "jhemr.serial_seq"
assert validate_sequence_identifier("SERIAL_SEQ") == "SERIAL_SEQ"
for bad in [
    "",
    "a;drop table x",
    "a b",
    "nextval('x')",
    "a--comment",
    "a/b",
    "a'||pg_sleep(1)--",
    "schema..obj",
]:
    try:
        validate_sequence_identifier(bad)
        raise AssertionError("should reject: " + repr(bad))
    except HTTPException:
        pass

# 默认配置必须为空
settings.jhemr_serial_whitelisted_sequence = ""
assert _whitelisted_serial_sequence() is None

# 危险配置在取号前失败关闭
settings.jhemr_serial_whitelisted_sequence = "evil;drop"
try:
    _whitelisted_serial_sequence()
    raise AssertionError("unsafe sequence config must fail")
except HTTPException:
    pass
settings.jhemr_serial_whitelisted_sequence = ""

# ---- readback SQL builders ----
sql, meta = build_readback_select("COMM.DIAGNOSIS_DICT", dialect="oracle", action_type="insert")
assert "DIAGNOSIS_CODE" in sql and ":code" in sql
assert meta["needs_hospital"] is False
sql_pg, meta_pg = build_readback_select("jhemr.diagnosis_dict", dialect="postgresql", action_type="insert")
assert "%(code)s" in sql_pg and "%(hospital_no)s" in sql_pg
assert meta_pg["needs_hospital"] is True
assert build_readback_select("public.evil", dialect="postgresql", action_type="insert") is None

# ---- same-connection readback fail-closed ----
class FakeCur:
    def __init__(self, rows):
        self._rows = rows
        self.description = [("code",), ("stopped",)]
    def execute(self, sql, params=None):
        self.last = (sql, params)
    def fetchall(self):
        return self._rows
    def fetchone(self):
        return self._rows[0] if self._rows else None
    def close(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

class FakeConn:
    def __init__(self, rows):
        self.rows = rows
    def cursor(self):
        return FakeCur(self.rows)

act = {
    "action_type": "insert",
    "target_table": "jhemr.diagnosis_dict",
    "item_code": "A01",
    "params": {"code": "A01", "hospital_no": "1110002"},
    "meta": {},
}

# 0 行 -> 拒绝成功
try:
    readback_actions_on_conn(FakeConn([]), "postgresql", [act])
    raise AssertionError("0-row readback must fail")
except HTTPException as e:
    assert "0 rows" in str(e.detail)

# 多行 -> conflict
try:
    readback_actions_on_conn(FakeConn([("A01", 0), ("A01", 0)]), "postgresql", [act])
    raise AssertionError("multi-row readback must fail")
except HTTPException as e:
    assert "conflict" in str(e.detail).lower() or "rows" in str(e.detail)

# 停用态不符合 insert 预期
try:
    readback_actions_on_conn(FakeConn([("A01", 1)]), "postgresql", [act])
    raise AssertionError("stopped insert must fail readback")
except HTTPException as e:
    assert "active" in str(e.detail) or "stopped" in str(e.detail)

# 正常 1 行 active
ok = readback_actions_on_conn(FakeConn([("A01", 0)]), "postgresql", [act])
assert ok["ok"] is True and ok["checked"] == 1

# stop 动作要求 stopped=1
stop_act = {
    "action_type": "stop",
    "target_table": "COMM.DIAGNOSIS_DICT",
    "item_code": "A01",
    "params": {"code": "A01"},
    "meta": {},
}
ok2 = readback_actions_on_conn(FakeConn([("A01", 1)]), "oracle", [stop_act])
assert ok2["ok"] is True
try:
    readback_actions_on_conn(FakeConn([("A01", 0)]), "oracle", [stop_act])
    raise AssertionError("stop without stopped=1 must fail")
except HTTPException:
    pass

print("READBACK_SEQUENCE_OK")
"""


def test_readback_and_sequence_guards():
    code = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("APP_") and not k.startswith("PYTEST_")
    }
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(BACKEND_DIR),
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "READBACK_SEQUENCE_OK" in proc.stdout
