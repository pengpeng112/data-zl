"""177 R2 回归测试：173 P2-1（新建系统列表可见性）与 P3-5（配方 create 表标识校验）。

- P2-1 实测根因：list_first_level_systems 的非 CANONICAL 分区返回了 upper() 规范化
  后的编码，用户按原始编码回查不可见、详情导航 404。修复后必须原样返回库内编码。
- P3-5：create 配方接受任意 primary_tables 键，错误拖到生成 SQL 才 400；修复后
  create 时非法标识直接 422。
"""
from __future__ import annotations


def test_non_canonical_system_readback_keeps_stored_code(client):
    """PUT 混合大小写系统 → GET 列表按原始编码可见且详情可达（173 P2-1）。"""
    code = "r177MixedCase"
    r = client.put("/api/v1/systems", json={
        "system_code": code,
        "system_name_cn": "r177混合编码系统",
        "system_type": "HIS",
    })
    assert r.status_code == 200, r.text
    items = client.get("/api/v1/systems").json()["data"]
    codes = [s["system_code"] for s in items]
    assert code in codes, f"readback missing {code}: {codes}"
    entry = next(s for s in items if s["system_code"] == code)
    assert entry["is_canonical"] is False
    # 前端用列表返回编码直达详情（systems/index.vue openDetail）
    assert client.get(f"/api/v1/systems/{code}/detail").status_code == 200


def test_canonical_systems_ordered_before_non_canonical(client):
    """预置系统仍排在非 CANONICAL 分区之前（177 C2 产品裁决）。"""
    client.put("/api/v1/systems", json={
        "system_code": "r177Extra", "system_name_cn": "r177非预置", "system_type": "HIS",
    })
    client.put("/api/v1/systems", json={
        "system_code": "HIS_SOURCE", "system_name_cn": "HIS", "system_type": "HIS",
    })
    client.post("/api/v1/systems/HIS_SOURCE/connections", json={
        "source_code": "r177_his_src", "source_name_cn": "r177连接",
        "db_type": "oracle", "target_host": "10.10.10.177", "port": 1521,
        "service_name": "x", "write_policy": "readonly",
    })
    items = client.get("/api/v1/systems").json()["data"]
    codes = [s["system_code"] for s in items]
    assert "HIS_SOURCE" in codes and "r177Extra" in codes
    assert codes.index("HIS_SOURCE") < codes.index("r177Extra")


def test_recipe_create_rejects_invalid_table_identifiers(client):
    """非法 primary_tables 在 create 即 422，不再拖到 SQL 生成才 400（173 P3-5）。"""
    r = client.post("/api/v1/recipes", json={
        "recipe_id": "r177-bad-tables",
        "recipe_name": "r177非法表标识",
        "primary_tables": ["HIS.PAT_VISIT", {"table": "DROP TABLE x; --"}],
        "joins": [],
    })
    assert r.status_code == 422, r.text


def test_recipe_create_accepts_valid_and_empty_tables(client):
    """合法标识 200；空表清单仍是合法草稿（不因收紧校验误伤）。"""
    r = client.post("/api/v1/recipes", json={
        "recipe_id": "r177-ok-tables",
        "recipe_name": "r177合法表标识",
        "primary_tables": ["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"],
        "joins": [{"join_type": "LEFT", "on": "HIS.PAT_VISIT.PATIENT_ID = HIS.PAT_MASTER_INDEX.PATIENT_ID"}],
    })
    assert r.status_code == 200, r.text
    r2 = client.post("/api/v1/recipes", json={
        "recipe_id": "r177-empty-tables", "recipe_name": "r177空表草稿",
    })
    assert r2.status_code == 200, r2.text
