from types import SimpleNamespace

from app.services.identity_sync_log import (
    reason_label,
    run_id_from_action,
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


def test_serialize_action_includes_emp_trace():
    action = SimpleNamespace(
        action_seq=1,
        target_system="JHEMR",
        subtask_code="jhemr_education_title_sync",
        action_type="update_title",
        status="executed",
        reason_code="already_has_signature",
        error_class=None,
        error_code_masked=None,
        rows_affected=1,
        account_fingerprint="abcdef1234567890",
        emp_no_masked="004061",
        params_summary={"emp_no": "004061", "person_name_masked": "张**", "dept_code": "021738"},
        executed_at=None,
    )
    data = serialize_action(action)
    assert data["target_system_name"] == "嘉和电子病历"
    assert data["account_fingerprint"] == "abcdef123456"
    assert data["emp_no"] == "004061"
    assert data["person_name_masked"] == "张**"
    assert data["dept_code"] == "021738"
    assert data["reason_name"] == "目标已有签名，未覆盖"
    assert "error_message" not in data


def test_run_id_from_action_supports_nightly_batch_and_signature_batch():
    assert run_id_from_action(SimpleNamespace(params_summary={"run_id": "RUN-aa"}, batch_id="x")) == "RUN-aa"
    assert (
        run_id_from_action(SimpleNamespace(params_summary={}, batch_id="NTL-RUN-4fab0af6fc29-195738e1"))
        == "RUN-4fab0af6fc29"
    )
    assert (
        run_id_from_action(
            SimpleNamespace(params_summary={}, batch_id="RUN-ea7c75b2b885:jhemr_signature_sync:d2ebdfae9c91abcd")
        )
        == "RUN-ea7c75b2b885"
    )
    assert reason_label("no_target_user") == "嘉和无此账号"
