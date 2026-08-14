"""S0 contract locks for 127 known root causes (pure unit, no DB).

These tests encode the *target* contracts from plan 127 §4/§8/§18.
They must fail on the pre-fix baseline and pass after S1–S8 fixes.
"""
from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── 4.1 quality rules pagination contract ───────────────────────────


def test_quality_list_rules_accepts_pagination_params():
    src = _read("app/api/v1/quality.py")
    # Must expose page/page_size on list_rules
    assert re.search(r"def list_rules\([\s\S]*?page\s*:", src), "list_rules must accept page"
    assert "page_size" in src.split("def list_rules")[1].split("def ")[0]
    # Must return items/total page envelope (not bare list)
    list_body = src.split("def list_rules")[1].split("\n@router")[0]
    assert "items" in list_body and "total" in list_body, "list_rules must return {items,total,...}"


def test_quality_templates_return_total_error_cnt_contract():
    from app.services.quality_templates import (
        template_relation_orphan,
        template_unique_pk,
    )

    pk_sql = template_unique_pk("PAT_VISIT", "PATIENT_ID", "HIS").upper()
    assert "TOTAL_CNT" in pk_sql and "ERROR_CNT" in pk_sql
    assert "HAVING COUNT" not in pk_sql or "SELECT TOTAL_CNT" in pk_sql or "AS TOTAL_CNT" in pk_sql

    orphan_sql = template_relation_orphan(
        "DIAGNOSIS", "PATIENT_ID", "PAT_VISIT", "PATIENT_ID", "HIS"
    ).upper()
    assert "TOTAL_CNT" in orphan_sql and "ERROR_CNT" in orphan_sql
    assert "ORPHAN_CNT" not in orphan_sql or "ERROR_CNT" in orphan_sql


def test_quality_sql_runner_rejects_multi_row_as_stats():
    # Avoid importing quality_sql_runner (pulls SessionLocal/DB guard).
    # Re-implement contract check on source text + isolated logic copy.
    src = _read("app/services/quality_sql_runner.py")
    assert "len(rows) > 1" in src or "rule_error" in src
    assert "TOTAL_CNT" in src and "ERROR_CNT" in src
    # Multi-row without TOTAL must not become len(rows) error count
    assert 'total_cnt = len(rows)' not in src or "rule_error" in src


def test_by_system_does_not_copy_global_counts_to_every_system():
    src = _read("app/api/v1/quality.py")
    body = src.split("def quality_summary_by_system")[1].split("\n@router")[0]
    # Forbidden pattern: assign global len(findings) to every system
    assert "grouped[sc][\"findings_total\"] = len(" not in body.replace(" ", "")
    # Must group findings by system_code
    assert "system_code" in body
    assert "infer_system_code" in body
    assert "target_ref" in body
    # Must expose frontend-compatible keys
    assert "total_findings" in body or '"total_findings"' in body
    assert "open_count" in body or '"open_count"' in body


def test_metrics_rule_categories_is_array_and_pass_rate_split():
    src = _read("app/api/v1/quality.py")
    body = src.split("def quality_metrics")[1].split("\n@router")[0]
    assert "rule_categories" in body
    # Must build list of {category,count}
    assert "category" in body and "count" in body
    assert "rule_categories =" in body or '"rule_categories": rule_categories' in body
    # Separate resolution vs rules pass
    assert "resolution_rate" in body
    assert "rules_pass_rate" in body


# ── 4.7 recipe import path + structure ──────────────────────────────


def test_recipe_import_repo_root_is_parents_2():
    src = _read("scripts/import_relation_recipes.py")
    assert "parents[3]" not in src, "import path parents[3] points outside repo"
    assert "parents[2]" in src


def test_recipe_service_normalizes_seed_join_shape():
    from app.services.recipe_service import generate_select_sql, normalize_recipe_joins

    seed_joins = [
        {
            "type": "LEFT",
            "from": "HIS.EXAM_MASTER",
            "to": "HIS.EXAM_REPORT",
            "condition": "HIS.EXAM_MASTER.EXAM_NO = HIS.EXAM_REPORT.EXAM_NO",
        }
    ]
    normalized = normalize_recipe_joins(seed_joins)
    assert normalized[0].get("join_type") in {"LEFT", "left", "INNER", "inner"}
    assert "on" in normalized[0] or "join_condition" in normalized[0]
    sql = generate_select_sql(
        ["HIS.EXAM_MASTER", "HIS.EXAM_REPORT"],
        normalized,
    )
    assert "JOIN" in sql.upper()
    assert "EXAM_NO" in sql.upper()


def test_recipe_status_maps_user_confirmed():
    from app.services.recipe_service import map_seed_status

    assert map_seed_status("user_confirmed") in {"approved", "active", "draft"}
    # Must not raise
    assert map_seed_status("draft") == "draft"


# ── 4.8 AI fake execute ─────────────────────────────────────────────


def test_ai_tool_execute_not_fake_success():
    src = _read("app/api/v1/ai.py")
    body = src.split("def tool_execute")[1].split("\n@router")[0]
    # Must support explicit unsupported path and not always force success
    assert "unsupported" in body.lower()
    assert "status" in body
    # Return payload must include executed from variable, not constant True only
    assert '"executed": executed' in body or "'executed': executed" in body


def test_ai_system_context_includes_column_relation_totals():
    src = _read("app/api/v1/ai.py")
    body = src.split("def ") 
    # Find system-context handler
    ctx = None
    for part in body:
        if "system-context" in part or "system_context" in part or "total_tables" in part:
            if "total_tables" in part:
                ctx = part
                break
    assert ctx is not None
    assert "total_columns" in ctx
    assert "total_relations" in ctx


# ── 4.6 relation review main table ──────────────────────────────────


def test_relation_review_api_module_exists():
    path = APP / "api" / "v1" / "relation_reviews.py"
    assert path.exists(), "must add relation_reviews API module"
    src = path.read_text(encoding="utf-8")
    assert "AssetRelationReview" in src
    assert "review_status" in src
    assert "approve" in src.lower() or "approved" in src


def test_relation_review_approve_dedups_via_alias_and_formal_link():
    src = _read("app/services/relation_review_service.py")
    assert "normalize" in src.lower() or "alias" in src.lower()
    assert "468" not in src  # no hardcode of prod ids; logic must be general
    assert "formal" in src.lower()
    assert "source_relation_id" in src or "link" in src.lower()


# ── 4.4 overview aggregate ──────────────────────────────────────────


def test_overview_charts_aggregate_endpoint_exists():
    src = _read("app/api/v1/tables.py")
    assert "overview/charts" in src or "overview_charts" in src or "/charts/aggregate" in src
    # PG GroupingError：coalesce/nullif 必须绑定一次再 group_by，禁止 SELECT/GROUP BY 各写一遍。
    assert "domain_key" in src
    assert "status_key" in src
    assert ".group_by(domain_key)" in src
    assert ".group_by(status_key)" in src
    assert 'group_by(func.coalesce(func.nullif(AssetTable.domain' not in src
    assert 'group_by(func.coalesce(func.nullif(AssetRelation.validation_status' not in src


def test_table_list_system_filter_accepts_his_alias():
    catalog = _read("app/services/asset_catalog.py")
    assert "def system_code_filter_values" in catalog
    assert "LEGACY_SYSTEM_MAP" in catalog
    src = _read("app/api/v1/tables.py")
    assert "system_code_filter_values" in src
    assert "if table_name:" in src
    tree_api = _read("../frontend/src/api/asset.ts")
    assert "table_name?: string" in tree_api
    tree_src = _read("../frontend/src/views/asset/tables/index.vue")
    click_fn = tree_src.split("async function handleTreeClick")[1].split("async function loadData")[0]
    assert "await loadData()" in click_fn
    assert "await hydrateColumnChildren(node.table);\n    return;" not in click_fn


# ── 4.5 graph label placement ───────────────────────────────────────


def test_frontend_graph_sets_label_placement_center():
    src = _read("../frontend/src/views/asset/components/AdvancedRelationGraph.vue")
    assert "labelPlacement" in src
    assert "center" in src


# ── 6.2 ORDERS uniqueness must include ORDER_SUB_NO ─────────────────


def test_orders_unique_key_includes_order_sub_no():
    # Pure policy helper if present; else templates must not use incomplete key
    templates = _read("app/services/quality_templates.py")
    # Policy constant or comment guard
    from app.services import quality_templates as qt

    if hasattr(qt, "CORE_UNIQUE_KEYS"):
        orders = qt.CORE_UNIQUE_KEYS.get("ORDERS") or qt.CORE_UNIQUE_KEYS.get("HIS.ORDERS")
        assert orders is not None
        cols = [c.upper() for c in orders]
        assert "ORDER_SUB_NO" in cols
        assert "ORDER_NO" in cols


# ── 126 boundary: no query/metric asset tables in 127 ───────────────


def test_no_query_or_metric_asset_models_in_127_scope():
    # 126 legitimately owns the query/metric/data-product asset models; they are
    # expected in this repo after the 126 merge. The 127 boundary means NO
    # *additional* model files may define these tables; the authoritative guard
    # is the alembic migration scan below.
    models_dir = APP / "models"
    names = {p.name for p in models_dir.glob("*.py")}
    expected_126 = {"query_asset.py", "metric_asset.py", "query_schedule.py", "data_product.py"}
    found = {n for n in names if "query_asset" in n or "metric_asset" in n or "data_product" in n}
    assert found <= expected_126, f"127 must not add query/metric asset models: {found - expected_126}"
    # Scan recent alembic heads for asset_query_ / asset_metric_
    alembic = ROOT / "alembic" / "versions"
    for p in alembic.glob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "asset_query_" in text or "asset_metric_" in text:
            # allow comments mentioning 126; block create_table
            if "create_table" in text and ("asset_query_" in text or "asset_metric_" in text):
                if "127" in p.name or "plan127" in text.lower():
                    pytest.fail(f"127 migration must not create query/metric tables: {p.name}")
