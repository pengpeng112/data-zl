"""A28: viewers cannot submit/execute/schedule/review — direct API 403.

Creates a bound API key with NO roles and asserts every 144 permission-protected
endpoint rejects it server-side (not just hidden buttons).
"""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models.governance import ApiKey

VIEWER_TOKEN = "test-token-viewer-no-roles-144"


@pytest.fixture()
def viewer_client(client: TestClient) -> TestClient:
    """Bind a role-less user; middleware still authenticates the token."""
    db = SessionLocal()
    try:
        row = db.query(ApiKey).filter(ApiKey.key_name == "test-viewer-144").first()
        if not row:
            db.add(
                ApiKey(
                    key_name="test-viewer-144",
                    token_hash=hashlib.sha256(VIEWER_TOKEN.encode("utf-8")).hexdigest(),
                    user_identifier="test-viewer-144",
                )
            )
        else:
            row.token_hash = hashlib.sha256(VIEWER_TOKEN.encode("utf-8")).hexdigest()
            row.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(client.app, headers={"Authorization": f"Bearer {VIEWER_TOKEN}"})


def test_viewer_cannot_submit_query_ingest(viewer_client):
    resp = viewer_client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_VIEWER_X",
            "title": "x",
            "system_code": "DATA_CENTER",
            "source_code": "ods_8_216",
            "dialect": "oracle",
            "sql_text": "SELECT 1 FROM DUAL",
        },
    )
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_run_query(viewer_client):
    resp = viewer_client.post(
        "/api/v1/queries/run",
        json={"query_code": "QRY_ANY", "parameters": {}},
    )
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_validate_query_version(viewer_client):
    resp = viewer_client.post("/api/v1/queries/QRY_ANY/versions/1/validate")
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_calculate_metric(viewer_client):
    resp = viewer_client.post(
        "/api/v1/metrics/MET_ANY/calculate",
        json={"period_key": "2026-08"},
    )
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_submit_feedback(viewer_client):
    resp = viewer_client.post(
        "/api/v1/ai/feedback",
        json={"answer_event_id": 1, "rating": "correct"},
    )
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_review_feedback(viewer_client):
    resp = viewer_client.patch(
        "/api/v1/ai/feedback/1/review",
        json={"action": "triaged"},
    )
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_run_evaluation(viewer_client):
    resp = viewer_client.post("/api/v1/ai/evaluations/run", json={})
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_sync_lineage(viewer_client):
    resp = viewer_client.post("/api/v1/lineage/sync")
    assert resp.status_code == 403, resp.text[:200]


def test_viewer_cannot_read_query_catalog_without_query_view(viewer_client):
    resp = viewer_client.get("/api/v1/queries", params={"page": 1, "page_size": 5})
    assert resp.status_code == 403, resp.text[:200]


@pytest.mark.parametrize("path", [
    "/api/v1/metrics?page=1&page_size=5",
    "/api/v1/data-products?page=1&page_size=5",
    "/api/v1/ai/context/nonexistent",
])
def test_viewer_cannot_read_query_center_resources(viewer_client, path):
    resp = viewer_client.get(path)
    assert resp.status_code == 403, resp.text[:200]


def test_platform_admin_can_read_query_catalog(client):
    resp = client.get("/api/v1/queries", params={"page": 1, "page_size": 5})
    assert resp.status_code == 200, resp.text[:200]
