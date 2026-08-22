"""Shared pure logic for plan139 asset packaging and draft importing.

Layering rules (plan 139 §4.2):
- explicit PK/FK  -> structural relations imported as ``db_constraint`` evidence;
- view references -> dependency/lineage edges only;
- view JOINs      -> ``asset_relation_reviews`` drafts (never auto-promoted);
- complex logic   -> ``asset_relation_recipes`` inactive drafts;
- cross-system    -> ``cross_system_pending``, never drawn as formal edges.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

PART_RE = re.compile(r"^[A-Z0-9_$#]+$")
MAX_PARTS = 4


def split_name(value: Any) -> list[str]:
    """Normalize a possibly quoted multi-part name into uppercase parts."""
    raw = str(value or "").strip()
    parts = [p.strip().strip('"[]`').strip().upper() for p in raw.split(".") if p.strip()]
    return parts


def qualify_name(value: Any, owner: str = "") -> str:
    """Return an uppercase dotted name with at most MAX_PARTS segments."""
    parts = split_name(value)
    owner_parts = split_name(owner)
    if len(parts) == 1 and owner_parts:
        parts = owner_parts + parts
    if not parts or len(parts) > MAX_PARTS or not all(PART_RE.fullmatch(p) for p in parts):
        raise ValueError(f"unsupported identifier: {value!r}")
    return ".".join(parts)


def columns_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = re.split(r"[|,+]", str(value or ""))
    out = []
    for item in items:
        part = str(item).strip().upper()
        if part:
            out.append(part)
    return out


def identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    left = (str(row.get("from_table", "")).upper(), tuple(columns_list(row.get("from_columns"))))
    right = (str(row.get("to_table", "")).upper(), tuple(columns_list(row.get("to_columns"))))
    return tuple(sorted((left, right)))


def qualifier_signature(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("qualifiers") or []
    if not isinstance(values, list):
        values = [values]
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


REVIEW_INTAKE_STATUSES = {"candidate", "partial"}


def prepare_review_groups(
    payload: Mapping[str, Any],
    *,
    owner_field: str = "owner",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Group parser candidates into deduplicated review-draft rows."""
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    for raw in payload.get("candidates", []):
        if not isinstance(raw, Mapping) or raw.get("intake_status") not in REVIEW_INTAKE_STATUSES:
            continue
        try:
            row = dict(raw)
            row["from_table"] = qualify_name(raw.get("from_table"), str(raw.get(owner_field) or ""))
            row["to_table"] = qualify_name(raw.get("to_table"), str(raw.get(owner_field) or ""))
            row["from_columns"] = columns_list(raw.get("from_columns"))
            row["to_columns"] = columns_list(raw.get("to_columns"))
            if not row["from_columns"] or len(row["from_columns"]) != len(row["to_columns"]):
                raise ValueError("empty_or_unbalanced_columns")
        except ValueError as exc:
            skipped.append({"view": raw.get("view"), "reason": str(exc)[:200]})
            continue
        key = (identity(row), qualifier_signature(row), row.get("intake_status"))
        evidence = {
            "owner": raw.get(owner_field),
            "view": raw.get("view"),
            "source_sql_sha256": raw.get("source_sql_sha256"),
            "runtime_status": raw.get("runtime_status") or "runtime_skipped",
            "warnings": raw.get("warnings") or [],
            "cross_database": bool(raw.get("cross_database")),
            # 143 修正：evidence 必须携带系统/数据源归属，导入器据此填
            # asset_relation_reviews.from/to_system_code，否则按系统筛选会漏掉草稿。
            "system_code": raw.get("system_code"),
            "source_code": raw.get("source_code"),
        }
        if key not in grouped:
            grouped[key] = {**row, "evidence": [evidence]}
        else:
            grouped[key]["evidence"].append(evidence)
    output = sorted(grouped.values(), key=lambda row: json.dumps(identity(row), sort_keys=True))
    for row in output:
        row["evidence"] = sorted(
            {json.dumps(item, sort_keys=True): item for item in row["evidence"]}.values(),
            key=lambda item: (str(item.get("owner")), str(item.get("view"))),
        )
    return output, skipped


def prepare_recipe_groups(payload: Mapping[str, Any], *, recipe_prefix: str) -> list[dict[str, Any]]:
    """Group recipe candidates into one inactive draft per source view."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in payload.get("recipe_candidates", []):
        if not isinstance(raw, Mapping):
            continue
        try:
            item = dict(raw)
            item["from_table"] = qualify_name(raw.get("from_table"), str(raw.get("owner") or ""))
            item["to_table"] = qualify_name(raw.get("to_table"), str(raw.get("owner") or ""))
            item["from_columns"] = columns_list(raw.get("from_columns"))
            item["to_columns"] = columns_list(raw.get("to_columns"))
        except ValueError:
            continue
        key = (
            str(raw.get("owner") or "").upper(),
            str(raw.get("view") or "").upper(),
            str(raw.get("source_sql_sha256") or ""),
        )
        grouped[key].append(item)
    recipes: list[dict[str, Any]] = []
    for (owner, view, sha), joins in sorted(grouped.items()):
        unique = {
            json.dumps((identity(row), qualifier_signature(row), row.get("branch")), sort_keys=True): row
            for row in joins
        }
        clean_joins = sorted(unique.values(), key=lambda row: json.dumps(identity(row), sort_keys=True))
        slug = re.sub(r"[^A-Z0-9_]", "_", f"{owner}_{view}")[:80]
        recipes.append(
            {
                "recipe_id": f"{recipe_prefix}_{slug}_{sha[:12]}"[:240],
                "owner": owner,
                "view": view,
                "source_sql_sha256": sha,
                "joins": clean_joins,
            }
        )
    return recipes


def metadata_check(
    row: Mapping[str, Any],
    table_names: set[str],
    column_names: Mapping[str, set[str]],
) -> tuple[bool, list[str]]:
    """Verify both endpoints and all key columns exist in platform metadata."""
    errors: list[str] = []
    for side in ("from", "to"):
        table = str(row.get(f"{side}_table", "")).upper()
        cols = columns_list(row.get(f"{side}_columns"))
        if table not in table_names:
            errors.append(f"missing_table:{table}")
            continue
        missing = sorted(set(cols) - set(column_names.get(table, set())))
        if missing:
            errors.append(f"missing_columns:{table}:{','.join(missing)}")
    return not errors, errors


def content_fingerprint(joins: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(joins), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def iter_unique(rows: Iterable[Mapping[str, Any]], key_fields: Sequence[str]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = json.dumps({f: row.get(f) for f in key_fields}, ensure_ascii=False, sort_keys=True)
        seen.setdefault(key, dict(row))
    return list(seen.values())
