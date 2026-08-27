"""A27: raw exceptions and sensitive parameters never reach API/audit records."""
from __future__ import annotations

import json

from app.services.query_runner import (
    classify_execution_error,
    safe_parameters_summary,
)


def test_raw_exception_message_not_leaked_into_safe_summary():
    exc = RuntimeError(
        "connection to 10.10.10.15:1521/orcl failed for user his_ro with password S3cret! in DSN"
    )
    res = classify_execution_error(exc)
    assert res["error_code"] in {"E_SOURCE", "E_INTERNAL"}
    assert "S3cret" not in json.dumps(res)
    assert "10.10.10.15" not in res.get("safe_message", "")


def test_error_codes_are_from_fixed_taxonomy():
    res = classify_execution_error(ValueError("bad parameter shape"))
    assert res["error_code"] == "E_PARAM"
    res2 = classify_execution_error(LookupError("source not found"))
    assert res2["error_code"] == "E_SOURCE"


def test_parameter_summary_masks_identifier_values():
    params = {"patient_id": "12345678", "month": "2026-01", "dept": "内科"}
    schema = {
        "type": "object",
        "properties": {
            "patient_id": {"type": "string", "sensitive": True},
            "month": {"type": "string"},
            "dept": {"type": "string"},
        },
    }
    summary = safe_parameters_summary(params, schema)
    blob = json.dumps(summary)
    assert "12345678" not in blob
    # non-sensitive parameters remain useful for reproduction
    assert summary["month"] == "2026-01"


def test_parameter_summary_includes_hash_not_values_for_sensitive():
    params = {"patient_id": "12345678"}
    schema = {"type": "object", "properties": {"patient_id": {"type": "string", "sensitive": True}}}
    summary = safe_parameters_summary(params, schema)
    assert "patient_id_hash" in summary
    assert len(summary["patient_id_hash"]) == 64
