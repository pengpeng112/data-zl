from app.services.query_fingerprint import normalize_sql, parameters_hash, sql_sha256
from app.services.query_gate import evaluate_query_gate, extract_table_refs


def test_sql_hash_stable_under_whitespace():
    a = "select  patient_id  from  his.pat_visit where rownum<=1"
    b = "SELECT patient_id FROM his.pat_visit WHERE ROWNUM<=1"
    assert sql_sha256(a) == sql_sha256(b)
    assert normalize_sql(a) == normalize_sql(b)


def test_parameters_hash_ignores_key_order():
    assert parameters_hash({"a": 1, "b": 2}) == parameters_hash({"b": 2, "a": 1})


def test_gate_blocks_dml():
    g = evaluate_query_gate("DELETE FROM HIS.PAT_VISIT", dialect="oracle", source_code="ods_8_216")
    assert g["status"] == "blocked"
    assert g["auto_activate"] is False


def test_gate_blocks_lab_result_unbounded():
    g = evaluate_query_gate(
        "SELECT * FROM HIS.LAB_RESULT",
        dialect="oracle",
        source_code="ods_8_216",
        require_source=False,
    )
    assert g["status"] == "blocked"


def test_gate_allows_simple_select():
    g = evaluate_query_gate(
        "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 10",
        dialect="oracle",
        source_code="ods_8_216",
        require_source=False,
    )
    assert g["status"] == "validated"
    assert g["auto_activate"] is True
    assert "HIS.PAT_VISIT" in extract_table_refs(
        "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 10"
    )
