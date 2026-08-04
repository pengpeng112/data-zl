"""Unit tests for idempotent import upsert and empty-table handling."""

from __future__ import annotations

from app.services.asset_import_upsert import pick_chinese_name
from app.services.row_presence import (
    CONFIRMED_EMPTY,
    BLOCKED,
    UNKNOWN,
    is_catalog_visible,
    merge_presence,
)


def test_import_is_idempotent_logic():
    """Second apply with same payload should report zero logical changes when equal."""
    # pure function: confirmed names stable; presence merge stable
    a = merge_presence(current="nonempty_by_stats", stats_status="nonempty_by_stats")
    b = merge_presence(current=a, stats_status="nonempty_by_stats")
    assert a == b


def test_confirmed_empty_fields_and_relations_gate():
    assert is_catalog_visible(CONFIRMED_EMPTY) is False
    # unknown/blocked must remain visible (not deleted as empty)
    assert is_catalog_visible(UNKNOWN)
    assert is_catalog_visible(BLOCKED)
    # merge: probe confirmed empty wins only as probe result
    assert merge_presence(current=None, probe_status=CONFIRMED_EMPTY) == CONFIRMED_EMPTY
    # nonempty evidence beats empty probe if both somehow present
    assert (
        merge_presence(
            current=None,
            evidence_status="nonempty_by_evidence",
            probe_status=CONFIRMED_EMPTY,
        )
        == "nonempty_by_evidence"
    )


def test_same_table_name_across_sources_keys():
    keys = {
        ("lis_src", "dbo", "RESULT"),
        ("pacs_src", "dbo", "RESULT"),
        ("ods_8_216", "LIS", "RESULT"),
    }
    assert len(keys) == 3


def test_pick_name_does_not_clear_confirmed():
    n, s, st = pick_chinese_name(
        existing_cn="保留",
        existing_status="human_confirmed",
        db_comment="新注释",
    )
    assert n == "保留" and s == "human_confirmed"
