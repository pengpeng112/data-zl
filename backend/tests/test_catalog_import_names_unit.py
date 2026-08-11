"""Pure source-contract checks for catalog import naming (no database required)."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = {
    "PAPERLESS_CDMS": "无纸化病案",
    "DOCARE": "Docare手术麻醉",
    "LIS_SOURCE": "LIS",
    "ULTRASOUND_ENDOSCOPY": "超声内镜",
    "PACS_SOURCE": "PACS",
    "MOBILE_NURSING": "移动护理",
}


def _assignment(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AssertionError(f"missing assignment {name}")


def test_explored_profiles_reference_canonical_system_names():
    source = (ROOT / "backend/scripts/import_explored_sources_to_platform.py").read_text(encoding="utf-8")
    profiles = _assignment(ast.parse(source), "PROFILES")
    assert isinstance(profiles, ast.Dict)
    for profile in profiles.values:
        assert isinstance(profile, ast.Dict)
        fields = {key.value: value for key, value in zip(profile.keys, profile.values) if isinstance(key, ast.Constant)}
        system_code = fields["system_code"].value
        name_ref = fields["system_name"]
        assert isinstance(name_ref, ast.Subscript)
        assert isinstance(name_ref.value, ast.Name) and name_ref.value.id == "CANONICAL_SYSTEMS"
        assert isinstance(name_ref.slice, ast.Constant)
        assert name_ref.slice.value == system_code
        assert system_code in CANONICAL


def test_normalized_import_has_no_ods_first_level_legacy_system_loop():
    source = (ROOT / "backend/scripts/import_normalized_to_platform.py").read_text(encoding="utf-8")
    assert 'CANONICAL_SYSTEMS["DATA_CENTER"]' in source
    assert 'CANONICAL_SYSTEMS["HIS_SOURCE"]' in source
    assert 'db, "DATA_CENTER", CANONICAL_SYSTEMS["DATA_CENTER"]' in source
    assert 'db, "HIS_SOURCE", CANONICAL_SYSTEMS["HIS_SOURCE"]' in source
    assert 'source_code.startswith("ods_")' in source
    assert 'src.system_code = "DATA_CENTER"' in source
    assert '("LIS", "检验系统"' not in source
    assert '("PACS", "影像系统"' not in source
    assert '("MOBILE_NURSING", "移动护理"' not in source


def test_backfill_uses_canonical_system_catalog():
    source = (ROOT / "backend/scripts/backfill_catalog_display_names.py").read_text(encoding="utf-8")
    assert "SYSTEM_NAMES = CANONICAL_SYSTEMS" in source
