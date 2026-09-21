# -*- coding: utf-8 -*-
"""S8b：结构探查（一次性 key，同款创建/即删）。看 system-context 响应结构与关系段形状。"""
import hashlib
import json
import secrets
import urllib.request
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole, GovernAuditLog

BASE = "http://127.0.0.1:8000"
UID = "ai_r195_inspect"


def call(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def main():
    db = SessionLocal()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    try:
        key = ApiKey(key_name="verify-r195-inspect", token_hash=thash, user_identifier=UID,
                     enabled=True, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
        db.add(key)
        db.flush()
        db.add(AssetUserRole(user_identifier=UID, role_code="platform_admin", status="active"))
        db.commit()
        d = call("/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50", token)
        data = d.get("data") or {}
        print("top keys:", list(data.keys()))
        for k, v in data.items():
            if isinstance(v, list):
                print(f"  {k}: list[{len(v)}]", json.dumps(v[0], ensure_ascii=False)[:300] if v else "")
            elif isinstance(v, dict):
                print(f"  {k}: dict keys={list(v.keys())[:10]}")
            else:
                print(f"  {k}:", str(v)[:100])
        # relations/value_domains 段深挖
        rel = data.get("relations") or data.get("key_relations") or []
        if rel:
            print("relation sample:", json.dumps(rel[:3], ensure_ascii=False)[:600])
        tabs = data.get("tables") or []
        if tabs:
            names = [t.get("table_name") or t.get("name") for t in tabs[:60]]
            print("tables returned:", names[:40])
        hv = call("/api/v1/ai/system-context?system_code=HIS_SOURCE&max_tables=5", token).get("data") or {}
        print("HIS_SOURCE keys:", list(hv.keys()))
        vd = hv.get("value_domains") or []
        print("value_domains[0:2]:", json.dumps(vd[:2], ensure_ascii=False)[:400])
    finally:
        db.query(ApiKey).filter(ApiKey.token_hash == thash).delete()
        db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).delete()
        db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref="verify-r195-inspect",
                              action="delete_one_time_readback", operator="ai:r195-intake"))
        db.commit()
        db.close()
    print("done")


if __name__ == "__main__":
    main()
