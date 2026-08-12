"""126 P5: board, MCP catalog, multi-source, schedule seed."""
from __future__ import annotations

from fastapi.testclient import TestClient

SAFE_SQL = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"


def test_metric_board_overview(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_CORE_98",
            "title": "看板测试查询",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
            "source_code": "ods_8_216",
        },
    )
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_CORE_98",
            "title": "看板测试指标",
            "definition_text": "测试",
            "query_code": "QRY_CORE_98",
            "category": "48项核心制度",
            "formula": "n/d",
        },
    )
    client.post(
        "/api/v1/metrics/results",
        json={
            "metric_code": "MET_CORE_98",
            "period_key": "2026-01",
            "numerator_value": "1",
            "denominator_value": "2",
            "metric_value": "50%",
            "status": "ok",
        },
    )
    r = client.get("/api/v1/metrics/board/overview")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "periods" in data and "metrics" in data and "cells" in data
    codes = {m["metric_code"] for m in data["metrics"]}
    assert "MET_CORE_98" in codes
    assert "2026-01" in data["periods"]
    assert data["cells"]["MET_CORE_98"]["2026-01"]["metric_value"] == "50%"


def test_mcp_catalog_and_tools(client: TestClient):
    tools = client.get("/api/v1/ai/tools")
    assert tools.status_code == 200
    names = {t["name"] for t in tools.json()["data"]["tools"]}
    assert "list_data_products" in names
    assert "metric_board" in names
    assert "execute_data_product" in names

    mcp = client.get("/api/v1/ai/mcp/catalog")
    assert mcp.status_code == 200
    body = mcp.json()["data"]
    assert body["mcp_compatible"] if "mcp_compatible" in body else True
    assert body["name"] == "data-asset-governance"
    assert any(t["name"] == "execute_data_product" for t in body["tools"])
    assert "arbitrary_sql" in body["forbidden"]


def test_source_capabilities(client: TestClient):
    r = client.get("/api/v1/queries/sources/capabilities")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "items" in data
    assert "supported_dialects" in data
    assert "oracle" in data["supported_dialects"]


def test_schedule_seed_defaults_disabled(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_CORE_97",
            "title": "调度测试",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
            "source_code": "ods_8_216",
        },
    )
    r = client.post("/api/v1/queries/schedules/seed-core")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["count"] >= 1
    # all seeded should be disabled
    lst = client.get("/api/v1/queries/schedules/list")
    assert lst.status_code == 200
    rows = lst.json()["data"]
    core = [x for x in rows if x["query_code"] == "QRY_CORE_97"]
    assert core
    assert core[0]["enabled"] is False
