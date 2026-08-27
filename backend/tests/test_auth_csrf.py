"""B1 回归：CSRF Origin/Referer 必须完整 origin 精确相等。

历史缺陷：`origin.startswith(allowed.rstrip("/"))` 前缀匹配可被
`http://<allowed>.evil.com` 绕过。修法：提取 scheme://host[:port] 后全等比较
（大小写归一、去尾部斜杠）。测试矩阵含"有/无 X-Requested-With"两组用例
（裁决 #23/#24）。
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.auth import _require_csrf


class _CIHeaders(dict):
    """大小写不敏感的 header 映射，模拟 Starlette Request.headers。"""

    def get(self, key, default=None):  # type: ignore[override]
        for k, v in self.items():
            if k.lower() == str(key).lower():
                return v
        return default


class _StubRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = _CIHeaders(headers)


def _check(headers: dict[str, str]) -> None:
    _require_csrf(_StubRequest(headers))


# ── 无 X-Requested-With：origin/referer 校验（真正的 CSRF 面） ──────────────


def test_origin_exact_match_passes():
    # cors_origins 默认含 http://localhost:5173
    _check({"Origin": "http://localhost:5173"})


def test_origin_case_and_trailing_slash_normalized():
    _check({"Origin": "HTTP://LocalHost:5173/"})
    _check({"Origin": "http://LOCALHOST:5173"})


def test_origin_evil_prefix_suffix_blocked():
    """B1 核心回归：startswith 时代该用例会被放行。"""
    with pytest.raises(HTTPException) as exc_info:
        _check({"Origin": "http://localhost:5173.evil.com"})
    assert exc_info.value.status_code == 403


def test_origin_evil_subpath_blocked():
    with pytest.raises(HTTPException):
        _check({"Origin": "http://localhost:5173.evil.com/x"})


def test_origin_unrelated_host_blocked():
    with pytest.raises(HTTPException):
        _check({"Origin": "https://evil.example.com"})


def test_origin_port_mismatch_blocked():
    with pytest.raises(HTTPException):
        _check({"Origin": "http://localhost:5174"})


def test_referer_same_origin_path_passes():
    _check({"Referer": "http://localhost:5173/views/graph/index"})


def test_referer_evil_blocked():
    with pytest.raises(HTTPException):
        _check({"Referer": "http://localhost:5173.evil.com/views/index"})


def test_referer_case_normalized_passes():
    _check({"Referer": "HTTP://LocalHost:5173/"})


# ── 有 X-Requested-With：非 cookie 表单面，直接放行 ────────────────────────


def test_xhr_header_passes_with_evil_origin():
    _check({"X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example.com"})


def test_xhr_header_passes_without_origin():
    _check({"X-Requested-With": "XMLHttpRequest"})


# ── 端到端：login 端点 CSRF 门（在鉴权之前生效） ──────────────────────────


def test_login_evil_origin_rejected_before_auth(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "whatever"},
        headers={"Origin": "http://localhost:5173.evil.com"},
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


def test_login_allowed_origin_passes_csrf_gate(client: TestClient):
    # 通过 CSRF 门后进入鉴权（凭据错误 → 401），不得是 403。
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "whatever"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code != 403
