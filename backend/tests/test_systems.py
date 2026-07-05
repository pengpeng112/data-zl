def test_upsert_system(client):
    resp = client.put("/api/v1/systems", json={
        "system_code": "DATA_CENTER",
        "system_name_cn": "数据中心",
        "system_type": "ODS",
        "description_cn": "8.216 数据中心 ODS 汇聚库",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["system_code"] == "DATA_CENTER"

    resp = client.put("/api/v1/systems", json={
        "system_code": "DATA_CENTER",
        "system_name_cn": "数据中心(已更新)",
    })
    assert resp.status_code == 200


def test_list_systems(client):
    test_upsert_system(client)
    resp = client.get("/api/v1/systems")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert any(s["system_code"] == "DATA_CENTER" for s in items)


def test_upsert_source(client):
    resp = client.put("/api/v1/sources", json={
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "source_name_cn": "8.216 ODS 汇聚库",
        "db_type": "oracle",
        "host_masked": "10.10.8.216",
        "port": 1521,
        "service_name": "orcl",
        "environment": "prod",
        "collect_mode": "metadata_only",
    })
    assert resp.status_code == 200

    resp = client.put("/api/v1/sources", json={
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "source_name_cn": "8.216 ODS(已更新)",
    })
    assert resp.status_code == 200


def test_upsert_source_no_system(client):
    resp = client.put("/api/v1/sources", json={
        "system_code": "NONEXISTENT",
        "source_code": "test_x",
        "source_name_cn": "测试",
    })
    assert resp.status_code == 400


def test_list_sources(client):
    test_upsert_source(client)
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert any(s["source_code"] == "ods_8_216" for s in items)


def test_check_source(client):
    resp = client.post("/api/v1/sources/ods_8_216/check")
    assert resp.status_code == 200
    assert resp.json()["data"]["source_code"] == "ods_8_216"


def test_assets_tree(client):
    resp = client.get("/api/v1/assets/tree")
    assert resp.status_code == 200
    tree = resp.json()["data"]
    assert isinstance(tree, list)


def test_delete_source(client):
    resp = client.delete("/api/v1/sources/ods_8_216")
    assert resp.status_code == 200
    resp = client.delete("/api/v1/systems/DATA_CENTER")
    assert resp.status_code == 200
