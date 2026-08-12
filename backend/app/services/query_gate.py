"""126 P1: automatic query gate — no admin click; pass → active, fail → blocked/candidate."""
from __future__ import annotations

import re
from typing import Any

from ..services.quality_rule_engine import validate_sql_safety

_TABLE_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w$#]*(?:\.[A-Za-z_][\w$#]*){0,2})",
    re.I,
)

# Hard denylist: unbounded scans forbidden without explicit bound markers
_HARD_BIG = {
    "LAB_RESULT": ("TEST_NO", "ROWNUM", "WHERE"),
    "INP_BILL_DETAIL": ("PATIENT_ID", "VISIT_ID", "ROWNUM", "WHERE"),
}


def extract_table_refs(sql: str) -> list[str]:
    found = []
    for m in _TABLE_RE.finditer(sql or ""):
        name = m.group(1).upper()
        if name not in found:
            found.append(name)
    return found


def evaluate_query_gate(
    sql: str,
    *,
    dialect: str = "oracle",
    system_code: str | None = None,
    source_code: str | None = None,
    require_source: bool = True,
) -> dict[str, Any]:
    """Return gate decision.

    status: validated | candidate | blocked
    auto_activate: bool
    """
    safety = validate_sql_safety(sql or "", db_type=(dialect or "oracle").lower())
    errors = list(safety.get("errors") or [])
    warnings = list(safety.get("warnings") or [])
    upper = (sql or "").upper()

    if require_source and not (source_code or "").strip():
        errors.append("缺少 source_code（登记的只读数据连接）")

    for table, markers in _HARD_BIG.items():
        if table in upper:
            if not any(m in upper for m in markers):
                errors.append(f"大表 {table} 缺少限定条件: 需要 {', '.join(markers)}")

    # Sensitive patterns in SQL comments already stripped by normalize; still scan raw
    sensitive_hits = []
    for pat, label in (
        (r"\b\d{17}[\dXx]\b", "疑似身份证"),
        (r"\b1[3-9]\d{9}\b", "疑似手机号"),
    ):
        if re.search(pat, sql or ""):
            sensitive_hits.append(label)
    if sensitive_hits:
        warnings.append("SQL 文本含敏感模式: " + ",".join(sensitive_hits))

    tables = extract_table_refs(sql)
    if not tables:
        warnings.append("未能解析 FROM/JOIN 表引用")

    if errors:
        return {
            "status": "blocked",
            "auto_activate": False,
            "errors": errors,
            "warnings": warnings,
            "tables": tables,
            "safety": safety,
        }

    # Soft warnings only → validated and auto active
    # If only table parse soft issues without hard errors, still activate
    status = "validated"
    return {
        "status": status,
        "auto_activate": True,
        "errors": [],
        "warnings": warnings,
        "tables": tables,
        "safety": safety,
    }
