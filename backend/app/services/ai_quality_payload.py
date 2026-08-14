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
    "business_domain", "problem", "rule_description", "table_name_cn", "related_table", "related_field",
    "target_display", "system_name_cn",
    "column_count", "missing_comment_count", "missing_comment_columns", "example_named_columns",
    "related_relations", "column_name_cn", "validation_status", "validation_metrics",
    "from_table", "to_table", "from_columns", "to_columns",
    "severity", "status", "metric_value", "total_cnt", "error_cnt", "error_rate", "pass_rate",
    "total_rules", "total_findings", "total_records", "error_records", "metadata", "data_type",
    "severity_counts", "status_counts", "top_tables", "count",
    "nullable", "is_primary_key", "relationships", "history_count", "check_scope", "safe_sql_hash",
    "rel_id", "relation_scene", "relation_scene_label", "already_split_to", "handling_hint",
}
# Keys that must never leave the platform. Identifier names such as PATIENT_ID
# and table names such as INP_BILL_DETAIL are allowed values.
FORBIDDEN_KEYS = {
    "sample_data", "sample", "token", "cookie", "api_key", "api-key",
    "password", "credential", "connection", "detail", "stack", "free_text",
    "patient_name", "person_name",
}
CONCRETE_PII = re.compile(
    r"("
    r"password\s*[:=]\s*\S+|"
    r"api[_-]?key\s*[:=]\s*\S+|"
    r"\b\d{17}[\dXx]\b|"
    r"(?<!\d)1[3-9]\d{9}(?!\d)|"
    r"(身份证号?|手机号)\s*[:：=]\s*\S+"
    r")",
    re.I,
)


def _is_forbidden_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in FORBIDDEN_KEYS or "api_key" in lowered or "password" in lowered


def _is_forbidden_value(value: str) -> bool:
    return bool(CONCRETE_PII.search(value or ""))


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
            if key_s not in ALLOWED_KEYS or _is_forbidden_key(key_s):
                dropped.append(path + key_s)
                continue
            out[key_s] = _clean(item, dropped, path + key_s + ".")
        return out
    if isinstance(value, list):
        return [_clean(item, dropped, path) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and _is_forbidden_value(value):
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
