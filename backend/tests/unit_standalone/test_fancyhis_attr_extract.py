from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "fancyhis_attr_extract.py"
SPEC = importlib.util.spec_from_file_location("fancyhis_attr_extract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("'/fancy/esb-interaction/esb/esbmsgmethod", "/fancy/esb-interaction/esb/esbmsgmethod"),
        ("!/api/InPatient/UpdateRegisterInfo", "/api/InPatient/UpdateRegisterInfo"),
        ('"/api/pub/SSO?sessionId={sessionId}', "/api/pub/SSO?sessionId={sessionId}"),
        (" /api/Term/UpdateTermState", "/api/Term/UpdateTermState"),
        ("Name", None),
    ],
)
def test_normalize_route(raw: str, expected: str | None) -> None:
    assert MODULE.normalize_route(raw) == expected
