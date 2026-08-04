"""Plan 90: first-level systems, empty-table gate, import upsert, classification."""

from __future__ import annotations

from app.api.v1.systems import _classify_asset_source
from app.services.asset_catalog import (
    CANONICAL_SYSTEMS,
    classify_for_tree,
    normalize_system_code,
)
from app.services.asset_import_upsert import pick_chinese_name
from app.services.row_presence import (
    CONFIRMED_EMPTY,
    NON_EMPTY_EVIDENCE,
    NON_EMPTY_STATS,
    UNKNOWN,
    build_probe_sql,
    classify_from_stats,
    is_catalog_visible,
    merge_presence,
    should_skip_probe,
    probe_one,
)


def test_system_name_single_source_of_truth_codes():
    assert len(CANONICAL_SYSTEMS) == 10
    assert CANONICAL_SYSTEMS["DATA_CENTER"] == "数据中心"
    assert CANONICAL_SYSTEMS["HIS_SOURCE"] == "HIS"
    assert "external_business" not in CANONICAL_SYSTEMS


def test_no_external_business_group():
    for code, name in [
        ("DOCARE", "Docare手术麻醉"),
        ("JHEMR_VASTBASE", "嘉和电子病历"),
        ("LIS_SOURCE", "LIS"),
        ("PACS_SOURCE", "PACS"),
        ("PAPERLESS_CDMS", "无纸化病案"),
        ("MOBILE_NURSING", "移动护理"),
        ("ULTRASOUND_ENDOSCOPY", "超声内镜"),
    ]:
        cat, cat_cn, _, label = _classify_asset_source(
            code, code.lower(), source_kind="physical_connection", source_name_cn=name
        )
        assert cat == code
        assert cat_cn == name or cat in CANONICAL_SYSTEMS
        assert "其他业务系统" not in (cat_cn or "")
        assert label  # connection label present


def test_data_center_aliases_stay_nested():
    for code, source in [
        ("LIS", "ods_lis"),
        ("PACS", "ods_pacs"),
        ("YDHL", "ods_ydhl"),
        ("SM", "ods_sm"),
        ("EMR", "ods_emr"),
    ]:
        normalized = normalize_system_code(code, source_code=source, source_kind="legacy_alias")
        assert normalized == "DATA_CENTER"
        info = classify_for_tree(code, source, source_kind="legacy_alias", schema_name=code)
        assert info["system_code"] == "DATA_CENTER"
        assert info["catalog_ok"] is True


def test_independent_sources_are_peers():
    for code in ("LIS_SOURCE", "PACS_SOURCE", "DOCARE", "JHEMR_VASTBASE", "MOBILE_NURSING"):
        assert normalize_system_code(code) == code
        assert code in CANONICAL_SYSTEMS
        cat, _, _, _ = _classify_asset_source(code, f"{code.lower()}_main", "physical_connection")
        assert cat == code


def test_legacy_codes_physical_remap():
    assert normalize_system_code("HIS", source_code="his_source_10_10_10_15") == "HIS_SOURCE"
    assert normalize_system_code("EMR", source_code="jhemr_vastbase_main") == "JHEMR_VASTBASE"
    assert normalize_system_code("LIS", source_code="lis_sqlserver_10_10_10_73") == "LIS_SOURCE"
    assert normalize_system_code("PACS", source_code="pacs_mysql_10_10_10_191") == "PACS_SOURCE"
    assert normalize_system_code("SM", source_code="docare_oracle") == "DOCARE"
    assert normalize_system_code("YDHL", source_code="mobile_nursing_oracle") == "MOBILE_NURSING"


def test_zero_row_table_is_not_imported_visible():
    assert is_catalog_visible(CONFIRMED_EMPTY) is False
    assert is_catalog_visible(UNKNOWN) is True
    assert is_catalog_visible(NON_EMPTY_STATS) is True
    assert is_catalog_visible(None) is True


def test_unknown_row_presence_is_not_deleted():
    # stats 0 alone does not become confirmed_empty
    assert classify_from_stats(0) is None
    assert classify_from_stats(None) is None
    assert classify_from_stats(100) == NON_EMPTY_STATS
    status = merge_presence(current=None, stats_status=None, probe_status=UNKNOWN)
    assert status == UNKNOWN
    assert is_catalog_visible(status)


def test_human_confirmed_name_not_overwritten():
    name, src, st = pick_chinese_name(
        existing_cn="人工确认名",
        existing_status="confirmed",
        db_comment="数据库注释",
        doc_name="文档名",
        ai_name="AI名",
    )
    assert name == "人工确认名"
    assert src == "human_confirmed"


def test_name_priority_db_then_doc_then_ai():
    n1, s1, _ = pick_chinese_name(
        existing_cn=None, existing_status=None, db_comment="库注释", doc_name="文档", ai_name="AI"
    )
    assert n1 == "库注释" and s1 == "db_comment"
    n2, s2, _ = pick_chinese_name(
        existing_cn=None, existing_status=None, db_comment=None, doc_name="文档", ai_name="AI"
    )
    assert n2 == "文档" and s2 == "confirmed_document"
    n3, s3, st3 = pick_chinese_name(
        existing_cn=None, existing_status=None, db_comment=None, doc_name=None, ai_name="AI建议"
    )
    assert n3 == "AI建议" and s3 == "ai_suggested" and st3 == "pending_review"


def test_lab_result_skip_probe_evidence():
    assert should_skip_probe("HIS_SOURCE", "HIS", "LAB_RESULT") == NON_EMPTY_EVIDENCE
    assert should_skip_probe("DATA_CENTER", "HIS", "LAB_RESULT") == NON_EMPTY_EVIDENCE


def test_probe_sql_shapes():
    assert "ROWNUM" in build_probe_sql("oracle", "HIS", "PAT_MASTER_INDEX")
    assert "LIMIT 1" in build_probe_sql("postgresql", "public", "t")
    assert "LIMIT 1" in build_probe_sql("mysql", "db", "t", database="db")
    assert "TOP (1)" in build_probe_sql("sqlserver", "dbo", "t", database="rmcloudlis7")
    assert "COUNT" not in build_probe_sql("oracle", "A", "B").upper().replace("ROWNUM", "")


def test_probe_one_is_bounded_and_sample_free():
    seen = {}
    def execute(sql, max_rows):
        seen.update(sql=sql, max_rows=max_rows)
        return [{"sensitive": "must-not-be-returned"}]
    result = probe_one(execute, db_type="postgresql", schema="public", table="t")
    assert result["status"] == "nonempty_by_probe"
    assert result["method"] == "readonly_limit_1"
    assert "sensitive" not in result
    assert seen["max_rows"] == 1


def test_probe_one_empty_and_failure_are_distinct():
    empty = probe_one(lambda *_args, **_kwargs: [], db_type="mysql", schema="db", table="t")
    assert empty["status"] == CONFIRMED_EMPTY
    failed = probe_one(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("timed out")),
        db_type="mysql", schema="db", table="t",
    )
    assert failed["status"] == UNKNOWN
    assert failed["status"] != CONFIRMED_EMPTY


def test_probe_sql_escapes_identifiers():
    sql = build_probe_sql("postgresql", 'a"b', 't"x')
    assert '"a""b"."t""x"' in sql


def test_primary_systems_classification():
    assert _classify_asset_source("HIS_SOURCE", "his_source_main")[0] == "HIS_SOURCE"
    assert _classify_asset_source("HRP", "hrp_main")[0] == "HRP"
    assert _classify_asset_source("DATA_CENTER", "ods_8_216")[0] == "DATA_CENTER"


def test_same_table_name_keys_differ_by_source():
    # documentation of stable key identity used by upsert
    key_a = ("src_a", "dbo", "PATIENT")
    key_b = ("src_b", "dbo", "PATIENT")
    assert key_a != key_b
