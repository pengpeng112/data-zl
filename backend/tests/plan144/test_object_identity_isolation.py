"""A06/A22: exact physical object keys; same-name tables never cross sources."""
from __future__ import annotations

import pytest

from app.services.ai_context_builder import filter_ai_readable
from app.services.object_identity import (
    AmbiguousObjectError,
    build_object_key,
    resolve_object,
)


def test_object_key_format_roundtrip():
    key = build_object_key(
        system_code="HIS",
        source_code="his_source_10_10_10_15",
        schema_name="FXHIS",
        object_name="PAT_VISIT",
        object_type="table",
    )
    assert key == "HIS|his_source_10_10_10_15||FXHIS|PAT_VISIT|table"


def test_object_key_rejects_missing_identity():
    with pytest.raises(ValueError):
        build_object_key(
            system_code="HIS", source_code="", schema_name="FXHIS",
            object_name="PAT_VISIT", object_type="table",
        )


_OBJECTS = [
    {
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "schema_name": "HIS",
        "object_name": "PAT_VISIT",
        "object_type": "table",
    },
    {
        "system_code": "HIS",
        "source_code": "his_source_10_10_10_15",
        "schema_name": "FXHIS",
        "object_name": "PAT_VISIT",
        "object_type": "table",
    },
]


def test_same_name_table_resolves_only_within_requested_source():
    hit = resolve_object(
        _OBJECTS, source_code="his_source_10_10_10_15", schema_name="FXHIS",
        object_name="PAT_VISIT",
    )
    assert hit["system_code"] == "HIS"


def test_resolution_without_source_fails_closed_when_ambiguous():
    # same schema+name across two sources: without source_code this is ambiguous
    same_schema = [
        {
            "system_code": "DATA_CENTER",
            "source_code": "ods_8_216",
            "schema_name": "HIS",
            "object_name": "PAT_VISIT",
            "object_type": "table",
        },
        {
            "system_code": "HIS",
            "source_code": "his_source_mirror",
            "schema_name": "HIS",
            "object_name": "PAT_VISIT",
            "object_type": "table",
        },
    ]
    with pytest.raises(AmbiguousObjectError):
        resolve_object(same_schema, schema_name="HIS", object_name="PAT_VISIT")


def test_unknown_object_resolves_to_none():
    assert (
        resolve_object(
            _OBJECTS, source_code="ods_8_216", schema_name="HIS", object_name="NOT_A_TABLE"
        )
        is None
    )


def test_ai_readable_false_filtered_even_without_system_filter():
    items = [
        {"object_name": "KEEP", "ai_readable": True, "system_code": "A"},
        {"object_name": "DROP", "ai_readable": False, "system_code": "A"},
        {"object_name": "UNKNOWN_FLAG", "system_code": "A"},  # missing flag: fail closed
    ]
    out = filter_ai_readable(items)
    assert [i["object_name"] for i in out] == ["KEEP"]
