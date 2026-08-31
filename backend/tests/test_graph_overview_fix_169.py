"""169 G1：overview 聚合性能护栏与 meta 口径（round-3 P1/P5 修复的回归锁）。

- P1：聚合分支必须复用 _EndpointResolver（源码断言防 N+1 回归——12702 表规模下曾 23.5s）。
- P5：非 object 层 meta.total_relations/matched_relations 填真实关系数（此前误填表数），
  truncated=聚合去重落差；跨系统关系在 system 层产出聚合边。
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.asset import AssetRelation

GRAPH_SRC = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "graph.py"


def _seed_cross_system_relation() -> None:
    """conftest 种子是 HIS 内部关系（system 层 f_id==t_id 不出边）——补一条跨系统关系。"""
    db = SessionLocal()
    try:
        if db.scalar(select(AssetRelation).where(AssetRelation.rel_id == 916901)):
            return
        rel = AssetRelation(
            rel_id=916901,
            domain="test",
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID",
            to_table="ODS.TEST_ASSET",
            to_columns="ASSET_ID",
            join_condition="HIS.PAT_VISIT.PATIENT_ID = ODS.TEST_ASSET.ASSET_ID",
            cardinality="N:1",
            confidence="B",
            validation_level="B",
            validation_status="verified",
        )
        from app.services.relation_identity import populate_endpoint_fields

        db.add(rel)
        db.flush()
        populate_endpoint_fields(db, rel)
        db.commit()
    finally:
        db.close()


def test_aggregation_branch_reuses_endpoint_resolver_source_guard():
    """P1 源码护栏：聚合循环必须传 resolver=（防 N+1 回归，plan146 式断言）。"""
    src = GRAPH_SRC.read_text(encoding="utf-8-sig")
    # 聚合分支（pair_counts 循环）内的两处端点解析必须带 resolver
    assert 'resolver=endpoint_resolver)\n                t_sys' in src.replace("\r\n", "\n"), (
        "聚合分支 _resolve_relation_endpoint 须复用 endpoint_resolver（169 P1）"
    )
    assert "endpoint_resolver = _EndpointResolver.load(db)" in src
    # 禁止再出现不带 resolver 的聚合调用形（宽松匹配：循环体内裸调用）
    assert src.count("_resolve_relation_endpoint(db, rel, ") - src.count("resolver=") <= 1


def test_overview_system_meta_counts_relations_not_tables(seeded_client: TestClient):
    """P5：total/matched 是关系数不是表数。"""
    _seed_cross_system_relation()
    resp = seeded_client.get("/api/v1/graph/overview?level=system")
    assert resp.status_code == 200
    data = resp.json()["data"]["data"]
    meta = data["meta"]
    tables = {n["id"] for n in data["nodes"]}
    # conftest 种子含 HIS/DATA_CENTER 两系统节点
    assert len(tables) >= 2
    # 关系总数 = 3 条种子关系（900001/900002 HIS 内 + 916901 跨系统），绝非表数 4
    assert meta["total_relations"] == 3, meta
    # 跨系统关系在 system 层聚合出 1 条边；matched=参与配对的关系数
    assert meta["returned_relations"] == len(data["edges"]) == 1
    assert meta["matched_relations"] == 1
    assert meta["truncated"] is False


def test_overview_empty_relations_meta_safe(seeded_client: TestClient):
    """无关系时口径安全（不 5xx，total=0/matched=0）。"""
    db = SessionLocal()
    try:
        db.query(AssetRelation).delete()
        db.commit()
    finally:
        db.close()
    resp = seeded_client.get("/api/v1/graph/overview?level=system")
    assert resp.status_code == 200
    meta = resp.json()["data"]["data"]["meta"]
    assert meta["total_relations"] == 0
    assert meta["matched_relations"] == 0
    assert meta["returned_relations"] == 0
    assert meta["truncated"] is False


def test_overview_schema_level_aggregation_still_correct(seeded_client: TestClient):
    """P1 修复不改变聚合行为：schema 层（走同一 resolver 路径）跨系统边仍产出。"""
    _seed_cross_system_relation()
    resp = seeded_client.get("/api/v1/graph/overview?level=schema&system_code=HIS")
    assert resp.status_code == 200
    data = resp.json()["data"]["data"]
    assert data["nodes"], "HIS schema 节点应存在"
    assert data["meta"]["total_relations"] == 3
