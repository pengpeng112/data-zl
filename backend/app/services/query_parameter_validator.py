"""144 S2: strict bind-parameter contract between query assets and connectors.

Rules (144 §4.1):
- bind names in SQL must exactly match the parameter schema;
- unknown, missing, or unused parameters are all blocked;
- values are validated against the parameter JSON Schema (type/range/enum/length);
- callers never rewrite values into SQL text — values only travel as bind dict.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_ORACLE_BIND_RE = re.compile(r"(?<![:\w]):([A-Za-z_][A-Za-z0-9_]*)")
_PG_BIND_RE = re.compile(r"%\(([A-Za-z_][A-Za-z0-9_]*)\)s")
_TSQL_BIND_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)\b")

# 144 §9: unified error taxonomy; parameter problems are E_PARAM.
ERROR_CODE = "E_PARAM"


class ParameterValidationError(ValueError):
    """Bind parameter contract violated (E_PARAM)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = ERROR_CODE


def extract_bind_names(sql: str, dialect: str = "oracle") -> set[str]:
    """Extract bind parameter names used by the SQL for the given dialect."""
    text = sql or ""
    dialect_l = (dialect or "oracle").lower()
    names: set[str] = set()
    if dialect_l in {"postgresql", "vastbase"}:
        names.update(_PG_BIND_RE.findall(text))
    elif dialect_l in {"sqlserver", "mssql", "tsql"}:
        if _PG_BIND_RE.search(text):
            # 161 P1-1（round-2 P2）：sqlserver 资产混入 %(name)s（pyformat）形态——
            # pymssql 执行侧只认 pyformat 且已 fail-closed，这里提前告警线索，不阻塞。
            logger.warning(
                "占位符风格冲突：sqlserver SQL 同时包含 @name 与 %(name)s 形态；"
                "pymssql 执行侧将拒绝该 SQL，请统一为 %(name)s"
            )
        names.update(_TSQL_BIND_RE.findall(text))
    else:
        # oracle colon binds; skip '::' casts by the negative lookbehind
        names.update(_ORACLE_BIND_RE.findall(text))
    return {n.lower() for n in names}


def _validate_type(name: str, value: Any, spec: dict) -> None:
    declared = (spec.get("type") or "string").lower()
    sensitive = bool(spec.get("sensitive"))
    if sensitive:
        # sensitive values must be strings or ints; never structured payloads
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ParameterValidationError(f"参数 {name} 为敏感标识，只允许标量值")
    if declared == "string":
        if not isinstance(value, str):
            raise ParameterValidationError(f"参数 {name} 必须是字符串")
        if "minLength" in spec and len(value) < int(spec["minLength"]):
            raise ParameterValidationError(f"参数 {name} 长度小于 minLength")
        if "maxLength" in spec and len(value) > int(spec["maxLength"]):
            raise ParameterValidationError(f"参数 {name} 长度超过 maxLength")
        if "pattern" in spec and not re.search(spec["pattern"], value):
            raise ParameterValidationError(f"参数 {name} 不符合 pattern")
    elif declared in {"integer", "number"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParameterValidationError(f"参数 {name} 必须是数值")
        if declared == "integer" and not float(value).is_integer():
            raise ParameterValidationError(f"参数 {name} 必须是整数")
        if "minimum" in spec and value < spec["minimum"]:
            raise ParameterValidationError(f"参数 {name} 低于 minimum")
        if "maximum" in spec and value > spec["maximum"]:
            raise ParameterValidationError(f"参数 {name} 超过 maximum")
    elif declared == "boolean":
        if not isinstance(value, bool):
            raise ParameterValidationError(f"参数 {name} 必须是布尔值")
    elif declared == "array":
        if not isinstance(value, list):
            raise ParameterValidationError(f"参数 {name} 必须是列表")
        if "minItems" in spec and len(value) < int(spec["minItems"]):
            raise ParameterValidationError(f"参数 {name} 少于 minItems")
        if "maxItems" in spec and len(value) > int(spec["maxItems"]):
            raise ParameterValidationError(f"参数 {name} 超过 maxItems")
    if "enum" in spec and value not in spec["enum"]:
        raise ParameterValidationError(f"参数 {name} 不在允许的枚举内")


def validate_query_parameters(
    sql: str,
    parameter_schema: dict | None,
    parameters: dict | None,
    dialect: str = "oracle",
) -> dict[str, Any]:
    """Validate parameters against SQL binds and schema; return normalized dict.

    Raises ParameterValidationError on any mismatch (missing/unknown/unused/type).
    """
    params = dict(parameters or {})
    schema = parameter_schema or {"type": "object", "properties": {}}
    properties: dict[str, dict] = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    binds = extract_bind_names(sql, dialect)
    provided = {str(k).lower(): v for k, v in params.items()}
    declared = {str(k).lower() for k in properties}

    unknown = sorted(provided.keys() - declared)
    if unknown:
        raise ParameterValidationError(f"未知参数（未在 schema 声明）: {', '.join(unknown)}")

    missing = sorted(binds - provided.keys())
    if missing:
        raise ParameterValidationError(f"SQL 需要但未提供的参数: {', '.join(missing)}")

    missing_required = sorted(required - provided.keys())
    if missing_required:
        raise ParameterValidationError(f"必填参数缺失: {', '.join(missing_required)}")

    unused = sorted(declared & (provided.keys() - binds))
    if unused:
        raise ParameterValidationError(
            f"参数已在 schema 提供但 SQL 未使用: {', '.join(unused)}"
        )

    normalized: dict[str, Any] = {}
    for name in binds:
        spec = properties.get(name) or {}
        value = provided[name]
        _validate_type(name, value, spec)
        normalized[name] = value
    return normalized


def build_bind_parameters(
    sql: str,
    parameter_schema: dict | None,
    parameters: dict | None,
    dialect: str = "oracle",
) -> dict[str, Any]:
    """Validate then return the exact bind dict handed to the connector."""
    return validate_query_parameters(sql, parameter_schema, parameters, dialect)
