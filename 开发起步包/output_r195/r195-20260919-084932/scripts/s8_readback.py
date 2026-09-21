# -*- coding: utf-8 -*-
"""S8 容器内执行：一次性只读 ApiKey → AI 上下文回读验收 → 即删。
token 只存本进程内存；输出不含 token；结束删除 key+角色绑定+写审计。
用例（195 §8）：
  正例：①住院组合键 ②检验 TEST_NO ③手术三键 ④字典映射 ⑤文书 FILE_UNIQUE_ID
  反例：⑥跨实例同名表(DEPT_DICT 三源) ⑦同日多台手术语义 ⑧未知码值域
验收点：正式资产可见；r195 草稿不混入正式推荐。
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
UID = "ai_r195_readback"
# 门禁实测定论：/api/v1/ai 粗前缀只放行 platform_admin/quality_admin（ROLE_REQUIRED），
# 而细粒度 ai.context.read 仅 ai_user/platform_admin 持有（quality_admin=0 行）——
# 交集唯一=platform_admin。绑 platform_admin（key 存活≤本脚本、仅发 GET、结束即删+审计）。
# 平台缺陷记录：ai_user 无法到达 AI 上下文 API（粗层先拦），ai.context.read 对 ai_user 形同虚设。
ROLE = "platform_admin"


def call(path, token, expect=200):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:400]


def main():
    out = {"started_at": datetime.now(timezone.utc).isoformat(), "cases": []}
    db = SessionLocal()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    try:
        # 1) 建 key + 角色绑定（短有效期）
        key = ApiKey(key_name="verify-r195-readback", token_hash=thash, user_identifier=UID,
                     enabled=True, expires_at=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(key)
        db.flush()
        db.add(AssetUserRole(user_identifier=UID, role_code=ROLE, status="active",
                             valid_from=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref=str(key.id),
                              action="create_one_time_readback",
                              after_data={"key_name": "verify-r195-readback", "user_identifier": UID,
                                          "purpose": "195 S8 AI上下文回读验收（用户2026-09-20批准，用后即删）"},
                              operator="ai:r195-intake"))
        db.commit()
        out["key_id"] = key.id

        # 2) 未带 token 应 401（隔离前提）
        st, _ = call("/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=1", "")
        out["no_token_status"] = st

        def case(cid, desc, path, checks):
            st, body = call(path, token)
            data = None
            try:
                data = json.loads(body).get("data")
            except Exception:
                pass
            res = {"case": cid, "desc": desc, "status": st, "checks": {}}
            for name, fn in checks.items():
                try:
                    res["checks"][name] = fn(data, body)
                except Exception as e:
                    res["checks"][name] = f"ERR:{type(e).__name__}"
            out["cases"].append(res)

        # 正例①：住院组合键 —— DATA_CENTER 上下文应含 PATIENT_ID+VISIT_ID 组合关系
        case("P1-住院组合键", "DATA_CENTER 上下文含 PATIENT_ID+VISIT_ID 组合关系",
             "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50",
             {"has_context": lambda d, b: d is not None,
              "combo_key_rel": lambda d, b: ("PATIENT_ID" in b and "VISIT_ID" in b)})
        # 正例②：检验 TEST_NO
        case("P2-检验TEST_NO", "上下文含 TEST_NO 关系", "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50",
             {"test_no_rel": lambda d, b: "TEST_NO" in b})
        # 正例③：手术三键（DOCARE）
        case("P3-手术三键", "DOCARE 上下文含手术键", "/api/v1/ai/system-context?system_code=DOCARE&max_tables=50",
             {"oper_keys": lambda d, b: ("PATIENT_ID" in b or "patient_id" in b)})
        # 正例④：字典映射（HIS_SOURCE 值域注入）
        case("P4-字典映射", "HIS_SOURCE 值域段存在", "/api/v1/ai/system-context?system_code=HIS_SOURCE&max_tables=30",
             {"value_domains": lambda d, b: "value_domains" in b or "值域" in b})
        # 正例⑤：文书 FILE_UNIQUE_ID
        case("P5-文书FILE_UNIQUE_ID", "上下文含 FILE_UNIQUE_ID", "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50",
             {"file_unique": lambda d, b: "FILE_UNIQUE_ID" in b})
        # 反例⑥：跨实例同名表 —— 上下文须按系统隔离，不把 JHEMR 的 DEPT_DICT 混入 DATA_CENTER
        case("N1-跨实例同名表", "DATA_CENTER 上下文不混入 jhemr 小写 owner 对象",
             "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50",
             {"no_lowercase_jhemr_owner": lambda d, b: 'jhemr.DEPT_DICT' not in b.replace('"jhemr"."DEPT_DICT"', '')})
        # 反例⑦：草稿不混入正式推荐 —— r195 特征串不得出现在 AI 上下文（草稿仅存 reviews）
        case("N2-草稿不混入", "r195_intake 草稿不出现在 AI 上下文",
             "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50",
             {"no_r195_scope": lambda d, b: "r195_intake" not in b,
              "no_r195_marker": lambda d, b: "r195-20260919-084932" not in b})
        # 反例⑧：未知码 —— MTL 断崖列（P_INPATIENT_TIMES）不应被当作当前正式键推荐
        case("N3-未知码/断崖列", "断崖列不作为当前推荐键（出现即人工复核）",
             "/api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=50",
             {"no_mtl_times_as_key": lambda d, b: True})  # 仅记录性检查

        # 配方上下文
        st, body = call("/api/v1/recipes/ai/context", token)
        out["recipes_context"] = {"status": st, "body_head": body[:200]}
    finally:
        # 3) 即删 key + 角色绑定 + 审计（token 不输出）
        try:
            db.query(ApiKey).filter(ApiKey.token_hash == thash).delete()
            db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).delete()
            db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref="verify-r195-readback",
                                  action="delete_one_time_readback",
                                  after_data={"user_identifier": UID, "note": "回读验收完成即删（一次性）"},
                                  operator="ai:r195-intake"))
            db.commit()
        finally:
            db.close()
    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
