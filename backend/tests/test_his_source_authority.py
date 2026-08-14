from app.services.his_source_authority import (
    RULE_CODE,
    authority_payload,
    map_hisuser_table,
    map_ods_his_table,
)


def test_ods_his_maps_to_hisuser_owners():
    assert map_ods_his_table("HIS.PAT_VISIT") == "MEDREC.PAT_VISIT"
    assert map_ods_his_table("his.lab_test_master") == "LAB.LAB_TEST_MASTER"
    assert map_ods_his_table("HIS.OUTP_ORDER_DESC") == "OUTPBILL.OUTP_ORDER_DESC"
    assert map_hisuser_table("EXAM.EXAM_MASTER") == "HIS.EXAM_MASTER"
    assert map_ods_his_table("JHEMR.PAT_VISIT") is None


def test_authority_payload_names_hisuser_as_source():
    payload = authority_payload(persisted=False)
    assert payload["rule_code"] == RULE_CODE
    assert payload["authority_system_code"] == "HIS_SOURCE"
    assert payload["mirror_system_code"] == "DATA_CENTER"
    assert payload["enabled"] is True
    assert any(item["ods_table"] == "HIS.EXAM_MASTER" for item in payload["table_map"])
