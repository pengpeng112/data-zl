from __future__ import annotations

import inspect
from pathlib import Path

from app.api.v1 import ai_quality
from app.services.ai_patrol_targets import load_patrol_targets
from app.services.hospital_llm_analysis import build_patrol_analysis_prompt


def test_patrol_target_snapshot_is_complete_and_aggregate_only():
    targets = load_patrol_targets()
    assert len(targets) == 3
    assert len({(row["system_code"], row["source_code"], row["schema_name"], row["table_name"]) for row in targets}) == 3
    for row in targets:
        assert len(set(row["finding_ids"])) >= 2
        assert row["evidence"]["finding_id"] in row["finding_ids"]
        assert row["evidence"]["metric_value"]
        serialized = str(row).lower()
        assert "patient_name" not in serialized
        assert "sample_data" not in serialized


def test_patrol_prompt_is_evidence_bound_and_read_only():
    prompt = build_patrol_analysis_prompt(
        request_id="AQJ-test",
        input_digest="a" * 64,
        payload_json='{"findings":[]}',
    )
    assert "禁止虚构" in prompt
    assert "只读" in prompt
    assert "AQJ-test" in prompt
    assert "a" * 64 in prompt


def test_patrol_endpoint_reuses_signed_preview_and_async_submit_chain():
    source = inspect.getsource(ai_quality.patrol_run)
    assert "_new_request_id()" in source
    assert "_make(" in source
    assert "_submit(" in source
    assert "patrol_run_id=run_id" in source
    assert "QualityTask" not in Path(ai_quality.__file__).read_text(encoding="utf-8")


def test_patrol_status_host_is_derived_from_configuration():
    source = inspect.getsource(ai_quality._status_payload)
    assert "hospital_llm_base_url" in source
    assert "10.10.8.83" not in source
    assert "masked_host" in source
