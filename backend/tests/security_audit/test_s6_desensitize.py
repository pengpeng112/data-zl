"""111 号 S6：异常与审计脱敏。

子进程纯逻辑测试：
  1) sanitize_text 剥离连接串/密码/Token，返回长度受限文本；
  2) api_error_message 对任意异常返回通用消息，绝不回显 str(exc)；
  3) generic_exception_handler 响应携带 request_id 与通用消息，错误细节只在服务端。
不连接数据库。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_SNIPPET = r"""
import sys, asyncio, json
sys.path.insert(0, r"{BACKEND_DIR}")

from app.services.data_masking import api_error_message, sanitize_text

# 1) 脱敏：连接串 / 密码 / Token
out = sanitize_text("conn user=u password=secret123")
assert "secret123" not in out
assert "Bearer abc.def.ghi" not in sanitize_text("Authorization: Bearer abc.def.ghi")
long = sanitize_text("e" * 5000)
assert len(long) <= 250
assert ".replace(" not in long

# 2) 通用错误消息，不回显 str(exc)
err = Exception("connection 10.0.0.1 mypassword=abc123")
msg = api_error_message(err)
assert "abc123" not in msg
assert str(err) != msg

# 3) handler 用 request_id + 通用消息
from starlette.requests import Request as SRequest
from app.core.exceptions import generic_exception_handler

_SCOPE = {
    "type": "http", "method": "GET", "path": "/api/x", "raw_path": "/api/x",
    "headers": [], "query_string": b"", "asgi": {"version": "3.0"},
    "app": None, "client": ("127.0.0.1", 1), "server": ("t", 80), "scheme": "http",
}

async def run():
    req = SRequest(dict(_SCOPE))
    req.state.request_id = "rid1234"
    resp = await generic_exception_handler(req, RuntimeError("leak pwd=ssss"))
    body = json.loads(resp.body.decode())
    assert body["request_id"] == "rid1234"
    assert body["message"] and "pwd" not in body["message"] and "ssss" not in body["message"]
    return resp

resp = asyncio.run(run())
print("SECURITY_S6_OK")
"""


def _clean_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("APP_") and not k.startswith("PYTEST_")}


def test_s6_exception_and_audit_desensitization():
    env = _clean_env()
    snippet = _SNIPPET.replace("{BACKEND_DIR}", str(BACKEND_DIR))
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True, text=True, env=env, cwd=str(BACKEND_DIR), timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "SECURITY_S6_OK" in proc.stdout