def test_backfill_p6(client):
    resp = client.post("/api/v1/admin/init/backfill-p6")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["table_count"] > 0
    assert data["system_count"] == 1
    assert data["source_count"] == 1
