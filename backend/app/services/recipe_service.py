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


# 198 F06/T11：r197 草稿把 join_family_ids/dedup_strategy/time_fields 字典直接
# 存进 joins——这是"知识型/结构未就绪"形态，不是可执行关联数组，不得静默当空关联。
_KNOWLEDGE_JOIN_KEYS = ("join_family_ids", "dedup_strategy", "time_fields")
# payload 级知识键：聚合/时间选价/先聚合再 JOIN/子查询回填等现有生成器无法
# 保真表达的口径（出现即归知识型，生成端显式拒绝，不降格平铺 SELECT *）。
_PAYLOAD_COMPLEX_KEYS = (
    "dedup_strategy",
    "time_fields",
    "outpatient_subquery",
    "conservation_probe",
    "sql_fragments",
    "pre_aggregate",
)


def _not_executable(code: str, reasons: list[str]) -> HTTPException:
    """机器可读的结构/就绪错误（198 T11/T12：治理前识别并拒绝）。"""
    return HTTPException(status_code=422, detail={"code": code, "reasons": reasons})


def normalize_recipe_joins(joins) -> list[dict]:
    """Normalize seed join shape {type,from,to,condition} → {join_type,on,from,to}.

    仅处理标准数组形态；dict/误形返回 []，由 classify_recipe_joins 与
    recipe_readiness 负责显式标记"知识型/结构未就绪"，不在这里静默当空关联。
    """
    if not isinstance(joins, list):
        return []
    out: list[dict] = []
    for join in joins:
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


def classify_recipe_joins(joins) -> tuple[list[dict], list[str]]:
    """joins → (标准数组, 结构未就绪原因)。dict/误形返回 ([], 原因列表)。

    空数组/None 是合法形态（单表配方允许无关联），返回 ([], [])。
    """
    if joins is None:
        return [], []
    if isinstance(joins, list):
        if not joins:
            return [], []
        bad_indexes = [str(i) for i, join in enumerate(joins) if not isinstance(join, dict)]
        if bad_indexes:
            return [], [f"joins 含非对象项（下标 {','.join(bad_indexes)}），无法解析关联定义"]
        return normalize_recipe_joins(joins), []
    if isinstance(joins, dict):
        markers = [k for k in _KNOWLEDGE_JOIN_KEYS if joins.get(k) is not None]
        if markers:
            return [], [
                "joins 为知识型 dict 形态（含 " + "/".join(markers) + "），"
                "未结构化为可执行关联数组 [{from,to,join_type,on}]"
            ]
        return [], ["joins 为 dict 形态，期望标准关联数组 [{from,to,join_type,on}]"]
    return [], [f"joins 形态非法（期望数组或知识型 dict），实际 {type(joins).__name__}"]


def recipe_readiness(data: dict) -> dict:
    """机器可读就绪标记（写入 recipe_json）：readiness + not_ready_reasons。

    未就绪原因覆盖：知识型/误形 joins、非法表标识、多表关联结构不完备
    （数量不足/空 ON/不安全/不支持 join_type）、payload 级复杂口径。
    """
    payload = data or {}
    reasons: list[str] = []
    normalized, join_reasons = classify_recipe_joins(payload.get("joins"))
    reasons.extend(join_reasons)
    if not join_reasons:
        names = extract_recipe_table_names(payload.get("primary_tables") or [])
        bad = [name for name in names if not _IDENTIFIER.fullmatch(name)]
        if bad:
            reasons.append("primary_tables 含非法表标识: " + ", ".join(bad[:3]))
        elif names:
            reasons.extend(_join_structure_reasons(names, normalized))
    for key in _PAYLOAD_COMPLEX_KEYS:
        if payload.get(key):
            reasons.append(
                f"payload 含 {key}（聚合/时间选价/复合去重口径），当前生成器无法保真表达"
            )
    return {
        "readiness": "not_executable" if reasons else "ready",
        "not_ready_reasons": reasons,
    }


def canonical_recipe_payload(data: dict) -> dict:
    payload = dict(data or {})
    payload["primary_tables"] = payload.get("primary_tables") or []
    raw_joins = payload.get("joins")
    normalized, _ = classify_recipe_joins(raw_joins)
    if isinstance(raw_joins, (list, type(None))):
        payload["joins"] = normalized
    # 知识型 dict/误形原样保留（知识载体），由 readiness 显式标记，不改写为空数组
    readiness = recipe_readiness(payload)
    payload["readiness"] = readiness["readiness"]
    payload["not_ready_reasons"] = readiness["not_ready_reasons"]
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
# 关系族引用：自描述形态（TABLE.COL=TABLE.COL，可带 owner 前缀）视为可解析；
# 其余（如 r197 本地 S2F-xxx 族 ID、S3F:复合键）在无登记表时视为未解析（198 T12）。
_FAMILY_MEMBER = r"[A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*){0,2}"
_SELF_DESCRIBING_FAMILY_RE = re.compile(rf"^{_FAMILY_MEMBER}\s*=\s*{_FAMILY_MEMBER}$")
_FAMILY_REF_KEYS = ("join_family_ids", "family_id")


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
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_table_identifier", "tables": bad[:3]},
        )


def unresolvable_family_refs(joins, known_family_ids=None) -> list[str]:
    """收集 join 条目内引用的关系族 ID/键，返回当前无法解析的引用。

    可解析 = 出现在 known_family_ids 白名单，或本身是自描述列对形态。
    """
    known = set(known_family_ids or ())
    unresolved: list[str] = []
    items = joins if isinstance(joins, list) else []
    for join in items:
        if not isinstance(join, dict):
            continue
        refs: list[str] = []
        for key in _FAMILY_REF_KEYS:
            value = join.get(key)
            if isinstance(value, str):
                refs.append(value)
            elif isinstance(value, list):
                refs.extend(v for v in value if isinstance(v, str))
        for ref in refs:
            clean = ref.strip()
            if clean in known:
                continue
            if _SELF_DESCRIBING_FAMILY_RE.match(clean):
                continue
            unresolved.append(clean)
    return unresolved


def _join_structure_reasons(names: list[str], normalized: list[dict]) -> list[str]:
    """标准数组形态下的多表关联结构原因（数量不足/空 ON/不安全/join_type）。"""
    reasons: list[str] = []
    if len(names) <= 1:
        return reasons
    if len(normalized) < len(names) - 1:
        reasons.append(f"joins 数量不足：{len(names)} 张表至少需要 {len(names) - 1} 条关联")
    for index, name in enumerate(names[1:]):
        join = normalized[index] if index < len(normalized) else {}
        condition = str(join.get("on") or join.get("join_condition") or "").strip()
        if not condition:
            reasons.append(f"表 {name} 缺少关联条件（空 ON）")
            continue
        if not _CONDITION.fullmatch(condition) or ";" in condition or "--" in condition:
            reasons.append(f"表 {name} 关联条件不安全")
            continue
        join_type = str(join.get("join_type") or "LEFT").upper()
        if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
            reasons.append(f"表 {name} 不支持的 join_type: {join_type}")
    return reasons


def validate_recipe_structure(
    primary_tables: list,
    joins,
    *,
    payload: dict | None = None,
    known_family_ids=None,
) -> list[str]:
    """提交/激活前结构校验；返回机器可读失败原因列表（空列表 = 通过）。

    校验：表名合法、joins 形态为标准数组、逐表 ON 非空且安全、join_type 合法、
    关系族引用可解析、payload 无知识型复杂口径。draft 允许未完备（not_ready_reasons
    记录在 recipe_json），但未通过本校验的版本不得 submit/activate（198 T12）。
    """
    reasons: list[str] = []
    names = extract_recipe_table_names(primary_tables or [])
    if not names:
        return ["primary_tables 为空（可执行配方至少需要一张主表）"]
    bad = [name for name in names if not _IDENTIFIER.fullmatch(name)]
    if bad:
        return [f"primary_tables 含非法表标识: {bad[:3]}"]
    normalized, join_reasons = classify_recipe_joins(joins)
    if join_reasons:
        return join_reasons
    reasons.extend(_join_structure_reasons(names, normalized))
    unresolved = unresolvable_family_refs(joins, known_family_ids)
    if unresolved:
        reasons.append("存在未解析的关系族引用: " + ", ".join(sorted(set(unresolved))[:5]))
    if payload:
        reasons.extend(recipe_readiness(payload)["not_ready_reasons"])
    return list(dict.fromkeys(reasons))


def generate_select_sql(primary_tables: list, joins, payload: dict | None = None) -> str:
    names = extract_recipe_table_names(primary_tables)
    bad = [name for name in names if not _IDENTIFIER.fullmatch(name)]
    if not names or bad:
        raise _not_executable("invalid_table_identifier", ["非法或缺失的表标识: " + ", ".join(bad[:3])])
    normalized, join_reasons = classify_recipe_joins(joins)
    if join_reasons:
        raise _not_executable("recipe_not_executable", join_reasons)
    if payload:
        payload_reasons = recipe_readiness({**payload, "joins": joins})["not_ready_reasons"]
        if payload_reasons:
            raise _not_executable("recipe_knowledge_only", payload_reasons)
    # 与既有安全门禁对齐：逐条 join 先做条件安全检查（单表配方的多余关联也要拦）
    for join in normalized:
        condition = str(join.get("on") or join.get("join_condition") or "").strip()
        if condition and (not _CONDITION.fullmatch(condition) or ";" in condition or "--" in condition):
            raise _not_executable("unsafe_join_condition", ["关联条件不安全: " + condition[:60]])
    sql = f"SELECT *\nFROM {names[0]}"
    for index, name in enumerate(names[1:]):
        join = normalized[index] if index < len(normalized) else {}
        condition = str(join.get("on") or join.get("join_condition") or "").strip()
        if not condition:
            raise _not_executable("missing_join_condition", [f"表 {name} 缺少安全的关联条件（空 ON）"])
        if not _CONDITION.fullmatch(condition) or ";" in condition or "--" in condition:
            raise _not_executable("unsafe_join_condition", [f"表 {name} 关联条件不安全"])
        join_type = str(join.get("join_type") or "LEFT").upper()
        if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
            raise _not_executable("unsupported_join_type", [f"表 {name} 不支持的 join_type: {join_type}"])
        sql += f"\n{join_type} JOIN {name} ON {condition}"
    return sql + ";"
