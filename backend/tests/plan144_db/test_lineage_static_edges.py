"""plan144 S5 / 138 first-phase: deterministic static lineage (A19/A20/A31)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.asset import AssetRelation
from app.models.data_product import AssetDataProduct
from app.models.lineage import AssetLineageEdge, AssetViewDependency
from app.models.metric_asset import AssetMetricDefinition, AssetMetricVersion
from app.models.query_asset import AssetQueryDefinition, AssetQueryVersion
from app.services.lineage_ingest import (
    collect_lineage_edges,
    lineage_impact,
    sync_lineage_edges,
    table_object_key,
)


@pytest.fixture()
def lineage_seed(db_session):
    qd = AssetQueryDefinition(query_code="QRY_LIN_T", title="lineage", source_code="his_source_10_10_10_15", system_code="HIS", status="active")
    db_session.add(qd)
    db_session.flush()
    qv = AssetQueryVersion(
        query_id=qd.id, query_code="QRY_LIN_T", version=1, status="active", is_active=True,
        dialect="oracle", sql_text="SELECT * FROM HIS.PAT_VISIT", sql_sha256="l" * 64,
    )
    db_session.add(qv)
    db_session.flush()
    # resolved dependency with physical object_key (via conftest-seeded HIS.PAT_VISIT)
    from app.models.query_asset import AssetQueryDependency

    dep = AssetQueryDependency(
        query_version_id=qv.id, dep_type="table", schema_name="HIS", object_name="PAT_VISIT",
        object_key=table_object_key("HIS", "his_source_10_10_10_15", "HIS", "PAT_VISIT"),
        resolution_status="resolved",
    )
    db_session.add(dep)
    db_session.add(AssetViewDependency(view_name="V_LIN_TEST", referenced_schema="HIS", referenced_table="PAT_VISIT"))
    md = AssetMetricDefinition(metric_code="MET_LIN_T", title="lineage metric")
    db_session.add(md)
    db_session.flush()
    mv = AssetMetricVersion(
        metric_id=md.id, metric_code="MET_LIN_T", version=1, status="active", is_active=True,
        query_code="QRY_LIN_T", query_version=1, definition_text="x",
    )
    db_session.add(mv)
    db_session.add(AssetDataProduct(
        product_code="DP_LIN_T", title="lineage product", product_type="query",
        query_code="QRY_LIN_T", pin_version=1, enabled=True,
    ))
    # business JOIN relation that must NEVER become lineage (A19)
    db_session.add(AssetRelation(
        from_table="HIS.PAT_VISIT", from_columns="PATIENT_ID,VISIT_ID",
        to_table="HIS.INP_BILL_DETAIL", to_columns="PATIENT_ID,VISIT_ID",
        validation_status="validated",
    ))
    db_session.commit()
    return {"qv": qv, "mv": mv}


def test_business_join_relations_never_enter_lineage(db_session, lineage_seed):
    edges, _unresolved = collect_lineage_edges(db_session)
    pairs = {(e["from_object_key"], e["to_object_key"]) for e in edges}
    # no edge between the two business-join tables themselves
    for f, t in pairs:
        assert not (f.endswith("PAT_VISIT|table") and t.endswith("INP_BILL_DETAIL|table")), pairs


def test_deterministic_edges_collected(db_session, lineage_seed):
    edges, unresolved = collect_lineage_edges(db_session)
    kinds = {(e["edge_type"], e["from_object_type"], e["to_object_type"]) for e in edges}
    assert ("reads_from", "table", "query") in kinds      # resolved query dependency
    assert ("reads_from", "table", "view") in kinds       # view dependency
    assert ("calculates", "query", "metric") in kinds     # metric version ref
    assert ("publishes", "query", "product") in kinds     # product pin
    assert all(e["evidence_type"] for e in edges)


def test_sync_dry_run_writes_nothing_then_idempotent(db_session, lineage_seed):
    dry = sync_lineage_edges(db_session, dry_run=True)
    assert dry["dry_run"] is True and dry["created"] >= 4
    n_after_dry = db_session.query(AssetLineageEdge).count()
    assert n_after_dry == 0, "dry-run must not persist rows"

    first = sync_lineage_edges(db_session, dry_run=False)
    assert first["created"] >= 4
    n_first = db_session.query(AssetLineageEdge).count()
    assert n_first == first["created"]

    second = sync_lineage_edges(db_session, dry_run=False)
    assert second["created"] == 0, "second run must create nothing (A31)"
    n_second = db_session.query(AssetLineageEdge).count()
    assert n_second == n_first


def func_count():
    from sqlalchemy import func

    return func.count(AssetLineageEdge.id)


def test_impact_traverses_typed_edges_precisely(db_session, lineage_seed):
    sync_lineage_edges(db_session, dry_run=False)
    key = table_object_key("HIS", "his_source_10_10_10_15", "HIS", "PAT_VISIT")
    result = lineage_impact(db_session, object_key=key, direction="downstream", max_hops=3)
    downstream = set(result["downstream_nodes"])
    assert "query|QRY_LIN_T|1" in downstream
    assert "metric|MET_LIN_T|1" in downstream
    assert "product|DP_LIN_T" in downstream
    # upstream from the product reaches the query
    up = lineage_impact(db_session, object_key="product|DP_LIN_T", direction="upstream", max_hops=3)
    assert "query|QRY_LIN_T|1" in set(up["upstream_nodes"])


def test_unresolved_deps_recorded_not_guessed(db_session, db_session_empty=None):
    # a dependency row without object_key lands in unresolved, never in edges
    from app.models.query_asset import AssetQueryDependency

    qd = AssetQueryDefinition(query_code="QRY_LIN_U", title="unresolved", source_code="his_source_10_10_10_15", status="active")
    db_session.add(qd)
    db_session.flush()
    qv = AssetQueryVersion(
        query_id=qd.id, query_code="QRY_LIN_U", version=1, status="active", is_active=True,
        dialect="oracle", sql_text="SELECT 1 FROM DUAL", sql_sha256="u" * 64,
    )
    db_session.add(qv)
    db_session.flush()
    db_session.add(AssetQueryDependency(query_version_id=qv.id, dep_type="table", schema_name="HIS", object_name="NO_SUCH_TABLE"))
    db_session.commit()
    edges, unresolved = collect_lineage_edges(db_session)
    assert any(u["kind"] == "query_dependency" for u in unresolved)
    assert not any(e["to_object_key"] == "query|QRY_LIN_U|1" and e["from_object_type"] == "table" for e in edges)
