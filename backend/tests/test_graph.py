from __future__ import annotations

from fastapi.testclient import TestClient

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.asset import AssetRelation, AssetTable


def _relation_count(db: Session) -> int:
    from sqlalchemy import func
    return db.scalar(select(func.count()).select_from(AssetRelation)) or 0


def _add_test_relation(
    db: Session,
    *,
    from_table: str,
    to_table: str,
    from_columns: str,
    to_columns: str,
    confidence: str = "A",
    validation_status: str = "verified",
    join_condition: str | None = None,
    domain: str = "test",
    rel_id: int,
) -> AssetRelation:
    from app.services.relation_identity import populate_endpoint_fields
    rel = AssetRelation(
        rel_id=rel_id,
        domain=domain,
        from_table=from_table,
        from_columns=from_columns,
        to_table=to_table,
        to_columns=to_columns,
        join_condition=join_condition or f"{from_table} = {to_table}",
        cardinality="N:1",
        confidence=confidence,
        validation_level="A_rechecked" if confidence == "A" else confidence,
        validation_status=validation_status,
    )
    db.add(rel)
    populate_endpoint_fields(db, rel)
    db.commit()
    return rel
    return rel


# ── B01 默认筛选不含 A_rechecked ──────────────────────────────


def test_default_view_mode_no_phantom_status(seeded_client: TestClient) -> None:
    options = seeded_client.get("/api/v1/graph/options").json()["data"]
    table_mode = next(item for item in options["view_modes"] if item["code"] == "table")
    assert table_mode["confidence"] == "A"
    assert table_mode["validation_status"] is None
    # 默认选项不注入任何幽灵状态
    assert "A_rechecked" not in options["validation_statuses"]


def test_default_graph_only_sends_confidence_A(seeded_client: TestClient) -> None:
    """前端默认只发送 confidence=A，不带 validation_status。"""
    resp = seeded_client.get("/api/v1/graph?confidence=A&limit=50")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["meta"]["total_relations"] >= 1
    assert data["meta"]["matched_relations"] >= 1
    for e in data["edges"]:
        assert e["confidence"] == "A"


def test_phantom_status_filter_matches_zero(seeded_client: TestClient) -> None:
    """若前端仍传 validation_status=A_rechecked，应命中 0 且不炸接口。"""
    resp = seeded_client.get("/api/v1/graph?confidence=A&validation_status=A_rechecked&limit=50")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["edges"] == []
    assert data["meta"]["matched_relations"] == 0
    assert data["meta"]["returned_relations"] == 0


# ── B02 options 与数据库状态一致 ──────────────────────────────


def test_options_match_database_statuses(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        from sqlalchemy import func
        db_statuses = {
            r[0]
            for r in db.execute(
                select(AssetRelation.validation_status).distinct()
            ).all()
            if r[0]
        }
    finally:
        db.close()
    options = seeded_client.get("/api/v1/graph/options").json()["data"]
    assert set(options["validation_statuses"]) >= db_statuses
    assert "A_rechecked" not in options["validation_statuses"] or "A_rechecked" in db_statuses


# ── B03 跨系统同名表不合并 ─────────────────────────────────────


def _seed_cross_system_same_table(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        # ODS 的 HIS 镜像：schema=ODS（与 HIS 源端 schema=HIS/MEDREC 区分，避免唯一约束碰撞）
        for schema, table, src, sys_c in [
            ("ODS", "PAT_VISIT", "ods_8_216", "DATA_CENTER"),
            ("ODS", "PAT_MASTER_INDEX", "ods_8_216", "DATA_CENTER"),
        ]:
            if not db.scalar(select(AssetTable).where(
                AssetTable.schema_name == schema,
                AssetTable.table_name == table,
                AssetTable.system_code == sys_c,
                AssetTable.source_code == src,
            )):
                db.add(AssetTable(
                    schema_name=schema, table_name=table,
                    namespace_name=schema, system_code=sys_c,
                    source_code=src, column_count=2, domain="test",
                ))
        # HIS 源端：schema=MEDREC（legacy alias 真实场景）
        for schema, table in [
            ("MEDREC", "PAT_VISIT"),
            ("MEDREC", "PAT_MASTER_INDEX"),
        ]:
            if not db.scalar(select(AssetTable).where(
                AssetTable.schema_name == schema,
                AssetTable.table_name == table,
                AssetTable.system_code == "HIS",
                AssetTable.source_code == "his_source_10_10_10_15",
            )):
                db.add(AssetTable(
                    schema_name=schema, table_name=table,
                    namespace_name=schema, system_code="HIS",
                    source_code="his_source_10_10_10_15", column_count=2, domain="test",
                ))
        # ODS 镜像关系：ODS.PAT_VISIT -> ODS.PAT_MASTER_INDEX
        _add_test_relation(
            db,
            from_table="ODS.PAT_VISIT", to_table="ODS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID", to_columns="PATIENT_ID",
            rel_id=910101, confidence="A",
        )
        # HIS 源端关系：MEDREC.PAT_VISIT -> MEDREC.PAT_MASTER_INDEX
        _add_test_relation(
            db,
            from_table="MEDREC.PAT_VISIT", to_table="MEDREC.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID", to_columns="PATIENT_ID",
            rel_id=910102, confidence="A",
        )
        db.commit()
    finally:
        db.close()


def test_cross_system_same_table_two_nodes(seeded_client: TestClient) -> None:
    _seed_cross_system_same_table(seeded_client)
    resp = seeded_client.get("/api/v1/graph?confidence=A&limit=200")
    assert resp.status_code == 200
    nodes = resp.json()["data"]["nodes"]
    # 至少两个 PAT_VISIT 节点，物理键不同
    pat_visit_nodes = [n for n in nodes if n["table_name"] == "PAT_VISIT"]
    ids = {n["id"] for n in pat_visit_nodes}
    assert len(ids) >= 2
    keys = {n["physical_key"] for n in pat_visit_nodes}
    assert len(keys) == len(ids) >= 2
    # 每条边 source/target 是完整物理键
    for e in resp.json()["data"]["edges"]:
        assert "|" in e["source"]
        assert "|" in e["target"]


# ── B04 同端点不同字段关系（合法多边）─────────────────────────


def _ensure_table(db: Session, schema: str, table: str, system: str, source: str) -> None:
    if not db.scalar(select(AssetTable).where(
        AssetTable.schema_name == schema,
        AssetTable.table_name == table,
        AssetTable.system_code == system,
        AssetTable.source_code == source,
    )):
        db.add(AssetTable(
            schema_name=schema, table_name=table, namespace_name=schema,
            system_code=system, source_code=source, column_count=2, domain="test",
        ))


def test_same_endpoint_multi_edge_kept(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        _ensure_table(db, "HIS", "DIAGNOSIS", "HIS", "his_source_10_10_10_15")
        _add_test_relation(
            db, from_table="HIS.PAT_VISIT", to_table="HIS.DIAGNOSIS",
            from_columns="PATIENT_ID,VISIT_ID", to_columns="PATIENT_ID,VISIT_ID",
            rel_id=910201, confidence="A", join_condition="f1",
        )
        _add_test_relation(
            db, from_table="HIS.PAT_VISIT", to_table="HIS.DIAGNOSIS",
            from_columns="PATIENT_ID", to_columns="PATIENT_ID",
            rel_id=910202, confidence="A", join_condition="f2",
        )
        db.commit()
    finally:
        db.close()
    resp = seeded_client.get("/api/v1/graph?confidence=A&limit=200")
    assert resp.status_code == 200
    edges = resp.json()["data"]["edges"]
    same_pair = [e for e in edges
                 if e["display_source"] == "HIS.PAT_VISIT"
                 and e["display_target"] == "HIS.DIAGNOSIS"]
    assert len(same_pair) == 2
    edge_ids = {e["id"] for e in same_pair}
    assert len(edge_ids) == 2  # 边 ID 不碰撞


def test_same_endpoint_multi_edge_not_unhealthy(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        # 先清掉无物理端点的 conftest 种子关系，确保诊断口径只针对完整关系
        for rel in db.scalars(select(AssetRelation)).all():
            db.delete(rel)
        _ensure_table(db, "HIS", "DIAGNOSIS", "HIS", "his_source_10_10_10_15")
        r1 = _add_test_relation(
            db, from_table="HIS.PAT_VISIT", to_table="HIS.DIAGNOSIS",
            from_columns="PATIENT_ID,VISIT_ID", to_columns="PATIENT_ID,VISIT_ID",
            rel_id=910301, confidence="A", join_condition="f1",
        )
        r2 = _add_test_relation(
            db, from_table="HIS.PAT_VISIT", to_table="HIS.DIAGNOSIS",
            from_columns="PATIENT_ID", to_columns="PATIENT_ID",
            rel_id=910302, confidence="A", join_condition="f2",
        )
        # 显式回填物理端点字段（模拟迁移回填后的正式关系）
        for rel in (r1, r2):
            rel.from_system_code = "HIS"
            rel.from_source_code = "his_source_10_10_10_15"
            rel.from_schema_name = "HIS"
            rel.from_table_name = "PAT_VISIT"
            rel.to_system_code = "HIS"
            rel.to_source_code = "his_source_10_10_10_15"
            rel.to_schema_name = "HIS"
            rel.to_table_name = "DIAGNOSIS"
        db.commit()
    finally:
        db.close()
    resp = seeded_client.get("/api/v1/graph/diagnostics")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["same_endpoint_multi_edges"] >= 1
    # 合法多边不降低健康状态（只要业务键不重复）
    assert data["duplicate_business_keys"] == 0, data
    assert data["unresolved_endpoints"] == 0, data
    assert data["missing_physical_endpoints"] == 0, data
    assert data["healthy"] is True, data


# ── B05 缺失物理端点 → diagnostics unresolved ─────────────────


def test_missing_endpoint_unresolved(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        # 纯表名无法唯一解析物理来源，应计入 unresolved 且不进正式图
        rel = AssetRelation(
            rel_id=910401, domain="test",
            from_table="LONELY_TABLE", from_columns="ID",
            to_table="HIS.PAT_MASTER_INDEX", to_columns="PATIENT_ID",
            join_condition="x", cardinality="N:1",
            confidence="A", validation_status="verified",
        )
        db.add(rel)
        db.commit()
    finally:
        db.close()
    resp = seeded_client.get("/api/v1/graph?confidence=A&limit=200")
    data = resp.json()["data"]
    assert data["meta"]["unresolved_endpoints"] >= 1
    diag = seeded_client.get("/api/v1/graph/diagnostics").json()["data"]
    assert diag["unresolved_endpoints"] >= 1


# ── B06/B07 旧 table 参数唯一/多命中 ──────────────────────────


def test_neighbors_legacy_table_unique(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&depth=1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["edges"]) > 0
    # 邻居图至少包含 PAT_VISIT 节点（可含上下游表）
    names = {n.get("table_name") for n in data["nodes"]}
    assert "PAT_VISIT" in names


def test_neighbors_legacy_table_ambiguous_409(seeded_client: TestClient) -> None:
    _seed_cross_system_same_table(seeded_client)
    # HIS.PAT_VISIT 的 aliases 同时命中 HIS 源端(HIS.PAT_VISIT)与 MEDREC 源端(MEDREC.PAT_VISIT)
    resp = seeded_client.get("/api/v1/graph/neighbors?table=HIS.PAT_VISIT&depth=1")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "candidates" in detail
    assert len(detail["candidates"]) >= 2


def test_neighbors_physical_key(seeded_client: TestClient) -> None:
    resp = seeded_client.get(
        "/api/v1/graph/neighbors?physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT&depth=1"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["edges"]) > 0


# ── B08 邻居方向 ──────────────────────────────────────────────


def test_neighbors_direction_in(seeded_client: TestClient) -> None:
    # 种子：PAT_VISIT -> PAT_MASTER_INDEX，所以 in 应指向 PAT_VISIT 被引用
    resp = seeded_client.get(
        "/api/v1/graph/neighbors?physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT&direction=in&depth=1"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    for e in data["edges"]:
        assert e["target"].startswith("HIS|his_source_10_10_10_15||HIS|PAT_VISIT")


def test_neighbors_direction_out(seeded_client: TestClient) -> None:
    resp = seeded_client.get(
        "/api/v1/graph/neighbors?physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT&direction=out&depth=1"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    for e in data["edges"]:
        assert e["source"].startswith("HIS|his_source_10_10_10_15||HIS|PAT_VISIT")


def test_neighbors_direction_both(seeded_client: TestClient) -> None:
    resp = seeded_client.get(
        "/api/v1/graph/neighbors?physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT&direction=both&depth=1"
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["edges"]) > 0


# ── B09 limit 与 truncated ────────────────────────────────────


def test_limit_truncated(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        for i in range(30):
            # 使用已存在的种子表，但每条的字段映射/条件不同 → 不同业务键
            _add_test_relation(
                db,
                from_table="HIS.PAT_VISIT", to_table="HIS.LAB_TEST_MASTER",
                from_columns=f"PATIENT_ID,VISIT_ID,{i}", to_columns=f"PATIENT_ID,VISIT_ID,{i}",
                rel_id=910500 + i, confidence="A", join_condition=f"j{i}",
            )
        db.commit()
    finally:
        db.close()
    resp = seeded_client.get("/api/v1/graph?confidence=A&limit=5")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["edges"]) == 5
    assert data["meta"]["returned_relations"] == 5
    assert data["meta"]["matched_relations"] > 5
    assert data["meta"]["truncated"] is True


# ── B10 diagnostics 健康口径 ──────────────────────────────────


def test_diagnostics_healthy_true(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/diagnostics")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["relation_count"] >= 1
    assert "backend_build_id" in data
    assert "data_version" in data


# ── B11 Pydantic 契约：关键字段不被丢弃 ───────────────────────


def test_graph_node_contract_fields(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "meta" in data
    for node in data["nodes"]:
        assert "physical_key" in node
        assert "display_id" in node
        assert node["id"] == node["physical_key"]
        assert "|" in node["id"]
    for e in data["edges"]:
        assert "display_source" in e
        assert "display_target" in e
        assert "db_id" in e
        assert "|" in e["source"]
        assert "|" in e["target"]


def test_graph_edge_stable_id(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=10")
    assert resp.status_code == 200
    for e in resp.json()["data"]["edges"]:
        # 边 ID 不依赖数据库自增 id（不以 formal: 前缀的 id 结尾）
        assert not e["id"].startswith("formal:")


def test_options_has_backend_build_id(seeded_client: TestClient) -> None:
    data = seeded_client.get("/api/v1/graph/options").json()["data"]
    assert "backend_build_id" in data
    assert data["default_mode"] == "table"


def test_options_keep_codes_and_expose_canonical_labels(seeded_client: TestClient) -> None:
    data = seeded_client.get("/api/v1/graph/options").json()["data"]
    assert all(isinstance(value, str) for value in data["systems"])
    assert all({"value", "label"}.issubset(item) for item in data["system_options"])
    assert all({"value", "label"}.issubset(item) for item in data["source_options"])


def test_edge_detail_endpoint(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph?limit=5")
    assert resp.status_code == 200
    edges = resp.json()["data"]["edges"]
    assert edges
    detail = seeded_client.get(f"/api/v1/graph/edges/{edges[0]['id']}")
    assert detail.status_code == 200
    edge = detail.json()["data"]
    assert "field_mappings" in edge
    assert edge["id"] == edges[0]["id"]


def test_namespace_compatible_enrichment_preserves_cn_name_and_domain(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        table = db.scalar(select(AssetTable).where(
            AssetTable.system_code == "HIS",
            AssetTable.source_code == "his_source_10_10_10_15",
            AssetTable.schema_name == "HIS",
            AssetTable.table_name == "PAT_VISIT",
        ))
        assert table is not None
        table.namespace_name = "HIS"
        table.table_name_cn = "病人住院主记录"
        table.domain = "就诊"
        # 关系端点 namespace 保持历史 NULL，模拟生产中的兼容富化场景。
        rel = db.scalar(select(AssetRelation).where(AssetRelation.rel_id == 900001))
        assert rel is not None
        rel.from_namespace_name = None
        rel.to_namespace_name = None
        db.commit()
    finally:
        db.close()
    data = seeded_client.get("/api/v1/graph?confidence=A&limit=20").json()["data"]
    node = next(item for item in data["nodes"] if item["table_name"] == "PAT_VISIT")
    assert node["table_name_cn"] == "病人住院主记录"
    assert node["business_domain"] == "就诊"
    assert node["metadata_match"] == "namespace_compatible"
    assert data["meta"]["enrichment"]["namespace_compatible"] >= 1


def test_server_side_overview_and_cascade_contract(seeded_client: TestClient) -> None:
    overview = seeded_client.get("/api/v1/graph/overview?level=system&limit=80")
    assert overview.status_code == 200
    body = overview.json()["data"]
    assert body["level"] == "system"
    assert body["next_level"] == "source"
    assert body["data"]["nodes"]
    assert body["data"]["meta"]["returned_nodes"] == len(body["data"]["nodes"])

    options = seeded_client.get("/api/v1/graph/filter-options?next_level=source&system_code=HIS")
    assert options.status_code == 200
    values = {item["value"] for item in options.json()["data"]["items"]}
    assert "his_source_10_10_10_15" in values

    objects = seeded_client.get(
        "/api/v1/graph/overview"
        "?level=object&system_code=HIS"
        "&source_code=his_source_10_10_10_15&schema=HIS&limit=80"
    )
    assert objects.status_code == 200
    object_data = objects.json()["data"]
    assert object_data["next_level"] == "field"
    assert all(not node["is_aggregate"] for node in object_data["data"]["nodes"])
    assert all(edge["relation_type"] != "hierarchy" for edge in object_data["data"]["edges"])
    assert any(edge["from_columns"] == "PATIENT_ID" for edge in object_data["data"]["edges"])


def test_field_overview_uses_physical_source_and_marks_keys(seeded_client: TestClient) -> None:
    db = SessionLocal()
    try:
        table = db.scalar(select(AssetTable).where(
            AssetTable.system_code == "HIS",
            AssetTable.source_code == "his_source_10_10_10_15",
            AssetTable.schema_name == "HIS",
            AssetTable.table_name == "PAT_VISIT",
        ))
        assert table is not None
        table.pk = "PATIENT_ID+VISIT_ID"
        db.commit()
    finally:
        db.close()

    resp = seeded_client.get(
        "/api/v1/graph/overview"
        "?level=field"
        "&parent_physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT"
        "&limit=80"
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["level"] == "field"
    assert body["next_level"] is None
    assert body["selected_path"]["object"] == "PAT_VISIT"

    nodes = body["data"]["nodes"]
    center = next(node for node in nodes if node["category"] == "table")
    fields = [node for node in nodes if node["category"] == "field"]
    assert center["physical_key"].endswith("|HIS|PAT_VISIT")
    assert {node["column_name"] for node in fields} >= {"PATIENT_ID", "VISIT_ID"}
    assert all(node["system_code"] == "HIS" for node in fields)
    assert all(node["source_code"] == "his_source_10_10_10_15" for node in fields)
    assert all(node["object_type"] == "column" for node in fields)
    assert all(node["is_primary_key"] for node in fields if node["column_name"] in {"PATIENT_ID", "VISIT_ID"})
    patient_id = next(node for node in fields if node["column_name"] == "PATIENT_ID")
    assert patient_id["is_relation_key"] is True
    assert body["data"]["meta"]["center_physical_key"] == center["physical_key"]
    assert len(body["data"]["edges"]) == len(fields)


def test_field_overview_requires_complete_table_physical_key(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/overview?level=field")
    assert resp.status_code == 422


def test_table_search_returns_physical_key_and_disambiguation(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/v1/graph/tables/search?q=PAT_VISIT&limit=30")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert items
    assert all(item["physical_key"].count("|") == 4 for item in items)
    assert all(item["technical_name"] for item in items)


def test_neighbors_center_physical_key_alias(seeded_client: TestClient) -> None:
    resp = seeded_client.get(
        "/api/v1/graph/neighbors?center_physical_key=HIS|his_source_10_10_10_15||HIS|PAT_VISIT&depth=1"
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["meta"]["center_physical_key"].endswith("|PAT_VISIT")
