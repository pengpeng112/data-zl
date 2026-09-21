# -*- coding: utf-8 -*-
"""188 low-load harvester pure-logic tests (no DB): masking, fingerprint,
batching, budget accounting, engine SQL guards (static)."""
import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "harvest_r188_lowload",
    Path(__file__).resolve().parents[1] / "scripts" / "harvest_r188_lowload.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_sanitize_definition_masks_passwords():
    d = MOD.sanitize_definition(
        "CREATE USER x IDENTIFIED BY secret123; PASSWORD='abc'", 100000)
    assert "secret123" not in d["text"] and "abc" not in d["text"]
    assert "***" in d["text"] and not d["truncated"]


def test_sanitize_definition_truncates_256kib():
    d = MOD.sanitize_definition("A" * 300000, 262144)
    assert d["truncated"] is True
    assert len(d["text"].encode()) <= 262144 + 64


def test_sanitize_definition_none():
    assert MOD.sanitize_definition(None, 10)["text"] is None


def test_sql_fingerprint_stable_and_normed():
    a = MOD.sql_fingerprint("SELECT  a  FROM t WHERE x=1")
    b = MOD.sql_fingerprint("select a from t where x=1\n")
    assert a == b and len(a) == 16


def test_chunks_boundaries():
    got = list(MOD.chunks(list(range(120)), 50))
    assert [len(g) for g in got] == [50, 50, 20]


def test_budget_limits_enforced(monkeypatch):
    logs = []
    b = MOD.Budget({"budget": {"throttle_seconds": 0, "pause_every": 1000,
                               "pause_seconds": 0, "max_statements_per_source": 3}},
                   logs.append)
    for _ in range(3):
        b.pre("x")
        b.post("x", "SELECT 1", 0.1)
    try:
        b.pre("x")
        raise AssertionError("budget not enforced")
    except MOD.BudgetExceeded as exc:
        assert "max_statements" in str(exc)


def test_budget_db_seconds_cap(monkeypatch):
    logs = []
    b = MOD.Budget({"budget": {"throttle_seconds": 0, "pause_every": 1000,
                               "pause_seconds": 0, "max_db_seconds_per_source": 0.05}},
                   logs.append)
    b.pre("x")
    b.post("x", "SELECT 1", 1.0)
    try:
        b.pre("x")
        raise AssertionError("db-seconds cap not enforced")
    except MOD.BudgetExceeded as exc:
        assert "max_db_seconds" in str(exc)


def test_oracle_system_owner_filter_present():
    assert "SYSTEM" in MOD.ORACLE_SYSTEM_OWNERS_SKIP
    assert "MHS5" not in MOD.ORACLE_SYSTEM_OWNERS_SKIP  # business owner must not be filtered


def test_engines_registry_covers_four_types():
    assert set(MOD.ENGINES) == {"oracle", "mysql", "sqlserver", "postgresql"}


def test_readonly_session_init_in_source():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    assert "SET TRANSACTION READ ONLY" in src            # oracle
    assert "SET SESSION TRANSACTION READ ONLY" in src    # mysql
    assert "default_transaction_read_only" in src        # pg
    assert "SET LOCK_TIMEOUT" in src                     # sqlserver


def test_oracle_no_fetch_first_or_explain():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    assert "FETCH FIRST" not in src
    assert "EXPLAIN PLAN" not in src
    assert "DBMS_STATS" not in src
    # no stats-refresh statements (LAST_ANALYZED dictionary column is fine)
    assert "ANALYZE TABLE" not in src and "ANALYZE " not in src.replace(
        "no COUNT/ANALYZE", "").replace("LAST_ANALYZED", "")


def test_sqlserver_rows_only_index_0_1():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    assert src.count("p.index_id IN (0,1)") >= 2  # rows estimate + capacity both deduped


def test_pg_dialect_fallbacks_present():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    # PG-compatible engines (HuaChainSQL): helper-function failures must degrade,
    # not block the source (capability matrix promise)
    assert "relations_lite" in src and "columns_lite" in src
    assert 'out["dialect_errors"]' in src
    # lite paths must avoid helper functions
    import re as _re
    lite = src[src.index("relations_lite"):src.index("relations_lite") + 500]
    assert "pg_get_expr" not in lite and "obj_description" not in lite


def test_11g_compat_fallbacks_present():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    assert "identity_con_name" in src          # CON_NAME probed separately (12c+ only)
    assert "owners_fallback" in src            # oracle_maintained column (12c+ only)
    assert "USER_SEGMENTS" in src              # capacity fallback when ALL_SEGMENTS hidden


def test_pg_session_init_literal_and_tolerant():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    # HuaChainSQL rejects bind parameters in SET; must be literal + fault-tolerant
    assert "SET statement_timeout = %s" not in src
    assert "_try_set" in src and '"session_init"' in src


def test_mysql_bytes_decode_fallback_chain():
    v, fb = MOD.MySQLEngine._decode_cell("正常".encode("gbk"))
    assert v == "正常" and fb is False
    v, fb = MOD.MySQLEngine._decode_cell("ok".encode("utf-8"))
    assert v == "ok" and fb is False
    v, fb = MOD.MySQLEngine._decode_cell(b"\xed\xa0\x80bad")
    assert fb is True and "\ufffd" in v
    v, fb = MOD.MySQLEngine._decode_cell(7)
    assert v == 7 and fb is False


def test_log_durability_incremental_flush():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    # per-event append+flush so abnormal termination keeps the SQL evidence log
    assert "log_fh" in src and "log_fh.flush()" in src
    assert "args.logs.write_text" not in src


def test_oracle_tcp_connect_timeout_present():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    assert "tcp_connect_timeout" in src


def test_pg_mysql_no_params_not_sent_as_empty_tuple():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    # an empty tuple would trigger psycopg/pymysql placeholder validation and
    # reject literal '%' (e.g. NOT LIKE 'pg_toast%'); no-params must pass None
    # PGEngine is the last engine class; everything after it is stages/helpers
    pg_block = src[src.index("class PGEngine"):]
    mysql_block = src[src.index("class MySQLEngine"):src.index("class SQLServerEngine")]
    assert "params or ()" not in pg_block
    assert "params or ()" not in mysql_block
    assert "if params:" in pg_block and "if params:" in mysql_block


def test_pg_indexdef_uses_pg_class_oid():
    src = (Path(MOD.__file__).read_text(encoding="utf-8"))
    # i is the pg_class alias (i.oid = ix.indexrelid); pg_class has no indexrelid column
    assert "pg_get_indexdef(i.oid)" in src
    assert "pg_get_indexdef(i.indexrelid)" not in src


if __name__ == "__main__":
    sys.exit(0)
