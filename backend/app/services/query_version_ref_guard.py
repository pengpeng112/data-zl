"""144 S2/S4: version-reference gate for metric activation and product publish (A04/A17).

Centralizes the rule: main/numerator/denominator query references and product
pin versions must resolve to runnable versions — active current versions, or
explicitly allowed legacy_unverified ones. candidate/blocked never qualify.
"""
from __future__ import annotations

from typing import Any, Callable

RunnableStates = {"active", "legacy_unverified"}


def validate_version_reference(
    resolver: Callable[[str, int], Any],
    query_code: str | None,
    version: int | None,
    *,
    allow_legacy: bool = False,
    context: str = "metric",
) -> dict[str, Any]:
    """resolver(code, version) → version object with status/is_active, or None."""
    if not query_code or version is None:
        raise ValueError(f"{context} 引用缺少 query_code/version")
    target = resolver(query_code, version)
    if target is None:
        raise LookupError(f"{context} 引用的查询版本不存在: {query_code}@{version}")
    status = getattr(target, "status", "")
    is_active = bool(getattr(target, "is_active", False))
    if status == "blocked":
        raise ValueError(f"{context} 引用了 blocked 查询版本: {query_code}@{version}")
    if status == "candidate":
        raise ValueError(f"{context} 引用了 candidate 查询版本: {query_code}@{version}")
    if status == "legacy_unverified":
        if not allow_legacy:
            raise ValueError(
                f"{context} 引用了 legacy_unverified 查询版本且未显式允许: {query_code}@{version}"
            )
        return {"ok": True, "status": status, "legacy": True}
    if status != "active" or not is_active:
        raise ValueError(
            f"{context} 引用了非现行查询版本（status={status}, is_active={is_active}）: "
            f"{query_code}@{version}"
        )
    return {"ok": True, "status": status, "legacy": False}


def validate_product_pin(
    resolver: Callable[[str, int], Any],
    query_code: str | None,
    version: int | None,
    *,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    """Product pin must point at a runnable, non-candidate/blocked version."""
    return validate_version_reference(
        resolver, query_code, version, allow_legacy=allow_legacy, context="product"
    )
