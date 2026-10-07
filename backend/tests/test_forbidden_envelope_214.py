"""DEF-01 / 214 E-A2：全站 403 统一信封契约测试。

契约见 开发起步包/output_r214/DEF-01_兼容性清单.md §4：
{code:403, message:"权限不足"(权限拒绝族), data:{"resource_code"}, detail:旧文案镜像, request_id}
仅 403 重塑，其余状态保持 FastAPI 默认 {"detail"} 形。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.core.db import SessionLocal
from app.core.security import PermissionDenied
from app.main import app, unified_403_envelope_handler
from app.models.governance import ApiKey


def _fake_request(request_id: str = "req-envelope-214") -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(request_id=request_id))


def _body(resp) -> dict:
    return json.loads(resp.body)


def test_permission_denied_envelope_shape():
    """require_permission 拒绝：message=权限不足，resource_code 进 data，旧文案镜像进 detail。"""
    resp = asyncio.run(unified_403_envelope_handler(
        _fake_request(), PermissionDenied("dict.medical.view")))
    assert resp.status_code == 403
    body = _body(resp)
    assert body["code"] == 403
    assert body["message"] == "权限不足"
    assert body["data"] == {"resource_code": "dict.medical.view"}
    assert body["detail"] == "缺少权限: dict.medical.view"
    assert body["request_id"] == "req-envelope-214"


def test_plain_403_keeps_message_and_mirrors_detail():
    """其它直接 HTTPException(403)：message 保留原文，detail 同文镜像，data=null。"""
    resp = asyncio.run(unified_403_envelope_handler(
        _fake_request(), HTTPException(status_code=403, detail="CSRF 校验失败")))
    body = _body(resp)
    assert resp.status_code == 403
    assert body["message"] == "CSRF 校验失败"
    assert body["detail"] == "CSRF 校验失败"
    assert body["data"] is None
    assert body["code"] == 403


def test_non_403_delegates_to_fastapi_default_shape():
    """非 403 不重塑：404 保持 FastAPI 默认 {"detail"} 形（兼容面不扩大）。"""
    resp = asyncio.run(unified_403_envelope_handler(
        _fake_request(), HTTPException(status_code=404, detail="not found")))
    assert resp.status_code == 404
    body = _body(resp)
    assert body.get("detail") == "not found"
    assert "message" not in body


def test_non_string_detail_falls_back():
    exc = HTTPException(status_code=403, detail={"reason_code": "x"})
    resp = asyncio.run(unified_403_envelope_handler(_fake_request(), exc))
    body = _body(resp)
    assert body["message"] == "权限不足"
    assert "reason_code" in body["detail"]


def test_endpoint_403_envelope_end_to_end(client: TestClient):
    """端到端：无权限角色调挂码端点 → 统一信封（兼容 209 的 message 断言）。"""
    seeded = client.post("/api/v1/permissions/seed?operator=tester")
    assert seeded.status_code == 200, seeded.text
    token = "test-token-envelope-214-viewer"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_name == "rbac-envelope-214").first()
        if not key:
            db.add(ApiKey(key_name="rbac-envelope-214", token_hash=token_hash,
                          user_identifier="rbac-envelope-214-viewer", enabled=True))
        else:
            key.token_hash = token_hash
            key.user_identifier = "rbac-envelope-214-viewer"
            key.enabled = True
        db.commit()
    finally:
        db.close()
    viewer = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    denied = viewer.get("/api/v1/dict-medical/code-sets?category_code=diagnosis")
    assert denied.status_code == 403
    body = denied.json()
    # 209 DEF-01 全局契约断言（原失败用例的读取方式）
    assert body.get("message") == "权限不足"
    # 214 统一信封全形状
    assert body["code"] == 403
    assert body["data"] == {"resource_code": "dict.medical.view"}
    assert body["detail"] == "缺少权限: dict.medical.view"
    assert isinstance(body.get("request_id"), str) and body["request_id"]
