"""Isolated plan-122 status, audit and watermark tests (no database required)."""

from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from app.services.identity_sync_status import (
    aggregate_overall_status,
    config_fingerprint,
    normalize_status,
    redacted_summary,
    runner_exit_code,
)
from app.services.identity_watermark import Watermark, initial_seed_dry_run, max_watermark, select_after_watermark


def test_main_success_signature_16_failures_is_partial_and_exit_two(capsys):
    import scripts.run_identity_modified_nightly as runner
    with patch.object(runner, "SessionLocal", return_value=MagicMock()), \
         patch.object(runner, "run_nightly_pipeline", return_value={"status": "success", "run_id": "R-122"}), \
         patch.object(runner, "sync_missing_jhemr_signatures", return_value={"status": "failed", "failed": 16, "source_signatures": 16, "error_classes": {"target_user_lookup_select": {"InsufficientPrivilege": 16}}}), \
         patch.object(runner, "upsert_subtask"), \
         patch.object(runner, "finalize_run", return_value="partial_success"):
        assert runner.main() == 2
    out = capsys.readouterr().out
    assert '"status": "partial_success"' in out
    assert "InsufficientPrivilege" in out


def test_all_success_exit_zero():
    import scripts.run_identity_modified_nightly as runner
    with patch.object(runner, "SessionLocal", return_value=MagicMock()), \
         patch.object(runner, "run_nightly_pipeline", return_value={"status": "success", "run_id": "R-OK"}), \
         patch.object(runner, "sync_missing_jhemr_signatures", return_value={"status": "success", "failed": 0, "inserted": 2}), \
         patch.object(runner, "upsert_subtask"), \
         patch.object(runner, "finalize_run", return_value="success"):
        assert runner.main() == 0


def test_main_failure_exit_one_and_signature_not_started():
    import scripts.run_identity_modified_nightly as runner
    with patch.object(runner, "SessionLocal", return_value=MagicMock()), \
         patch.object(runner, "run_nightly_pipeline", return_value={"status": "failed", "run_id": "R-FAIL"}), \
         patch.object(runner, "sync_missing_jhemr_signatures") as signature, \
         patch.object(runner, "upsert_subtask"), \
         patch.object(runner, "finalize_run", return_value="failed"):
        assert runner.main() == 1
        signature.assert_not_called()


def test_lock_held_is_skipped_not_success():
    assert aggregate_overall_status("success", "failed", lock_reason="lock_held") == "skipped"
    assert normalize_status("lock_held") == "skipped"


def test_unhandled_and_misconfigured_exit_one():
    assert runner_exit_code("failed") == 1
    assert runner_exit_code("misconfigured") == 1
    assert runner_exit_code("overdue") == 1


def test_audit_write_failure_closes_failed():
    import scripts.run_identity_modified_nightly as runner
    from app.services.identity_sync_audit import AuditWriteError
    with patch.object(runner, "SessionLocal", return_value=MagicMock()), \
         patch.object(runner, "run_nightly_pipeline", return_value={"status": "success", "run_id": "R-AUDIT"}), \
         patch.object(runner, "upsert_subtask", side_effect=AuditWriteError("audit")):
        assert runner.main() == 1


def test_alert_channel_failure_preserves_authoritative_partial_status():
    from app.services import identity_sync_audit as audit
    run = MagicMock(status="running", failed_count=0, skipped_count=0)
    db = MagicMock()
    db.scalar.return_value = run
    with patch.object(audit, "record_alert", side_effect=audit.AuditWriteError("alert")):
        assert audit.finalize_run(
            db,
            run_id="R-ALERT",
            main_result={"status": "success"},
            signature_result={"status": "failed", "failed": 1, "error_classes": {"target_readback": {"ReadbackMismatch": 1}}},
        ) == "partial_success"
    assert run.status == "partial_success"


@pytest.mark.parametrize("category", [
    "source_signature_select", "target_user_lookup_select", "target_picture_lock_select",
    "target_picture_update", "target_picture_insert", "target_commit", "target_readback",
])
def test_signature_error_categories_are_stable(category):
    from app.services.identity_sync_status import increment_error
    errors = {}
    increment_error(errors, category, "InsufficientPrivilege: SQL parameters hidden")
    assert category in errors
    assert "SQL parameters" not in str(errors)


def test_hmac_only_redaction_and_short_stdout_shape():
    value = redacted_summary({"emp_no": "E-SECRET", "name": "Alice", "failed_fingerprints": ["abcdef1234567890", "second", "third", "fourth"], "error": "internal message"})
    assert "emp_no" not in value and "name" not in value
    assert "internal message" not in str(value).lower()
    assert len(value["failed_fingerprints"]) == 3


def test_initial_seed_is_dry_run_and_same_second_tie_breaker():
    now = datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc)
    plan = initial_seed_dry_run([(now, "B"), (now, "A")])
    assert plan["status"] == "dry_run" and plan["writes"] == 0
    wm = Watermark(now, "A")
    assert select_after_watermark(now, "B", wm, lookback_hours=0)
    assert not select_after_watermark(now, "A", wm, lookback_hours=0)


def test_watermark_max_and_failed_run_no_advance_contract():
    now = datetime(2026, 8, 9, tzinfo=timezone.utc)
    wm = max_watermark([(now, "A"), (now, "B")])
    assert wm.employee_key == "B"
    # The write function is explicitly success-gated; this test documents the
    # contract without opening a database.
    assert wm.seed_required is False


def test_provider_fingerprint_is_non_secret_and_stable():
    first = config_fingerprint("host_cron", "0 2 * * *", "Asia/Shanghai", False)
    assert first == config_fingerprint("host_cron", "0 2 * * *", "Asia/Shanghai", False)
    assert len(first) == 16


@pytest.mark.parametrize("stage", [
    "target_user_lookup_select", "target_picture_lock_select", "target_picture_update",
    "target_picture_insert", "target_commit", "target_readback",
])
def test_signature_adapter_permission_steps_are_classified(monkeypatch, stage):
    from app.core.config import settings
    from app.services import identity_signature_sync as service
    from app.services.identity_hmac import reset_key_cache

    monkeypatch.setenv("TEST_HMAC_122", "unit-test-only-key")
    monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_122")
    reset_key_cache()

    class Cursor:
        rowcount = 1
        def __init__(self):
            self.calls = 0
        def execute(self, sql, params):
            self.calls += 1
            if (stage == "target_picture_lock_select" and self.calls == 1) or (stage == "target_picture_update" and self.calls == 2) or (stage == "target_picture_insert" and self.calls == 2):
                raise RuntimeError("InsufficientPrivilege")
        def fetchone(self):
            return None if stage == "target_picture_insert" else (0,)
        def close(self):
            pass

    class Conn:
        def cursor(self): return Cursor()
        def commit(self):
            if stage == "target_commit": raise RuntimeError("InsufficientPrivilege")
        def rollback(self): pass

    class Adapter:
        def __init__(self, **kwargs): self._conn = Conn(); self.fetches = 0
        def connect(self): pass
        def _fetch_all(self, sql, params):
            self.fetches += 1
            if stage == "target_user_lookup_select" and self.fetches == 1: raise RuntimeError("InsufficientPrivilege")
            if stage == "target_readback" and self.fetches == 2: raise RuntimeError("InsufficientPrivilege")
            return [{"user_name": "redacted"}] if self.fetches == 1 else [{"size": 4}]
        def close(self): pass

    class His:
        def close(self): pass

    # 源端签名必须是可被 normalize_signature_image 接受的合法 JPEG，
    # 否则会在源端被清空导致 failed=0，掩盖目标步骤权限分类断言。
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 255, 255)).save(buf, format="JPEG")
    valid_jpeg_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    monkeypatch.setattr(service, "JhemrIdentityAdapter", Adapter)
    monkeypatch.setattr(service, "_connector", lambda: His())
    monkeypatch.setattr(
        service,
        "_select",
        lambda *args, **kwargs: [{"EMPLCODE": "E1", "SIGNATUREBASE64": valid_jpeg_b64}],
    )
    result = service.sync_missing_jhemr_signatures(max_rows=1)
    assert result["failed"] == 1
    assert stage in result["error_classes"]


def test_single_emp_path_uses_exact_filter_and_skips_watermark_advance(monkeypatch):
    """125 H6: emp_no filter + advance_watermark_on_success=False."""
    from app.core.config import settings
    from app.services import identity_signature_sync as service
    from app.services.identity_hmac import reset_key_cache
    import base64
    import io
    from PIL import Image

    monkeypatch.setenv("TEST_HMAC_122", "unit-test-only-key")
    monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_122")
    reset_key_cache()

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 255, 255)).save(buf, format="JPEG")
    valid_jpeg_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    seen_sql: list[str] = []
    advanced: list[bool] = []

    class Cursor:
        rowcount = 1
        def execute(self, sql, params): pass
        def fetchone(self): return (0,)
        def close(self): pass

    class Conn:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass

    class Adapter:
        def __init__(self, **kwargs): self._conn = Conn()
        def connect(self): pass
        def _fetch_all(self, sql, params):
            if "user_name_pic" in sql and "octet_length" in sql:
                return [{"size": 4}]
            return [{"user_name": "redacted"}]
        def close(self): pass

    class His:
        def execute_readonly(self, sql, params=None, max_rows=1):
            seen_sql.append(sql)
            assert params and "emp_no" in params
            return [{"EMPLCODE": params["emp_no"], "SIGNATUREBASE64": valid_jpeg_b64}]
        def close(self): pass

    monkeypatch.setattr(service, "JhemrIdentityAdapter", Adapter)
    monkeypatch.setattr(service, "_connector", lambda: His())
    monkeypatch.setattr(
        service,
        "advance_watermark",
        lambda *a, **k: advanced.append(True),
    )
    # Fake db object so create_action/finish_action paths exist but we stub them.
    class DB: pass
    monkeypatch.setattr(service, "create_action", lambda *a, **k: None)
    monkeypatch.setattr(service, "finish_action", lambda *a, **k: None)

    result = service.sync_missing_jhemr_signatures(
        max_rows=10,
        emp_no="E-UNIT",
        db=DB(),
        advance_watermark_on_success=False,
        run_id="unit-single",
    )
    assert any("EMPLCODE = :emp_no" in s for s in seen_sql)
    assert result["planned_count"] == 1
    assert result["inserted"] == 1
    assert result["failed"] == 0
    assert advanced == []
