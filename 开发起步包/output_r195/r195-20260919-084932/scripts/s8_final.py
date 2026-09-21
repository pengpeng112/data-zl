# -*- coding: utf-8 -*-
"""S8 终版：一次性 ApiKey → export-context/resolve 定向回读 8 用例 → 即删。
产物仅含聚合结论与计数，无 token、无患者数据。
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


def call(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {}


def export(token, tables):
    st, j = call("POST", "/api/v1/ai/export-context", token,
                 {"tables": tables, "include_relations": True, "include_columns": False})
    return st, ((j.get("data") or {}))


def main():
    out = {"started_at": datetime.now(timezone.utc).isoformat(), "cases": [], "notes": []}
    db = SessionLocal()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    try:
        key = ApiKey(key_name="verify-r195-readback", token_hash=thash, user_identifier=UID,
                     enabled=True, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
        db.add(key)
        db.flush()
        db.add(AssetUserRole(user_identifier=UID, role_code="platform_admin", status="active"))
        db.commit()
        out["key_id"] = key.id

        def add(cid, desc, st, data, checks):
            out["cases"].append({"case": cid, "desc": desc, "status": st,
                                 "n_tables": len(data.get("tables", [])),
                                 "n_relations": len(data.get("relations", [])),
                                 "checks": checks})

        # P1 住院组合键
        st, d = export(token, ["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"])
        rels = d.get("relations", [])
        add("P1-住院组合键", "PAT_VISIT/PAT_MASTER_INDEX 组合键关系", st, d, {
            "has_combo": any("PATIENT_ID" in (r.get("from_columns") or "") + (r.get("to_columns") or "")
                             for r in rels),
            "rel_samples": [f'{r.get("from")}->{r.get("to")}[{r.get("from_columns")}]' for r in rels[:3]]})

        # P2 检验 TEST_NO
        st, d = export(token, ["HIS.LAB_TEST_MASTER", "HIS.LAB_RESULT"])
        rels = d.get("relations", [])
        add("P2-检验TEST_NO", "LAB_TEST_MASTER/LAB_RESULT 关系", st, d, {
            "has_test_no": any("TEST_NO" in (r.get("from_columns") or "") + (r.get("to_columns") or "") for r in rels),
            "rel_samples": [f'{r.get("from")}->{r.get("to")}' for r in rels[:3]]})

        # P3 手术三键（SM）
        st, d = export(token, ["SM.MED_OPERATION_MASTER"])
        rels = d.get("relations", [])
        add("P3-手术三键", "MED_OPERATION_MASTER 关系", st, d, {
            "has_3key": any(("PATIENT_ID" in (r.get("from_columns") or "") and "VISIT_ID" in (r.get("from_columns") or ""))
                            or ("PATIENT_ID" in (r.get("to_columns") or "") and "VISIT_ID" in (r.get("to_columns") or ""))
                            for r in rels),
            "rel_samples": [f'{r.get("from")}[{r.get("from_columns")}]->{r.get("to")}' for r in rels[:3]]})

        # P4 值域注入（system-context HIS_SOURCE）
        st, j = call("GET", "/api/v1/ai/system-context?system_code=HIS_SOURCE&max_tables=5", token)
        vds = ((j.get("data") or {}).get("value_domains")) or []
        add("P4-字典映射值域", "HIS_SOURCE confirmed 值域注入", st, {"relations": [], "tables": []}, {
            "vd_count": len(vds),
            "has_disposition_trap": any("离院" in str(v.get("note", "")) + str(v.get("meaning", "")) for v in vds)})

        # P5 文书 FILE_UNIQUE_ID
        st, d = export(token, ["JHEMR.JHMR_FILE_INDEX", "JHEMR.JHMR_FILE_CONTENT_TEXT"])
        rels = d.get("relations", [])
        add("P5-文书FILE_UNIQUE_ID", "JHMR 文书索引-内容关系", st, d, {
            "has_fuid": any("FILE_UNIQUE_ID" in (r.get("from_columns") or "") + (r.get("to_columns") or "") for r in rels),
            "rel_samples": [f'{r.get("from")}->{r.get("to")}' for r in rels[:3]]})

        # N1 跨实例同名表隔离：只请求 DATA_CENTER 的 HIS.DEPT_DICT，不得混入 jhemr 系
        st, d = export(token, ["HIS.DEPT_DICT"])
        tabs = [t.get("name") for t in d.get("tables", [])]
        add("N1-跨实例同名表", "DEPT_DICT 按请求精确返回", st, d, {
            "returned_tables": tabs,
            "no_jhemr_mixed": all(not str(t).lower().startswith("jhemr.") for t in tabs)})

        # N2 草稿不混入：r195_intake 只在 reviews；正式关系来源=asset_relations
        st, d = export(token, ["HIS.PAT_VISIT"])
        body_str = json.dumps(d, ensure_ascii=False)
        add("N2-草稿不混入", "r195 草稿不进正式关系导出", st, d, {
            "no_r195_marker": "r195" not in body_str})

        # N3 断崖列不被当正式键：P_INPATIENT_TIMES 不应出现在正式关系的键列
        st, d = export(token, ["MTL.EPR_INPATIENT_DOCINDEX"])
        rels = d.get("relations", [])
        add("N3-断崖列不为键", "P_INPATIENT_TIMES 不作正式键", st, d, {
            "not_used_as_key": not any("P_INPATIENT_TIMES" in (r.get("from_columns") or "") + (r.get("to_columns") or "")
                                       for r in rels)})
    finally:
        db.query(ApiKey).filter(ApiKey.token_hash == thash).delete()
        db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).delete()
        db.add(GovernAuditLog(module="admin", entity_type="api_key", entity_ref="verify-r195-readback",
                              action="delete_one_time_readback",
                              after_data={"note": "S8 回读验收完成即删（一次性；platform_admin 绑定为门禁交集唯一可行项，缺陷已记录）"},
                              operator="ai:r195-intake"))
        db.commit()
        # 残留复核
        left_keys = db.query(ApiKey).filter(ApiKey.key_name.like("verify-r195%")).count()
        left_roles = db.query(AssetUserRole).filter(AssetUserRole.user_identifier == UID).count()
        out["residual_check"] = {"verify_r195_keys": left_keys, "readback_roles": left_roles}
        db.close()
    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
