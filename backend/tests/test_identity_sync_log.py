from types import SimpleNamespace

from app.services.identity_sync_log import (
    serialize_action,
    serialize_run,
    status_label,
    subtask_label,
    system_label,
    trigger_label,
)


def test_identity_sync_log_uses_chinese_labels():
    assert subtask_label("jhemr_signature_sync") == "嘉和签名同步"
    assert system_label("CDMS") == "合理用药"
    assert status_label("partial_success") == "部分成功"
    assert trigger_label("host_cron_modified_sync") == "宿主机增量同步"


def test_serialize_run_hides_sensitive_fields():
    run = SimpleNamespace(
        run_id="run-1",
        triggered_by="host_cron_modified_sync",
        status="success",
        started_at=None,
        finished_at=None,
        duration_ms=1200,
        candidates_total=4,
        success_count=4,
        failed_count=0,
        skipped_count=0,
        watermark_advanced=True,
        circuit_breaker_triggered=False,
        last_error_class=None,
        provider_code="host_cron",
    )
    data = serialize_run(run, [])
    assert data["triggered_by_name"] == "宿主机增量同步"
    assert data["status_name"] == "成功"
    assert "emp_no" not in data


def test_serialize_action_uses_fingerprint_only():
    action = SimpleNamespace(
        action_seq=1,
        target_system="JHEMR",
        subtask_code="jhemr_education_title_sync",
        action_type="update_title",
        status="executed",
        reason_code="idempotent_skip",
        error_class=None,
        error_code_masked=None,
        rows_affected=1,
        account_fingerprint="abcdef1234567890",
        executed_at=None,
    )
    data = serialize_action(action)
    assert data["target_system_name"] == "嘉和电子病历"
    assert data["account_fingerprint"] == "abcdef123456"
    assert "error_message" not in data
    assert "emp_no" not in data
