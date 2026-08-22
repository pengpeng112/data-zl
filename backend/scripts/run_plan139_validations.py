"""Run bounded aggregate validations for selected plan-139 view-JOIN candidates.

Safety contract (plan 139 §4.4):
- read-only session, per-query timeout from the harvest config;
- each item aggregates at most 10,000 distinct child keys;
- only counts/match rates are returned and stored -- never patient values;
- items whose endpoints or columns do not exist are skipped, never guessed;
- no EXECUTE, no DML/DDL, no temp tables.

Runs on the server inside the API container (pymssql/pymysql available).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import harvest_mysql_readonly as mysql_harvest  # noqa: E402
import harvest_sqlserver_readonly as sqlserver_harvest  # noqa: E402

IDENT_OK = re.compile(r"^[\w#$\u4e00-\u9fff]+$")
MAX_KEYS = 10_000


def _safe_ident(value: Any) -> str:
    text = str(value or "").strip().strip("[]")
    if not IDENT_OK.fullmatch(text):
        raise ValueError(f"unsafe identifier: {value!r}")
    return text


def _parts(qualified: str) -> tuple[str, ...]:
    parts = tuple(_safe_ident(p) for p in str(qualified).split("."))
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"unsupported qualified name: {qualified!r}")
    return parts


def _columns(value: Any) -> list[str]:
    """Accept plain CSV, JSON list or Python-repr list column values."""
    text = str(value or "").strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text.replace("'", '"'))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass
        return [x.strip(" []'\"") for x in text.split(",") if x.strip(" []'\"")]
    return [x.strip() for x in text.split(",") if x.strip()]


def build_sqlserver_query(item: Mapping[str, Any]) -> str:
    child = _parts(item.get("_from") or item["from_table"])
    parent = _parts(item.get("_to") or item["to_table"])
    ccols = [_safe_ident(c) for c in _columns(item["from_columns"])]
    pcols = [_safe_ident(c) for c in _columns(item["to_columns"])]
    if len(ccols) != len(pcols) or not ccols:
        raise ValueError("unbalanced composite key")
    ctable = ".".join(f"[{p}]" for p in child)
    ptable = ".".join(f"[{p}]" for p in parent)
    key_select = ", ".join(f"c.[{c}] AS k{i}" for i, c in enumerate(ccols))
    null_filter = " AND ".join(f"c.[{c}] IS NOT NULL" for c in ccols)
    join_on = " AND ".join(f"p.[{p}] = c.k{i}" for i, p in enumerate(pcols))
    matched = " + ".join(f"CASE WHEN p.[{p}] IS NOT NULL THEN 1 ELSE 0 END" for p in pcols)
    return (
        f"WITH child_keys AS (SELECT DISTINCT TOP ({MAX_KEYS}) {key_select} "
        f"FROM {ctable} c WHERE {null_filter}) "
        f"SELECT COUNT(*) AS sampled, COALESCE(SUM({matched}), 0) AS matched "
        f"FROM child_keys c LEFT JOIN {ptable} p ON {join_on}"
    )


def build_mysql_query(item: Mapping[str, Any]) -> str:
    child = _parts(item.get("_from") or item["from_table"])
    parent = _parts(item.get("_to") or item["to_table"])
    ccols = [_safe_ident(c) for c in _columns(item["from_columns"])]
    pcols = [_safe_ident(c) for c in _columns(item["to_columns"])]
    if len(ccols) != len(pcols) or not ccols:
        raise ValueError("unbalanced composite key")
    ctable = ".".join(f"`{p}`" for p in child)
    ptable = ".".join(f"`{p}`" for p in parent)
    key_select = ", ".join(f"c.`{c}` AS k{i}" for i, c in enumerate(ccols))
    null_filter = " AND ".join(f"c.`{c}` IS NOT NULL" for c in ccols)
    join_on = " AND ".join(f"p.`{p}` = c.k{i}" for i, p in enumerate(pcols))
    matched = " + ".join(f"CASE WHEN p.`{p}` IS NOT NULL THEN 1 ELSE 0 END" for p in pcols)
    return (
        f"WITH child_keys AS (SELECT DISTINCT {key_select} FROM {ctable} c WHERE {null_filter} LIMIT {MAX_KEYS}) "
        f"SELECT COUNT(*) AS sampled, COALESCE(SUM({matched}), 0) AS matched "
        f"FROM child_keys c LEFT JOIN {ptable} p ON {join_on}"
    )


def run_items(batch: Sequence[Mapping[str, Any]], configs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    engines: dict[str, Any] = {}
    for item in batch:
        system = str(item.get("system_code") or "")
        config = configs.get(system)
        if config is None:
            skipped.append({**_meta(item), "status": "VALIDATION_SKIPPED_RISK", "reason": "no_config"})
            continue
        engine = config.get("db_type") or config.get("source", {}).get("db_type")
        try:
            if engine == "mysql":
                sql = build_mysql_query(item)
            else:
                sql = build_sqlserver_query(item)
        except ValueError as exc:
            skipped.append({**_meta(item), "status": "VALIDATION_SKIPPED_RISK", "reason": str(exc)[:200]})
            continue
        entry = {
            **_meta(item),
            "status": "pending",
            "query_shape": "distinct_top_left_join_aggregate",
            "max_keys": MAX_KEYS,
            "sql_fingerprint": _fingerprint(sql),
        }
        try:
            if system not in engines:
                engines[system] = _connect(config, engine)
            conn = engines[system]
            cursor = conn.cursor()
            try:
                if engine == "sqlserver":
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
                    cursor.execute("SET LOCK_TIMEOUT 15000")
                    cursor.execute("SET DEADLOCK_PRIORITY LOW")
                else:
                    cursor.execute("SET SESSION TRANSACTION READ ONLY")
                cursor.execute(sql)
                row = cursor.fetchone()
                if not isinstance(row, Mapping):
                    names = [d[0].lower() for d in cursor.description]
                    row = dict(zip(names, row))
                sampled = int(row.get("sampled") or 0)
                matched = int(row.get("matched") or 0)
                entry.update({
                    "status": "validated",
                    "sampled": sampled,
                    "matched": matched,
                    "match_rate": round(matched / sampled, 6) if sampled else None,
                })
            finally:
                cursor.close()
                conn.rollback()
        except Exception as exc:
            text = sqlserver_harvest.sanitize_text(exc) if engine != "mysql" else mysql_harvest.sanitize_text(exc)
            status = "VALIDATION_TIMEOUT" if "timeout" in str(exc).lower() else "VALIDATION_SKIPPED_RISK"
            entry.update({"status": status, "reason": text[:300]})
            engines.pop(system, None)
        results.append(entry)
    for conn in engines.values():
        try:
            conn.close()
        except Exception:
            pass
    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "max_keys": MAX_KEYS,
            "aggregates_only": True,
            "patient_values_returned": False,
            "read_only_session": True,
        },
        "items": results,
        "skipped": skipped,
        "source_writes": 0,
    }


def _connect(config: Mapping[str, Any], engine: str) -> Any:
    if engine == "mysql":
        credentials = mysql_harvest._credential(config)
        return mysql_harvest._connect(config, credentials)
    credentials = sqlserver_harvest.load_credentials(config)
    tds, _attempts = sqlserver_harvest.resolve_tds_version(config, credentials)
    return sqlserver_harvest._connect(config, credentials, None, tds_version=tds)


def _meta(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "system_code": item.get("system_code"),
        "source_code": item.get("source_code"),
        "view_name": item.get("view_name"),
        # Batch rows may carry only fully-qualified ``_from``/``_to`` names;
        # fall back to them so evidence records stay self-describing.
        "from_table": item.get("from_table") or item.get("_from"),
        "from_columns": item.get("from_columns"),
        "to_table": item.get("to_table") or item.get("_to"),
        "to_columns": item.get("to_columns"),
        "intake_status": item.get("intake_status"),
        "source_sql_sha256": item.get("source_sql_sha256"),
    }


def _fingerprint(sql: str) -> str:
    import hashlib

    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


def _flatten_config(data: Mapping[str, Any]) -> dict[str, Any]:
    """Mirror the harvesters' ``load_config`` source flattening for in-memory dicts."""
    source = data.get("source", data)
    if "source" not in data and isinstance(data.get("endpoint"), dict):
        source = {**{k: v for k, v in data.items() if k != "endpoint"}, **data["endpoint"]}
    if not isinstance(source, dict):
        raise ValueError("config.source must be an object")
    if "source" in data:
        source = {**{k: v for k, v in data.items() if k != "source"}, **source}
    return dict(source)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--config", action="append", required=True,
                        help="SYSTEM_CODE=path/to/harvest/config.json (repeatable)")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    configs: dict[str, Mapping[str, Any]] = {}
    for pair in args.config:
        system, _, path = pair.partition("=")
        configs[system] = _flatten_config(json.loads(Path(path).read_text(encoding="utf-8")))
    result = run_items(batch, configs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    validated = sum(1 for i in result["items"] if i["status"] == "validated")
    print(json.dumps({"validated": validated, "items": len(result["items"]),
                      "skipped": len(result["skipped"]), "source_writes": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
