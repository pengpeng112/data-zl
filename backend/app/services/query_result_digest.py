"""144 S2: content-addressed result digests (144 §4.5).

- result_digest: SHA-256 over canonical (column-set, sorted rows) content —
  same row count with different content must produce different digests;
- schema_digest: SHA-256 over the sorted column-name set;
- decimals and floats normalize identically so driver variance cannot
  fabricate digest churn.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

RESULT_DIGEST_VERSION = "result_digest/v1"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        # canonical numeric string: 1.0 == 1.00 == 1
        return str(value.normalize())
    if isinstance(value, float):
        return str(Decimal(repr(value)).normalize())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int,)):
        return str(Decimal(value).normalize())
    if isinstance(value, str):
        return value
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in sorted(value.items(), key=lambda kv: kv[0])}
    # datetimes etc: ISO-ish textual form
    return str(value)


def _canonical_rows(columns: list[str], rows: list[dict]) -> list[list[Any]]:
    normalized = []
    for row in rows:
        normalized.append([_normalize_value(row.get(c)) for c in columns])
    normalized.sort(key=lambda r: json.dumps(r, ensure_ascii=False, default=str))
    return normalized


def compute_result_digest(columns: list[str], rows: list[dict]) -> str:
    """SHA-256 over canonical column set + sorted normalized rows."""
    cols = sorted(c for c in (columns or []))
    payload = {
        "v": RESULT_DIGEST_VERSION,
        "columns": cols,
        "rows": _canonical_rows(cols, rows or []),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_schema_digest(columns: list[str]) -> str:
    """SHA-256 over the sorted column-name set (order-insensitive)."""
    cols = sorted(c for c in (columns or []))
    blob = json.dumps({"v": "schema_digest/v1", "columns": cols}, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def summary_digest(counts: dict[str, int]) -> str:
    """SHA-256 over aggregate counts only (for detail runs we never store)."""
    blob = json.dumps(
        {"v": "summary_digest/v1", "counts": dict(sorted((counts or {}).items()))},
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
