"""Plan 90 classification: peers + nested DATA_CENTER mirrors."""

from app.api.v1.systems import _classify_asset_source
from app.services.asset_catalog import normalize_system_code


def test_peripheral_sources_remain_under_data_center():
    for code, source in [
        ("LIS", "ods_lis"),
        ("PACS", "ods_pacs"),
        ("YDHL", "ods_ydhl"),
        ("SM", "ods_sm"),
        ("EMR", "ods_emr"),
    ]:
        cat, cat_cn, _, _ = _classify_asset_source(
            code, source, source_kind="legacy_alias"
        )
        assert cat == "DATA_CENTER"
        assert cat_cn == "数据中心" or "数据中心" in cat_cn
        assert normalize_system_code(code, source_code=source, source_kind="legacy_alias") == "DATA_CENTER"


def test_explored_physical_sources_are_business_systems():
    for code, name in [
        ("DOCARE", "Docare手术麻醉"),
        ("JHEMR_VASTBASE", "嘉和电子病历"),
        ("LIS_SOURCE", "LIS"),
        ("PACS_SOURCE", "PACS"),
        ("PAPERLESS_CDMS", "无纸化病案"),
    ]:
        category, category_cn, _, label = _classify_asset_source(
            code, code.lower(), source_kind="physical_connection", source_name_cn=name
        )
        # plan 90: peers, not external_business
        assert category == code
        assert category != "external_business"
        assert "其他业务系统" not in (category_cn or "")
        assert label == name or label  # connection uses source_name_cn


def test_primary_system_classification_is_preserved():
    assert _classify_asset_source("HIS_SOURCE", "his_source_main")[0] == "HIS_SOURCE"
    assert _classify_asset_source("HRP", "hrp_main")[0] == "HRP"
    assert _classify_asset_source("DATA_CENTER", "ods_8_216")[0] == "DATA_CENTER"
