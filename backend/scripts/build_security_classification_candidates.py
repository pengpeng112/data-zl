"""210 S6: offline security classification candidate builder (no DB, no network).

Reads the offline asset pack CSVs (tables/columns) and produces *candidate*
classification proposals for every table/column -- a candidate is a rule hit,
never a confirmed label. Labels produced here MUST satisfy the strict enum
contract implemented in backend/app/services/dataset_security.py (B02 v1).

Outputs (written to --out-dir):
  candidates.csv   one row per table/column object
  proposals.json   payload for POST /api/v1/datasets/classifications:import
  summary.json     denominators by level / personal_info / parse errors
  SHA256SUMS.txt   digests of the three files above (deterministic re-runs
                   produce byte-identical outputs; timestamps are derived
                   from input file mtimes, never from wall clock)

Usage (repo root):
  backend/.venv/Scripts/python.exe backend/scripts/build_security_classification_candidates.py
  ... --limit 200          # quick validation subset
  ... --self-check         # re-read candidates.csv and re-validate invariants
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLES = REPO_ROOT / "开发起步包" / "数据资产_资产包" / "tables.csv"
DEFAULT_COLUMNS = REPO_ROOT / "开发起步包" / "数据资产_资产包" / "columns.csv"
DEFAULT_OUT = (REPO_ROOT / "开发起步包" / "output_r210" / "r210-20261001-2153"
               / "candidates")

RULE_VERSION = "cand_r1"

VALID_LEVELS = ("P1", "P2", "P3", "P4")
VALID_PERSONAL = ("none", "personal", "sensitive_personal", "pending")
VALID_DATA_FORMS = ("structured", "free_text", "image", "audio_video",
                    "time_series", "derived", "vector", "model_artifact")
VALID_PROCESSING = ("raw", "de_identified", "masked_display",
                    "anonymization_pending", "anonymization_assessed")

# 候选一律不放开用途/导出/训练（确认定级属人工治理终态，S10 另批）
CLOSED_USAGE = {"purposes": [], "export_allowed": False, "training_allowed": False}

# 名称/注释线索（候选，有误报漏报；不是确认敏感数量）
NAME_SIGNALS = [
    ("patient_name", ("PATIENT_NAME", "病人名", "患者姓名", "姓名")),
    ("id_card", ("ID_NO", "ID_CARD", "IDENTITY_NO", "身份证", "证件")),
    ("phone", ("PHONE", "MOBILE", "TEL_NO", "电话", "手机")),
    ("address", ("ADDRESS", "住址", "地址", "家庭住址")),
]
LEVEL_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


def canonical_object_ref(object_type: str, physical_key: dict) -> str:
    return json.dumps({"t": object_type, "k": physical_key},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def split_schema(raw: str) -> tuple[str, str]:
    """`AnyImage.db_datareader` -> ("AnyImage", "db_datareader")；无点则 namespace 空。"""
    raw = (raw or "").strip()
    if "." in raw:
        head, _, tail = raw.rpartition(".")
        return head, tail
    return "", raw


def _namespace_schema(row: dict) -> tuple[str, str]:
    """S10：导出 CSV 可带显式 `namespace` 列（平台 namespace_name 原值，可含点号，
    如 namespace=schema="EIS.DBO" 的采集形态，rpartition 组合串无法还原）；
    列缺失或为空时回落历史 split_schema 组合串解析，与 S6 离线包行为一致。"""
    ns = (row.get("namespace") or "").strip()
    if ns:
        return ns, (row.get("schema") or "").strip()
    return split_schema(row.get("schema", ""))


def _hit(text: str, keywords: tuple[str, ...]) -> bool:
    t = text.upper()
    return any(k.upper() in t for k in keywords)


def classify_table(table_name: str, comment: str, domain: str) -> tuple[dict, list[str], bool]:
    """表级候选：返回 (labels, reasons, name_signal)。"""
    labels: dict = {}
    reasons: list[str] = []
    text = f"{table_name} {comment or ''}"
    level = "P4"
    personal = "pending"
    markers: list[str] = []
    categories: list[str] = []
    data_form = "structured"
    if _hit(table_name, ("DICT", "字典")) or "字典" in (domain or ""):
        level = "P2"
        personal = "none"
        reasons.append("dict_like_table")
    if _hit(text, ("VISIT", "INP_", "住院", "挂号", "就诊")) and level != "P2":
        level = "P3"
        personal = "personal"
        categories.append("visit")
        reasons.append("visit_like_table")
    for signal, keywords in NAME_SIGNALS:
        if _hit(text, keywords):
            level = "P4"
            markers.append("identity_marker")
            if signal in ("id_card",):
                personal = "sensitive_personal"
            elif personal != "sensitive_personal":
                personal = "personal"
            reasons.append(f"name_signal:{signal}")
    if not reasons:
        reasons.append("no_rule_hit")
        labels = {"protection_level": "P4", "personal_info": "pending",
                  "data_form": "structured", "processing_state": "raw",
                  "usage_constraints": dict(CLOSED_USAGE)}
        if categories:
            labels["business_categories"] = sorted(set(categories))
        return labels, reasons, any("name_signal" in r for r in reasons)
    labels = {"protection_level": level, "personal_info": personal,
              "data_form": data_form, "processing_state": "raw",
              "usage_constraints": dict(CLOSED_USAGE)}
    if categories:
        labels["business_categories"] = sorted(set(categories))
    if markers:
        labels["pi_markers"] = sorted(set(markers))
    return labels, reasons, any("name_signal" in r for r in reasons)


def classify_column(column_name: str, comment: str) -> tuple[dict, list[str], bool]:
    text = f"{column_name} {comment or ''}"
    reasons: list[str] = []
    level = "P4"
    personal = "pending"
    markers: list[str] = []
    data_form = "structured"
    for signal, keywords in NAME_SIGNALS:
        if _hit(text, keywords):
            level = "P4"
            markers.append("identity_marker")
            if signal == "id_card":
                personal = "sensitive_personal"
            elif personal != "sensitive_personal":
                personal = "personal"
            reasons.append(f"name_signal:{signal}")
    if _hit(text, ("备注", "描述", "内容", "SUMMARY", "NOTE", "DESC")):
        data_form = "free_text"
        reasons.append("free_text_hint")
    if not reasons:
        reasons.append("no_rule_hit")
        return ({"protection_level": "P4", "personal_info": "pending",
                 "data_form": "structured", "processing_state": "raw",
                 "usage_constraints": dict(CLOSED_USAGE)}, reasons, False)
    labels = {"protection_level": level, "personal_info": personal,
              "data_form": data_form, "processing_state": "raw",
              "usage_constraints": dict(CLOSED_USAGE)}
    if markers:
        labels["pi_markers"] = sorted(set(markers))
    return labels, reasons, any("name_signal" in r for r in reasons)


def _deterministic_timestamp(paths: list[Path]) -> str:
    latest = max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)
    from datetime import datetime, timezone
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()


def iter_csv(path: Path, limit: int):
    """流式读取（BOM 容错）；yield dict；limit>0 时截断。"""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                return
            yield row


def build(tables_csv: Path, columns_csv: Path, out_dir: Path,
          limit: int = 0, source_filter: str = "",
          cancel_after: int = 0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "rule_version": RULE_VERSION,
        "tables_total": 0, "columns_total": 0,
        "by_level": {}, "by_personal_info": {},
        "name_signal_columns": 0, "parse_errors": 0,
        "limit_used": limit, "source_filter": source_filter,
        "cancelled": False,
        "generated_at": _deterministic_timestamp([tables_csv, columns_csv]),
    }
    levels: dict[str, int] = {}
    personals: dict[str, int] = {}
    rows: list[dict] = []
    proposals: list[dict] = []
    processed = 0

    def emit(object_type: str, physical_key: dict, labels: dict,
             reasons: list[str], evidence: dict, suggestion_level: str):
        nonlocal processed
        processed += 1
        row = {
            "object_type": object_type,
            "physical_key": json.dumps(physical_key, sort_keys=True,
                                       ensure_ascii=False, separators=(",", ":")),
            "object_ref": canonical_object_ref(object_type, physical_key),
            "suggested_labels": json.dumps(labels, sort_keys=True,
                                           ensure_ascii=False,
                                           separators=(",", ":")),
            "suggestion_level": suggestion_level,
            "reasons": json.dumps(reasons, ensure_ascii=False),
            "rule_version": RULE_VERSION,
            "evidence": json.dumps(evidence, ensure_ascii=False),
            "existing_formal_label": "unknown_offline",
        }
        rows.append(row)
        proposals.append({"object_type": object_type, "physical_key": physical_key,
                          "labels": labels, "evidence": evidence})
        key = labels.get("protection_level", "undecided")
        lvl = suggestion_level if suggestion_level == "undecided" else key
        levels[lvl] = levels.get(lvl, 0) + 1
        pi = labels.get("personal_info", "pending")
        personals[pi] = personals.get(pi, 0) + 1

    for row in iter_csv(tables_csv, limit):
        try:
            src = (row.get("source") or "platform").strip() or "platform"
            if source_filter and src != source_filter:
                continue
            namespace, schema = _namespace_schema(row)
            table = (row.get("table") or "").strip()
            if not table:
                summary["parse_errors"] += 1
                continue
            key = {"source_code": src, "namespace_name": namespace,
                   "schema_name": schema, "table_name": table}
            comment = (row.get("comment") or "")[:100]
            labels, reasons, _sig = classify_table(
                table, comment, row.get("domain") or "")
            evidence = {"domain": row.get("domain") or "",
                        "comment": comment, "name_signal": _sig}
            suggestion = "undecided" if reasons == ["no_rule_hit"] else \
                labels["protection_level"]
            emit("table", key, labels, reasons, evidence, suggestion)
            summary["tables_total"] += 1
            if cancel_after and processed >= cancel_after:
                summary["cancelled"] = True
                break
        except Exception:
            summary["parse_errors"] += 1

    if not summary["cancelled"]:
        for row in iter_csv(columns_csv, limit):
            try:
                # S10：生产导出带真实 source_code 列；离线包无该列时回落 "platform"
                src = (row.get("source") or "platform").strip() or "platform"
                if source_filter and src != source_filter:
                    continue
                namespace, schema = _namespace_schema(row)
                table = (row.get("table") or "").strip()
                column = (row.get("column") or "").strip()
                if not table or not column:
                    summary["parse_errors"] += 1
                    continue
                key = {"source_code": src, "namespace_name": namespace,
                       "schema_name": schema, "table_name": table,
                       "column_name": column}
                comment = (row.get("comment") or "")[:100]
                labels, reasons, sig = classify_column(column, comment)
                if sig:
                    summary["name_signal_columns"] += 1
                evidence = {"comment": comment, "name_signal": sig}
                suggestion = "undecided" if reasons == ["no_rule_hit"] else \
                    labels["protection_level"]
                emit("column", key, labels, reasons, evidence, suggestion)
                summary["columns_total"] += 1
                if cancel_after and processed >= cancel_after:
                    summary["cancelled"] = True
                    break
            except Exception:
                summary["parse_errors"] += 1

    summary["by_level"] = dict(sorted(levels.items()))
    summary["by_personal_info"] = dict(sorted(personals.items()))

    cand_path = out_dir / "candidates.csv"
    with cand_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [
            "object_type", "physical_key", "object_ref", "suggested_labels",
            "suggestion_level", "reasons", "rule_version", "evidence",
            "existing_formal_label"])
        writer.writeheader()
        writer.writerows(rows)

    (out_dir / "proposals.json").write_text(
        json.dumps({"rule_version": RULE_VERSION,
                    "generated_at": summary["generated_at"],
                    "proposals": proposals},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    digests = []
    for name in ("candidates.csv", "proposals.json", "summary.json"):
        digests.append(f"{hashlib.sha256((out_dir / name).read_bytes()).hexdigest()}  {name}")
    (out_dir / "SHA256SUMS.txt").write_text("\n".join(digests) + "\n", encoding="utf-8")
    return summary


def self_check(out_dir: Path) -> int:
    """Re-read candidates.csv and re-validate invariants (no DB)."""
    path = out_dir / "candidates.csv"
    seen: set[tuple] = set()
    n = bad_ref = bad_enum = dup = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            n += 1
            key = json.loads(row["physical_key"])
            if row["object_ref"] != canonical_object_ref(row["object_type"], key):
                bad_ref += 1
            labels = json.loads(row["suggested_labels"])
            if (labels.get("protection_level") not in VALID_LEVELS
                    or labels.get("personal_info") not in VALID_PERSONAL
                    or labels.get("data_form", "structured") not in VALID_DATA_FORMS
                    or labels.get("processing_state", "raw") not in VALID_PROCESSING):
                bad_enum += 1
            ident = (key.get("source_code"), key.get("namespace_name"),
                     key.get("schema_name"), key.get("table_name"),
                     key.get("column_name"))
            if ident in seen:
                dup += 1
            seen.add(ident)
    ok = bad_ref == 0 and bad_enum == 0 and dup == 0
    print(json.dumps({"rows": n, "bad_object_ref": bad_ref,
                      "bad_enum": bad_enum, "duplicates": dup,
                      "status": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-csv", type=Path, default=DEFAULT_TABLES)
    parser.add_argument("--columns-csv", type=Path, default=DEFAULT_COLUMNS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--source", default="")
    parser.add_argument("--cancel-after", type=int, default=0)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        return self_check(args.out_dir)
    summary = build(args.tables_csv, args.columns_csv, args.out_dir,
                    limit=args.limit, source_filter=args.source,
                    cancel_after=args.cancel_after)
    print(json.dumps({k: summary[k] for k in (
        "tables_total", "columns_total", "by_level", "by_personal_info",
        "name_signal_columns", "parse_errors", "cancelled", "rule_version")},
        ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
