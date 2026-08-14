"""Parse stored relation validation_metrics into hit / orphan rates."""
from __future__ import annotations

import json
import re
from typing import Any

SCENE_BY_REL_ID: dict[int, str] = {
    14: "exam_mixed",
    16: "lab_mixed",
    553: "exam_inpatient",
    554: "exam_outpatient",
    555: "lab_inpatient",
    556: "lab_outpatient",
}

SCENE_LABELS: dict[str, str] = {
    "exam_inpatient": "检查·住院",
    "exam_outpatient": "检查·门诊",
    "exam_mixed": "检查·未拆分",
    "exam": "检查",
    "lab_inpatient": "检验·住院",
    "lab_outpatient": "检验·门诊",
    "lab_mixed": "检验·未拆分",
    "lab": "检验",
}

# Mixed exam/lab relations already have formal inpatient/outpatient splits.
MIXED_RELATION_HINTS: dict[int, dict[str, str]] = {
    14: {
        "relation_scene": "exam_mixed",
        "relation_scene_label": "检查·未拆分",
        "already_split_to": "553 住院检查、554 门诊检查",
        "handling_hint": "混合检查关系已拆成正式关系 553（住院 VISIT_ID<>0）和 554（门诊）。本条孤儿率偏高，多半是门诊检查被算成住院孤儿，不必再按混合关系改业务数据。",
    },
    16: {
        "relation_scene": "lab_mixed",
        "relation_scene_label": "检验·未拆分",
        "already_split_to": "555 住院检验、556 门诊检验",
        "handling_hint": "混合检验关系已拆成正式关系 555（住院）和 556（门诊 VISIT_ID=0/空）。本条更像口径噪音，应看拆后正式关系，不要按混合关系改业务数据。",
    },
}


def mixed_relation_hint(rel_id: int | None) -> dict[str, str] | None:
    if rel_id is None:
        return None
    hint = MIXED_RELATION_HINTS.get(int(rel_id))
    return dict(hint) if hint else None

_KV_RE = re.compile(
    r"(?i)\b(n|sample|sample_size|ods_sample|his_source_sample|sampled|total|miss|missed|orphan|"
    r"orphan_n|orphan_count|hit|hit_rate|match_rate|map_rate|coverage_rate|"
    r"orphan_rate|matched|matched_rows|result_n|result_rows|detail_rows)\s*[=:]\s*([0-9.]+%?)"
)
_RATIO_RE = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def _as_rate(value: Any, *, raw_text: str | None = None) -> float | None:
    """Normalize percent or ratio into 0-1."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    number = _to_float(value)
    if number is None:
        return None
    if text.endswith("%") or (raw_text or "").endswith("%"):
        return max(0.0, min(number / 100.0, 1.0))
    if number > 1.0:
        return max(0.0, min(number / 100.0, 1.0))
    return max(0.0, min(number, 1.0))


def _first_number(data: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        if key in data:
            number = _to_float(data[key])
            if number is not None:
                return number
    return None


def _first_rate(data: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        if key in data:
            raw = data[key]
            rate = _as_rate(raw, raw_text=str(raw) if not isinstance(raw, (int, float)) else None)
            if rate is not None:
                return rate
    return None


def parse_relation_metrics(raw: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "sample_size": None,
        "matched": None,
        "missed": None,
        "hit_rate": None,
        "orphan_rate": None,
        "orphan_count": None,
        "raw": raw or "",
    }
    text = (raw or "").strip()
    if not text:
        return result

    data: dict[str, Any] = {}
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            data = {str(k).strip().lower(): v for k, v in parsed.items()}

    if not data:
        for part in re.split(r"[;；]", text):
            item = part.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            data[key.strip().lower()] = value.strip()

    for match in _KV_RE.finditer(text):
        data.setdefault(match.group(1).lower(), match.group(2))

    ratio = _RATIO_RE.search(text)
    ratio_num = _to_float(ratio.group(1)) if ratio else None
    ratio_den = _to_float(ratio.group(2)) if ratio else None

    sampled = _first_number(
        data,
        ["sampled", "sample_size", "sample", "ods_sample", "his_source_sample", "n", "total", "result_n", "result_rows", "detail_rows"],
    )
    matched = _first_number(data, ["matched", "matched_rows"])
    missed = _first_number(data, ["miss", "missed", "orphan", "orphan_n", "orphan_count"])
    hit_rate = _first_rate(data, ["hit_rate", "match_rate", "hit", "map_rate", "coverage_rate"])
    orphan_rate = _first_rate(data, ["orphan_rate"])

    if ratio_den is not None:
        # "matched_visit_keys=1996/2000" 之类比值：分母才是样本数，
        # 优先于 detail_rows/result_rows 等明细行数（明细行可远大于抽样对数）。
        sampled = ratio_den
    if matched is None:
        matched = ratio_num

    if hit_rate is None and sampled and missed is not None and sampled > 0:
        hit_rate = max(0.0, min(1.0 - missed / sampled, 1.0))
    if hit_rate is None and sampled and matched is not None and sampled > 0:
        hit_rate = max(0.0, min(matched / sampled, 1.0))
    if orphan_rate is None and hit_rate is not None:
        orphan_rate = max(0.0, min(1.0 - hit_rate, 1.0))
    if hit_rate is None and orphan_rate is not None:
        hit_rate = max(0.0, min(1.0 - orphan_rate, 1.0))
    if missed is None and sampled and hit_rate is not None:
        missed = round(sampled * (1.0 - hit_rate))
    if matched is None and sampled and hit_rate is not None:
        matched = round(sampled * hit_rate)

    result["sample_size"] = int(sampled) if sampled is not None else None
    result["matched"] = int(matched) if matched is not None else None
    result["missed"] = int(missed) if missed is not None else None
    result["hit_rate"] = round(hit_rate, 6) if hit_rate is not None else None
    result["orphan_rate"] = round(orphan_rate, 6) if orphan_rate is not None else None
    result["orphan_count"] = int(missed) if missed is not None else None
    return result


def classify_relation_scene(
    *,
    rel_id: int | None = None,
    from_table: str | None = None,
    to_table: str | None = None,
    from_columns: str | None = None,
    to_columns: str | None = None,
    join_condition: str | None = None,
    note: str | None = None,
    validation_note: str | None = None,
    domain: str | None = None,
) -> str | None:
    if rel_id in SCENE_BY_REL_ID:
        return SCENE_BY_REL_ID[rel_id]
    blob = " ".join(
        [
            from_table or "",
            to_table or "",
            from_columns or "",
            to_columns or "",
            join_condition or "",
            note or "",
            validation_note or "",
            domain or "",
        ]
    )
    upper = blob.upper()
    compact = upper.replace(" ", "")
    is_exam = "EXAM_MASTER" in upper
    is_lab = "LAB_TEST_MASTER" in upper
    is_outpatient = (
        "门诊" in blob
        or "OUTP" in upper
        or "RCPT_NO" in upper and ("VISIT_ID=0" in compact or "NVL(VISIT_ID,0)=0" in compact)
    )
    is_inpatient = (
        "住院" in blob
        or "VISIT_ID<>0" in compact
        or "VISIT_ID!=0" in compact
        or "VISIT_ID IS NOT NULL AND VISIT_ID <> 0" in upper
    )
    if is_exam and is_outpatient:
        return "exam_outpatient"
    if is_exam and is_inpatient:
        return "exam_inpatient"
    if is_lab and is_outpatient:
        return "lab_outpatient"
    if is_lab and is_inpatient:
        return "lab_inpatient"
    if is_exam:
        return "exam"
    if is_lab:
        return "lab"
    return None


def scene_label(scene: str | None) -> str | None:
    if not scene:
        return None
    return SCENE_LABELS.get(scene, scene)


def hit_rate_tone(hit_rate: float | None) -> str:
    if hit_rate is None:
        return "info"
    if hit_rate >= 0.99:
        return "success"
    if hit_rate >= 0.90:
        return "primary"
    if hit_rate >= 0.70:
        return "warning"
    return "danger"
