import hashlib
import json
import re

from fastapi import HTTPException


def canonical_recipe_payload(data: dict) -> dict:
    payload = dict(data)
    payload["primary_tables"] = payload.get("primary_tables") or []
    payload["joins"] = payload.get("joins") or []
    return payload


def recipe_hash(data: dict) -> str:
    raw = json.dumps(canonical_recipe_payload(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def assert_transition(current: str, target: str) -> None:
    allowed = {"draft": {"submitted"}, "submitted": {"approved", "draft"}, "approved": {"active"}, "active": {"deprecated"}, "deprecated": set()}
    if target not in allowed.get(current, set()):
        raise HTTPException(status_code=400, detail=f"配方状态不能从 {current} 转为 {target}")


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$")
_CONDITION = re.compile(r"^[A-Za-z0-9_$#.\s=<>!()+\-*/]+$")


def generate_select_sql(primary_tables: list, joins: list) -> str:
    names = [str(item.get("table") or item.get("name") or "") if isinstance(item, dict) else str(item) for item in primary_tables]
    if not names or any(not _IDENTIFIER.fullmatch(name) for name in names):
        raise HTTPException(status_code=400, detail="配方包含非法或缺失的表标识")
    # Reject dangerous content even when a malformed caller supplies unused
    # joins for a single-table recipe.
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
