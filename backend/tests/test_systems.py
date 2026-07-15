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
    client.put("/api/v1/systems", json={
        "system_code": "DATA_CENTER",
        "system_name_cn": "数据中心",
    })
    resp = client.put("/api/v1/sources", json={
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "source_name_cn": "8.216 ODS 汇聚库",
        "db_type": "oracle",
        "target_host": "10.10.8.216",
        "port": 1521,
        "service_mode": "service_name",
        "service_name": "orcl",
        "environment": "prod",
        "collect_mode": "metadata_only",
        "write_policy": "readonly",
    })
    assert resp.status_code == 200

    resp = client.put("/api/v1/sources", json={
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "source_name_cn": "8.216 ODS(已更新)",
        "db_type": "oracle",
        "target_host": "10.10.8.216",
        "port": 1521,
        "service_name": "orcl",
    })
    assert resp.status_code == 200


def test_upsert_source_no_system(client):
    resp = client.put("/api/v1/sources", json={
        "system_code": "NONEXISTENT",
        "source_code": "test_x",
        "source_name_cn": "测试",
        "db_type": "oracle",
        "target_host": "10.0.0.1",
        "port": 1521,
        "service_name": "orcl",
    })
    assert resp.status_code == 400


def test_list_sources(client):
    test_upsert_source(client)
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert any(s["source_code"] == "ods_8_216" for s in items)
    # password / credential_ref never exposed
    assert "credential_ref" not in items[0]
    assert "password" not in items[0]


def test_check_source(client):
    test_upsert_source(client)
    resp = client.post("/api/v1/sources/ods_8_216/check")
    assert resp.status_code == 200
    assert resp.json()["data"]["source_code"] == "ods_8_216"


def test_assets_tree(client):
    resp = client.get("/api/v1/assets/tree")
    assert resp.status_code == 200
    tree = resp.json()["data"]
    assert isinstance(tree, list)


def test_delete_source_soft(client):
    test_upsert_source(client)
    resp = client.delete("/api/v1/sources/ods_8_216")
    assert resp.status_code == 200
    assert resp.json()["data"]["action"] == "disabled"


def test_create_system_with_connections(client, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_CREDENTIAL_DIR", str(tmp_path))
    resp = client.post("/api/v1/systems-with-connections", json={
        "system_code": "NEW_SYS",
        "system_name_cn": "新系统",
        "system_type": "business",
        "connections": [{
            "source_code": "new_sys_pg",
            "source_name_cn": "PG",
            "db_type": "postgresql",
            "target_host": "10.1.2.3",
            "port": 5432,
            "database_name": "appdb",
            "username": "readonly_user",
            "password": "not-echoed",
            "write_policy": "readonly",
        }],
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["system_code"] == "NEW_SYS"
    assert "new_sys_pg" in data["sources"]

    detail = client.get("/api/v1/systems/NEW_SYS/detail")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["connection_count"] == 1
    conn = body["connections"][0]
    assert conn["credential_configured"] is True
    assert "password" not in conn
    assert conn.get("credential_username_masked")


def test_connection_identity_conflict(client):
    client.put("/api/v1/systems", json={"system_code": "S1", "system_name_cn": "S1"})
    payload = {
        "system_code": "S1",
        "source_code": "s1_a",
        "source_name_cn": "A",
        "db_type": "mysql",
        "target_host": "10.9.9.9",
        "port": 3306,
        "database_name": "db1",
        "write_policy": "readonly",
    }
    assert client.put("/api/v1/sources", json=payload).status_code == 200
    payload2 = {**payload, "source_code": "s1_b", "source_name_cn": "B"}
    resp = client.put("/api/v1/sources", json=payload2)
    assert resp.status_code == 409


def test_db_types(client):
    resp = client.get("/api/v1/db-types")
    assert resp.status_code == 200
    types = {x["db_type"] for x in resp.json()["data"]}
    assert types == {"oracle", "mysql", "sqlserver", "vastbase", "postgresql"}


def test_soft_disable_system_keeps_sources(client):
    test_upsert_source(client)
    resp = client.delete("/api/v1/systems/DATA_CENTER")
    assert resp.status_code == 200
    assert resp.json()["data"]["action"] == "soft_disabled"
    # source still exists (disabled)
    sources = client.get("/api/v1/sources").json()["data"]
    assert any(s["source_code"] == "ods_8_216" for s in sources)
