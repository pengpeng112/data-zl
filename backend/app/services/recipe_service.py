import hashlib
import json
import re

from fastapi import HTTPException

# Historical seed statuses → current state machine
_SEED_STATUS_MAP = {
    "user_confirmed": "approved",
    "confirmed": "approved",
    "formal": "active",
    "verified": "approved",
    "candidate": "draft",
    "draft": "draft",
    "submitted": "submitted",
    "approved": "approved",
    "active": "active",
    "deprecated": "deprecated",
}


def map_seed_status(raw: str | None) -> str:
    """Map historical seed status strings into draft→submitted→approved→active."""
    key = (raw or "draft").strip().lower()
    return _SEED_STATUS_MAP.get(key, "draft")


def normalize_recipe_joins(joins: list | None) -> list[dict]:
    """Normalize seed join shape {type,from,to,condition} → {join_type,on,from,to}."""
    out: list[dict] = []
    for join in joins or []:
        if not isinstance(join, dict):
            continue
        item = dict(join)
        join_type = (
            item.get("join_type")
            or item.get("type")
            or "LEFT"
        )
        on = (
            item.get("on")
            or item.get("join_condition")
            or item.get("condition")
            or ""
        )
        item["join_type"] = str(join_type).upper()
        item["on"] = str(on).strip()
        if "join_condition" not in item:
            item["join_condition"] = item["on"]
        out.append(item)
    return out


def canonical_recipe_payload(data: dict) -> dict:
    payload = dict(data or {})
    payload["primary_tables"] = payload.get("primary_tables") or []
    raw_joins = payload.get("joins") or []
    payload["joins"] = normalize_recipe_joins(raw_joins)
    # Preserve full knowledge fields when present
    for key in (
        "field_logic",
        "hard_rules",
        "validation_evidence",
        "do_not_use_as_primary_join",
        "sql_fragments",
        "filters",
        "dedup",
        "scope",
        "forbidden",
    ):
        if key in data:
            payload[key] = data[key]
    return payload


def recipe_hash(data: dict) -> str:
    raw = json.dumps(canonical_recipe_payload(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def assert_transition(current: str, target: str) -> None:
    allowed = {
        "draft": {"submitted"},
        "submitted": {"approved", "draft"},
        "approved": {"active"},
        "active": {"deprecated"},
        "deprecated": set(),
    }
    if target not in allowed.get(current, set()):
        raise HTTPException(status_code=400, detail=f"配方状态不能从 {current} 转为 {target}")


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$")
_CONDITION = re.compile(r"^[A-Za-z0-9_$#.\s=<>!()+\-*/]+$")


def extract_recipe_table_names(primary_tables: list) -> list[str]:
    names = [
        str(item.get("table") or item.get("name") or "") if isinstance(item, dict) else str(item)
        for item in primary_tables
    ]
    return names


def validate_recipe_tables(primary_tables: list) -> None:
    """Create-time guard: reject non-identifier table keys with 422 instead of
    letting them surface as a 400 at SQL-generation time (173 P3-5). An empty
    list stays valid — drafts may be created before tables are chosen."""
    bad = [name for name in extract_recipe_table_names(primary_tables or [])
           if not _IDENTIFIER.fullmatch(name)]
    if bad:
        raise HTTPException(status_code=422, detail=f"primary_tables 含非法表标识: {bad[:3]}")


def generate_select_sql(primary_tables: list, joins: list) -> str:
    names = extract_recipe_table_names(primary_tables)
    if not names or any(not _IDENTIFIER.fullmatch(name) for name in names):
        raise HTTPException(status_code=400, detail="配方包含非法或缺失的表标识")
    joins = normalize_recipe_joins(joins)
    for join in joins:
        if not isinstance(join, dict):
            raise HTTPException(status_code=400, detail="配方包含非法关联定义")
        condition = str(join.get("on") or join.get("join_condition") or "").strip()
        if condition and (not _CONDITION.fullmatch(condition) or ";" in condition or "--" in condition):
            raise HTTPException(status_code=400, detail="配方包含不安全的关联条件")
    sql = f"SELECT *\nFROM {names[0]}"
    for index, name in enumerate(names[1:]):
        join = joins[index] if index < len(joins) and isinstance(joins[index], dict) else {}
        condition = str(join.get("on") or join.get("join_condition") or "").strip()
        if not condition or not _CONDITION.fullmatch(condition) or ";" in condition or "--" in condition:
            raise HTTPException(status_code=400, detail=f"表 {name} 缺少安全的关联条件")
        join_type = str(join.get("join_type") or "LEFT").upper()
        if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
            raise HTTPException(status_code=400, detail="不支持的 join_type")
        sql += f"\n{join_type} JOIN {name} ON {condition}"
    return sql + ";"
