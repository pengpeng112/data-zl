"""207 T08（208 A3 补全）：confirmed 值域通用执行器。

契约（207 计划 T08 / 208 A包第3条）：
- 值域判定必须绑定 confirmed 版本 + 生效时间（confirmed_at）+ 物理源（source_code）；
- pending / 失效（deprecated）/ 冲突（conflicted）/ 未登记 的值域只报「待确认 / 受阻」
  （blocked），绝不权威判非法（FAIL）；
- confirmed 码值集合冻结进运行观测（threshold_snapshot.value_domain），值域版本
  （指纹）变化后旧 PASS 复测证据失效；
- 空集语义：数据侧零行为 NO_DATA；confirmed 集合无 enum 码为 blocked，不得视为
  「全部非法」。

本模块只做纯逻辑与平台库查询；源端分布采集走 quality_sql_runner.fetch_readonly_rows
（受控只读 + SQL 安全校验），产物仅聚合指标与去标识样本。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.value_domain import AssetColumnValueDomain

# 标识符白名单：字母/下划线开头，允许字母数字下划线美元符井号（Oracle/PG 常见）
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]{0,127}$")

# 分布采样上限：值域枚举校验只适用于低基数编码列；超限说明该列不适合枚举口径
DEFAULT_MAX_DISTINCT = 500

# 快照中保留的未知码样本上限（码值与计数非患者明细）
UNKNOWN_SAMPLE_CAP = 20

BINDING_FIELDS = ("system_code", "source_code", "schema_name", "table_name", "column_name")


class ValueDomainBindingError(ValueError):
    """绑定身份配置不完整或非法（检测器 result_mapping 问题）。"""


def parse_binding(mapping: dict[str, Any] | None) -> dict[str, str]:
    """从检测器 result_mapping 提取并校验列身份五元组。"""
    m = mapping if isinstance(mapping, dict) else {}
    binding: dict[str, str] = {}
    for f in BINDING_FIELDS:
        v = str(m.get(f) or "").strip()
        if not v:
            raise ValueDomainBindingError(f"value_domain 检测器缺少绑定字段 {f}")
        if f in ("schema_name", "table_name", "column_name") and not _IDENT_RE.match(v):
            raise ValueDomainBindingError(f"绑定字段 {f} 含非法标识符: {v!r}")
        binding[f] = v
    return binding


def build_distribution_sql(binding: dict[str, str]) -> str:
    """按绑定身份生成分布 SQL（标识符已白名单校验；无字面量拼接）。"""
    return (
        f"SELECT {binding['column_name']} AS CODE, COUNT(*) AS CNT "
        f"FROM {binding['schema_name']}.{binding['table_name']} "
        f"GROUP BY {binding['column_name']}"
    )


@dataclass
class DomainVerdict:
    """一次值域判定的完整结论（可序列化入观测快照）。"""

    status: str  # ok / not_registered / pending_only / deprecated_only / conflicted_only / no_enum_codes
    codes: list[dict[str, Any]] = field(default_factory=list)  # 权威码集 [{code, meaning, confirmed_at}]
    pending_count: int = 0
    deprecated_count: int = 0
    conflicted_count: int = 0
    message: str = ""

    @property
    def authoritative(self) -> bool:
        return self.status == "ok" and bool(self.codes)

    def fingerprint(self) -> str:
        """版本指纹：码集 + 含义 + 确认版本号 + 生效时间（confirmed_at）。"""
        material = [
            [c["code"], c.get("meaning") or "", str(c.get("current_version_id") or ""),
             str(c.get("confirmed_at") or "")]
            for c in sorted(self.codes, key=lambda x: str(x["code"]))
        ]
        return hashlib.sha256(
            json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:32]

    def effective_window(self) -> dict[str, str | None]:
        times = [c.get("confirmed_at") for c in self.codes if c.get("confirmed_at")]
        if not times:
            return {"confirmed_at_min": None, "confirmed_at_max": None}
        strs = [t.isoformat() if hasattr(t, "isoformat") else str(t) for t in times]
        return {"confirmed_at_min": min(strs), "confirmed_at_max": max(strs)}


def load_domain_verdict(
    db: Session, binding: dict[str, str],
) -> "DomainVerdict":
    """平台库查询列的值域登记状态（不连源库）。

    权威码集 = status=confirmed 且 conflict_status≠conflicted 且 domain_kind=enum。
    deprecated 码不进集合；pending 码不进集合（只计数提示）。
    """
    rows = db.scalars(
        select(AssetColumnValueDomain).where(
            AssetColumnValueDomain.system_code == binding["system_code"],
            AssetColumnValueDomain.source_code == binding["source_code"],
            AssetColumnValueDomain.schema_name == binding["schema_name"],
            AssetColumnValueDomain.table_name == binding["table_name"],
            AssetColumnValueDomain.column_name == binding["column_name"],
        )
    ).all()
    if not rows:
        return DomainVerdict(
            "not_registered",
            message="值域知识库未登记该列（无法权威判非法；先按 149 流程登记并 confirm）",
        )
    codes: list[dict[str, Any]] = []
    pending = deprecated = conflicted = 0
    for r in rows:
        if r.status == "pending":
            pending += 1
            continue
        if r.status == "deprecated":
            deprecated += 1
            continue
        if r.status != "confirmed":
            continue
        if (r.conflict_status or "none") == "conflicted":
            conflicted += 1
            continue
        if (r.domain_kind or "enum") != "enum":
            # threshold/literal/trap 不是枚举码，不进入 IN 集合
            continue
        codes.append({
            "code": str(r.code),
            "meaning": r.meaning,
            "current_version_id": r.current_version_id,
            "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
        })
    if codes:
        v = DomainVerdict("ok", codes=codes, pending_count=pending,
                          deprecated_count=deprecated, conflicted_count=conflicted)
        return v
    if pending:
        return DomainVerdict(
            "pending_only", pending_count=pending, deprecated_count=deprecated,
            conflicted_count=conflicted,
            message=f"值域未确认：{pending} 条候选仍为 pending（待人工 confirm，不权威判非法）",
        )
    if conflicted:
        return DomainVerdict(
            "conflicted_only", pending_count=pending, deprecated_count=deprecated,
            conflicted_count=conflicted,
            message=f"值域候选冲突未裁决：{conflicted} 条（resolve-conflict 前不进入权威链路）",
        )
    if deprecated:
        return DomainVerdict(
            "deprecated_only", pending_count=pending, deprecated_count=deprecated,
            conflicted_count=conflicted,
            message=f"值域已全部失效（deprecated {deprecated} 条）：旧口径不可继续判错，需重新确认或停用清单",
        )
    return DomainVerdict(
        "no_enum_codes", pending_count=pending, deprecated_count=deprecated,
        conflicted_count=conflicted,
        message="confirmed 记录均非 enum 类型（阈值/字面量/陷阱），无法构成码值集合",
    )


def _normalize_code(value: Any) -> str | None:
    """数据侧码值归一为文本（与登记 code 文本可比）。NULL → None。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    try:  # Decimal
        if value == value.to_integral_value():
            return str(int(value))
        return str(value)
    except AttributeError:
        return str(value)


@dataclass
class DistributionOutcome:
    """分布比对结论（纯逻辑，可独立合成真值验收）。"""

    status: str  # pass / fail / no_data / blocked
    total: int = 0
    illegal: int = 0
    null_count: int = 0
    unknown_codes: list[dict[str, Any]] = field(default_factory=list)
    known_distribution: list[dict[str, Any]] = field(default_factory=list)
    error_code: str | None = None
    message: str = ""


def compare_distribution(
    rows: list[dict[str, Any]],
    codes: list[dict[str, Any]],
    *,
    null_is_error: bool = False,
) -> DistributionOutcome:
    """将源端分布（CODE/CNT 行）与权威码集比对。

    - total=0 → no_data（空集语义，不得据此关单或判非法）；
    - NULL 默认不计非法（缺失由空值规则管），可按 null_is_error 收紧；
    - 未知码（不在 confirmed 集合）计非法并单列清单（码值映射证据）。
    """
    code_map = {c["code"]: c for c in codes}
    total = illegal = null_count = 0
    unknown: dict[str, int] = {}
    known: dict[str, int] = {}
    for row in rows:
        raw = row.get("CODE", row.get("code"))
        try:
            cnt = int(row.get("CNT", row.get("cnt")) or 0)
        except (TypeError, ValueError):
            cnt = 0
        total += cnt
        if raw is None:
            null_count += cnt
            if null_is_error:
                illegal += cnt
            continue
        norm = _normalize_code(raw)
        if norm in code_map:
            known[norm] = known.get(norm, 0) + cnt
        else:
            unknown[norm] = unknown.get(norm, 0) + cnt
            illegal += cnt
    if total <= 0:
        return DistributionOutcome(
            "no_data", total=0, error_code="EMPTY_SCOPE",
            message="分母为 0（零样本），按 NO_DATA 处理",
        )
    out = DistributionOutcome(
        "fail" if illegal > 0 else "pass",
        total=total, illegal=illegal, null_count=null_count,
        unknown_codes=[
            {"code": k, "count": v} for k, v in
            sorted(unknown.items(), key=lambda kv: -kv[1])[:UNKNOWN_SAMPLE_CAP]
        ],
        known_distribution=[
            {"code": k, "count": v, "meaning": code_map[k].get("meaning")}
            for k, v in sorted(known.items(), key=lambda kv: -kv[1])[:UNKNOWN_SAMPLE_CAP]
        ],
    )
    if unknown:
        out.message = (
            f"发现 {len(unknown)} 个未登记码值（合计 {illegal} 行，占 {round(illegal / total * 100, 2)}%）；"
            "仅 confirmed 码值集合参与权威判定"
        )
    return out


def domain_snapshot_for_observation(
    binding: dict[str, str], verdict: DomainVerdict,
    outcome: DistributionOutcome | None = None,
) -> dict[str, Any]:
    """冻结值域绑定进观测（threshold_snapshot.value_domain）。"""
    snap: dict[str, Any] = {
        "binding": dict(binding),
        "fingerprint": verdict.fingerprint(),
        "code_count": len(verdict.codes),
        "effective": verdict.effective_window(),
        "pending_count": verdict.pending_count,
        "deprecated_count": verdict.deprecated_count,
        "conflicted_count": verdict.conflicted_count,
    }
    if outcome is not None:
        snap["unknown_codes"] = outcome.unknown_codes
        snap["known_distribution"] = outcome.known_distribution
        snap["null_count"] = outcome.null_count
        snap["total"] = outcome.total
        snap["illegal"] = outcome.illegal
    return snap


def current_fingerprint(db: Session, mapping: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """计算当前绑定指纹；返回 (fingerprint, error)。绑定缺失/值域未确认时 error 有值。"""
    try:
        binding = parse_binding(mapping)
    except ValueDomainBindingError as exc:
        return None, str(exc)
    verdict = load_domain_verdict(db, binding)
    if not verdict.authoritative:
        return None, verdict.message
    return verdict.fingerprint(), None
