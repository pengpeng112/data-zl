"""Parse-level unit tests for medical dict import (no DB write)."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.import_medical_maintenance_dicts import (
    MANAGED_CODE_SETS,
    build_payload,
    find_source_files,
)

SOURCE_DIR = Path(__file__).resolve().parents[2] / "开发起步包" / "诊断与手术维护"


@pytest.mark.skipif(not SOURCE_DIR.exists(), reason="maintenance Excel not present")
def test_find_source_files():
    diag, oper = find_source_files(SOURCE_DIR)
    assert "诊断" in diag.name
    assert "手术" in oper.name


@pytest.mark.skipif(not SOURCE_DIR.exists(), reason="maintenance Excel not present")
def test_build_payload_baseline_shape():
    items, mappings, meta = build_payload(SOURCE_DIR)
    assert meta["code_sets"] == 8
    assert len(MANAGED_CODE_SETS) == 8
    assert meta["items"] > 0
    assert meta["mappings"] > 0
    assert meta["diagnosis_sha256"]
    assert meta["operation_sha256"]
    # baseline from plan 75 (informational; do not hard-fail on small drift)
    assert meta["items"] >= 100000
    assert set(meta["items_by_code_set"]) <= MANAGED_CODE_SETS or set(meta["items_by_code_set"]).issubset(MANAGED_CODE_SETS)
