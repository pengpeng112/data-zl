from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api.v1 import ai_quality
from app.core.config import settings
from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetUserRole
from app.models.quality import AiQualityJob, QualityCheckRun, QualityFinding, QualityRule
from app.services.dify_quality_client import DifyResponse


def _finding(db, *, table="PAT_VISIT", rule="TEST_AI_RULE", source="his_source_10_10_10_15"):
    if not db.scalar(select(QualityRule).where(QualityRule.rule_code == rule)):
        db.add(QualityRule(rule_code=rule, rule_name="测试规则", rule_type="metadata", rule_category="completeness"))
    row = QualityFinding(
        run_id=1,
        rule_code=rule,
        target_type="column",
        target_ref=f"HIS.{table}.PATIENT_ID",
        system_code="HIS",
        source_code=source,
        schema_name="HIS",
        table_name=table,
        column_name="PATIENT_ID",
        severity="major",
        status="open",
        metric_value="error_rate=1%",
        total_cnt=100,
        error_cnt=1,
        sample_data={"patient_name": "must-never-leave"},
        detail={"free_text": "must-never-leave"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _enable_mock(monkeypatch):
    monkeypatch.setattr(settings, "dify_quality_enabled", True)
    monkeypatch.setattr(settings, "dify_quality_api_key_ref", "env:TEST_DIFY_QUALITY_KEY")
    monkeypatch.setenv("TEST_DIFY_QUALITY_KEY", "test-secret-never-return")


def test_preview_create_idempotent_review_attach_without_mutating_finding(client, db_session, monkeypatch):
    finding = _finding(db_session)
    _enable_mock(monkeypatch)
    calls = []

    def run_workflow(_self, *, inputs, user):
        calls.append((inputs, user))
        output = {
            "schema_version": "quality-analysis-output/v1",
            "request_id": inputs["request_id"],
            "input_digest": inputs["input_digest"],
            "summary": "元数据质量问题，需人工复核",
            "risk_level": "medium",
            "root_causes": [{"title": "注释缺失", "reason": "聚合规则命中", "confidence": 0.8, "evidence_finding_ids": [finding.id]}],
            "recommendations": [{"title": "核对元数据", "action_type": "manual_review", "priority": "P2", "reason": "避免误报", "confidence": 0.7, "target_refs": ["HIS.PAT_VISIT.PATIENT_ID"]}],
            "false_positive": {"possible": True, "reason": "采集批次可能滞后"},
            "follow_up_checks": [{"description": "核对字段注释", "sql_draft": None}],
            "limitations": ["仅使用聚合元数据"],
        }
        return DifyResponse({"workflow_run_id": "safe-run-1", "data": {"outputs": output, "usage": {"total_tokens": 12}}}, 200)

    monkeypatch.setattr(ai_quality.DifyQualityClient, "run_workflow", run_workflow)
    preview = client.post("/api/v1/quality/ai/preview", json={"task_type": "finding", "finding_ids": [finding.id]})
    assert preview.status_code == 200
    safe = preview.json()["data"]
    assert safe["item_count"] == 1
    assert safe["finding_ids"] == [finding.id]
    assert "findings" in safe["payload_json"]
    assert "must-never-leave" not in safe["payload_json"]

    create_body = {"task_type": "finding", "finding_ids": [finding.id], "request_id": safe["request_id"], "input_digest": safe["input_digest"]}
    created = client.post("/api/v1/quality/ai/jobs", json=create_body)
    assert created.status_code == 200
    job = created.json()["data"]
    assert job["status"] == "succeeded"
    assert job["result"]["structured_result"]["follow_up_checks"][0]["sql_draft"] is None
    assert len(calls) == 1
    assert "test-secret-never-return" not in str(created.json())

    reused = client.post("/api/v1/quality/ai/jobs", json=create_body)
    assert reused.status_code == 200
    assert reused.json()["data"]["id"] == job["id"]
    assert len(calls) == 1

    result_id = job["result"]["id"]
    reviewed = client.patch(f"/api/v1/quality/ai/results/{result_id}/review", json={"status": "accepted", "note": "人工确认"})
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["review_status"] == "accepted"
    attached = client.post(f"/api/v1/quality/ai/results/{result_id}/attach", json={"recommendation_indexes": [0], "note": "挂接展示"})
    assert attached.status_code == 200
    db_session.expire_all()
    unchanged = db_session.get(QualityFinding, finding.id)
    assert unchanged.status == "open"
    assert unchanged.note is None


def test_task_scope_preview_token_and_run_summary_contract(client, db_session, monkeypatch):
    first = _finding(db_session)
    second = _finding(db_session, table="LAB_TEST_MASTER")
    run = QualityCheckRun(status="success", total_rules=2, total_findings=2, pass_rate=50)
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    _enable_mock(monkeypatch)

    cross_table = client.post("/api/v1/quality/ai/preview", json={"task_type": "finding_batch", "finding_ids": [first.id, second.id]})
    assert cross_table.status_code == 422
    arbitrary = client.post("/api/v1/quality/ai/preview", json={"task_type": "finding", "finding_ids": [first.id], "payload": {"sample_data": [1]}})
    assert arbitrary.status_code == 422
    run_preview = client.post("/api/v1/quality/ai/preview", json={"task_type": "run_summary", "run_id": run.id})
    assert run_preview.status_code == 200
    assert run_preview.json()["data"]["run_id"] == run.id
    forged = client.post("/api/v1/quality/ai/jobs", json={"task_type": "finding", "finding_ids": [first.id], "request_id": "AQJ-000000000000000000000000-00000000000000000000000000000000", "input_digest": "0" * 64})
    assert forged.status_code == 422


def test_rbac_and_stale_running_recovery(client, db_session):
    token = "ai-quality-viewer-token"
    db_session.add(AssetRole(role_code="test_ai_viewer", role_name_cn="测试只读", role_type="test"))
    db_session.add(AssetUserRole(user_identifier="test-ai-viewer", role_code="test_ai_viewer", status="active"))
    db_session.add(ApiKey(key_name="test-ai-viewer-key", token_hash=hashlib.sha256(token.encode()).hexdigest(), user_identifier="test-ai-viewer", enabled=True))
    stale = AiQualityJob(job_key="stale-job", task_type="finding", prompt_version="v1", schema_version="quality-analysis-input/v1", input_digest="a" * 64, request_id="AQJ-stale", status="running", attempt=1, started_at=datetime.now(timezone.utc) - timedelta(hours=1))
    db_session.add(stale)
    db_session.commit()

    denied = client.get("/api/v1/quality/ai/status", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 403
    listed = client.get("/api/v1/quality/ai/jobs")
    assert listed.status_code == 200
    stale_item = next(item for item in listed.json()["data"]["items"] if item["id"] == stale.id)
    assert stale_item["status"] == "unknown"
    assert stale_item["error_class"] == "stale_running"
