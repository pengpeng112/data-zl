# -*- coding: utf-8 -*-
"""r203 前端候选 B 发布回读：page_size 边界 API 抽查（一次性 ApiKey，即删）。
验证 PushWizard 两码拉取的后端契约：page_size=200 可用（修复后向导有码可选）、500 超上限 422。"""
import hashlib
import json
import secrets
import urllib.request
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole, GovernAuditLog

BASE = "http://127.0.0.1:8000"
UID = "ai_r203_readback_b"
ROLE = "platform_admin"  # dict 域只读端点抽查，平台管理员；同 195 S8 先例


def call(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:200]


def main():
    out = {}
    db = SessionLocal()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    try:
        key = ApiKey(key_name="verify-r203-pushwizard", token_hash=thash, user_identifier=UID,
                     enabled=True, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add(key)
        db.flush()
        db.add(AssetUserRole(user_identifier=UID, role_code=ROLE, status="active",
                             valid_from=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref=str(key.id),
                              action="create_one_time_readback",
                              after_data={"key_name": "verify-r203-pushwizard",
                                          "purpose": "r203 前端发布回读 page_size 边界抽查（即删）"},
                              operator="ai:r203-release"))
        db.commit()
        cs = "/api/v1/dict-medical/code-sets/diagnosis_local_clinical/items"
        for ps, tag in ((200, "in_limit"), (500, "over_limit")):
            st, body = call(f"{cs}?status=active&page_size={ps}&page=1", token)
            item = {"expect": (200 if ps == 200 else 422), "status": st}
            try:
                d = json.loads(body)
                dd = d.get("data") or {}
                item["items_len"] = len(dd.get("items", [])) if isinstance(dd, dict) else None
                item["total"] = dd.get("total") if isinstance(dd, dict) else None
            except Exception:
                item["body_head"] = body[:100]
            out[f"items_ps{ps}"] = item
    finally:
        try:
            db.query(ApiKey).filter(ApiKey.token_hash == thash).delete()
            db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).delete()
            db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref="verify-r203-pushwizard",
                                  action="delete_one_time_readback",
                                  after_data={"note": "PushWizard 回读抽查完成即删"},
                                  operator="ai:r203-release"))
            db.commit()
        finally:
            db.close()
    db2 = SessionLocal()
    try:
        out["residual_keys"] = db2.query(ApiKey).filter(ApiKey.token_hash == thash).count()
    finally:
        db2.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
