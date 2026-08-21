from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "harvest_his_views_readonly.py"
SPEC = importlib.util.spec_from_file_location("harvest_his_views_readonly", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validate_owners_normalizes_and_sorts() -> None:
    assert MODULE.validate_owners(["medrec", "HISUSER", "medrec"]) == ["HISUSER", "MEDREC"]


@pytest.mark.parametrize("owner", ["MEDREC;DROP", "A B", "A.B", "'HISUSER'"])
def test_validate_owners_rejects_non_identifiers(owner: str) -> None:
    with pytest.raises(ValueError):
        MODULE.validate_owners([owner])


def test_sanitize_text_removes_common_secret_shapes() -> None:
    text = (
        "select 'password=secret-value' a, "
        "'http://user:secret@example.invalid/x?token=token-value' b from dual"
    )
    sanitized = MODULE.sanitize_text(text)
    assert sanitized is not None
    assert "secret-value" not in sanitized
    assert "token-value" not in sanitized
    assert "***" in sanitized


def test_view_definition_sanitizer_masks_literals_and_bounds_clob() -> None:
    sql = "SELECT * FROM t WHERE patient_id=123456 AND name='person' AND token='secret'"
    cleaned = MODULE.sanitize_view_definition(sql)
    assert cleaned is not None
    assert "123456" not in cleaned
    assert "person" not in cleaned
    assert "secret" not in cleaned
    assert len(MODULE.sanitize_view_definition("x" * 1_100_000)) == MODULE.MAX_VIEW_DEFINITION_LENGTH


def test_normalize_rows_uses_lowercase_keys() -> None:
    assert MODULE.normalize_rows([{"OWNER": "MEDREC", "COUNT": 2}]) == [
        {"owner": "MEDREC", "count": 2}
    ]
