from __future__ import annotations

import inspect

from app.api.v1 import ai
from app.models.asset import AssetColumn, AssetTable
from app.services.hospital_llm_client import HospitalLlmResponse


def _seed(db):
    db.add(AssetTable(system_code="DATA_CENTER", source_code="ods_r167", schema_name="R167", table_name="VISITS"))
    db.add_all([AssetColumn(system_code="DATA_CENTER", source_code="ods_r167", schema_name="R167", table_name="VISITS", column_name=name) for name in ["PATIENT_ID", "VISIT_ID"]])
    db.commit()


def test_ai_sql_generate_sanitizes_never_executes_and_audits(client, db_session, monkeypatch):
    _seed(db_session)
    seen = []
    def complete(self, prompt, max_tokens=None):
        seen.append(prompt)
        return HospitalLlmResponse("```sql\nSELECT PATIENT_ID, VISIT_ID FROM R167.VISITS WHERE ROWNUM <= 20\n```", "mock", {"choices": [{"finish_reason": "stop"}]})
    monkeypatch.setattr(ai.HospitalLlmClient if hasattr(ai, "HospitalLlmClient") else __import__("app.services.hospital_llm_client", fromlist=["HospitalLlmClient"]).HospitalLlmClient, "complete", complete)
    response = client.post("/api/v1/ai/ai-sql/generate", json={"question": "查询患者<script>alert(1)</script>列表", "system_code": "DATA_CENTER", "selected_tables": ["R167.VISITS"]})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["sql"].startswith("SELECT") and data["sql"].endswith(";")
    assert data["executed"] is False
    assert "script" not in seen[0].lower()
    history = client.get("/api/v1/ai/ai-sql/history")
    assert history.status_code == 200
    assert history.json()["data"]["items"][0]["request"]["question_sha256"]
    assert "查询患者" in history.json()["data"]["items"][0]["request"]["question_summary"]


def test_ai_sql_generate_retries_once_on_truncation(client, db_session, monkeypatch):
    _seed(db_session)
    calls = []
    from app.services import hospital_llm_client
    def complete(self, prompt, max_tokens=None):
        calls.append(prompt)
        if len(calls) == 1:
            return HospitalLlmResponse("SELECT * FROM", "mock", {"choices": [{"finish_reason": "length"}]})
        return HospitalLlmResponse("SELECT * FROM R167.VISITS WHERE ROWNUM <= 10", "mock", {"choices": [{"finish_reason": "stop"}]})
    monkeypatch.setattr(hospital_llm_client.HospitalLlmClient, "complete", complete)
    response = client.post("/api/v1/ai/ai-sql/generate", json={"question": "列出十条记录", "selected_tables": ["R167.VISITS"]})
    assert response.status_code == 200
    assert len(calls) == 2


def test_ai_sql_contract_has_permission_and_no_execution_path():
    source = inspect.getsource(ai.generate_ai_sql)
    assert 'require_permission("ai.context.read")' in source
    assert "executed\": False" in source
    assert "sanitize_text(req.question" in source
    assert "build_ai_sql_context" in source
    assert "execute_approved" not in source
