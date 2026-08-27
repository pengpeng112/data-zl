"""144 S3: exact physical object identity (144 §4.6, 138 §3.3).

object_key = system_code|source_code|namespace_name|schema_name|object_name|object_type
Table-name-only or ILIKE matching is never a valid resolution result.
"""
from __future__ import annotations

from typing import Any, Iterable


class AmbiguousObjectError(ValueError):
    """More than one physical object matched — fail closed instead of guessing."""


def build_object_key(
    *,
    system_code: str,
    source_code: str,
    schema_name: str,
    object_name: str,
    object_type: str = "table",
    namespace_name: str = "",
) -> str:
    parts = {
        "system_code": system_code,
        "source_code": source_code,
        "namespace_name": namespace_name,
        "schema_name": schema_name,
        "object_name": object_name,
        "object_type": object_type,
    }
    missing = [k for k, v in parts.items() if not (v or "").strip()]
    # namespace may be empty; everything else is required
    missing = [m for m in missing if m != "namespace_name"]
    if missing:
        raise ValueError(f"object_key 缺少必需身份字段: {', '.join(missing)}")
    if any("|" in str(v) for v in parts.values()):
        raise ValueError("object_key 各段不允许包含分隔符 |")
    return "|".join(
        [
            system_code.strip(),
            source_code.strip(),
            (namespace_name or "").strip(),
            schema_name.strip(),
            object_name.strip(),
            object_type.strip(),
        ]
    )


def parse_object_key(key: str) -> dict[str, str]:
    parts = (key or "").split("|")
    if len(parts) != 6:
        raise ValueError(f"非法 object_key（必须 6 段）: {key!r}")
    system_code, source_code, namespace_name, schema_name, object_name, object_type = parts
    return {
        "system_code": system_code,
        "source_code": source_code,
        "namespace_name": namespace_name,
        "schema_name": schema_name,
        "object_name": object_name,
        "object_type": object_type,
    }


def resolve_object(
    objects: Iterable[dict[str, Any]],
    *,
    source_code: str | None = None,
    schema_name: str | None = None,
    object_name: str | None = None,
    object_type: str | None = None,
    system_code: str | None = None,
) -> dict[str, Any] | None:
    """Exact-match resolution across physical identity fields.

    - object_name + schema_name must match exactly (case-insensitive);
    - if source_code/system_code omitted and multiple physical objects match,
      raise AmbiguousObjectError (never pick the first silently);
    - no match → None.
    """
    if not object_name:
        raise ValueError("resolve_object 需要 object_name")
    wanted_schema = (schema_name or "").strip().upper()
    wanted_source = (source_code or "").strip().upper()
    wanted_system = (system_code or "").strip().upper()
    wanted_type = (object_type or "").strip().lower()

    hits: list[dict[str, Any]] = []
    for obj in objects or []:
        if str(obj.get("object_name", "")).upper() != object_name.upper():
            continue
        obj_schema = str(obj.get("schema_name", "")).upper()
        if wanted_schema and obj_schema != wanted_schema:
            continue
        if wanted_source and str(obj.get("source_code", "")).upper() != wanted_source:
            continue
        if wanted_system and str(obj.get("system_code", "")).upper() != wanted_system:
            continue
        if wanted_type and str(obj.get("object_type", "table")).lower() != wanted_type:
            continue
        hits.append(obj)
    if not hits:
        return None
    if len(hits) > 1:
        raise AmbiguousObjectError(
            "对象解析存在多个物理身份（同名表跨来源），必须提供 source_code/system_code: "
            + "; ".join(
                f"{h.get('system_code')}|{h.get('source_code')}|{h.get('schema_name')}.{h.get('object_name')}"
                for h in hits[:5]
            )
        )
    return hits[0]
