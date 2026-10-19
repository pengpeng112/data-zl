"""对账层：受影响键核存在性与内容，条数相等不判完整。

对应计划 §6.3：
- 先核键集、再核内容；计数相等只是一项检查。
- 逐受影响键内容 diff 用回读类型契约（CLOB/Decimal/时间精度）。
- 目标多出的未解释键单列；源-ODS-目标三方延迟由调用方分别记录，本层不
  用两时点 count 差冒充漏数判定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from app.services.reporting_pipeline.readback_types import (
    ColumnMeta,
    content_fingerprint,
    row_diff,
)


@dataclass
class ReconcileResult:
    keys_missing_in_target: list[tuple] = field(default_factory=list)
    keys_extra_in_target: list[tuple] = field(default_factory=list)
    content_diffs: list[dict] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not (self.keys_missing_in_target or self.keys_extra_in_target
                    or self.content_diffs)

    def summary(self) -> dict:
        return {
            "missing_in_target": len(self.keys_missing_in_target),
            "extra_in_target": len(self.keys_extra_in_target),
            "content_diffs": len(self.content_diffs),
            "complete": self.complete,
            "note": "complete 仅指本取证范围键集+内容一致；不外推源→ODS 同步完整性",
        }


class ReconcileService:
    def __init__(self, stable_key_columns: Sequence[str], column_meta: Mapping[str, ColumnMeta]) -> None:
        self.stable_key_columns = tuple(stable_key_columns)
        self.column_meta = dict(column_meta)
        self.metas = sorted(self.column_meta.values(), key=lambda m: m.name)

    def compare(
        self,
        source_rows: Sequence[Mapping],
        target_rows: Mapping[tuple, Mapping],
    ) -> ReconcileResult:
        result = ReconcileResult()
        source_keys: set[tuple] = set()
        seen_fingerprints: dict[tuple, str] = {}
        for row in source_rows:
            key = tuple(row.get(c) for c in self.stable_key_columns)
            source_keys.add(key)
            target_row = target_rows.get(key)
            if target_row is None:
                result.keys_missing_in_target.append(key)
                continue
            diffs = row_diff(row, target_row, self.metas)
            if diffs:
                result.content_diffs.append({"key": key, "diffs": diffs})
            seen_fingerprints[key] = content_fingerprint(row, self.metas)
        for key in target_rows:
            if key not in source_keys:
                result.keys_extra_in_target.append(key)
        return result

    @staticmethod
    def counts_equal_is_not_completeness(
        source_keys: set[tuple],
        target_keys: set[tuple],
    ) -> dict:
        """口径提醒：条数相等但键集不同 → 不完整（不能只数数）。"""
        return {
            "source_count": len(source_keys),
            "target_count": len(target_keys),
            "counts_equal": len(source_keys) == len(target_keys),
            "key_sets_equal": source_keys == target_keys,
            "missing_in_target": sorted(source_keys - target_keys),
            "extra_in_target": sorted(target_keys - source_keys),
            "warning": "counts_equal 不构成完整性证据；必须比对键集与内容",
        }
