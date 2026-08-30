from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "harvest_oracle_readonly.py"
SPEC = importlib.util.spec_from_file_location("harvest_oracle_readonly", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_json_username_is_normalized_to_user(tmp_path: Path) -> None:
    credential_file = tmp_path / "oracle.json"
    credential_file.write_text(
        json.dumps({"username": "readonly_user", "password": "secret"}),
        encoding="utf-8",
    )

    assert MODULE.read_credential_file(str(credential_file)) == {
        "user": "readonly_user",
        "password": "secret",
    }


def test_index_join_uses_both_index_and_table_identity() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "c.INDEX_NAME=i.INDEX_NAME" in source
    assert "c.TABLE_OWNER=i.TABLE_OWNER" in source
    assert "c.TABLE_NAME=i.TABLE_NAME" in source
    assert "c.INDEX_NAME=c.INDEX_NAME" not in source


def test_default_client_path_is_oracle_11g_compatible_thick_client() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"/opt/oracle/instantclient_21"' in source
    assert "Oracle thick client initialization failed" in source
