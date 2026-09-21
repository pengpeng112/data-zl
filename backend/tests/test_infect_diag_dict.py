"""COMM.INFECT_DIAG_DICT lookup used by diagnosis mapping 传染病诊断."""
from app.services.db_connectors import validate_readonly_sql
from app.services.infect_diag_dict import (
    HIS_SQL,
    HIS_TABLE,
    clear_infect_diag_cache,
    load_infect_diag_dict,
    match_infect_diag_dict,
    normalize_infect_rows,
)


def test_his_infect_sql_is_readonly():
    assert validate_readonly_sql(HIS_SQL).startswith("SELECT")


def test_match_infect_diag_by_hanzi_pinyin_and_code():
    items = [
        {"code": "A00.1xx001", "name": "霍乱", "input_code": "HL"},
        {"code": "B15.900", "name": "甲型肝炎", "input_code": "JXGYY"},
    ]
    assert [i["name"] for i in match_infect_diag_dict(items, "霍")] == ["霍乱"]
    assert [i["name"] for i in match_infect_diag_dict(items, "hl")] == ["霍乱"]
    assert [i["name"] for i in match_infect_diag_dict(items, "A00")] == ["霍乱"]
    assert [i["name"] for i in match_infect_diag_dict(items, "肝炎")] == ["甲型肝炎"]
    assert match_infect_diag_dict(items, "xyz") == []
    assert len(match_infect_diag_dict(items, "")) == 2


def test_normalize_infect_rows_dedupes_and_builds_pinyin():
    rows = [
        {"DIAG_CODE": "A00.1xx001", "INFECT_NAME": "霍乱"},
        {"diag_code": "A00.1xx001", "infect_name": "霍乱"},
        {"DIAG_CODE": "", "INFECT_NAME": ""},
    ]
    items = normalize_infect_rows(rows)
    assert len(items) == 1
    assert items[0]["code"] == "A00.1xx001"
    assert items[0]["name"] == "霍乱"
    assert items[0]["input_code"] == "HL"


def test_load_infect_diag_dict_uses_his_fetcher(client):
    clear_infect_diag_cache()

    def fake_fetch(_source):
        return [{"DIAG_CODE": "A00.1xx001", "INFECT_NAME": "霍乱"}]

    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        payload = load_infect_diag_dict(db, fetcher=fake_fetch)
        assert payload["source"] == HIS_TABLE
        assert payload["items"][0]["name"] == "霍乱"
        assert payload["items"][0]["input_code"] == "HL"
    finally:
        db.close()
        clear_infect_diag_cache()


def test_mapping_options_exposes_infect_dict(client, monkeypatch):
    clear_infect_diag_cache()
    monkeypatch.setattr(
        "app.services.infect_diag_dict.load_infect_diag_dict",
        lambda db: {
            "source": HIS_TABLE,
            "table": HIS_TABLE,
            "items": [{"code": "A00.1xx001", "name": "霍乱", "input_code": "HL"}],
        },
    )
    resp = client.get("/api/v1/dict-medical/mapping-options", params={"category_code": "diagnosis"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["infectious_source"] == HIS_TABLE
    assert data["infectious_diagnoses"][0]["name"] == "霍乱"

    op = client.get("/api/v1/dict-medical/mapping-options", params={"category_code": "operation"})
    assert op.status_code == 200
    assert "infectious_diagnoses" not in (op.json().get("data") or {})
