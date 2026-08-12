"""126 P1 integration tests for query ingest / versions / idempotency."""
from __future__ import annotations

from fastapi.testclient import TestClient


SAFE_SQL = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"
BLOCK_SQL = "DELETE FROM HIS.PAT_VISIT"


def test_gate_preview(client: TestClient):
    ok = client.post("/api/v1/queries/gate", json={"sql_text": SAFE_SQL, "dialect": "oracle"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "validated"

    bad = client.post("/api/v1/queries/gate", json={"sql_text": BLOCK_SQL, "dialect": "oracle"})
    assert bad.status_code == 200
    assert bad.json()["data"]["status"] == "blocked"


def test_ingest_auto_activates_and_idempotent(client: TestClient):
    payload = {
        "query_code": "QRY_P1_TEST_PAT_VISIT",
        "title": "测试住院患者抽样",
        "sql_text": SAFE_SQL,
        "purpose": "126 P1 测试",
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "dialect": "oracle",
    }
    r1 = client.post("/api/v1/queries/ingest", json=payload)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["activated"] is True or d1.get("idempotent")
    assert d1["version"]["status"] == "active"
    assert d1["version"]["is_active"] is True
    ver = d1["version"]["version"]
    sha = d1["version"]["sql_sha256"]

    r2 = client.post("/api/v1/queries/ingest", json=payload)
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["idempotent"] is True
    assert d2["version"]["sql_sha256"] == sha
    assert d2["version"]["version"] == ver


def test_ingest_blocked_not_active(client: TestClient):
    payload = {
        "query_code": "QRY_P1_BLOCKED",
        "title": "应被门禁阻断",
        "sql_text": BLOCK_SQL,
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "dialect": "oracle",
    }
    r = client.post("/api/v1/queries/ingest", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["version"]["status"] == "blocked"
    assert d["version"]["is_active"] is False
    assert d.get("activated") is not True


def test_revise_creates_new_version(client: TestClient):
    base = {
        "query_code": "QRY_P1_REVISE",
        "title": "修订测试",
        "sql_text": SAFE_SQL,
        "system_code": "HIS",
        "source_code": "his_source",
        "dialect": "oracle",
    }
    assert client.post("/api/v1/queries/ingest", json=base).status_code == 200
    new_sql = "SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"
    r = client.post(
        "/api/v1/queries/QRY_P1_REVISE/revise",
        json={"sql_text": new_sql, "revision_reason": "增加就诊次数字段"},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["version"]["version"] >= 2
    assert d["version"]["is_active"] is True
    assert d["version"]["revision_reason"]


def test_list_and_detail(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_P1_LIST",
            "title": "列表测试",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
        },
    )
    lst = client.get("/api/v1/queries", params={"keyword": "QRY_P1_LIST"})
    assert lst.status_code == 200
    assert lst.json()["data"]["total"] >= 1
    detail = client.get("/api/v1/queries/QRY_P1_LIST")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["definition"]["query_code"] == "QRY_P1_LIST"
    assert body["active_version"] is not None


def test_ai_context(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_P1_CTX",
            "title": "上下文测试",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
        },
    )
    r = client.get("/api/v1/queries/ai/context")
    assert r.status_code == 200
    codes = [x["query_code"] for x in r.json()["data"]]
    assert "QRY_P1_CTX" in codes


def test_run_without_source_fails_gracefully(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_P1_RUN_NOSRC",
            "title": "无连接执行",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
        },
    )
    r = client.post(
        "/api/v1/queries/run",
        json={"query_code": "QRY_P1_RUN_NOSRC", "result_storage": "none"},
    )
    # missing source or source not found → 400/404
    assert r.status_code in (400, 404)
