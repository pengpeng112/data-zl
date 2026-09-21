# r188 builder FK-candidate derivation regressions (pure logic, no DB)
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


_builder = _load("build_r188_package_and_import")
_oracle_fk_candidates = _builder._oracle_fk_candidates
_pg_fk_candidate = _builder._pg_fk_candidate


def _r(owner, table, col, pos, r_owner=None, r_table=None, r_col=None, name="FK_1"):
    return {"constraint_type": "R", "owner": owner, "table_name": table,
            "column_name": col, "position": pos, "constraint_name": name,
            "r_owner": r_owner, "r_table_name": r_table, "r_column_name": r_col}


def _pu(ctype, owner, table, col, pos, name):
    return {"constraint_type": ctype, "owner": owner, "table_name": table,
            "column_name": col, "position": pos, "constraint_name": name}


def test_oracle_single_fk_derives_refcol_by_position():
    rows = [
        _pu("P", "APP", "DEPT", "DEPT_ID", 1, "PK_DEPT"),
        _r("APP", "EMP", "DEPT_ID", 1, "APP", "DEPT", None, name="FK_EMP_DEPT"),
    ]
    (cand,) = _oracle_fk_candidates(rows)
    assert cand["from_table"] == "APP.EMP" and cand["to_table"] == "APP.DEPT"
    assert cand["from_columns"] == "DEPT_ID" and cand["to_columns"] == "DEPT_ID"
    assert cand["evidence_kind"] == "declared_fk_pos_derived"
    assert cand["join_condition"] == "DEPT_ID=DEPT_ID"


def test_oracle_composite_fk_merges_rows_in_position_order():
    rows = [
        _pu("U", "APP", "ORD_LINE", "ORD_ID", 1, "UK_LINE"),
        _pu("U", "APP", "ORD_LINE", "LINE_NO", 2, "UK_LINE"),
        _r("APP", "ITEM", "O_ID", 1, "APP", "ORD_LINE", None, name="FK_C"),
        _r("APP", "ITEM", "L_NO", 2, "APP", "ORD_LINE", None, name="FK_C"),
    ]
    (cand,) = _oracle_fk_candidates(rows)
    assert cand["from_columns"] == "O_ID,L_NO"
    assert cand["to_columns"] == "ORD_ID,LINE_NO"
    assert cand["join_condition"] == "O_ID=ORD_ID,L_NO=LINE_NO"


def test_oracle_ambiguous_reference_keeps_refcol_missing():
    # two same-arity unique constraints on the referenced table -> cannot map
    rows = [
        _pu("U", "APP", "T", "A", 1, "U1"),
        _pu("U", "APP", "T", "B", 1, "U2"),
        _r("APP", "S", "X", 1, "APP", "T", None, name="FK_A"),
    ]
    (cand,) = _oracle_fk_candidates(rows)
    assert cand["evidence_kind"] == "declared_fk_refcol_missing"
    assert cand["to_columns"] == ""


def test_oracle_unbalanced_arity_not_derived():
    rows = [
        _pu("P", "APP", "T", "A", 1, "PK1"),
        _pu("P", "APP", "T", "B", 2, "PK1"),
        _r("APP", "S", "X", 1, "APP", "T", None, name="FK_B"),
    ]
    (cand,) = _oracle_fk_candidates(rows)
    assert cand["to_columns"] == ""


def test_pg_definition_parsed_same_schema_and_qualified():
    row = {"schema": "public", "table_name": "Child",
           "definition": 'FOREIGN KEY ("PId") REFERENCES "Parent"("Id") ON DELETE CASCADE'}
    cand = _pg_fk_candidate(row)
    assert cand["from_table"] == "public.Child"
    assert cand["to_table"] == "public.Parent"
    assert cand["from_columns"] == "PId" and cand["to_columns"] == "Id"
    assert cand["evidence_kind"] == "declared_fk_def_parsed"

    row2 = {"schema": "public", "table_name": "Child",
            "definition": 'FOREIGN KEY ("A","B") REFERENCES other."Parent"("X","Y")'}
    cand2 = _pg_fk_candidate(row2)
    assert cand2["to_table"] == "other.Parent"
    assert cand2["from_columns"] == "A,B" and cand2["to_columns"] == "X,Y"


def test_pg_unparseable_falls_back_to_def_text():
    row = {"schema": "public", "table_name": "T", "definition": "something odd"}
    cand = _pg_fk_candidate(row)
    assert cand["evidence_kind"] == "declared_fk_def_text"
    assert cand["from_columns"] == "" and cand["to_columns"] == ""
    assert cand["join_condition"] == "something odd"
