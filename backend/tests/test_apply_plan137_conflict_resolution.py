from scripts.apply_plan137_conflict_resolution import (
    MARKER,
    REVIEW_SPECS,
    append_marker,
    columns,
    identity,
    merge_json,
)


def test_columns_accepts_supported_separators():
    assert columns("PATIENT_ID+VISIT_ID") == ("PATIENT_ID", "VISIT_ID")
    assert columns("patient_id|visit_id") == ("PATIENT_ID", "VISIT_ID")
    assert columns("PATIENT_ID,VISIT_ID") == ("PATIENT_ID", "VISIT_ID")


def test_review_specs_are_five_exact_fragments():
    assert len(REVIEW_SPECS) == 5
    key = identity(
        "drug_user.pha_inp_request_drug",
        "pat_id,in_count",
        "ordadm.orders",
        "patient_id,visit_id",
    )
    assert REVIEW_SPECS[key][0] == "R031"


def test_append_marker_is_idempotent():
    first, changed = append_marker("base", "detail")
    assert changed is True
    assert f"[{MARKER}]" in first
    second, changed_again = append_marker(first, "different")
    assert changed_again is False
    assert second == first


def test_merge_json_is_idempotent_and_preserves_existing_data():
    payload = {"status": "resolved"}
    first, changed = merge_json({"runtime_status": "runtime_skipped"}, payload)
    assert changed is True
    assert first["runtime_status"] == "runtime_skipped"
    second, changed_again = merge_json(first, payload)
    assert changed_again is False
    assert second == first
