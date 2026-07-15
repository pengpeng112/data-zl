from app.api.v1.systems import _classify_asset_source


def test_peripheral_sources_remain_under_data_center():
    for code, source in [("LIS", "lis"), ("PACS", "pacs"), ("YDHL", "mobile_nursing"), ("SM", "sm"), ("EMR", "emr")]:
        category, _, owner, owner_name = _classify_asset_source(code, source)
        assert category == "ods_center"
        assert owner.startswith("owner_")
        assert "数据中心" in owner_name


def test_primary_system_classification_is_preserved():
    assert _classify_asset_source("HIS_SOURCE", "his_source_main")[0] == "his_source"
    assert _classify_asset_source("HRP", "hrp_main")[0] == "hrp_source"
    assert _classify_asset_source("DATA_CENTER", "ods_8_216")[0] == "ods_center"
