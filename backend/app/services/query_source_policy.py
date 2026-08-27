"""144 S2: source policy gate — disabled/non-readonly/misconfigured sources rejected (A05)."""
from __future__ import annotations

from typing import Any

# 144 §9 fixed error taxonomy for source-level failures.
ERROR_CODE = "E_SOURCE"


class SourcePolicyError(PermissionError):
    def __init__(self, message: str):
        super().__init__(message)
        self.code = ERROR_CODE


def validate_source_policy(source: Any) -> dict[str, Any]:
    """Validate an AssetDataSource-like object for query execution.

    Raises SourcePolicyError when: source missing/disabled, access mode is not
    readonly, db type unsupported, or required connection fields absent.
    """
    if source is None:
        raise SourcePolicyError("数据源不存在")
    enabled = getattr(source, "enabled", None)
    if enabled is False:
        raise SourcePolicyError(f"数据源 {getattr(source, 'source_code', '?')} 已停用")
    access_mode = (getattr(source, "access_mode", "readonly") or "").lower()
    if access_mode not in {"readonly", "read_only", "read-only", ""}:
        raise SourcePolicyError(
            f"数据源 {getattr(source, 'source_code', '?')} 非只读模式，禁止取数执行"
        )
    db_type = (getattr(source, "db_type", "") or "").lower()
    if db_type not in {"oracle", "postgresql", "vastbase", "mysql", "sqlserver"}:
        raise SourcePolicyError(
            f"数据源 {getattr(source, 'source_code', '?')} 数据库类型不受支持: {db_type}"
        )
    host = (
        getattr(source, "target_host", None)
        or getattr(source, "host", None)
        or ((getattr(source, "extra_config", None) or {}) or {}).get("host")
    )
    if not host:
        raise SourcePolicyError(
            f"数据源 {getattr(source, 'source_code', '?')} 缺少连接主机配置"
        )
    return {"ok": True, "source_code": getattr(source, "source_code", "")}


def schema_belongs_to_source(source: Any, schema_name: str) -> bool:
    """Check the queried schema is within the source's declared scope."""
    if not schema_name:
        return True
    declared = getattr(source, "schema_scope", None) or getattr(source, "schemas", None)
    if not declared:
        return True  # no declared scope → cannot disprove; metadata gate handles exactness
    if isinstance(declared, str):
        declared = [p.strip().upper() for p in declared.split(",") if p.strip()]
    else:
        declared = [str(p).upper() for p in declared]
    return schema_name.upper() in declared
