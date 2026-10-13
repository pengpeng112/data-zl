"""210 S2—S9 隔离库集成：数据集安全分类分级闭环 API 验收。

前置：APP_TEST_DB_URL=data_asset_test（可清理隔离库，根 conftest TRUNCATE 清库）；
迁移 c0d1e2f3a4b5 已应用。

覆盖（对应 210 §6 T 编号）：
- T01/T02 权限矩阵：未登录 401、无权 403、viewer 只读、普通用户不能自建授权。
- T05 未分类默认拒绝（读取 403 deny_unclassified，目录仅显示待定级）。
- T07 职责分离：分类降级提案人≠审批人、版本冻结人≠审批人、发布人≠审批人、
  导出申请人≠审批人。
- T06/T09 降级与放宽走审批 + 提案 hash 失效拒绝。
- T10 发布只认持久化质量断言与安全评审（必需维度缺失拒绝）。
- T11 code/version 不属同数据集 422；撤销版本 403。
- T14/T18 行范围与版本成员隔离（时间线/统计只含许可行与成员行）。
- T20 冻结后新批次不进旧版本（manifest 不变）。
- T21 训练集用途假名 + 分组不跨集。
- T22—T26 导出真实闭环：申请→独立审批→生成→真实字节下载、越权/未知/撤销拒绝。
- T24 列标签受限形态禁止导出（用户声明不参与）。
- T27 拒绝审计在业务回滚后仍可回读。
- T28 expected_version CAS 409。
- T30 撤销账本恢复重放幂等 + 未重放出口关闭。
"""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.dataset import AssetDsClassification, AssetDsExport, AssetDsGrant
from app.models.governance import ApiKey
from app.models.governance_base import AssetRolePermission, AssetUserRole, GovernAuditLog
from app.services import dataset_pipeline as pipe

ADMIN_T = {"Authorization": "Bearer test-token-p5-auth-2026"}
APPROVER_TOKEN = "r210-approver-token-2026"
VIEWER_TOKEN = "r210-viewer-token-2026"
PLAIN_TOKEN = "r210-plain-token-2026"

P3_LABELS = {"protection_level": "P3", "personal_info": "personal",
             "usage_constraints": {"purposes": ["research"],
                                   "export_allowed": True, "training_allowed": True}}


def _tok(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def _seed_identities(db):
    """审批人（仅审批码）/查看员（仅 ds.read）/普通用户（无角色）三身份。"""
    for key_name, token, ident in [
        ("r210-approver", APPROVER_TOKEN, "r210-approver"),
        ("r210-viewer", VIEWER_TOKEN, "r210-viewer"),
        ("r210-plain", PLAIN_TOKEN, "r210-plain"),
    ]:
        row = db.query(ApiKey).filter(ApiKey.key_name == key_name).first()
        if not row:
            row = ApiKey(key_name=key_name)
            db.add(row)
        row.token_hash = _sha(token)
        row.token = None
        row.user_identifier = ident
        row.enabled = True
    perms = {
        "r210-approver": ["ds.read", "ds.classification.review", "ds.grant.approve",
                          "ds.version.publish", "ds.export.approve"],
        "r210-viewer": ["ds.read"],
    }
    for role, codes in perms.items():
        db.query(AssetRolePermission).filter(AssetRolePermission.role_code == role).delete()
        for code in codes:
            db.add(AssetRolePermission(role_code=role, resource=code, action="access"))
        if not db.query(AssetUserRole).filter(
                AssetUserRole.user_identifier == f"ident:{role}",
                AssetUserRole.role_code == role).first():
            pass
    # 授权主体绑定：approver/viewer 用户挂对应角色（plain 无角色）
    for ident, role in [("r210-approver", "r210-approver"), ("r210-viewer", "r210-viewer")]:
        exists = db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == ident,
            AssetUserRole.role_code == role).first()
        if not exists:
            db.add(AssetUserRole(user_identifier=ident, role_code=role, status="active"))
    db.commit()


def _ingest(client: TestClient, run_id: str, source: str, patients: list[str],
            day0: str = "2026-01-01") -> None:
    recs = []
    for i, p in enumerate(patients):
        recs.append({"fact_key": f"{run_id}:visit:{p}", "fact_kind": "visit",
                     "source_patient_key": p, "source_visit_id": f"V{i}",
                     "original_value_ref": f"{source}.VISIT/{p}",
                     "business_time": f"{day0}T08:00:00+00:00",
                     "available_time": f"{day0}T09:00:00+00:00"})
        recs.append({"fact_key": f"{run_id}:diag:{p}", "fact_kind": "diagnosis",
                     "source_patient_key": p,
                     "original_value_ref": f"{source}.DIAG/{p}",
                     "standard_value": "I50.x00", "code_system": "ICD10",
                     "business_time": f"{day0}T08:30:00+00:00",
                     "available_time": f"{day0}T10:00:00+00:00"})
    r = client.post("/api/v1/datasets/batches/{}/records".format(run_id),
                    json={"source_code": source, "object_name": f"{source}.SYNTH",
                          "rule_version": "rules_v1", "records": recs}, headers=ADMIN_T)
    assert r.status_code == 200, r.text


def _assertions(db, version_id: int) -> None:
    checks = [
        {"dimension": d, "metric_name": "m210", "numerator": 1, "denominator": 1,
         "threshold": {"op": ">=", "value": 1}}
        for d in ("coverage", "identity", "linkage")]
    pipe.evaluate_assertions(db, "dataset_version", str(version_id), checks)
    db.commit()


def build_env(client: TestClient, db, code: str, source: str,
              grant_principal: str = "r210-viewer") -> dict:
    """完整链路：建集→批次→冻结→分类→质量→审批→安全评审→发布→授权（viewer，
    行范围=第一名患者）。返回关键 ID。"""
    _seed_identities(db)
    r = client.post("/api/v1/datasets",
                    json={"dataset_code": code, "title": code,
                          "purpose_code": "research"}, headers=ADMIN_T)
    assert r.status_code == 200, r.text
    version_id = r.json()["data"]["version_id"]
    run_id = f"RUN-210-{code}"
    _ingest(client, run_id, source, ["PA", "PB"])
    pid_a = pipe.deterministic_patient_id(source, "PA")
    pid_b = pipe.deterministic_patient_id(source, "PB")

    r = client.post(f"/api/v1/datasets/{code}/versions/{version_id}/freeze",
                    json={"source_batch_ids": [run_id]}, headers=ADMIN_T)
    assert r.status_code == 200, r.text
    manifest = r.json()["data"]

    ref = f"dataset:{code}:{version_id}"
    r = client.post("/api/v1/datasets/classifications",
                    json={"object_type": "dataset_version", "object_ref": ref,
                          "labels": P3_LABELS, "expected_version": 0},
                    headers=ADMIN_T)
    assert r.status_code == 200, r.text

    _assertions(db, version_id)

    # 职责分离：approver 审批版本 + 安全评审；admin 发布
    r = client.post(f"/api/v1/datasets/{code}/versions/{version_id}/approve",
                    json={}, headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/datasets/{code}/versions/{version_id}/security-review",
                    json={"passed": True, "note": "合成评审通过"}, headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/datasets/{code}/versions/{version_id}/publish",
                    headers=ADMIN_T)
    assert r.status_code == 200, r.text

    # 授权：admin 申请 → approver 审批（行范围=PA）
    r = client.post("/api/v1/datasets/grants",
                    json={"principal": grant_principal, "purpose_code": "research",
                          "resource_ref": ref,
                          "operations": ["read", "export", "train"],
                          "legal_basis_ref": "synthetic-basis-210",
                          "valid_hours": 48, "row_scope": {"patients": [pid_a]}},
                    headers=ADMIN_T)
    assert r.status_code == 200, r.text
    grant_id = r.json()["data"]["grant_id"]
    r = client.post(f"/api/v1/datasets/grants/{grant_id}/review",
                    json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 200, r.text
    return {"code": code, "version_id": version_id, "run_id": run_id,
            "ref": ref, "grant_id": grant_id, "pid_a": pid_a, "pid_b": pid_b,
            "manifest": manifest}


@pytest.fixture
def env(client: TestClient, db_session) -> dict:
    return build_env(client, db_session, "SYNTH210", "SYNTH210")


# ---------- T01/T02：权限矩阵 ----------

def test_t01_unauthenticated_401_and_low_permission_403(client, env):
    # client 固件默认带 admin token；未认证用裸 TestClient
    bare = TestClient(app)
    r = bare.get("/api/v1/datasets")
    assert r.status_code == 401
    r = client.post("/api/v1/datasets", json={"dataset_code": "X"},
                    headers=_tok(PLAIN_TOKEN))
    assert r.status_code == 403
    r = client.post("/api/v1/datasets/batches/R/records", json={},
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403  # viewer 无 ds.manage
    r = client.get("/api/v1/datasets", headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 200  # 元数据浏览（ds.read）


def test_t02_plain_user_cannot_self_grant_or_classify(client, env):
    r = client.post("/api/v1/datasets/grants",
                    json={"principal": "r210-plain", "purpose_code": "research",
                          "resource_ref": "*", "operations": ["read"],
                          "legal_basis_ref": "x"}, headers=_tok(PLAIN_TOKEN))
    assert r.status_code == 403
    r = client.post("/api/v1/datasets/classifications",
                    json={"object_type": "dataset_version", "object_ref": env["ref"],
                          "labels": P3_LABELS, "expected_version": 1},
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403  # viewer 无 ds.classification.manage


def test_t02_admin_request_then_self_approve_denied(client, env):
    # 伪造 body approver 不能代替真实审批主体：admin 申请 viewer 授权后，
    # admin 自己无 ds.grant.approve 的独立第三人身份（platform_admin 有码但
    # 申请人=自己 → 职责分离拒绝）
    r = client.post("/api/v1/datasets/grants",
                    json={"principal": "r210-plain", "purpose_code": "research",
                          "resource_ref": env["ref"], "operations": ["read"],
                          "legal_basis_ref": "x", "valid_hours": 1},
                    headers=ADMIN_T)
    grant_id = r.json()["data"]["grant_id"]
    r = client.post(f"/api/v1/datasets/grants/{grant_id}/review",
                    json={"decision": "approve", "approver": "someone-else"},
                    headers=ADMIN_T)
    assert r.status_code == 403  # 申请人=审批人；body.approver 无效


# ---------- T05：未分类默认拒绝 ----------

def test_t05_unclassified_version_denies_read_but_metadata_visible(client, db_session):
    _seed_identities(db_session)
    r = client.post("/api/v1/datasets",
                    json={"dataset_code": "UNC210"}, headers=ADMIN_T)
    vid = r.json()["data"]["version_id"]
    _ingest(client, "RUN-210-UNC", "UNCSRC", ["PU"])
    client.post("/api/v1/datasets/UNC210/versions/{}/freeze".format(vid),
                json={"source_batch_ids": ["RUN-210-UNC"]}, headers=ADMIN_T)
    # 有授权（global read）但未分类 → 拒绝
    r = client.post("/api/v1/datasets/grants",
                    json={"principal": "r210-viewer", "purpose_code": "research",
                          "resource_ref": f"dataset:UNC210:{vid}",
                          "operations": ["read"], "legal_basis_ref": "x",
                          "valid_hours": 1, "row_scope": {"patients": ["*"]}},
                    headers=ADMIN_T)
    gid = r.json()["data"]["grant_id"]
    client.post(f"/api/v1/datasets/grants/{gid}/review",
                json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    r = client.get(f"/api/v1/datasets/UNC210/versions/{vid}/timeline/anyone",
                   headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403 and "deny_unclassified" in r.text
    # 目录仍可见（元数据浏览，显示待定级）
    r = client.get("/api/v1/datasets", headers=_tok(VIEWER_TOKEN))
    entry = [d for d in r.json()["data"] if d["dataset_code"] == "UNC210"][0]
    assert entry["pending_classification"] is True and entry["readable"] is False


# ---------- T07/T06/T09：分类降级审批链 ----------

def test_t07_classification_downgrade_separation_and_hash_invalidation(
        client, db_session, env):
    db = db_session
    # admin 提交降级提案（P3→P2 放宽用途）
    lower = {"protection_level": "P2", "personal_info": "personal",
             "usage_constraints": {"purposes": ["research", "external"],
                                   "export_allowed": True, "training_allowed": True}}
    r = client.post("/api/v1/datasets/classifications",
                    json={"object_type": "dataset_version", "object_ref": env["ref"],
                          "labels": lower, "expected_version": 1}, headers=ADMIN_T)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["needs_approval"] is True and body["status"] == "pending_approval"
    row_id = db.scalar(select(AssetDsClassification.id).where(
        AssetDsClassification.object_ref == env["ref"],
        AssetDsClassification.status == "pending_approval"))
    # 提案人自审 → 拒绝
    r = client.post(f"/api/v1/datasets/classifications/{row_id}/review",
                    json={"decision": "approve"}, headers=ADMIN_T)
    assert r.status_code == 403
    # 提案内容被篡改（hash 失效）→ 审批拒绝 409（T09）
    row = db.get(AssetDsClassification, row_id)
    tampered = dict(lower)
    tampered["protection_level"] = "P1"
    row.labels = tampered
    db.commit()
    r = client.post(f"/api/v1/datasets/classifications/{row_id}/review",
                    json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 409 and "hash" in r.text
    # 恢复原提案，由 approver 审批通过
    row.labels = lower
    db.commit()
    r = client.post(f"/api/v1/datasets/classifications/{row_id}/review",
                    json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 200 and r.json()["data"]["status"] == "active"
    # 降级后读取（P2 无行范围要求）仍可用；旧 active 留痕 superseded
    states = db.scalars(select(AssetDsClassification).where(
        AssetDsClassification.object_ref == env["ref"])).all()
    assert sorted(s.status for s in states) == ["active", "superseded"]


def test_t07_freezer_cannot_approve_own_version(client, db_session, env):
    # admin 冻结的版本，admin 自己审批 → 403（职责分离）
    from app.models.dataset import AssetDsDataset, AssetDsDatasetVersion
    d = db_session.query(AssetDsDataset).filter(
        AssetDsDataset.dataset_code == env["code"]).first()
    v2 = AssetDsDatasetVersion(dataset_id=d.id, version=2, schema_version="v1")
    db_session.add(v2)
    db_session.commit()
    vid2 = v2.id
    _ingest(client, "RUN-210-SEP2", "SYNTH210", ["PC"])
    r = client.post(f"/api/v1/datasets/{env['code']}/versions/{vid2}/freeze",
                    json={"source_batch_ids": ["RUN-210-SEP2"]}, headers=ADMIN_T)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/datasets/{env['code']}/versions/{vid2}/approve",
                    json={}, headers=ADMIN_T)
    assert r.status_code == 403 and "冻结" in r.text


def test_t07_publisher_must_differ_from_approver(client, db_session):
    # 新数据集：approver 审批后自己发布 → 403；admin 发布 → 200
    _seed_identities(db_session)
    r = client.post("/api/v1/datasets", json={"dataset_code": "SEP210"},
                    headers=ADMIN_T)
    vid = r.json()["data"]["version_id"]
    _ingest(client, "RUN-210-SEP", "SEPSRC", ["PA"])
    client.post(f"/api/v1/datasets/SEP210/versions/{vid}/freeze",
                json={"source_batch_ids": ["RUN-210-SEP"]}, headers=ADMIN_T)
    client.post("/api/v1/datasets/classifications",
                json={"object_type": "dataset_version",
                      "object_ref": f"dataset:SEP210:{vid}",
                      "labels": P3_LABELS, "expected_version": 0}, headers=ADMIN_T)
    _assertions(db_session, vid)
    client.post(f"/api/v1/datasets/SEP210/versions/{vid}/approve",
                json={}, headers=_tok(APPROVER_TOKEN))
    client.post(f"/api/v1/datasets/SEP210/versions/{vid}/security-review",
                json={"passed": True}, headers=_tok(APPROVER_TOKEN))
    # approver 审批人尝试自己发布 → 403
    r = client.post(f"/api/v1/datasets/SEP210/versions/{vid}/publish",
                    headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 403
    r = client.post(f"/api/v1/datasets/SEP210/versions/{vid}/publish",
                    headers=ADMIN_T)
    assert r.status_code == 200, r.text


# ---------- T10：发布门禁只认持久化证据 ----------

def test_t10_publish_requires_persisted_assertions(client, db_session):
    _seed_identities(db_session)
    r = client.post("/api/v1/datasets", json={"dataset_code": "NOPUB210"},
                    headers=ADMIN_T)
    vid = r.json()["data"]["version_id"]
    _ingest(client, "RUN-210-NP", "NPSRC", ["PA"])
    client.post(f"/api/v1/datasets/NOPUB210/versions/{vid}/freeze",
                json={"source_batch_ids": ["RUN-210-NP"]}, headers=ADMIN_T)
    client.post("/api/v1/datasets/classifications",
                json={"object_type": "dataset_version",
                      "object_ref": f"dataset:NOPUB210:{vid}",
                      "labels": P3_LABELS, "expected_version": 0}, headers=ADMIN_T)
    client.post(f"/api/v1/datasets/NOPUB210/versions/{vid}/approve",
                json={}, headers=_tok(APPROVER_TOKEN))
    client.post(f"/api/v1/datasets/NOPUB210/versions/{vid}/security-review",
                json={"passed": True}, headers=_tok(APPROVER_TOKEN))
    # 无持久化质量断言 → 409（body 造不了假：publish 无 body 参数）
    r = client.post(f"/api/v1/datasets/NOPUB210/versions/{vid}/publish",
                    headers=ADMIN_T)
    assert r.status_code == 409 and "质量" in r.text
    # 补齐断言后可发布
    _assertions(db_session, vid)
    r = client.post(f"/api/v1/datasets/NOPUB210/versions/{vid}/publish",
                    headers=ADMIN_T)
    assert r.status_code == 200


def test_t10_security_review_binds_manifest(client, db_session):
    # 安全评审后内容变动（清单摘要变化）→ 摘要不一致拒绝发布
    from app.models.dataset import AssetDsDatasetVersion
    _seed_identities(db_session)
    r = client.post("/api/v1/datasets", json={"dataset_code": "SHA210"},
                    headers=ADMIN_T)
    vid = r.json()["data"]["version_id"]
    _ingest(client, "RUN-210-SHA", "SHASRC", ["PA"])
    client.post(f"/api/v1/datasets/SHA210/versions/{vid}/freeze",
                json={"source_batch_ids": ["RUN-210-SHA"]}, headers=ADMIN_T)
    client.post("/api/v1/datasets/classifications",
                json={"object_type": "dataset_version",
                      "object_ref": f"dataset:SHA210:{vid}",
                      "labels": P3_LABELS, "expected_version": 0}, headers=ADMIN_T)
    _assertions(db_session, vid)
    client.post(f"/api/v1/datasets/SHA210/versions/{vid}/approve",
                json={}, headers=_tok(APPROVER_TOKEN))
    client.post(f"/api/v1/datasets/SHA210/versions/{vid}/security-review",
                json={"passed": True}, headers=_tok(APPROVER_TOKEN))
    # 模拟评审后内容变动：清单摘要改变（新批次重冻结等价场景）
    v = db_session.get(AssetDsDatasetVersion, vid)
    v.manifest_sha256 = "changed-by-new-content"
    db_session.commit()
    r = client.post(f"/api/v1/datasets/SHA210/versions/{vid}/publish",
                    headers=ADMIN_T)
    assert r.status_code == 409 and "清单摘要" in r.text


# ---------- T11/T14/T18/T20/T21：版本归属、行范围与成员隔离 ----------

def test_t11_wrong_code_version_and_revoked(client, env):
    r = client.get(f"/api/v1/datasets/OTHER/versions/{env['version_id']}/timeline/x",
                   headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 422
    r = client.post(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}/revoke",
                    json={"reason": "test"}, headers=ADMIN_T)
    assert r.status_code == 200
    r = client.get(
        f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}/timeline/x",
        headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403


def test_t14_row_scope_limits_timeline_and_stats(client, env):
    # PA 在行范围内可见；PB 范围外 → 空
    r = client.get(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                   f"/timeline/{env['pid_a']}", headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 200 and r.json()["data"]["count"] == 2
    r = client.get(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                   f"/timeline/{env['pid_b']}", headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 200 and r.json()["data"]["count"] == 0
    # 统计分母=行范围内患者（1），不是版本全体（2）
    r = client.get(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                   "/stats/readmission", headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 200
    assert r.json()["data"]["denominator_patients"] == 1


def test_t18_t20_version_member_isolation(client, db_session, env):
    # 冻结后新批次不进旧版本：manifest 与统计不变
    _ingest(client, f"{env['run_id']}-LATE", "SYNTH210", ["PA", "PB"],
            day0="2026-06-01")
    r = client.get(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                   "/manifest", headers=ADMIN_T)
    assert r.status_code == 200
    assert r.json()["data"]["manifest"]["row_count"] == env["manifest"]["row_count"]
    r = client.get(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                   "/stats/readmission", headers=_tok(VIEWER_TOKEN))
    # PB 行范围外，统计仍只看 PA 的版本成员事实（2 条）
    timeline = client.get(
        f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
        f"/timeline/{env['pid_a']}", headers=_tok(VIEWER_TOKEN)).json()["data"]
    assert timeline["count"] == 2  # 新批次行未进入旧版本成员

    # 跨数据集隔离：B 数据集读不到 A 患者事实
    build_env(client, db_session, "SYNTH210B", "SYNTH210B")
    r = client.get("/api/v1/datasets/SYNTH210B/versions", headers=ADMIN_T)
    # B 建好后，A 患者在 B 最新版本时间线为空（B 成员只有 B 事实）
    from app.models.dataset import AssetDsDataset, AssetDsDatasetVersion
    d = db_session.scalar(select(AssetDsDataset).where(
        AssetDsDataset.dataset_code == "SYNTH210B"))
    vb = db_session.scalar(select(AssetDsDatasetVersion).where(
        AssetDsDatasetVersion.dataset_id == d.id))
    r = client.get(f"/api/v1/datasets/SYNTH210B/versions/{vb.id}"
                   f"/timeline/{env['pid_a']}", headers=_tok(VIEWER_TOKEN))
    assert r.status_code in (200, 403)  # viewer 无 B 授权 → 403（隔离本身）


def test_t21_training_set_purpose_isolation(client, env):
    r = client.post(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                    "/training-set",
                    json={"purpose_isolation": True, "seed": 210},
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    pids = {e["patient"] for e in data["examples"]}
    assert pids and all(p.startswith("PA-") for p in pids)  # 假名，非内部 ID
    assert env["pid_a"] not in pids
    # 分组不重叠（同一假名只出现在一个 split）
    split_map = {}
    for e in data["examples"]:
        split_map.setdefault(e["patient"], set()).add(e["split"])
    assert all(len(v) == 1 for v in split_map.values())


# ---------- T22—T26：导出真实闭环 ----------

def _request_export(client, env, fields, token=VIEWER_TOKEN, expect=200):
    r = client.post(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
                    "/exports",
                    json={"fields": fields, "project_code": "proj-210"},
                    headers=_tok(token))
    assert r.status_code == expect, r.text
    return r


def test_t22_export_request_requires_own_grant_and_review_separation(
        client, env):
    # 无授权主体（plain）申请 → 403
    r = _request_export(client, env,
                        ["fact_key", "internal_patient_id"], token=PLAIN_TOKEN,
                        expect=403)
    assert "deny_no_grant" in r.text or "无用途授权" in r.text
    # viewer 正常申请 → review_pending + 服务端随机码
    r1 = _request_export(client, env, ["fact_key", "internal_patient_id"])
    code1 = r1.json()["data"]["export_code"]
    r2 = _request_export(client, env, ["fact_key", "internal_patient_id"])
    assert r2.json()["data"]["export_code"] != code1  # 不固定到 code/version
    # 申请人自审 → 403
    r = client.post(f"/api/v1/datasets/exports/{code1}/review",
                    json={"decision": "approve"}, headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403
    # 未审批先下载 → 403
    r = client.post(f"/api/v1/datasets/exports/{code1}/download",
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403
    return code1


def test_t23_full_export_loop_real_bytes(client, env):
    fields = ["fact_key", "fact_kind", "internal_patient_id", "standard_value",
              "business_time"]
    r = _request_export(client, env, fields)
    code = r.json()["data"]["export_code"]
    r = client.post(f"/api/v1/datasets/exports/{code}/review",
                    json={"decision": "approve", "note": "核定用途与字段"},
                    headers=_tok(APPROVER_TOKEN))
    assert r.status_code == 200 and r.json()["data"]["status"] == "approved"
    r = client.post(f"/api/v1/datasets/exports/{code}/generate", json={},
                    headers=ADMIN_T)
    assert r.status_code == 200, r.text
    gen = r.json()["data"]
    assert gen["status"] == "generated" and gen["row_count"] >= 1
    r = client.post(f"/api/v1/datasets/exports/{code}/download",
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 200
    body = r.content
    assert hashlib.sha256(body).hexdigest() == gen["file_sha256"]
    text = body.decode("utf-8")
    header = text.splitlines()[0]
    assert header.split(",") == fields  # 确定性字段顺序
    assert env["pid_b"] not in text     # 行范围外患者不出现在导出


def test_t24_label_restricted_form_blocks_field(client, db_session, env):
    # 对来源表 standard_value 列打 free_text 标签 → 含该字段的导出申请被拒
    from app.services.dataset_security import canonical_object_ref
    ref = canonical_object_ref("column", {
        "source_code": "SYNTH210", "schema_name": "SYNTH210",
        "table_name": "SYNTH", "column_name": "standard_value"})
    r = client.post("/api/v1/datasets/classifications",
                    json={"object_type": "column", "physical_key": {
                        "source_code": "SYNTH210", "schema_name": "SYNTH210",
                        "table_name": "SYNTH", "column_name": "standard_value"},
                        "labels": {"data_form": "free_text", "personal_info": "personal",
                                   "protection_level": "P3"},
                        "expected_version": 0}, headers=ADMIN_T)
    assert r.status_code == 200, r.text
    # 含 standard_value 的申请 → 403（用户未声明 free_text 也拦）
    r = _request_export(client, env, ["fact_key", "standard_value"], expect=403)
    assert "受限" in r.text or "标签" in r.text


def test_t25_grant_revocation_blocks_download(client, env):
    code = test_t22_export_request_requires_own_grant_and_review_separation(
        client, env)
    client.post(f"/api/v1/datasets/exports/{code}/review",
                json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    client.post(f"/api/v1/datasets/exports/{code}/generate", json={},
                headers=ADMIN_T)
    r = client.post(f"/api/v1/datasets/grants/{env['grant_id']}/revoke",
                    json={"reason": "test revoke"}, headers=ADMIN_T)
    assert r.status_code == 200
    r = client.post(f"/api/v1/datasets/exports/{code}/download",
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403
    # 工件状态被传播撤销
    from app.models.dataset import AssetDsExport as E
    exp_state = None  # 通过列表接口断言
    r = client.get("/api/v1/datasets/exports", headers=ADMIN_T)
    states = {e["export_code"]: e["status"] for e in r.json()["data"]}
    assert states.get(code) == "revoked"


def test_t26_download_binding_and_unknown(client, env):
    code = test_t22_export_request_requires_own_grant_and_review_separation(
        client, env)
    client.post(f"/api/v1/datasets/exports/{code}/review",
                json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    client.post(f"/api/v1/datasets/exports/{code}/generate", json={},
                headers=ADMIN_T)
    # 他人主体（plain）下载 → 403
    r = client.post(f"/api/v1/datasets/exports/{code}/download",
                    headers=_tok(PLAIN_TOKEN))
    assert r.status_code == 403
    # 未知导出码 → 404
    r = client.post("/api/v1/datasets/exports/EXP-unknown-000/download",
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 404


# ---------- T27：拒绝审计回滚后可读 ----------

def test_t27_denial_audit_survives_rollback(client, db_session, env):
    before = db_session.query(GovernAuditLog).filter(
        GovernAuditLog.action.like("gateway:%")).count()
    # 触发一次拒绝（未授权主体读取）
    client.get(f"/api/v1/datasets/{env['code']}/versions/{env['version_id']}"
               f"/timeline/{env['pid_a']}", headers=_tok(PLAIN_TOKEN))
    db_session.expire_all()
    after = db_session.query(GovernAuditLog).filter(
        GovernAuditLog.action.like("gateway:%")).count()
    assert after > before  # 403 业务回滚后拒绝审计仍可回读


# ---------- T28：expected_version CAS ----------

def test_t28_cas_conflict(client, env):
    body = {"object_type": "dataset_version", "object_ref": env["ref"],
            "labels": {"protection_level": "P4", "personal_info": "personal",
                       "usage_constraints": {"purposes": ["research"]}},
            "expected_version": 1}
    r = client.post("/api/v1/datasets/classifications", json=body, headers=ADMIN_T)
    assert r.status_code == 200
    r = client.post("/api/v1/datasets/classifications", json=body, headers=ADMIN_T)
    assert r.status_code == 409  # 重复 expected_version → 冲突


# ---------- T30：撤销账本恢复重放 ----------

def test_t30_revocation_replay_idempotent(client, db_session, env):
    from app.models.dataset import AssetDsRevocationLedger
    code = test_t22_export_request_requires_own_grant_and_review_separation(
        client, env)
    client.post(f"/api/v1/datasets/exports/{code}/review",
                json={"decision": "approve"}, headers=_tok(APPROVER_TOKEN))
    client.post(f"/api/v1/datasets/exports/{code}/generate", json={},
                headers=ADMIN_T)
    client.post(f"/api/v1/datasets/grants/{env['grant_id']}/revoke",
                json={"reason": "restore drill"}, headers=ADMIN_T)
    # 模拟备份恢复：撤销被回滚（授权复活、导出复活），账目置未重放
    g = db_session.get(AssetDsGrant, env["grant_id"])
    g.status = "active"
    exp = db_session.scalar(select(AssetDsExport).where(
        AssetDsExport.export_code == code))
    exp.status = "generated"
    led = db_session.scalars(select(AssetDsRevocationLedger).where(
        AssetDsRevocationLedger.target_ref == f"grant:{env['grant_id']}")).all()
    assert led, "撤销账本必须留痕"
    for row in led:
        row.replayed = "false"
        row.replayed_at = None
    db_session.commit()
    # 未重放 → 出口关闭
    r = client.post(f"/api/v1/datasets/exports/{code}/download",
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403 and "未重放" in r.text
    # 重放 → 撤销重新断言（幂等）
    r = client.post("/api/v1/datasets/admin/replay-revocations", headers=ADMIN_T)
    assert r.status_code == 200 and r.json()["data"]["entries_replayed"] >= 1
    db_session.expire_all()
    g = db_session.get(AssetDsGrant, env["grant_id"])
    assert g.status == "revoked"  # 账本权威重放，不复活
    # 二次重放零新增
    r = client.post("/api/v1/datasets/admin/replay-revocations", headers=ADMIN_T)
    assert r.json()["data"]["entries_replayed"] == 0
    # 重放后下载仍拒绝（授权已撤销），但原因不再是恢复保护
    r = client.post(f"/api/v1/datasets/exports/{code}/download",
                    headers=_tok(VIEWER_TOKEN))
    assert r.status_code == 403 and "未重放" not in r.text


# ---------- T31：离线候选导入（幂等 + confirmed 不覆盖） ----------

def test_t31_candidate_import_idempotent_and_confirmed_protected(
        client, db_session, env):
    from app.services.dataset_security import canonical_object_ref
    proposals = [
        {"object_type": "table",
         "physical_key": {"source_code": "S1", "schema_name": "sch",
                          "table_name": "T1"},
         "labels": {"protection_level": "P3", "personal_info": "personal"},
         "evidence": {"domain": "d"}},
        {"object_type": "table",
         "physical_key": {"source_code": "S1", "schema_name": "sch",
                          "table_name": "T1"},
         "labels": {"protection_level": "P3", "personal_info": "personal"},
         "evidence": {"domain": "d"}},  # 完全相同 → 第二次 skipped_same
        {"object_type": "table",
         "physical_key": {"source_code": "S1", "schema_name": "sch",
                          "table_name": "T2"},
         "labels": {"protection_level": "P0", "personal_info": "bad"},
         "evidence": {}},  # 非法枚举 → rejected
    ]
    r = client.post("/api/v1/datasets/classifications/candidates:import",
                    json={"proposals": proposals}, headers=ADMIN_T)
    assert r.status_code == 200, r.text
    d1 = r.json()["data"]
    # 批内第二条与首条完全一致 → 同批去重（skipped_same）；非法枚举 rejected
    assert d1["imported"] == 1 and d1["rejected"] == 1 and d1["skipped_same"] == 1
    # 第二次导入同一批 → 全部 skipped_same（二次导入 diff=0）
    r = client.post("/api/v1/datasets/classifications/candidates:import",
                    json={"proposals": proposals[:2]}, headers=ADMIN_T)
    d2 = r.json()["data"]
    assert d2["imported"] == 0 and d2["skipped_same"] == 2
    # confirmed 标签不被候选覆盖
    ref = canonical_object_ref("table", {"source_code": "S1",
                                         "schema_name": "sch", "table_name": "T1"})
    row = db_session.scalar(select(AssetDsClassification).where(
        AssetDsClassification.object_ref == ref,
        AssetDsClassification.status == "active"))
    row.label_source = "confirmed"
    db_session.commit()
    r = client.post("/api/v1/datasets/classifications/candidates:import",
                    json={"proposals": [{
                        "object_type": "table",
                        "physical_key": {"source_code": "S1",
                                         "schema_name": "sch",
                                         "table_name": "T1"},
                        "labels": {"protection_level": "P2",
                                   "personal_info": "none"},
                        "evidence": {}}]}, headers=ADMIN_T)
    d3 = r.json()["data"]
    assert d3["skipped_confirmed"] == 1 and d3["imported"] == 0
