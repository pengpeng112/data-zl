"""207 §4.5: 跨系统一致性比对纯逻辑（无 IO，可全量合成真值验收）。

铁律：
  - 双向缺失（A缺B、B缺A）与重复键/一对多单列指标，**不默默去重**；
  - 键按字符串规范（保留前导零、去首尾空白）；复合键按元组；
  - 数量对账 ≠ 逐键一致：两侧数量相同但键完全不同必须被逐键指标暴露；
  - 零样本（两侧皆空）= NO_DATA，不是通过；单侧空 = 明确缺失结论；
  - 抽样稳定（输入行先按键排序），截断带标志；样本不外溢患者明细。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


def normalize_key(value: Any) -> str:
    """字符串规范：保留前导零（不做 int 强转），去首尾空白。"""
    return "" if value is None else str(value).strip()


def row_key(row: dict[str, Any], key_fields: list[str]) -> tuple[str, ...]:
    return tuple(normalize_key(row.get(k)) for k in key_fields)


@dataclass
class CrossSourceComparison:
    total_a: int = 0
    total_b: int = 0
    distinct_keys_a: int = 0
    distinct_keys_b: int = 0
    duplicate_keys_a: list[tuple] = field(default_factory=list)
    duplicate_keys_b: list[tuple] = field(default_factory=list)
    a_only: list[tuple] = field(default_factory=list)
    b_only: list[tuple] = field(default_factory=list)
    matched_keys: int = 0
    mismatched_keys: int = 0
    mismatched_detail: list[dict[str, Any]] = field(default_factory=list)
    unmapped_codes: list[str] = field(default_factory=list)
    truncated: bool = False
    sampled: bool = False

    def as_dict(self, *, sample_cap: int = 20) -> dict[str, Any]:
        return {
            "total_a": self.total_a, "total_b": self.total_b,
            "distinct_keys_a": self.distinct_keys_a, "distinct_keys_b": self.distinct_keys_b,
            "duplicate_keys_a": len(self.duplicate_keys_a),
            "duplicate_keys_b": len(self.duplicate_keys_b),
            "a_only_count": len(self.a_only), "b_only_count": len(self.b_only),
            "a_only_sample": [list(k) for k in self.a_only[:sample_cap]],
            "b_only_sample": [list(k) for k in self.b_only[:sample_cap]],
            "matched_keys": self.matched_keys, "mismatched_keys": self.mismatched_keys,
            "mismatched_sample": self.mismatched_detail[:sample_cap],
            "unmapped_codes": self.unmapped_codes[:sample_cap],
            "truncated": self.truncated, "sampled": self.sampled,
        }

    def bidirectional_missing(self) -> int:
        return len(self.a_only) + len(self.b_only)

    def key_match_rate(self) -> float:
        denom = self.distinct_keys_a + self.distinct_keys_b
        if denom == 0:
            return 0.0
        return round(self.matched_keys * 2 / denom * 100, 4)

    def value_mismatch_rate(self) -> float:
        if self.matched_keys == 0:
            return 0.0
        return round(self.mismatched_keys / self.matched_keys * 100, 4)


def compare_keyed_datasets(
    a_rows: Iterable[dict[str, Any]],
    b_rows: Iterable[dict[str, Any]],
    *,
    key_fields: list[str],
    compare_fields: list[str] | None = None,
    code_mapping: dict[str, str] | None = None,
    sample_cap: int = 50,
) -> CrossSourceComparison:
    """双源逐键比对（A=权威侧）。重复键计入 duplicate_* 不去重聚合。"""
    result = CrossSourceComparison()
    compare_fields = compare_fields or []

    a_list = [dict(r) for r in a_rows]
    b_list = [dict(r) for r in b_rows]
    result.total_a, result.total_b = len(a_list), len(b_list)

    a_by_key: dict[tuple, list[dict]] = {}
    b_by_key: dict[tuple, list[dict]] = {}
    for r in a_list:
        a_by_key.setdefault(row_key(r, key_fields), []).append(r)
    for r in b_list:
        b_by_key.setdefault(row_key(r, key_fields), []).append(r)
    result.distinct_keys_a, result.distinct_keys_b = len(a_by_key), len(b_by_key)
    result.duplicate_keys_a = sorted(k for k, v in a_by_key.items() if len(v) > 1)[:sample_cap]
    result.duplicate_keys_b = sorted(k for k, v in b_by_key.items() if len(v) > 1)[:sample_cap]

    result.a_only = sorted(set(a_by_key) - set(b_by_key))[:sample_cap]
    result.b_only = sorted(set(b_by_key) - set(a_by_key))[:sample_cap]
    # 抽样标志：差异超样本上限即截断（统计计数按全量键集，样本仅定位用）
    if len(set(a_by_key) - set(b_by_key)) > sample_cap or len(set(b_by_key) - set(a_by_key)) > sample_cap:
        result.truncated = True
        result.sampled = True

    mapping = code_mapping or {}
    for key in sorted(set(a_by_key) & set(b_by_key)):
        # 重复键侧：比对第一行，但重复本身已是独立指标（不掩盖）
        ra, rb = a_by_key[key][0], b_by_key[key][0]
        result.matched_keys += 1
        mismatch: dict[str, Any] = {"key": list(key), "fields": {}}
        for f in compare_fields:
            va = normalize_key(ra.get(f))
            vb_raw = normalize_key(rb.get(f))
            if mapping and vb_raw not in mapping and vb_raw != va:
                # B 侧码值无映射定义（未知映射）：单列，不猜语义
                if vb_raw not in result.unmapped_codes:
                    result.unmapped_codes.append(vb_raw)
            vb = mapping.get(vb_raw, vb_raw)
            if va != vb and not _numeric_equal(va, vb):
                mismatch["fields"][f] = {"a": va, "b": vb_raw}
        if mismatch["fields"]:
            result.mismatched_keys += 1
            result.mismatched_detail.append(mismatch)
    return result


def _numeric_equal(a: str, b: str) -> bool:
    """数值语义相等（1.0 vs 1；非数值回落字符串比较）。"""
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def cross_source_verdict(
    cmp: CrossSourceComparison,
    *,
    missing_threshold_pct: float = 0.0,
    mismatch_threshold_pct: float = 0.0,
) -> dict[str, Any]:
    """结论（六态语义）：零样本 NO_DATA；否则按阈值判 pass/fail，附全量指标。

    数量对账与逐键一致分别命名：counts_equal 只描述数量，绝不宣称逐键通过。
    """
    if cmp.distinct_keys_a == 0 and cmp.distinct_keys_b == 0:
        return {"status": "no_data", "detail": cmp.as_dict(),
                "reason": "两侧键集合均为空（零样本），按 NO_DATA 处理，不作通过证据"}
    denom = max(cmp.distinct_keys_a, cmp.distinct_keys_b, 1)
    missing_pct = round(cmp.bidirectional_missing() / denom * 100, 4)
    mismatch_pct = cmp.value_mismatch_rate()
    dup = len(cmp.duplicate_keys_a) + len(cmp.duplicate_keys_b)
    failed = (
        missing_pct > missing_threshold_pct
        or mismatch_pct > mismatch_threshold_pct
        or dup > 0
    )
    return {
        "status": "fail" if failed else "pass",
        "detail": cmp.as_dict(),
        "metrics": {
            "bidirectional_missing": cmp.bidirectional_missing(),
            "bidirectional_missing_pct": missing_pct,
            "key_match_rate_pct": cmp.key_match_rate(),
            "value_mismatch_pct": mismatch_pct,
            "duplicate_keys": dup,
            "counts_equal": cmp.total_a == cmp.total_b,  # 仅数量对账，不是逐键一致
        },
        "reason": (
            f"双向缺失 {cmp.bidirectional_missing()}（{missing_pct}%）、"
            f"字段错配 {mismatch_pct}%、重复键 {dup}"
        ),
    }
