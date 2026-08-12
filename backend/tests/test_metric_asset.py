"""126 P2 metric asset tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

SAFE_SQL = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"


def _ingest_query(client: TestClient, code: str = "QRY_FOR_METRIC") -> None:
    r = client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": code,
            "title": "指标依赖查询",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
            "system_code": "DATA_CENTER",
        },
    )
    assert r.status_code == 200, r.text


def test_metric_ingest_auto_active(client: TestClient):
    _ingest_query(client, "QRY_M_NUM")
    r = client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_P2_DEMO",
            "title": "示例率",
            "meaning": "测试指标含义",
            "numerator_desc": "分子说明",
            "denominator_desc": "分母说明",
            "formula": "分子/分母*100",
            "query_code": "QRY_M_NUM",
            "unit": "%",
            "frequency": "month",
            "limitations": ["仅测试库"],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["version"]["is_active"] is True
    assert d["version"]["status"] == "active"
    assert d["version"]["query_code"] == "QRY_M_NUM"


def test_metric_idempotent(client: TestClient):
    _ingest_query(client, "QRY_M_IDEM")
    payload = {
        "metric_code": "MET_P2_IDEM",
        "title": "幂等指标",
        "definition_text": "定义不变",
        "query_code": "QRY_M_IDEM",
        "formula": "x",
    }
    r1 = client.post("/api/v1/metrics/ingest", json=payload)
    r2 = client.post("/api/v1/metrics/ingest", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["data"]["idempotent"] is True


def test_metric_result_no_overwrite(client: TestClient):
    _ingest_query(client, "QRY_M_RES")
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_P2_RES",
            "title": "结果测试",
            "definition_text": "口径",
            "query_code": "QRY_M_RES",
            "formula": "a/b",
        },
    )
    a = client.post(
        "/api/v1/metrics/results",
        json={
            "metric_code": "MET_P2_RES",
            "period_key": "2026-01",
            "numerator_value": "10",
            "denominator_value": "100",
            "metric_value": "10%",
        },
    )
    b = client.post(
        "/api/v1/metrics/results",
        json={
            "metric_code": "MET_P2_RES",
            "period_key": "2026-01",
            "numerator_value": "12",
            "denominator_value": "100",
            "metric_value": "12%",
        },
    )
    assert a.status_code == 200 and b.status_code == 200
    assert b.json()["data"]["is_recalc"] is True
    assert b.json()["data"]["prev_result_id"] == a.json()["data"]["id"]
    lst = client.get("/api/v1/metrics/MET_P2_RES/results", params={"period_key": "2026-01"})
    assert lst.status_code == 200
    assert lst.json()["data"]["total"] >= 2


def test_metric_list_and_context(client: TestClient):
    _ingest_query(client, "QRY_M_CTX")
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_P2_CTX",
            "title": "上下文指标",
            "definition_text": "定义",
            "query_code": "QRY_M_CTX",
            "formula": "x",
        },
    )
    lst = client.get("/api/v1/metrics", params={"keyword": "MET_P2_CTX"})
    assert lst.status_code == 200
    assert lst.json()["data"]["total"] >= 1
    ctx = client.get("/api/v1/metrics/ai/context")
    assert ctx.status_code == 200
    codes = [x["metric_code"] for x in ctx.json()["data"]]
    assert "MET_P2_CTX" in codes
