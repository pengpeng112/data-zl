"""108 号 GraphNode/GraphEdge JSON 契约固化测试。

目标：physical_key/display_id/meta 等关键字段绝不能被 Pydantic 静默丢弃；
schema 采用 extra="forbid"，多字段会被序列化拦截。
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.graph import GraphData, GraphEdge, GraphMeta, GraphNode


# ── GraphNode 契约 ─────────────────────────────────────────────


def test_graphnode_contract_fields_present():
    node = GraphNode(
        id="DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
        physical_key="DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
        display_id="HIS.PAT_VISIT",
        label="就诊主表",
        system_code="DATA_CENTER",
        source_code="ods_8_216",
        namespace_name="",
        schema_name="HIS",
        table_name="PAT_VISIT",
    )
    payload = node.model_dump()
    assert payload["id"] == payload["physical_key"]
    assert payload["display_id"] == "HIS.PAT_VISIT"
    assert payload["system_code"] == "DATA_CENTER"
    assert payload["source_code"] == "ods_8_216"
    assert payload["schema_name"] == "HIS"
    assert payload["table_name"] == "PAT_VISIT"


def test_graphnode_forbid_unknown_fields():
    """extra="forbid"：未知字段必须被拒绝，防止静默丢弃契约外字段。"""
    try:
        GraphNode(id="x", label="y", unknown_ghost_field="z")
        raised = False
    except ValidationError:
        raised = True
    assert raised


def test_graphnode_physical_key_matches_contract_example():
    node = GraphNode.model_validate({
        "id": "DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
        "physical_key": "DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
        "display_id": "HIS.PAT_VISIT",
        "label": "x",
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "namespace_name": "",
        "schema_name": "HIS",
        "table_name": "PAT_VISIT",
    })
    assert node.id == "DATA_CENTER|ods_8_216||HIS|PAT_VISIT"


# ── GraphEdge 契约 ─────────────────────────────────────────────


def test_graphedge_contract_fields_present():
    edge = GraphEdge(
        id="biz-key-1",
        source="DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
        target="DATA_CENTER|ods_8_216||HIS|DIAGNOSIS",
        display_source="HIS.PAT_VISIT",
        display_target="HIS.DIAGNOSIS",
        relation_type="formal",
        db_id=1,
        rel_id=900001,
    )
    payload = edge.model_dump()
    assert payload["source"].startswith("DATA_CENTER|ods_8_216|")
    assert payload["display_source"] == "HIS.PAT_VISIT"
    assert payload["db_id"] == 1
    assert payload["relation_layer"] is None


def test_graphedge_forbid_unknown_fields():
    try:
        GraphEdge(id="x", source="a", target="b", ghost_field="z")
        raised = False
    except ValidationError:
        raised = True
    assert raised


def test_graphedge_stable_id_contract():
    """边 ID 使用稳定业务键；数据库自增 id 只作为 db_id 属性。"""
    edge = GraphEdge(
        id="relation_business_key",
        source="a", target="b",
        db_id=12345,
        rel_id=54321,
    )
    assert edge.id == "relation_business_key"
    assert edge.db_id == 12345
    assert edge.rel_id == 54321


# ── GraphMeta / GraphData 契约 ─────────────────────────────────


def test_graph_meta_contract():
    meta = GraphMeta(
        total_relations=537,
        matched_relations=192,
        returned_relations=120,
        truncated=True,
        unresolved_endpoints=0,
        filters={"confidence": "A"},
        data_version="sha-abc",
        backend_build_id="build-1",
    )
    payload = meta.model_dump()
    assert payload["total_relations"] == 537
    assert payload["matched_relations"] == 192
    assert payload["returned_relations"] == 120
    assert payload["truncated"] is True
    assert payload["filters"] == {"confidence": "A"}
    assert payload["backend_build_id"] == "build-1"


def test_graph_data_contract_meta_required_fields():
    data = GraphData(nodes=[], edges=[], meta=GraphMeta())
    payload = data.model_dump()
    assert "meta" in payload
    assert payload["meta"]["total_relations"] == 0
    assert payload["meta"]["truncated"] is False


def test_graph_data_meta_optional():
    data = GraphData(nodes=[], edges=[])
    assert data.meta is None


# ── 通过 HTTP 验证响应序列化（含 meta）────────────────────────


def test_graph_response_includes_meta(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert {"nodes", "edges", "meta"}.issubset(data.keys())
    meta = data["meta"]
    for field in (
        "total_relations", "matched_relations", "returned_relations",
        "truncated", "filters", "data_version", "backend_build_id",
        "unresolved_endpoints",
    ):
        assert field in meta


def test_options_response_contract(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for field in (
        "systems", "sources", "schemas", "domains",
        "validation_statuses", "confidences", "relation_types",
        "view_modes", "default_mode", "backend_build_id",
    ):
        assert field in data
    mode = data["view_modes"][0]
    for field in (
        "code", "label", "group_by", "layout_mode", "confidence",
        "validation_status", "include_candidates", "include_dependencies",
        "show_review_layer", "requires_table",
    ):
        assert field in mode


def test_neighbors_response_contract(seeded_client: TestClient) -> None:
    resp = seeded_client.get(
        "/api/v1/graph/neighbors?physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT&depth=1"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {"nodes", "edges", "meta"}.issubset(data.keys())
