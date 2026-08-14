import hashlib
import json

import pytest

from app.services.ai_quality_payload import build_payload
from app.services.ai_quality_result import validate_output


def test_payload_drops_samples_and_has_stable_digest():
    first = build_payload(schema_version="quality-analysis-input/v1", request_id="AQJ-1", task_type="finding", prompt_version="v1", payload={"table_name": "HIS.T", "sample_data": [{"患者": "x"}], "error_cnt": 2})
    second = build_payload(schema_version="quality-analysis-input/v1", request_id="AQJ-2", task_type="finding", prompt_version="v1", payload={"error_cnt": 2, "table_name": "HIS.T"})
    assert first["input_digest"] == second["input_digest"]
    assert first["dropped_fields"] == ["sample_data"]
    assert "患者" not in first["payload_json"]


def test_payload_limit():
    with pytest.raises(ValueError, match="byte limit"):
        build_payload(schema_version="quality-analysis-input/v1", request_id="x", task_type="finding", prompt_version="v1", payload={"table_name": "x" * 100}, max_bytes=10)


def test_payload_keeps_identifier_names():
    built = build_payload(
        schema_version="quality-analysis-input/v1",
        request_id="AQJ-1",
        task_type="finding",
        prompt_version="v1",
        payload={
            "table_name": "EXAM_MASTER",
            "from_columns": "PATIENT_ID,VISIT_ID",
            "to_columns": "PATIENT_ID,VISIT_ID",
            "related_table": "INP_BILL_DETAIL",
            "problem": "住院检查关系孤儿率偏高，患者ID+VISIT_ID 需拆门诊住院",
            "handling_hint": "已拆 553/554",
        },
    )
    assert "PATIENT_ID" in built["payload_json"]
    assert "INP_BILL_DETAIL" in built["payload_json"]
    assert "患者ID" in built["payload_json"]
    assert "553/554" in built["payload_json"]
    assert "[REDACTED]" not in built["payload_json"]


def test_output_requires_correlation_and_rejects_sensitive():
    digest = "a" * 64
    valid = {"schema_version": "quality-analysis-output/v1", "request_id": "AQJ-1", "input_digest": digest, "summary": "ok", "risk_level": "low", "root_causes": [], "recommendations": [], "false_positive": {"possible": False, "reason": ""}, "follow_up_checks": [], "limitations": []}
    assert validate_output({"data": {"outputs": valid}}, request_id="AQJ-1", input_digest=digest).summary == "ok"
    valid["summary"] = "患者ID关联缺失，住院号字段需拆门诊住院"
    assert validate_output(valid, request_id="AQJ-1", input_digest=digest).summary.startswith("患者ID")
    valid["summary"] = "身份证号=370102199001011234 不可出现"
    with pytest.raises(ValueError, match="sensitive"):
        validate_output(valid, request_id="AQJ-1", input_digest=digest)
