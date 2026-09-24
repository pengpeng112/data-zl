# -*- coding: utf-8 -*-
"""r203 回读 A4 复测：连续两次 system-context 调用，逐字比较 relations 原始数组顺序。"""
import hashlib
import json
import secrets
import urllib.request
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole, GovernAuditLog

BASE = "http://127.0.0.1:8000"
UID = "ai_r203_readback_a4"
ROLE = "ai_user"


def call(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:300]


def main():
    out = {}
    db = SessionLocal()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    try:
        key = ApiKey(key_name="verify-r203-a4", token_hash=thash, user_identifier=UID,
                     enabled=True, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add(key)
        db.flush()
        db.add(AssetUserRole(user_identifier=UID, role_code=ROLE, status="active",
                             valid_from=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref=str(key.id),
                              action="create_one_time_readback",
                              after_data={"key_name": "verify-r203-a4", "purpose": "A4 确定性排序复测（即删）"},
                              operator="ai:r203-release"))
        db.commit()
        path = "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=20&max_relations=10"
        bodies = []
        for i in range(3):
            st, b = call(path, token)
            bodies.append((st, b))
        out["statuses"] = [s for s, _ in bodies]
        # 逐字比较整个响应体（同参调用应逐字一致）
        out["body_identical_1_2"] = bodies[0][1] == bodies[1][1]
        out["body_identical_1_3"] = bodies[0][1] == bodies[2][1]
        # relations 位置探查
        d = json.loads(bodies[0][1]).get("data") or {}
        out["data_keys"] = list(d.keys())
        def find_rels(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "relations" and isinstance(v, list):
                        yield path + "/" + k, v
                    else:
                        yield from find_rels(v, path + "/" + k)
        rels = list(find_rels(d))
        out["relations_locations"] = [(p, len(v)) for p, v in rels]
        for p, v in rels[:2]:
            out.setdefault("first_items_keys", []).append([list(x.keys())[:8] if isinstance(x, dict) else str(x)[:50] for x in v[:2]])
    finally:
        try:
            db.query(ApiKey).filter(ApiKey.token_hash == thash).delete()
            db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).delete()
            db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref="verify-r203-a4",
                                  action="delete_one_time_readback",
                                  after_data={"note": "A4 复测完成即删"},
                                  operator="ai:r203-release"))
            db.commit()
        finally:
            db.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
