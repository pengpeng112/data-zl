"""Validated, configuration-only targets for the AI patrol demonstration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TARGETS_PATH = Path(__file__).with_name("ai_patrol_targets.json")
REQUIRED_TARGET = {"system_code", "source_code", "schema_name", "table_name", "name_cn", "issue_label", "finding_ids", "evidence"}
REQUIRED_EVIDENCE = {"rule_id", "finding_id", "metric_value", "captured_at", "data_as_of", "snapshot_version"}


def _non_empty(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def load_patrol_targets(path: Path = TARGETS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("patrol targets must contain a targets array")
    clean: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not REQUIRED_TARGET.issubset(row):
            raise ValueError(f"patrol target #{index + 1} is incomplete")
        if any(not _non_empty(row[key]) for key in REQUIRED_TARGET - {"finding_ids", "evidence"}):
            raise ValueError(f"patrol target #{index + 1} has blank identity fields")
        finding_ids = row.get("finding_ids")
        evidence = row.get("evidence")
        if not isinstance(finding_ids, list) or len(set(finding_ids)) < 2 or any(not isinstance(item, int) for item in finding_ids):
            raise ValueError(f"patrol target #{index + 1} requires at least two unique finding_ids")
        if not isinstance(evidence, dict) or not REQUIRED_EVIDENCE.issubset(evidence):
            raise ValueError(f"patrol target #{index + 1} evidence is incomplete")
        if any(not _non_empty(evidence[key]) for key in REQUIRED_EVIDENCE):
            raise ValueError(f"patrol target #{index + 1} evidence has blank values")
        if int(evidence["finding_id"]) not in finding_ids:
            raise ValueError(f"patrol target #{index + 1} evidence finding is outside finding_ids")
        clean.append({**row, "finding_ids": sorted(set(finding_ids))})
    return clean
