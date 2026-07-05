from fastapi.testclient import TestClient


def test_collect_metadata_nonexistent_source(client: TestClient):
    resp = client.post("/api/v1/sources/nonexistent_source/collect-metadata")
    assert resp.status_code == 400


def test_list_changes(client: TestClient):
    resp = client.get("/api/v1/metadata-changes")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data


def test_list_changes_system_code_filter(client: TestClient):
    resp = client.get("/api/v1/metadata-changes?system_code=DATA_CENTER")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["system_code"] == "DATA_CENTER"


def test_list_changes_change_type_filter(client: TestClient):
    resp = client.get("/api/v1/metadata-changes?change_type=column_added")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["change_type"] == "column_added"


def test_list_changes_severity_filter(client: TestClient):
    resp = client.get("/api/v1/metadata-changes?severity=high")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["severity"] == "high"


def test_update_change_404(client: TestClient):
    resp = client.patch("/api/v1/metadata-changes/99999?status=acknowledged&assigned_to=user1")
    assert resp.status_code == 404


def test_changes_summary(client: TestClient):
    resp = client.get("/api/v1/metadata-changes/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total" in data
    assert "by_system" in data
    assert "by_type" in data
    assert "open" in data
    assert "acknowledged" in data
    assert "resolved" in data


def test_diff_nonexistent_snapshots(client: TestClient):
    resp = client.post("/api/v1/metadata-changes/diff?snapshot_id_from=99999&snapshot_id_to=99998")
    assert resp.status_code == 404


def test_diff_valid_snapshots(client: TestClient):
    r1 = client.post("/api/v1/admin/snapshots", json={"label": "diff_snap_1"})
    assert r1.status_code == 200
    id1 = r1.json()["data"]["id"]

    r2 = client.post("/api/v1/admin/snapshots", json={"label": "diff_snap_2"})
    assert r2.status_code == 200
    id2 = r2.json()["data"]["id"]

    resp = client.post(f"/api/v1/metadata-changes/diff?snapshot_id_from={id1}&snapshot_id_to={id2}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "snapshot_from" in data
    assert "snapshot_to" in data
    assert "total_changes" in data
    assert data["snapshot_from"]["id"] == id1
    assert data["snapshot_to"]["id"] == id2


def test_change_impact_404(client: TestClient):
    resp = client.get("/api/v1/metadata-changes/99999/impact")
    assert resp.status_code == 404


def test_source_snapshots(client: TestClient):
    resp = client.get("/api/v1/sources/ods_8_216/snapshots")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
