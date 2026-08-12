"""126 P4 data product + result import tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

SAFE_SQL = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"


def test_publish_and_execute_metric_product(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_CORE_99",
            "title": "产品测试查询",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
            "source_code": "ods_8_216",
        },
    )
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_CORE_99",
            "title": "产品测试指标",
            "definition_text": "测试",
            "query_code": "QRY_CORE_99",
            "formula": "x",
            "numerator_desc": "n",
            "denominator_desc": "d",
        },
    )
    pub = client.post("/api/v1/data-products/publish-core")
    assert pub.status_code == 200, pub.text
    assert pub.json()["data"]["count"] >= 1

    lst = client.get("/api/v1/data-products", params={"keyword": "MET_CORE_99"})
    assert lst.status_code == 200
    assert lst.json()["data"]["total"] >= 1

    # metric product without SQL execute returns definition
    ex = client.post(
        "/api/v1/data-products/DP_MET_CORE_99/execute",
        json={"execute_sql": False},
    )
    assert ex.status_code == 200, ex.text
    body = ex.json()["data"]
    assert body["product_type"] == "metric"
    assert body["executed"] is False
    assert body["metric_code"] == "MET_CORE_99"
    assert "definition_text" in body


def test_metric_result_import_dry_run(client: TestClient):
    r = client.post("/api/v1/data-products/import/metric-results", params={"dry_run": True})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["file_count"] >= 1
    assert data["dry_run"] is True


def test_ai_product_context(client: TestClient):
    r = client.get("/api/v1/data-products/ai/context")
    assert r.status_code == 200
