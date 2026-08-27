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


def test_board_overview_category_filter_hitset_unchanged(client: TestClient):
    """A10 行为锁：删除冗余 == 分支后，精确等于与子串包含两类命中都不变。"""
    _ingest_query(client, "QRY_M_BOARD")
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_BOARD_EXACT",
            "title": "精确类目指标",
            "definition_text": "定义",
            "query_code": "QRY_M_BOARD",
            "formula": "x",
            "category": "48项核心制度",
        },
    )
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_BOARD_SUBSTR",
            "title": "子串类目指标",
            "definition_text": "定义",
            "query_code": "QRY_M_BOARD",
            "formula": "y",
            "category": "48项核心制度-医疗质量",
        },
    )
    client.post(
        "/api/v1/metrics/ingest",
        json={
            "metric_code": "MET_BOARD_OTHER",
            "title": "其它类目指标",
            "definition_text": "定义",
            "query_code": "QRY_M_BOARD",
            "formula": "z",
            "category": "运营分析",
        },
    )
    resp = client.get("/api/v1/metrics/board/overview", params={"category": "48项核心制度"})
    assert resp.status_code == 200, resp.text
    codes = [m["metric_code"] for m in resp.json()["data"]["metrics"]]
    # 精确等于（原 == 分支口径）与子串包含（原 in 分支口径）都必须命中。
    assert "MET_BOARD_EXACT" in codes
    assert "MET_BOARD_SUBSTR" in codes
    assert "MET_BOARD_OTHER" not in codes


def test_board_overview_response_structure_locked(client: TestClient):
    """C4 行为不变锁：SQL 聚合改写后响应结构与 cells 字段口径一致。"""
    from app.services.metric_service import ingest_metric, register_metric_result
    from app.services.query_intake import ingest_query
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        ingest_query(db, query_code="QRY_M_BOARD2", title="看板结构",
                     sql_text="SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5",
                     system_code="DATA_CENTER", source_code="ods_8_216", dialect="oracle")
        ingest_metric(db, metric_code="MET_BOARD_STRUCT", title="结构锁定",
                      definition_text="d", query_code="QRY_M_BOARD2", formula="x",
                      category="48项核心制度", created_by="t")
        register_metric_result(db, metric_code="MET_BOARD_STRUCT", period_key="2026-01",
                               metric_value="42", numerator_value="42", denominator_value="100",
                               created_by="t")
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/metrics/board/overview", params={"category": "48项核心制度"})
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert set(body.keys()) == {"periods", "metrics", "cells", "total_results", "category"}
    assert body["category"] == "48项核心制度"
    assert "2026-01" in body["periods"]
    cell = body["cells"].get("MET_BOARD_STRUCT", {}).get("2026-01")
    if cell is not None:
        assert set(cell.keys()) == {
            "metric_value", "numerator_value", "denominator_value",
            "status", "limitations_note", "is_recalc", "run_batch",
        }
    metric = next(m for m in body["metrics"] if m["metric_code"] == "MET_BOARD_STRUCT")
    assert set(metric.keys()) == {"metric_code", "title", "unit", "status", "has_active", "query_code", "period_count"}
