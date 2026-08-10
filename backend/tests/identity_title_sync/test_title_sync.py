import json
import os
from unittest.mock import MagicMock

import pytest

from scripts import sync_jhemr_education_titles as title_sync


def test_build_source_map_uses_employee_title_dictionary_and_skips_unmapped():
    source, stats = title_sync._build_source_map(
        [
            {"DICT_CODE": "L1", "DICT_NAME": "Title One"},
            {"DICT_CODE": "L1", "DICT_NAME": "Title One"},
        ],
        [
            {"EMPLCODE": "E1", "LEVLCODE": "L1"},
            {"EMPLCODE": "E2", "LEVLCODE": None},
        ],
    )
    assert source == {"E1": "Title One"}
    assert stats["mapped_employees"] == 1
    assert stats["unmapped_employees"] == 1


def test_build_source_map_fails_closed_on_conflicting_dictionary_name():
    with pytest.raises(title_sync.TitleSyncError, match="source_dictionary_ambiguous"):
        title_sync._build_source_map(
            [
                {"DICT_CODE": "L1", "DICT_NAME": "Title One"},
                {"DICT_CODE": "L1", "DICT_NAME": "Title Two"},
            ],
            [{"EMPLCODE": "E1", "LEVLCODE": "L1"}],
        )


def test_build_source_map_fails_closed_on_conflicting_employee_levels():
    with pytest.raises(title_sync.TitleSyncError, match="source_employee_title_ambiguous"):
        title_sync._build_source_map(
            [
                {"DICT_CODE": "L1", "DICT_NAME": "Title One"},
                {"DICT_CODE": "L2", "DICT_NAME": "Title Two"},
            ],
            [
                {"EMPLCODE": "E1", "LEVLCODE": "L1"},
                {"EMPLCODE": "E1", "LEVLCODE": "L2"},
            ],
        )


def test_build_changes_overwrites_existing_nonempty_value(monkeypatch):
    monkeypatch.setattr(
        title_sync,
        "compute_account_fingerprint",
        lambda user_id, target, key_ref: f"fp-{user_id}",
    )
    changes, stats = title_sync._build_changes(
        {"E1": "New Title", "E2": "Same Title", "E3": "Missing"},
        {"E1": "Old Title", "E2": "Same Title"},
        21,
    )
    assert [(row.user_id, row.old_title, row.new_title) for row in changes] == [
        ("E1", "Old Title", "New Title")
    ]
    assert stats == {
        "matched_target_users": 2,
        "already_equal": 1,
        "missing_target_users": 1,
        "changed_users": 1,
        "overlength_titles": 0,
    }


def test_backup_is_mode_0600_and_bound_to_exact_plan(tmp_path):
    path = tmp_path / "title-backup.json"
    changes = [title_sync.Change("E1", "Old", "New", "fingerprint")]
    digest = title_sync._write_backup(path, changes)
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    title_sync._load_and_verify_backup(path, digest, changes)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["new_title"] = "Changed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(title_sync.TitleSyncError, match="backup_digest_mismatch"):
        title_sync._load_and_verify_backup(path, digest, changes)


def test_adapter_overwrites_nonempty_title_and_reads_it_back():
    from app.services.jhemr_identity_adapter import JhemrIdentityAdapter

    adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
    adapter.hospital_no = "49557032X"
    adapter.sync_operator_id = "TEST"
    adapter._fetch_user = lambda emp_no: {
        "user_id": emp_no,
        "education_title": "Old Title",
    }
    conn = MagicMock()
    adapter._ensure_conn = lambda: conn
    writes = []

    def execute_write(sql, params):
        writes.append((sql, params))
        return 1

    def fetch_one(sql, params):
        if "SELECT education_title" in sql:
            return {"education_title": "New Title"}
        if "users_control_mode" in sql:
            return {"user_id": params[0]}
        return {"role_group_id": "001"}

    adapter._execute_write = execute_write
    adapter._fetch_one = fetch_one
    adapter._existing_dept_codes = lambda user_id: {"D001"}
    adapter._fetch_all = lambda sql, params: (
        [{"login_way": way} for way in ("0", "2", "4")]
        if "users_sublogin" in sql
        else [{"sign_way": way} for way in ("0", "2", "4")]
    )

    result = adapter.align_existing_user(
        "E001", "doctor", ["D001"], "001", job_title="New Title"
    )

    assert result["status"] == "success"
    title_writes = [(sql, params) for sql, params in writes if "education_title" in sql]
    assert len(title_writes) == 1
    assert title_writes[0][1][0] == "New Title"
    conn.commit.assert_called_once()
