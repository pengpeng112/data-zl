from unittest.mock import MagicMock

from app.services.jhemr_identity_adapter import ACCOUNT_STATUS_LOCKED, JhemrIdentityAdapter, JhemrIdentityError


def _adapter() -> JhemrIdentityAdapter:
    adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
    adapter.hospital_no = "49557032X"
    adapter._conn = MagicMock()
    return adapter


def test_lock_account_success():
    adapter = _adapter()
    conn = MagicMock()
    adapter._ensure_conn = lambda: conn
    adapter._fetch_one = MagicMock(side_effect=[
        {"user_id": "000151", "account_status": 0, "locked_time": None},
        {"account_status": 8, "locked_time": "2026-08-18 12:00:00"},
    ])
    adapter._execute_write = MagicMock(return_value=1)
    result = adapter.lock_account("000151")
    assert result["status"] == "success"
    assert result["account_status"] == ACCOUNT_STATUS_LOCKED
    conn.commit.assert_called_once()


def test_lock_account_already_locked():
    adapter = _adapter()
    adapter._ensure_conn = lambda: MagicMock()
    adapter._fetch_one = MagicMock(return_value={
        "user_id": "000151", "account_status": 8, "locked_time": "2026-08-01",
    })
    adapter._execute_write = MagicMock()
    result = adapter.lock_account("000151")
    assert result["status"] == "skipped"
    assert result["reason"] == "already_locked"
    adapter._execute_write.assert_not_called()


def test_lock_account_missing():
    adapter = _adapter()
    adapter._fetch_one = MagicMock(return_value=None)
    result = adapter.lock_account("000151")
    assert result["status"] == "missing_target"


def test_lock_account_readback_mismatch_rolls_back():
    adapter = _adapter()
    conn = MagicMock()
    adapter._ensure_conn = lambda: conn
    adapter._fetch_one = MagicMock(side_effect=[
        {"user_id": "000151", "account_status": 0, "locked_time": None},
        {"account_status": 0, "locked_time": None},
    ])
    adapter._execute_write = MagicMock(return_value=1)
    try:
        adapter.lock_account("000151")
        raise AssertionError("expected JhemrIdentityError")
    except JhemrIdentityError:
        conn.rollback.assert_called()
