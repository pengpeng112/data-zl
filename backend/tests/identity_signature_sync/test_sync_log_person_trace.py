from types import SimpleNamespace

from app.services.identity_sync_audit import _mask_person_name
from app.services.identity_sync_log import reason_label, run_id_from_action, serialize_action


def test_mask_person_name():
    assert _mask_person_name("张三") == "张*"
    assert _mask_person_name("张三四") == "张**"
    assert _mask_person_name("") == ""


def test_serialize_action_includes_emp_trace():
    action = SimpleNamespace(
        action_seq=1,
        target_system="JHEMR",
        subtask_code="jhemr_signature_sync",
        action_type="signature_sync",
        status="skipped",
        reason_code="already_has_signature",
        error_class=None,
        error_code_masked=None,
        rows_affected=0,
        account_fingerprint="abcdef1234567890",
        emp_no_masked="004061",
        params_summary={"emp_no": "004061", "person_name_masked": "张**", "dept_code": "021738"},
        executed_at=None,
    )
    data = serialize_action(action)
    assert data["emp_no"] == "004061"
    assert data["person_name_masked"] == "张**"
    assert data["reason_name"] == "目标已有签名，未覆盖"
    assert data["account_fingerprint"] == "abcdef123456"


def test_run_id_from_action_parses_batch_shapes():
    assert run_id_from_action(SimpleNamespace(params_summary={"run_id": "RUN-aa"}, batch_id="x")) == "RUN-aa"
    assert (
        run_id_from_action(SimpleNamespace(params_summary={}, batch_id="NTL-RUN-4fab0af6fc29-195738e1"))
        == "RUN-4fab0af6fc29"
    )
    assert reason_label("no_target_user") == "嘉和无此账号"
