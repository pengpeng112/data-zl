"""DEF-09（194）：登录失败与限流响应统一 {code,message,data} 信封。

纯逻辑：直接调用响应构造函数，不启动应用、不连数据库。
"""
from __future__ import annotations

import json

from fastapi import Request

from app.api.v1.auth import _auth_error_response
from app.main import _rate_limit_envelope_handler
from app.services.auth_service import AuthError


class _FakeRateLimitError(Exception):
    """模拟 slowapi RateLimitExceeded：携带 detail 与限流头。"""

    def __init__(self, detail: str, headers: dict | None = None):
        super().__init__(detail)
        self.detail = detail
        self.headers = headers or {}


def test_auth_error_response_envelope_keeps_status_and_detail():
    err = AuthError("账号或密码错误", status_code=401)
    resp = _auth_error_response(err)
    assert resp.status_code == 401
    body = json.loads(resp.body)
    assert body["code"] == 401
    assert body["message"] == "账号或密码错误"
    assert body["data"] is None
    # 兼容字段：旧调用方读取 detail
    assert body["detail"] == "账号或密码错误"


def test_auth_error_response_envelope_lock_status():
    err = AuthError("账号已锁定，请联系管理员", status_code=423)
    resp = _auth_error_response(err)
    assert resp.status_code == 423
    body = json.loads(resp.body)
    assert body["code"] == 423
    assert body["detail"] == "账号已锁定，请联系管理员"


def test_rate_limit_handler_envelope_and_headers():
    exc = _FakeRateLimitError(
        "Rate limit exceeded: 5 per 1 minute",
        headers={"Retry-After": "30", "X-RateLimit-Limit": "5"},
    )
    resp = _rate_limit_envelope_handler(request=None, exc=exc)  # type: ignore[arg-type]
    assert resp.status_code == 429
    body = json.loads(resp.body)
    assert body["code"] == 429
    assert body["message"] == "Rate limit exceeded: 5 per 1 minute"
    assert body["data"] is None
    assert body["detail"] == "Rate limit exceeded: 5 per 1 minute"
    # 限流头原样保留
    assert resp.headers["Retry-After"] == "30"
    assert resp.headers["X-RateLimit-Limit"] == "5"


def test_rate_limit_handler_fallback_without_detail():
    exc = Exception("boom")
    resp = _rate_limit_envelope_handler(request=None, exc=exc)  # type: ignore[arg-type]
    assert resp.status_code == 429
    body = json.loads(resp.body)
    assert body["code"] == 429
    assert body["message"] == "请求过于频繁，请稍后再试"
    assert body["detail"] == "请求过于频繁，请稍后再试"


def test_rate_limit_handler_non_string_detail_uses_fallback():
    exc = _FakeRateLimitError(detail=None)  # type: ignore[arg-type]
    resp = _rate_limit_envelope_handler(request=None, exc=exc)  # type: ignore[arg-type]
    body = json.loads(resp.body)
    assert body["message"] == "请求过于频繁，请稍后再试"


def test_request_import_available():
    # 保持 fastapi Request 导入被真实使用路径覆盖（防未用导入告警误判）
    assert Request is not None
