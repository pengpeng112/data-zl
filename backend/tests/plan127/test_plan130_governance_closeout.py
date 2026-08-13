from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.plan130_governance_closeout import (
    apply_gate,
    duplicate_finding_groups,
    match_finding_table,
    require_formal_review_result,
    rollback_gate,
    rollback_state_matches,
    validate_manifest_path,
    write_manifest,
)


def finding(**kw):
    base = dict(id=1, run_id=1, rule_code="R", target_type="column", target_ref="NS.A.T.C", system_code="SYS", source_code="SRC", namespace_name="NS", schema_name="A", table_name="T", column_name="C", severity="high", metric_value="1", total_cnt=1, error_cnt=1)
    base.update(kw)
    return SimpleNamespace(**base)


def test_default_apply_gate_is_closed():
    with pytest.raises(RuntimeError):
        apply_gate(env={}, backup_ref=None, manifest=None)


def test_unique_and_ambiguous_table_match():
    f = finding()
    one = SimpleNamespace(id=8, system_code="SYS", source_code="SRC", namespace_name="NS", schema_name="A", table_name="T")
    assert match_finding_table(f, [one])["status"] == "matched"
    two = SimpleNamespace(id=9, system_code="SYS", source_code="SRC", namespace_name="NS", schema_name="A", table_name="T")
    assert match_finding_table(f, [one, two])["status"] == "ambiguous"


def test_duplicate_group_is_report_only():
    rows = [finding(id=1), finding(id=2)]
    groups = duplicate_finding_groups(rows)
    assert groups and groups[0]["count"] == 2


def test_candidate_review_never_passes_formal_gate():
    with pytest.raises(RuntimeError):
        require_formal_review_result({"ok": True, "action": "linked_candidate_no_promote"})
    require_formal_review_result({"ok": True, "action": "linked_formal"})


def test_rollback_conflict_and_idempotent_state():
    assert rollback_state_matches({"status": "approved"}, {"status": "approved"})
    assert not rollback_state_matches({"status": "changed"}, {"status": "approved"})


def test_manifest_is_outside_repo_and_0600(tmp_path: Path):
    path = tmp_path / "rollback.json"
    out = write_manifest(path, {"before": {"sample_data": "hidden"}})
    assert out == path.resolve()
    if os.name != "nt":
        assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert "sample_data" not in json.loads(path.read_text(encoding="utf-8"))["before"]
    with pytest.raises(FileExistsError):
        write_manifest(path, {"second": True})


def test_manifest_inside_repo_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        validate_manifest_path(Path(__file__).resolve())


def test_rollback_gate_uses_existing_source_manifest(tmp_path: Path):
    manifest = tmp_path / "rollback.json"
    manifest.write_text("{}", encoding="utf-8")
    rollback_gate(env={"APP_PLAN130_PLATFORM_APPLY": "true"}, backup_ref="backup.dump", manifest_from=str(manifest))
    with pytest.raises(RuntimeError):
        rollback_gate(env={}, backup_ref="backup.dump", manifest_from=str(manifest))
