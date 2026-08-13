"""Strict, deterministic payload boundary for Dify quality analysis."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

ALLOWED_KEYS = {
    "findings",
    "id", "finding_id", "run_id", "rule_code", "rule_name", "rule_type", "rule_category",
    "system_code", "source_code", "namespace_name", "schema_name", "table_name", "column_name", "target_ref", "target_type",
    "business_domain",
    "severity", "status", "metric_value", "total_cnt", "error_cnt", "error_rate", "pass_rate",
    "total_rules", "total_findings", "total_records", "error_records", "metadata", "data_type",
    "severity_counts", "status_counts", "top_tables", "count",
    "nullable", "is_primary_key", "relationships", "history_count", "check_scope", "safe_sql_hash",
}
FORBIDDEN = re.compile(r"(sample_data|patient|person|姓名|身份证|电话|地址|住院号|门诊号|病历号|token|cookie|api[_-]?key|password|credential|connection|detail|stack)", re.I)


def _reject_long_lists(value: Any, limit: int) -> None:
    if isinstance(value, list):
        if len(value) > limit:
            raise ValueError("payload item count exceeds limit")
        for item in value:
            _reject_long_lists(item, limit)
    elif isinstance(value, dict):
        for item in value.values():
            _reject_long_lists(item, limit)


def _clean(value: Any, dropped: list[str], path: str = "") -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s not in ALLOWED_KEYS or FORBIDDEN.search(key_s):
                dropped.append(path + key_s)
                continue
            out[key_s] = _clean(item, dropped, path + key_s + ".")
        return out
    if isinstance(value, list):
        return [_clean(item, dropped, path) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and FORBIDDEN.search(value):
            dropped.append(path.rstrip("."))
            return "[REDACTED]"
        return value
    dropped.append(path.rstrip("."))
    return None


def build_payload(*, schema_version: str, request_id: str, task_type: str, prompt_version: str,
                  payload: dict[str, Any], max_bytes: int = 65536, max_items: int = 50) -> dict[str, Any]:
    _reject_long_lists(payload, max_items)
    dropped: list[str] = []
    clean = _clean(payload, dropped)
    if isinstance(clean, dict) and len(clean) > max_items:
        raise ValueError("payload item count exceeds limit")
    payload_json = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    result = {"schema_version": schema_version, "request_id": request_id, "task_type": task_type,
              "prompt_version": prompt_version, "payload_json": payload_json, "input_digest": digest,
              "dropped_fields": sorted(set(dropped)), "payload_bytes": len(payload_json.encode("utf-8"))}
    if result["payload_bytes"] > max_bytes:
        raise ValueError("payload exceeds byte limit")
    return result


def canonical_digest(value: dict[str, Any]) -> str:
    raw = value.get("payload_json", "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
