"""Row presence governance (plan 90).

Never use COUNT(*). Prefer limited existence probes. Stats alone never delete.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
import re
import time

# Status vocabulary
NON_EMPTY_STATS = "nonempty_by_stats"
NON_EMPTY_PROBE = "nonempty_by_probe"
NON_EMPTY_EVIDENCE = "nonempty_by_evidence"
CONFIRMED_EMPTY = "confirmed_empty"
UNKNOWN = "unknown"
BLOCKED = "blocked"

# Known large tables: do not probe; use evidence
KNOWN_NONEMPTY_EVIDENCE = {
    ("HIS", "LAB_RESULT"),
    ("HIS_SOURCE", "LAB_RESULT"),
}

DEFAULT_TIMEOUT_SEC = 5
MAX_CONCURRENCY_PER_CONN = 2
MAX_RETRIES = 1
CIRCUIT_BREAKER_TIMEOUTS = 10


def classify_from_stats(row_count_stats: Any) -> str | None:
    """Map rough stats to a *non-deleting* status. Never treat missing stats as empty."""
    if row_count_stats is None or row_count_stats == "":
        return None
    try:
        n = int(str(row_count_stats).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if n > 0:
        return NON_EMPTY_STATS
    # stats say 0 → still not confirmed_empty without probe
    return None


def should_skip_probe(system_code: str | None, schema: str | None, table: str | None) -> str | None:
    """Return evidence status if probe must be skipped."""
    sch = (schema or "").upper()
    tbl = (table or "").upper()
    sys = (system_code or "").upper()
    if (sch, tbl) in KNOWN_NONEMPTY_EVIDENCE or (sys, tbl) in KNOWN_NONEMPTY_EVIDENCE:
        return NON_EMPTY_EVIDENCE
    if tbl == "LAB_RESULT" and sch in {"HIS", "LAB"}:
        return NON_EMPTY_EVIDENCE
    return None


def build_probe_sql(db_type: str, schema: str, table: str, database: str | None = None) -> str:
    """Build limited existence SQL. Read-only SELECT 1 only."""
    dt = (db_type or "").lower()
    sch = schema or "public"
    tbl = table
    def dq(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'
    def bt(value: str) -> str:
        return '`' + value.replace('`', '``') + '`'
    def br(value: str) -> str:
        return '[' + value.replace(']', ']]') + ']'
    if dt in {"oracle"}:
        return f"SELECT 1 FROM {dq(sch)}.{dq(tbl)} WHERE ROWNUM <= 1"
    if dt in {"postgresql", "postgres", "vastbase"}:
        return f"SELECT 1 FROM {dq(sch)}.{dq(tbl)} LIMIT 1"
    if dt in {"mysql", "mariadb"}:
        db = database or sch
        return f"SELECT 1 FROM {bt(db)}.{bt(tbl)} LIMIT 1"
    if dt in {"sqlserver", "mssql"}:
        db = database
        # schema may be database.schema
        if "." in sch:
            parts = sch.split(".", 1)
            return f"SELECT TOP (1) 1 FROM {br(parts[0])}.{br(parts[1])}.{br(tbl)} WITH (NOLOCK)"
        prefix = f"{br(db)}." if db else ""
        return f"SELECT TOP (1) 1 FROM {prefix}{br(sch)}.{br(tbl)} WITH (NOLOCK)"
    raise ValueError(f"unsupported db_type for probe: {db_type}")


def merge_presence(
    *,
    current: str | None,
    stats_status: str | None = None,
    probe_status: str | None = None,
    evidence_status: str | None = None,
) -> str:
    """Priority: evidence/probe nonempty > confirmed_empty > stats nonempty > unknown."""
    for s in (evidence_status, probe_status, stats_status, current):
        if s in {NON_EMPTY_EVIDENCE, NON_EMPTY_PROBE, NON_EMPTY_STATS}:
            return s
    if probe_status == CONFIRMED_EMPTY:
        return CONFIRMED_EMPTY
    if probe_status in {UNKNOWN, BLOCKED}:
        return probe_status
    if stats_status:
        return stats_status
    return current or UNKNOWN


def is_catalog_visible(status: str | None) -> bool:
    """confirmed_empty must not appear in normal catalog."""
    return (status or "") != CONFIRMED_EMPTY


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def probe_one(
    execute_readonly: Callable[..., list[dict]],
    *,
    db_type: str,
    schema: str,
    table: str,
    database: str | None = None,
) -> dict[str, Any]:
    """Execute exactly one bounded SELECT and return a sample-free result."""
    started = time.perf_counter()
    try:
        rows = execute_readonly(
            build_probe_sql(db_type, schema, table, database), max_rows=1
        )
        status = NON_EMPTY_PROBE if rows else CONFIRMED_EMPTY
        return {
            "status": status,
            "method": "readonly_limit_1",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "error_code": None,
        }
    except Exception as exc:
        name = type(exc).__name__
        message = str(exc).lower()
        status = BLOCKED if any(x in message for x in ("permission", "privilege", "denied")) else UNKNOWN
        return {
            "status": status,
            "method": "readonly_limit_1",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "error_code": re.sub(r"[^A-Z0-9_]", "_", name.upper())[:80],
        }
