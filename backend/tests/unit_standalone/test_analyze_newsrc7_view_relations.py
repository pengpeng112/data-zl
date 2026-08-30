from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "analyze_newsrc7_view_relations.py"
SPEC = importlib.util.spec_from_file_location("analyze_newsrc7_view_relations", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_cte_alias_is_not_emitted_as_a_physical_table() -> None:
    edges, statements, parsed = MODULE.extract_edges(
        "WITH a AS (SELECT id FROM dbo.source_table) "
        "SELECT * FROM a JOIN dbo.real_table r ON a.id = r.id",
        "tsql",
    )

    assert parsed is True
    assert statements == 1
    assert edges == set()


def test_tsql_name_resolves_against_snapshot_identity() -> None:
    index = {"CATALOG": {"REPORTSERVER.DBO.CATALOG"}}

    assert MODULE.qualify_tsql_name("CATALOG", index, "REPORTSERVER", "DBO") == (
        "REPORTSERVER.DBO.CATALOG"
    )
    assert MODULE.qualify_tsql_name("missing", index, "REPORTSERVER", "DBO") is None
