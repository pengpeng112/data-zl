"""126 P3 + core-48 import tests."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.core_metric_import import parse_metric_sql_file, discover_core_sql_files
from app.services.query_relation_extract import extract_join_candidates


def test_parse_core_sql_files_discoverable():
    files = discover_core_sql_files()
    assert len(files) >= 10
    sample = parse_metric_sql_file(files[0])
    assert sample["query_code"].startswith("QRY_CORE_")
    assert sample["metric_code"].startswith("MET_CORE_")
    assert "SELECT" in sample["sql_text"].upper() or "WITH" in sample["sql_text"].upper()
    assert sample["title"]


def test_extract_join_candidates_unit():
    sql = """
    SELECT a.patient_id
    FROM HIS.PAT_VISIT a
    LEFT JOIN HIS.PAT_MASTER_INDEX b ON a.PATIENT_ID = b.PATIENT_ID
    WHERE ROWNUM <= 10
    """
    cands = extract_join_candidates(sql)
    assert len(cands) >= 1
    assert cands[0]["from_column"] == "PATIENT_ID"
    assert cands[0]["formal"] is False


def test_core_import_dry_run_api(client: TestClient):
    r = client.post("/api/v1/queries/import/core-48", json={"dry_run": True})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["dry_run"] is True
    assert data["count"] >= 10


def test_core_import_apply_and_impact(client: TestClient):
    r = client.post(
        "/api/v1/queries/import/core-48",
        json={"dry_run": False, "only_numbers": [3, 4]},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["count"] == 2
    assert data["items"][0]["query"]["status"] in {"active", "blocked", "candidate"}

    # impact on PAT_VISIT
    imp = client.get(
        "/api/v1/queries/impact/table",
        params={"table_name": "PAT_VISIT", "schema_name": "HIS"},
    )
    assert imp.status_code == 200
    body = imp.json()["data"]
    assert body["query_count"] >= 1

    # relation candidates
    qc = data["items"][0]["query_code"]
    rc = client.get(f"/api/v1/queries/{qc}/relation-candidates")
    assert rc.status_code == 200
    assert "candidates" in rc.json()["data"]


def test_schedule_defaults_disabled(client: TestClient):
    r = client.post(
        "/api/v1/queries/schedules",
        json={
            "query_code": "QRY_CORE_03",
            "schedule_cron": "0 4 * * *",
            "enabled": False,
            "source_code": "ods_8_216",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["enabled"] is False
    lst = client.get("/api/v1/queries/schedules/list")
    assert lst.status_code == 200
    assert any(x["query_code"] == "QRY_CORE_03" for x in lst.json()["data"])
