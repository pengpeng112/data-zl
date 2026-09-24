# -*- coding: utf-8 -*-
"""r203 发布专项回读（候选 A）：一次性 ai_user 身份 → AI 路由/契约验证 → 即删。
沿用 195 S8 先例模式（用户批准过同型一次性 ApiKey；本次属 203 §21 条件式发布的
『AI 路由、权限、system-context 生产回读』环节）。token 只存本进程内存，输出不含 token。
用例：
  A1 无 token system-context = 401
  A2 ai_user system-context = 200 且含 exported_relations/total_relations/matched_via（缺陷2 契约）
  A3 ai_user /api/v1/ai/sessions = 403（粗门禁未放宽——未挂码路由仍拦截）
  A4 两次调用 relations 顺序一致（确定性排序）
  A5 ai_user /api/v1/ai/export-context = 200（豁免名单内路径，挂码可达）
"""
import hashlib
import json
import secrets
import urllib.request
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole, GovernAuditLog

BASE = "http://127.0.0.1:8000"
UID = "ai_r203_readback"
ROLE = "ai_user"  # 候选A修复目标角色：修复前粗门禁先拦（195 S8 实测），修复后应可达


def call(path, token, expect=None):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:400]


def main():
    out = {"started_at": datetime.now(timezone.utc).isoformat(), "cases": []}
    db = SessionLocal()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    try:
        key = ApiKey(key_name="verify-r203-release", token_hash=thash, user_identifier=UID,
                     enabled=True, expires_at=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(key)
        db.flush()
        db.add(AssetUserRole(user_identifier=UID, role_code=ROLE, status="active",
                             valid_from=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref=str(key.id),
                              action="create_one_time_readback",
                              after_data={"key_name": "verify-r203-release", "user_identifier": UID,
                                          "role": ROLE,
                                          "purpose": "r203 发布回读：ai_user 可达性+system-context 契约（203 §21 授权，用后即删）"},
                              operator="ai:r203-release"))
        db.commit()
        out["key_id"] = key.id

        # A1 无 token
        st, _ = call("/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=5", "")
        out["A1_no_token"] = {"expect": 401, "status": st}

        # A2 system-context 契约
        st, body = call("/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=20&max_relations=10", token)
        a2 = {"expect": 200, "status": st}
        try:
            d = json.loads(body).get("data") or {}
            a2["has_exported_relations"] = "exported_relations" in json.dumps(d)
            a2["has_total_relations"] = "total_relations" in json.dumps(d)
            a2["has_matched_via"] = "matched_via" in json.dumps(d)
            out["_rel_sig_1"] = json.dumps(d.get("relations", d.get("context", {}).get("relations", [])),
                                           ensure_ascii=False, sort_keys=True)[:2000]
        except Exception as e:
            a2["parse"] = f"ERR:{type(e).__name__}"
        out["A2_system_context"] = a2

        # A3 sessions（未挂码路由，粗门禁保持拦截 ai_user）
        st, body3 = call("/api/v1/ai/sessions", token)
        out["A3_sessions"] = {"expect": 403, "status": st, "body_head": body3[:120]}

        # A4 确定性排序：同参两次调用 relations 序列一致
        st4, body4 = call("/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=20&max_relations=10", token)
        try:
            d4 = json.loads(body4).get("data") or {}
            sig2 = json.dumps(d4.get("relations", d4.get("context", {}).get("relations", [])),
                              ensure_ascii=False, sort_keys=True)[:2000]
            out["A4_deterministic"] = {"status": st4,
                                       "consistent": (sig2 == out.get("_rel_sig_1", "") and st == 200)}
        except Exception as e:
            out["A4_deterministic"] = {"parse": f"ERR:{type(e).__name__}"}
        out.pop("_rel_sig_1", None)

        # A5 export-context（豁免名单内、挂码路由）
        st5, _ = call("/api/v1/ai/export-context?system_code=DATA_CENTER", token)
        out["A5_export_context"] = {"expect": 200, "status": st5}
    finally:
        try:
            db.query(ApiKey).filter(ApiKey.token_hash == thash).delete()
            db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).delete()
            db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref="verify-r203-release",
                                  action="delete_one_time_readback",
                                  after_data={"user_identifier": UID, "note": "r203 发布回读完成即删（一次性）"},
                                  operator="ai:r203-release"))
            db.commit()
        finally:
            db.close()
    # 残留复核
    db2 = SessionLocal()
    try:
        out["residual_keys"] = db2.query(ApiKey).filter(ApiKey.token_hash == thash).count()
        out["residual_roles"] = db2.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).count()
    finally:
        db2.close()
    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
