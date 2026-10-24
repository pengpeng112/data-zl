"""质量层：行级/组级/批级规则、互斥分类、隔离继续。

对应计划 §6：
- 行级：必填、类型、值域、字节长度与精度。
- 组级：父子完整、同键冲突；父键缺失的子行进 BLOCKED_DEPENDENCY 待父，
  不与规则违规混同。
- 批级：分片完整（借 manifest）、分类守恒。
- 隔离继续：坏组 QUARANTINED 且生成工单引用；独立合法组继续 VALID；
  失败不是跳过，也不是全批失败。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from app.services.reporting_pipeline.contracts import BatchManifest
from app.services.reporting_pipeline.readback_types import (
    ColumnMeta,
    byte_length,
)

# 行互斥分类（与 manifest 分类对齐）
VALID = "VALID"
QUARANTINED = "QUARANTINED"
PENDING_PARENT = "PENDING_PARENT"
DUPLICATE_CONFLICT = "DUPLICATE_CONFLICT"


class QualityRuleViolation(ValueError):
    """规则定义本身非法。"""


@dataclass(frozen=True)
class RequiredRule:
    columns: tuple[str, ...]


@dataclass(frozen=True)
class ByteLengthRule:
    column: str
    max_bytes: int
    charset: str = "utf-8"  # 目标库字符集（Oracle VARCHAR2 BYTE 语义按库字符集计）


@dataclass(frozen=True)
class PrecisionRule:
    column: str
    precision: int
    scale: int


@dataclass(frozen=True)
class EnumRule:
    column: str
    allowed: tuple[str, ...]


@dataclass(frozen=True)
class TypeRule:
    column: str
    expected: str  # int/decimal/str/date/datetime


@dataclass
class RowIssue:
    row_index: int
    group_key: tuple
    column: str | None
    rule: str
    detail: str


@dataclass
class QualityOutcome:
    classifications: dict[int, str]  # row_index -> 互斥分类
    issues: list[RowIssue]
    valid_group_keys: set[tuple]
    quarantined_group_keys: set[tuple]
    ticket_hint: str | None = None

    def conservation_ok(self, staged_rows: int) -> bool:
        counts: dict[str, int] = {}
        for cls in self.classifications.values():
            counts[cls] = counts.get(cls, 0) + 1
        return sum(counts.values()) == staged_rows

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for cls in self.classifications.values():
            counts[cls] = counts.get(cls, 0) + 1
        return {
            "counts": counts,
            "valid_groups": len(self.valid_group_keys),
            "quarantined_groups": len(self.quarantined_group_keys),
            "ticket_hint": self.ticket_hint,
        }


class QualityService:
    """规则驱动校验：rows 为 dict 行；group_key_columns 定义记录组。"""

    def __init__(
        self,
        *,
        group_key_columns: Sequence[str],
        parent_key_columns: Sequence[str] | None = None,
        column_meta: Mapping[str, ColumnMeta] | None = None,
    ) -> None:
        self.group_key_columns = tuple(group_key_columns)
        self.parent_key_columns = tuple(parent_key_columns or ())
        self.column_meta = dict(column_meta or {})

    def verify(
        self,
        rows: Sequence[Mapping],
        *,
        rules: Sequence[object],
        known_parent_keys: set[tuple] | None = None,
    ) -> QualityOutcome:
        known_parent_keys = known_parent_keys if known_parent_keys is not None else None
        issues: list[RowIssue] = []
        classifications: dict[int, str] = {}
        row_group_keys: dict[int, tuple] = {}

        for idx, row in enumerate(rows):
            gk = tuple(row.get(c) for c in self.group_key_columns)
            row_group_keys[idx] = gk
            row_issues = self._check_row(idx, gk, row, rules)
            issues.extend(row_issues)

        # 同组同稳定键冲突检测：组内同键多行且内容不同 → 冲突
        conflicts = self._detect_key_conflicts(rows, row_group_keys)
        issues.extend(conflicts)

        quarantined_groups: set[tuple] = set()
        for issue in issues:
            if issue.rule in ("REQUIRED", "TYPE", "BYTE_LENGTH", "PRECISION",
                              "ENUM", "DUPLICATE_CONFLICT"):
                quarantined_groups.add(issue.group_key)

        pending_parent_groups: set[tuple] = set()
        if self.parent_key_columns:
            for idx, row in enumerate(rows):
                pk = tuple(row.get(c) for c in self.parent_key_columns)
                if known_parent_keys is not None and pk not in known_parent_keys:
                    pending_parent_groups.add(row_group_keys[idx])
                    issues.append(
                        RowIssue(
                            row_index=idx, group_key=row_group_keys[idx],
                            column=".".join(self.parent_key_columns),
                            rule="PARENT_MISSING",
                            detail="父键不在已证父集合，子组待父",
                        )
                    )

        for idx in range(len(rows)):
            gk = row_group_keys[idx]
            if gk in quarantined_groups:
                classifications[idx] = QUARANTINED
            elif gk in pending_parent_groups:
                classifications[idx] = PENDING_PARENT
            else:
                classifications[idx] = VALID

        valid_groups = {
            gk for gk in set(row_group_keys.values())
            if gk not in quarantined_groups and gk not in pending_parent_groups
        }
        return QualityOutcome(
            classifications=classifications,
            issues=issues,
            valid_group_keys=valid_groups,
            quarantined_group_keys=quarantined_groups,
            ticket_hint=(
                f"人工工单候选：{len(quarantined_groups)} 组隔离，规则见 issues"
                if quarantined_groups else None
            ),
        )

    # -- 行级规则 -----------------------------------------------------------

    def _check_row(
        self,
        idx: int,
        group_key: tuple,
        row: Mapping,
        rules: Sequence[object],
    ) -> list[RowIssue]:
        out: list[RowIssue] = []
        for rule in rules:
            if isinstance(rule, RequiredRule):
                for col in rule.columns:
                    value = row.get(col)
                    if value is None or (isinstance(value, str) and value == ""):
                        out.append(RowIssue(idx, group_key, col, "REQUIRED",
                                            "必填缺失/空串"))
            elif isinstance(rule, ByteLengthRule):
                value = row.get(rule.column)
                actual = byte_length(value, rule.charset)
                if value is not None and actual > rule.max_bytes:
                    out.append(RowIssue(
                        idx, group_key, rule.column, "BYTE_LENGTH",
                        f"{rule.charset} 字节长 {actual} > {rule.max_bytes}",
                    ))
            elif isinstance(rule, PrecisionRule):
                value = row.get(rule.column)
                if value is not None:
                    try:
                        dec = value if isinstance(value, Decimal) else Decimal(str(value))
                    except InvalidOperation:
                        out.append(RowIssue(idx, group_key, rule.column, "PRECISION",
                                            f"非数值 {value!r}"))
                        continue
                    digits, exponent = dec.as_tuple()[1:]
                    significant = len([d for d in digits if d != 0]) or 1
                    scale = max(-exponent, 0)
                    if significant > rule.precision or scale > rule.scale:
                        out.append(RowIssue(
                            idx, group_key, rule.column, "PRECISION",
                            f"精度超限 significant={significant}>{rule.precision}"
                            f" 或 scale={scale}>{rule.scale}",
                        ))
            elif isinstance(rule, EnumRule):
                value = row.get(rule.column)
                if value is not None and str(value) not in rule.allowed:
                    out.append(RowIssue(idx, group_key, rule.column, "ENUM",
                                        f"值 {value!r} 不在值域"))
            elif isinstance(rule, TypeRule):
                value = row.get(rule.column)
                if value is None:
                    continue
                ok = self._type_matches(value, rule.expected)
                if not ok:
                    out.append(RowIssue(idx, group_key, rule.column, "TYPE",
                                        f"类型 {type(value).__name__} != {rule.expected}"))
        return out

    @staticmethod
    def _type_matches(value, expected: str) -> bool:
        import datetime as _dt

        if expected == "int":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "decimal":
            return isinstance(value, (int, Decimal)) and not isinstance(value, bool)
        if expected == "str":
            return isinstance(value, str)
        if expected == "date":
            return isinstance(value, _dt.date) and not isinstance(value, _dt.datetime)
        if expected == "datetime":
            return isinstance(value, _dt.datetime)
        return True

    def _detect_key_conflicts(
        self,
        rows: Sequence[Mapping],
        row_group_keys: Mapping[int, tuple],
    ) -> list[RowIssue]:
        """同组同稳定键不同内容 → DUPLICATE_CONFLICT（隔离，不"最后一条胜出"）。"""
        from app.services.reporting_pipeline.readback_types import content_fingerprint

        if not self.column_meta:
            return []
        metas = sorted(self.column_meta.values(), key=lambda m: m.name)
        by_key: dict[tuple, dict[str, int]] = {}
        conflicts: list[RowIssue] = []
        stable_cols = tuple(m.name for m in metas if m.name in self._stable_columns)
        if not stable_cols:
            return []
        for idx, row in enumerate(rows):
            key = tuple(row.get(c) for c in stable_cols)
            fp = content_fingerprint(row, metas)
            seen = by_key.setdefault(key, {})
            if fp in seen:
                continue  # 完全相同内容：重复行另行计数，不算内容冲突
            if seen:
                first_idx = next(iter(seen.values()))
                conflicts.append(
                    RowIssue(
                        row_index=idx, group_key=row_group_keys[idx],
                        column=",".join(stable_cols), rule="DUPLICATE_CONFLICT",
                        detail=f"同键不同内容（行 {first_idx} vs {idx}）",
                    )
                )
            seen[fp] = idx
        return conflicts

    @property
    def _stable_columns(self) -> set[str]:
        # 稳定键列约定为组键列或显式 parent 键；简化为组键
        return set(self.group_key_columns)


def verify_batch_conservation(
    manifest: BatchManifest, outcome: QualityOutcome, staged_rows: int
) -> dict:
    """批级守恒：manifest 分类、质量分类、暂存行数三方对账。"""
    problems: list[str] = []
    if staged_rows != manifest.rows.source_read_rows:
        problems.append(
            f"暂存行数 {staged_rows} != manifest 读取 {manifest.rows.source_read_rows}"
        )
    quality_valid = sum(
        1 for c in outcome.classifications.values() if c == VALID
    )
    quality_quarantined = sum(
        1 for c in outcome.classifications.values() if c == QUARANTINED
    )
    quality_pending = sum(
        1 for c in outcome.classifications.values() if c == PENDING_PARENT
    )
    if quality_valid + quality_quarantined + quality_pending != staged_rows:
        problems.append("质量互斥分类与暂存行数不守恒")
    if quality_valid != manifest.rows.valid:
        problems.append(
            f"有效行 {quality_valid} != manifest.valid {manifest.rows.valid}"
        )
    if quality_quarantined != manifest.rows.quarantined:
        problems.append(
            f"隔离行 {quality_quarantined} != manifest.quarantined "
            f"{manifest.rows.quarantined}"
        )
    return {
        "ok": not problems,
        "problems": problems,
        "counts": {
            "valid": quality_valid,
            "quarantined": quality_quarantined,
            "pending_parent": quality_pending,
        },
    }
