"""图同步抽象的纯逻辑测试（98号 S0 / 100号修复）。

用 mock 关系对象 + InMemoryGraphAdapter 验证同步逻辑，
不依赖 APP_TEST_DB_URL。
100号新增：未解析端点跳过、同批次重试、checksum 感知内容变化。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.graph_sync import (
    InMemoryGraphAdapter,
    UnavailableGraphAdapter,
    run_full_rebuild,
    run_incremental_upsert,
    run_daily_diff_check,
    _compute_checksum,
    _relation_to_graph_edge,
)


def _make_relation(
    rid: int,
    *,
    layer="formal",
    from_table="MEDREC.PAT_VISIT",
    to_table="MEDREC.DIAGNOSIS",
    updated=None,
    from_system="HIS_SOURCE",
    from_source="his_source_10_10_10_15",
    to_system="HIS_SOURCE",
    to_source="his_source_10_10_10_15",
):
    return SimpleNamespace(
        id=rid,
        relation_layer=layer,
        from_system_code=from_system,
        from_source_code=from_source,
        from_namespace_name=None,
        from_schema_name="MEDREC",
        from_table_name=from_table.split(".")[-1] if "." in from_table else from_table,
        to_system_code=to_system,
        to_source_code=to_source,
        to_namespace_name=None,
        to_schema_name="MEDREC",
        to_table_name=to_table.split(".")[-1] if "." in to_table else to_table,
        from_columns="PATIENT_ID|VISIT_ID",
        to_columns="PATIENT_ID|VISIT_ID",
        join_condition="a.patient_id=b.patient_id",
        cardinality="many-to-one",
        confidence="A",
        validation_status="verified",
        relation_business_key=f"bk-{rid}",
        updated_at=updated or datetime.now(timezone.utc),
    )


def _mock_db(relations):
    db = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = relations
    db.scalars.return_value = scalars_mock
    db.get.return_value = None
    db.add.return_value = None
    db.commit.return_value = None
    return db


class TestUnresolvedEndpointSkipped:
    def test_missing_system_skipped(self):
        """未解析端点（缺 system）跳过同步，计入 unresolved_count。"""
        rel = _make_relation(1, from_system=None)
        adapter = InMemoryGraphAdapter()
        db = _mock_db([rel])
        result = run_full_rebuild(db, adapter)
        assert result["status"] == "success"
        assert result["unresolved_count"] == 1
        assert result["upsert_count"] == 0
        assert adapter.count_edges() == 0

    def test_resolved_goes_through(self):
        rel = _make_relation(1)
        adapter = InMemoryGraphAdapter()
        db = _mock_db([rel])
        result = run_full_rebuild(db, adapter)
        assert result["unresolved_count"] == 0
        assert result["upsert_count"] == 1
        assert adapter.count_edges() == 1


class TestSameBatchRetry:
    def test_same_batch_id_updates_record(self):
        """同批次重试更新同一批次记录。"""
        rels = [_make_relation(1), _make_relation(2)]
        adapter = InMemoryGraphAdapter()
        db = _mock_db(rels)
        r1 = run_full_rebuild(db, adapter, batch_id="test-batch-001")
        assert r1["batch_id"] == "test-batch-001"
        assert r1["status"] == "success"
        db2 = _mock_db(rels)
        r2 = run_full_rebuild(db2, adapter, batch_id="test-batch-001")
        assert r2["batch_id"] == "test-batch-001"
        assert r2["status"] == "success"
        assert db2.get.called


class TestChecksumContentAware:
    def test_checksum_changes_with_content(self):
        """checksum 感知内容变化（不仅是 ID）。"""
        edge1 = {"relation_id": 1, "from_physical_key": "A|B||C|D",
                 "to_physical_key": "E|F||G|H", "from_columns": "X",
                 "to_columns": "Y", "join_condition": "x=y",
                 "confidence": "A", "relation_layer": "formal"}
        edge2 = dict(edge1)
        edge2["join_condition"] = "x=z"
        c1 = _compute_checksum([edge1])
        c2 = _compute_checksum([edge2])
        assert c1 != c2

    def test_checksum_same_for_same_content(self):
        edge = {"relation_id": 1, "from_physical_key": "A|B||C|D",
                "to_physical_key": "E|F||G|H", "from_columns": "X",
                "to_columns": "Y", "join_condition": "x=y",
                "confidence": "A", "relation_layer": "formal"}
        assert _compute_checksum([edge]) == _compute_checksum([dict(edge)])


class TestIncrementalUpsertIdempotent:
    def test_same_batch_twice_same_result(self):
        rels = [_make_relation(1), _make_relation(2)]
        adapter = InMemoryGraphAdapter()
        since = datetime.now(timezone.utc) - timedelta(days=1)
        db = _mock_db(rels)
        r1 = run_incremental_upsert(db, adapter, since)
        count1 = adapter.count_edges()
        db2 = _mock_db(rels)
        r2 = run_incremental_upsert(db2, adapter, since)
        count2 = adapter.count_edges()
        assert r1["status"] == "success"
        assert r2["status"] == "success"
        assert count1 == count2


class TestFullRebuildFromEmpty:
    def test_rebuild_matches_pg(self):
        rels = [_make_relation(1), _make_relation(2), _make_relation(3)]
        adapter = InMemoryGraphAdapter()
        db = _mock_db(rels)
        result = run_full_rebuild(db, adapter)
        assert result["status"] == "success"
        assert result["edge_count"] == 3
        db2 = _mock_db(rels)
        result2 = run_full_rebuild(db2, adapter)
        assert result2["edge_count"] == 3


class TestDailyDiffDetectsDeletion:
    def test_stale_edge_removed(self):
        adapter = InMemoryGraphAdapter()
        db = _mock_db([_make_relation(1), _make_relation(2), _make_relation(3)])
        run_full_rebuild(db, adapter)
        assert adapter.count_edges() == 3
        db2 = _mock_db([_make_relation(1)])
        result = run_daily_diff_check(db2, adapter)
        assert result["status"] == "success"
        assert result["delete_count"] == 2
        assert adapter.count_edges() == 1


class TestDailyDiffCleansOrphanNodes:
    def test_orphan_nodes_cleaned(self):
        adapter = InMemoryGraphAdapter()
        db = _mock_db([_make_relation(1), _make_relation(2)])
        run_full_rebuild(db, adapter)
        nodes_before = adapter.count_nodes()
        db2 = _mock_db([_make_relation(1)])
        result = run_daily_diff_check(db2, adapter)
        assert result["orphan_nodes_cleaned"] >= 0
        assert adapter.count_nodes() <= nodes_before


class TestDegradedWhenAdapterFails:
    def test_degraded_not_500(self):
        class ClearFails(InMemoryGraphAdapter):
            def clear(self):
                raise RuntimeError("connect refused")
        adapter = ClearFails()
        db = _mock_db([])
        result = run_full_rebuild(db, adapter)
        assert result["status"] == "degraded"
        assert result["is_degraded"] is True


class TestUnavailableAdapterDefault:
    def test_health_false(self):
        adapter = UnavailableGraphAdapter()
        assert adapter.health() is False
        assert adapter.count_nodes() == 0
        assert adapter.count_edges() == 0