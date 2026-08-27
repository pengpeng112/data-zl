"""plan144 S6 DB tests: unified AI context contract (A21/A22/A23)."""
from __future__ import annotations

import pytest

from app.models.query_asset import AssetQueryDefinition, AssetQueryVersion
from app.services.ai_context_builder import (
    build_context_snapshot,
    filter_ai_readable,
    load_context_snapshot,
)


@pytest.fixture()
def seeded_queries(db_session):
    d1 = AssetQueryDefinition(
        query_code="QRY_CTX_OK", title="readable", source_code="ods_8_216",
        system_code="DATA_CENTER", ai_readable=True, status="active",
    )
    d2 = AssetQueryDefinition(
        query_code="QRY_CTX_HIDDEN", title="not readable", source_code="ods_8_216",
        system_code="DATA_CENTER", ai_readable=False, status="active",
    )
    db_session.add_all([d1, d2])
    db_session.flush()
    db_session.add(AssetQueryVersion(
        query_id=d1.id, query_code="QRY_CTX_OK", version=1, status="active", is_active=True,
        dialect="oracle", sql_text="SELECT 1 FROM DUAL", sql_sha256="c" * 64,
        parameter_schema={"type": "object", "properties": {}},
    ))
    db_session.add(AssetQueryVersion(
        query_id=d2.id, query_code="QRY_CTX_HIDDEN", version=1, status="active", is_active=True,
        dialect="oracle", sql_text="SELECT 2 FROM DUAL", sql_sha256="d" * 64,
    ))
    db_session.commit()
    return d1, d2


def test_context_snapshot_roundtrip_and_manifest(db_session, seeded_queries):
    doc = build_context_snapshot(
        db_session, question_summary="住院次均费用", system_code=None, max_objects=100,
    )
    assert doc["schema_version"] == "ai-data-context/v1"
    assert doc["context_id"].startswith("ctx-")
    assert doc["manifest_hash"].startswith("sha256:")
    assert doc["query_count"] >= 1

    loaded = load_context_snapshot(db_session, doc["context_id"])
    assert loaded is not None
    assert loaded["context_id"] == doc["context_id"]
    assert loaded["manifest_hash"] == doc["manifest_hash"]
    assert loaded["expired"] is False


def test_context_excludes_ai_readable_false_definitions(db_session, seeded_queries):
    doc = build_context_snapshot(db_session, max_objects=100)
    codes = [q["query_code"] for q in doc["queries"]]
    assert "QRY_CTX_OK" in codes
    assert "QRY_CTX_HIDDEN" not in codes


def test_context_never_carries_full_sql(db_session, seeded_queries):
    doc = build_context_snapshot(db_session, include_sql=False, max_objects=100)
    for q in doc["queries"]:
        assert "sql_text" not in q
        assert "sql_available" in q or "sql_sha256" in q


def test_filter_ai_readable_fails_closed_on_missing_flag():
    items = [
        {"name": "a", "ai_readable": True},
        {"name": "b", "ai_readable": False},
        {"name": "c"},  # missing flag → dropped (fail closed)
    ]
    assert [i["name"] for i in filter_ai_readable(items)] == ["a"]


def test_mcp_catalog_tools_map_to_real_routes(client):
    from app.main import app
    from app.api.v1.ai import UNIFIED_TOOLS_144

    resp = client.get("/api/v1/ai/mcp/catalog")
    assert resp.status_code == 200, resp.text[:200]
    data = resp.json()["data"]
    declared = {t["name"] for t in data["tools"]}
    # every unified tool is declared
    for tool in UNIFIED_TOOLS_144:
        assert tool["name"] in declared
    # every unified tool path maps to a registered route (openapi paths;
    # app.routes may hold lazy _IncludedRouter wrappers without .path)
    registered = set(app.openapi()["paths"].keys())
    for tool in UNIFIED_TOOLS_144:
        path = tool["path"]
        if "{" in path:
            prefix = path.split("/{")[0]
            assert any(r.startswith(prefix + "/") for r in registered), path
        else:
            assert path in registered, path
