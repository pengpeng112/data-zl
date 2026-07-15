from app.services.connection_identity import (
    ODS_ALIAS_SOURCES,
    build_database_key,
    build_endpoint_key,
)
from scripts.backfill_connection_targets import row_connection_identity_key


def test_endpoint_and_database_key_for_ods():
    ep = build_endpoint_key("oracle", "10.10.8.216", 1521)
    assert ep == "oracle://10.10.8.216:1521"
    dbk = build_database_key("oracle", "10.10.8.216", 1521, "orcl", None, "service_name")
    assert dbk == "oracle://10.10.8.216:1521/service_name/orcl"
    # all ODS aliases share same physical key
    for code in ODS_ALIAS_SOURCES:
        assert ODS_ALIAS_SOURCES[code]["canonical"] == "ods_8_216"


def test_hrp_and_his_keys_distinct():
    hrp = build_database_key("oracle", "10.10.10.23", 1521, "hrpdb", None, "service_name")
    his = build_database_key("oracle", "10.10.10.15", 1521, "his", None, "service_name")
    ods = build_database_key("oracle", "10.10.8.216", 1521, "orcl", None, "service_name")
    assert len({hrp, his, ods}) == 3


def test_legacy_alias_has_unique_row_identity_but_shared_database_key():
    physical = "oracle:10.10.8.216:1521:service_name:orcl"
    assert row_connection_identity_key("ods_8_216", "physical_connection", physical) == physical
    lis = row_connection_identity_key("ods_lis", "legacy_alias", physical)
    pacs = row_connection_identity_key("ods_pacs", "legacy_alias", physical)
    assert lis != physical
    assert pacs != physical
    assert lis != pacs
