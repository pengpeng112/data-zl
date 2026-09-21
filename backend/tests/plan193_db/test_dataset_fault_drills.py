"""193 B17 故障演练矩阵（隔离库，合成数据）。

覆盖：断电模拟（提交边界中断→续跑不漏不重）、超时取消→恢复、迟到修改/删除、
schema 漂移隔离（其他源不受影响）、来源缺片→质量门禁阻止发布、错误合并拆分恢复、
策略撤销传播、发布失败旧版仍可用（回滚语义）、恢复后撤销重放、
权限反例（伪造主体/操作越界/用途不匹配）、B12 对账守恒、B14 导出到期、
B15 保留义务三分支。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.dataset import AssetDsBatch, AssetDsFact, AssetDsGrant
from app.services import dataset_pipeline as pipe
from app.services import dataset_products as prod
from app.services import dataset_security as sec

T = {"Authorization": "Bearer test-token-p5-auth-2026"}
T2 = {"Authorization": "Bearer test-token-second-user-2026"}


def _rec(run, kind, key, patient, t="2026-01-01T08:00:00+00:00", **kw):
    d = {"fact_key": f"{run}:{kind}:{key}", "fact_kind": kind,
         "source_patient_key": patient, "original_value_ref": f"ref/{key}",
         "business_time": t, "available_time": t}
    d.update(kw)
    return d


# ---------- B07：断电模拟（提交边界中断→续跑不漏不重） ----------

def test_drill_power_loss_mid_batch(db_session):
    records = [_rec("RUN-PL", "visit", f"P{i}", f"S{i}") for i in range(10)]
    try:
        pipe.ingest_batch_chunked(db_session, "RUN-PL", "SYNTH_A", "o", records,
                                  "rules_v1", chunk_size=2, crash_after_chunks=3)
        raise AssertionError("应在第 3 chunk 后模拟崩溃")
    except RuntimeError as e:
        assert "模拟断电" in str(e)
    db_session.rollback()  # 崩溃现场回滚
    # 已提交 3 chunks=6 条持久化
    persisted = db_session.scalars(select(AssetDsFact).where(
        AssetDsFact.batch_run_id == "RUN-PL")).all()
    assert len(persisted) == 6
    # 续跑全量：6 跳过 + 4 写入 = 10 总
    r = pipe.ingest_batch(db_session, "RUN-PL", "SYNTH_A", "o", records, "rules_v1")
    db_session.commit()
    assert r["skipped"] == 6 and r["written"] == 4
    keys = pipe.resume_batch_from_checkpoint(db_session, "RUN-PL")
    assert len(keys) == 10 and len(set(keys)) == 10  # 不漏不重


# ---------- B07：超时取消→恢复 ----------

def test_drill_cancel_then_resume(db_session):
    records = [_rec("RUN-TC", "visit", f"P{i}", f"S{i}") for i in range(4)]
    pipe.ingest_batch(db_session, "RUN-TC", "SYNTH_A", "o", records[:2], "rules_v1")
    db_session.commit()
    pipe.cancel_batch(db_session, "RUN-TC", reason="timeout 30m")
    db_session.commit()
    b = db_session.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == "RUN-TC"))
    assert b.status == "cancelled" and b.error_class == "cancelled"
    # 恢复=同 run 重跑（检查点保留）
    r = pipe.ingest_batch(db_session, "RUN-TC", "SYNTH_A", "o", records, "rules_v1")
    db_session.commit()
    assert r["written"] == 2 and r["skipped"] == 2


# ---------- B07：迟到修改/删除 ----------

def test_drill_late_modify_and_delete(db_session):
    recs = [_rec("RUN-LM", "diagnosis", "D1", "S1", standard_value="I50.x00",
                 code_system="ICD10")]
    pipe.ingest_batch(db_session, "RUN-LM", "SYNTH_A", "o", recs, "rules_v1")
    db_session.commit()
    m = pipe.late_modify_fact(db_session, "RUN-LM:diagnosis:D1", "I50.x01",
                              "RUN-LM-FIX")
    db_session.commit()
    assert "late@RUN-LM-FIX" in m["new_rule_version"]
    # 读侧最新版本生效；旧版本保留（来源保真）
    latest = {f.fact_key: f for f in pipe.latest_facts(db_session)}
    assert latest["RUN-LM:diagnosis:D1"].standard_value == "I50.x01"
    all_rows = db_session.scalars(select(AssetDsFact).where(
        AssetDsFact.fact_key == "RUN-LM:diagnosis:D1")).all()
    assert len(all_rows) == 2  # 新旧两行
    # 迟到删除：全部版本软删，读侧排除
    d = pipe.late_delete_fact(db_session, "RUN-LM:diagnosis:D1", "RUN-LM-DEL")
    db_session.commit()
    assert d["rows_marked"] == 2
    assert all(f.fact_key != "RUN-LM:diagnosis:D1" for f in pipe.latest_facts(db_session))


# ---------- B07：schema 漂移隔离（其他源不受影响） ----------

def test_drill_schema_drift_isolated(db_session):
    good = [_rec("RUN-OK", "visit", "P1", "S1")]
    drift = [_rec("RUN-DRIFT", "visit", "P2", "S2")]
    drift[0].pop("original_value_ref")  # 关键字段缺失=漂移
    r1 = pipe.ingest_batch_with_drift_guard(
        db_session, "RUN-OK", "SYNTH_A", "o", good, "rules_v1",
        expected_fields=["fact_key", "fact_kind", "source_patient_key",
                         "original_value_ref", "business_time"])
    db_session.commit()
    r2 = pipe.ingest_batch_with_drift_guard(
        db_session, "RUN-DRIFT", "SYNTH_B", "o", drift, "rules_v1",
        expected_fields=["fact_key", "fact_kind", "source_patient_key",
                         "original_value_ref", "business_time"])
    db_session.commit()
    assert r1["isolated"] is False and r1["written"] == 1
    assert r2["isolated"] is True and r2["written"] == 0
    b = db_session.scalar(select(AssetDsBatch).where(AssetDsBatch.run_id == "RUN-DRIFT"))
    assert b.status == "failed" and b.error_class == "schema_drift"
    # 其他批次照常入库
    rows = db_session.scalars(select(AssetDsFact).where(
        AssetDsFact.batch_run_id == "RUN-OK")).all()
    assert len(rows) == 1


# ---------- B09/B10：来源缺片→质量门禁阻止发布 ----------

def test_drill_missing_shard_blocks_publish(db_session):
    # 期望 3 个分片，仅 2 个到达
    checks = [{"dimension": "coverage", "metric_name": "shard_coverage",
               "numerator": 2, "denominator": 3,
               "threshold": {"op": "==", "value": 1.0}}]
    results = pipe.evaluate_assertions(db_session, "batch", "RUN-MISS", checks)
    assert results[0]["result"] == "fail"


# ---------- B06：错误合并→拆分恢复 ----------

def test_drill_wrong_merge_recovery(db_session):
    m1 = pipe.register_identity(db_session, "SYNTH_A", "WX1")
    m2 = pipe.register_identity(db_session, "SYNTH_A", "WX2")
    pipe.ingest_batch(db_session, "RUN-WM", "SYNTH_A", "o", [
        _rec("RUN-WM", "visit", "X1", "WX1"), _rec("RUN-WM", "visit", "X2", "WX2")],
        "rules_v1")
    db_session.commit()
    n = pipe.merge_identities(db_session, m1.internal_patient_id,
                              m2.internal_patient_id, "误合并")
    db_session.commit()
    assert n >= 1
    chain = pipe.effective_patient_ids(db_session, [m2.internal_patient_id])
    assert chain[m2.internal_patient_id] == m1.internal_patient_id
    # 发现错误→拆分，身份与事实归属恢复
    restored = pipe.split_identity(db_session, m2.internal_patient_id, "拆分")
    db_session.commit()
    assert restored >= 1
    chain2 = pipe.effective_patient_ids(db_session, [m2.internal_patient_id])
    assert chain2[m2.internal_patient_id] == m2.internal_patient_id
    # 事实仍归属各自身份（事实按登记时的身份写入，合并只影响解析链）
    facts = db_session.scalars(select(AssetDsFact).where(
        AssetDsFact.batch_run_id == "RUN-WM")).all()
    assert {f.internal_patient_id for f in facts} == {
        m1.internal_patient_id, m2.internal_patient_id}


# ---------- B04/B05：策略撤销传播（分类替换→读取立即拒绝） ----------

def test_drill_policy_supersede_denies(db_session):
    from app.models.dataset import AssetDsClassification
    ref = "dataset:DSX:9"
    db_session.add(AssetDsClassification(
        object_type="dataset_version", object_ref=ref,
        labels={"protection_level": "P3", "personal_info": "personal",
                "usage_constraints": {"purposes": ["rp2"]}},
        protection_level="P3", version=1))
    db_session.flush()
    r1 = sec.enforce_read(db_session, "u1", "rp2", ref)
    assert r1.decision == "deny_no_grant"  # 有分类无授权
    db_session.add(AssetDsGrant(
        principal="u1", purpose_code="rp2", resource_type="dataset_version",
        resource_ref=ref, operations=["read"], legal_basis_ref="t",
        approved_by="op"))
    db_session.flush()
    r2 = sec.enforce_read(db_session, "u1", "rp2", ref)
    assert r2.allowed
    # 分类被替换（旧版 superseded，新版 P4 无用途允许）
    db_session.query(AssetDsClassification).filter(
        AssetDsClassification.object_ref == ref,
        AssetDsClassification.version == 1).update({"status": "superseded"})
    db_session.add(AssetDsClassification(
        object_type="dataset_version", object_ref=ref,
        labels={"protection_level": "P4", "personal_info": "sensitive_personal",
                "usage_constraints": {"purposes": []}},
        protection_level="P4", version=2))
    db_session.flush()
    r3 = sec.enforce_read(db_session, "u1", "rp2", ref)
    # 新版标签未允许该用途 → 拒绝（组合条件取交）
    assert not r3.allowed


# ---------- B10：发布失败旧版仍可用（回滚语义） ----------

def test_drill_publish_fail_old_version_usable(client: TestClient):
    # v1 走完整链到 published
    r = client.post("/api/v1/datasets", json={
        "dataset_code": "DS_RB", "purpose_code": "rp_rb"}, headers=T)
    assert r.status_code == 200
    v1 = r.json()["data"]["version_id"]
    ref = f"dataset:DS_RB:{v1}"
    client.post("/api/v1/datasets/batches/RUN-RB/records", json={
        "source_code": "SYNTH_A", "records": [
            _rec("RUN-RB", "visit", "P1", "S1")], "rule_version": "rules_v1"}, headers=T)
    client.post("/api/v1/datasets/classifications", json={
        "object_ref": ref,
        "labels": {"protection_level": "P3", "personal_info": "personal",
                   "usage_constraints": {"purposes": ["rp_rb"], "export_allowed": True,
                                         "training_allowed": True}}}, headers=T)
    client.post("/api/v1/datasets/grants", json={
        "principal": "test-platform-admin", "purpose_code": "rp_rb",
        "resource_ref": ref, "operations": ["read", "export", "derive"],
        "legal_basis_ref": "t", "valid_hours": 2}, headers=T)
    client.post(f"/api/v1/datasets/DS_RB/versions/{v1}/freeze", json={}, headers=T)
    client.post(f"/api/v1/datasets/DS_RB/versions/{v1}/approve",
                json={"approver": "ap"}, headers=T)
    r = client.post(f"/api/v1/datasets/DS_RB/versions/{v1}/publish", json={
        "quality_results": [{"dimension": "coverage", "result": "pass"}],
        "security_ok": True, "approved_by": "ap"}, headers=T)
    assert r.status_code == 200 and r.json()["data"]["status"] == "published"
    # 旧版可读（发布成功基线）
    r = client.get(f"/api/v1/datasets/DS_RB/versions/{v1}/stats/readmission", headers=T)
    assert r.status_code == 200
    # v2 质量失败 → 发布拒绝；v1 仍可读
    from app.core.db import SessionLocal
    from app.models.dataset import AssetDsDataset, AssetDsDatasetVersion
    db = SessionLocal()
    ds = db.scalar(select(AssetDsDataset).where(AssetDsDataset.dataset_code == "DS_RB"))
    v2 = AssetDsDatasetVersion(dataset_id=ds.id, version=2)
    db.add(v2)
    db.commit()
    v2_id = v2.id
    db.close()
    r = client.post(f"/api/v1/datasets/DS_RB/versions/{v2_id}/publish", json={
        "quality_results": [{"dimension": "coverage", "result": "fail"}],
        "security_ok": True, "approved_by": "ap"}, headers=T)
    assert r.status_code == 409  # 质量门禁拒绝
    r = client.get(f"/api/v1/datasets/DS_RB/versions/{v1}/stats/readmission", headers=T)
    assert r.status_code == 200  # 旧版不受影响


# ---------- B15：恢复后撤销重放 ----------

def test_drill_restore_replay_revocations(db_session):
    plan = prod.replay_revocations_after_restore(["EXP-A", "EXP-B"])
    assert set(plan["replay_export_codes"]) == {"EXP-A", "EXP-B"}
    assert plan["policy"] == "restore_then_replay_revocations"


# ---------- B05：权限反例（API 级） ----------

def test_drill_permission_negatives(client: TestClient):
    r = client.post("/api/v1/datasets", json={
        "dataset_code": "DS_NEG", "purpose_code": "rp_neg"}, headers=T)
    vid = r.json()["data"]["version_id"]
    ref = f"dataset:DS_NEG:{vid}"
    client.post("/api/v1/datasets/classifications", json={
        "object_ref": ref,
        "labels": {"protection_level": "P3", "personal_info": "personal",
                   "usage_constraints": {"purposes": ["rp_neg"]}}}, headers=T)
    # 只读授权（无 export）
    r = client.post("/api/v1/datasets/grants", json={
        "principal": "test-platform-admin", "purpose_code": "rp_neg",
        "resource_ref": ref, "operations": ["read"],
        "legal_basis_ref": "t", "valid_hours": 1}, headers=T)
    gid = r.json()["data"]["grant_id"]
    # 反例1：操作越界（read-only grant 尝试 export）
    client.post(f"/api/v1/datasets/DS_NEG/versions/{vid}/freeze", json={}, headers=T)
    client.post(f"/api/v1/datasets/DS_NEG/versions/{vid}/approve",
                json={"approver": "ap"}, headers=T)
    client.post(f"/api/v1/datasets/DS_NEG/versions/{vid}/publish", json={
        "quality_results": [{"result": "pass"}], "security_ok": True,
        "approved_by": "ap"}, headers=T)
    r = client.post(f"/api/v1/datasets/DS_NEG/versions/{vid}/exports",
                    json={"grant_id": gid, "fields": ["fact_key"]}, headers=T)
    assert r.status_code == 403
    # 反例2：伪造主体（另一用户 token 无授权）
    r = client.get(f"/api/v1/datasets/DS_NEG/versions/{vid}/stats/readmission",
                   headers=T2)
    assert r.status_code == 403
    # 反例3：用途不匹配（正确主体、错误 purpose 无授权）；global 通配边界
    r = client.post("/api/v1/datasets/grants", json={
        "principal": "test-platform-admin", "purpose_code": "rp_other",
        "resource_ref": "*", "operations": ["read"],
        "legal_basis_ref": "t", "valid_hours": 1}, headers=T)
    assert r.status_code == 200
    from app.core.db import SessionLocal
    s = SessionLocal()
    try:
        # 用途取交（B02 §3.1）：对象标签用途=[rp_neg]不含 rp_other，
        # 即使存在 rp_other 的 global 授权也必须拒绝——分类约束优先于授权宽度
        rr = sec.enforce_read(s, "test-platform-admin", "rp_other", ref)
        assert not rr.allowed
        assert rr.decision == "deny_level"
    finally:
        s.rollback()
        s.close()  # 必须关闭：否则空闲事务持锁阻塞 teardown TRUNCATE


# ---------- B12：旧口径/治理口径对账守恒 ----------

def test_reconcile_old_vs_governed_conserved(db_session):
    # 3 行源数据：1 正常 + 1 未知码隔离 + 1 迟到修改（产生 1 行被取代） + 1 迟到删除
    pipe.ingest_batch(db_session, "RUN-REC", "SYNTH_A", "o", [
        _rec("RUN-REC", "visit", "A", "S1"),
        _rec("RUN-REC", "diagnosis", "B", "S1", require_standard=True),
        _rec("RUN-REC", "diagnosis", "C", "S1", standard_value="I50.x00"),
        _rec("RUN-REC", "visit", "D", "S2"),
    ], "rules_v1")
    db_session.commit()
    pipe.late_modify_fact(db_session, "RUN-REC:diagnosis:C", "I50.x01", "RUN-REC-FIX")
    pipe.late_delete_fact(db_session, "RUN-REC:visit:D", "RUN-REC-DEL")
    db_session.commit()
    rows = db_session.scalars(select(AssetDsFact).where(
        AssetDsFact.batch_run_id == "RUN-REC")).all()
    # 源行 4 = 4 个 fact_key；迟到修改追加 1 行被取代版本（平台侧，不入守恒式）
    rep = prod.reconcile_old_vs_governed(source_row_count=4, governed_rows=list(rows) + [
        # late_modify 的新行 batch_run_id 是 FIX run，手动并入对账域
        *db_session.scalars(select(AssetDsFact).where(
            AssetDsFact.batch_run_id == "RUN-REC-FIX")).all()])
    assert rep["conserved"], rep
    # 按键口径：governed=A/C 两键=2, B=未知码隔离=1, D=迟到删除=1；守恒 2+1+1=4
    assert rep["governed_facts"] == 2
    assert rep["quarantined"] == 1 and rep["excluded_deleted"] == 1
    assert rep["superseded_versions"] == 1 and rep["unexplained"] == 0


# ---------- B14：导出到期 ----------

def test_export_expiry_rejected(db_session):
    from app.models.dataset import AssetDsDataset, AssetDsDatasetVersion
    ds = AssetDsDataset(dataset_code="DS_EXP_T", title="t", purpose_code="p")
    db_session.add(ds)
    db_session.flush()
    v = AssetDsDatasetVersion(dataset_id=ds.id, version=1, status="published")
    db_session.add(v)
    db_session.flush()
    g = AssetDsGrant(principal="u1", purpose_code="p", resource_type="dataset_version",
                     resource_ref=f"dataset:DS_EXP_T:{v.id}",
                     operations=["read", "export"], legal_basis_ref="t",
                     approved_by="op")
    db_session.add(g)
    db_session.flush()
    exp = prod.request_export(db_session, g.id, v.id, ["fact_key"], "u1",
                              expires_in_hours=1)
    db_session.commit()
    assert exp.status == "approved"
    # 模拟过期：把 expires_at 拨回过去
    exp.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.flush()
    try:
        prod.generate_export_csv(db_session, exp, [{"fact_key": "k"}])
        raise AssertionError("过期导出应被拒绝")
    except PermissionError as e:
        assert "过期" in str(e)
    assert exp.status == "expired"


# ---------- B15：保留义务三分支（纯逻辑） ----------

def test_deletion_policy_three_branches():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    facts = ["f1", "f2"]
    # 分支1：保留义务生效 → 封存不硬删
    r = prod.resolve_deletion_policy(facts, active_grants=0, legal_hold=True, now=now)
    assert r["action"] == "restricted_seal" and r["hard_deleted"] == 0
    r = prod.resolve_deletion_policy(facts, active_grants=0,
                                     retention_until=now + timedelta(days=30), now=now)
    assert r["action"] == "restricted_seal"
    # 分支2：无义务但有活跃授权 → 先撤权
    r = prod.resolve_deletion_policy(facts, active_grants=2,
                                     retention_until=now - timedelta(days=1), now=now)
    assert r["action"] == "defer_revoke_grants" and r["revoke_grants_first"]
    # 分支3：义务尽+无授权 → 允许硬删
    r = prod.resolve_deletion_policy(facts, active_grants=0,
                                     retention_until=now - timedelta(days=1), now=now)
    assert r["action"] == "hard_delete" and r["hard_deleted"] == 2
