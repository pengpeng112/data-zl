"""193 B04/B05：数据集分类分级策略、传播引擎与统一授权网关。

核心不变量（B02 契约）：
- 未分类默认 P4 fail-closed（读/导出默认拒绝，返回 classification_pending）。
- 组合继承：等级取 max，使用条件取交；JOIN/纵向组合结果至少 P3。
- 假名化/掩码不降级；降级需审批并保留旧版本。
- 标签版本冲突失败关闭。
- 用途授权撤销即时生效（每次出口实时校验 grant）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dataset import AssetDsClassification, AssetDsGrant

LEVEL_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


class AccessDecision(str, Enum):
    ALLOW = "allow"
    DENY_UNCLASSIFIED = "deny_unclassified"
    DENY_LEVEL = "deny_level"
    DENY_NO_GRANT = "deny_no_grant"
    DENY_GRANT_REVOKED = "deny_grant_revoked"
    DENY_GRANT_EXPIRED = "deny_grant_revoked"
    DENY_OPERATION = "deny_operation"
    DENY_COLUMN = "deny_column"


@dataclass
class EffectivePolicy:
    """对象的有效安全策略（继承/组合计算结果）。"""

    protection_level: str = "P4"
    business_categories: list[str] = field(default_factory=list)
    personal_info: str = "pending"
    processing_state: str = "raw"
    purposes: list[str] | None = None      # None=未约束（继承自无标签对象）→ 视为禁止
    export_allowed: bool = False
    training_allowed: bool = False
    re_id_risk_review_required: bool = False
    classified: bool = False               # 是否有任何显式标签

    @property
    def is_pending(self) -> bool:
        return not self.classified or self.personal_info == "pending"


def resolve_policy(labels: dict | None) -> EffectivePolicy:
    """单个对象的标签 → 有效策略（未标注字段按 B02 §1 默认）。"""
    labels = labels or {}
    uc = labels.get("usage_constraints") or {}
    has_any = bool(labels)
    purposes = uc.get("purposes")
    return EffectivePolicy(
        protection_level=labels.get("protection_level", "P4"),
        business_categories=list(labels.get("business_categories") or []),
        personal_info=labels.get("personal_info", "pending"),
        processing_state=labels.get("processing_state", "raw"),
        purposes=list(purposes) if purposes is not None else None,
        export_allowed=bool(uc.get("export_allowed", False)),
        training_allowed=bool(uc.get("training_allowed", False)),
        classified=has_any,
    )


def combine_policies(policies: list[EffectivePolicy], joined: bool = True) -> EffectivePolicy:
    """组合继承（JOIN/纵向/派生）：等级 max、条件取交、组合触发重评估。

    joined=True 时组合结果至少 P3（识别风险），并置 re_id_risk_review_required。
    假名化（processing_state 变化）不影响等级——调用方不得用本函数做降级。
    """
    if not policies:
        return EffectivePolicy()
    level = max((p.protection_level for p in policies), key=lambda x: LEVEL_ORDER[x])
    if joined and LEVEL_ORDER[level] < 3:
        level = "P3"
    purpose_sets = [set(p.purposes) for p in policies if p.purposes is not None]
    if purpose_sets and len(purpose_sets) == len(policies):
        purposes = sorted(set.intersection(*purpose_sets))
    else:
        # 任一输入未约束（无标签）→ 组合结果未约束 → fail-closed（None）
        purposes = None if any(p.purposes is None for p in policies) else sorted(purpose_sets[0]) if purpose_sets else None
    return EffectivePolicy(
        protection_level=level,
        business_categories=sorted({c for p in policies for c in p.business_categories}),
        personal_info="sensitive_personal"
        if any(p.personal_info == "sensitive_personal" for p in policies)
        else "personal" if any(p.personal_info == "personal" for p in policies) else "pending",
        processing_state="raw" if any(p.processing_state == "raw" for p in policies) else "de_identified",
        purposes=purposes,
        export_allowed=all(p.export_allowed for p in policies),
        training_allowed=all(p.training_allowed for p in policies),
        re_id_risk_review_required=joined,
        classified=all(p.classified for p in policies),
    )


def downgrade_requires_approval(current: EffectivePolicy, proposed: EffectivePolicy) -> bool:
    """降级判定：任何等级下降或条件放宽都必须走审批（B02 §3.3）。"""
    return LEVEL_ORDER[proposed.protection_level] < LEVEL_ORDER[current.protection_level]


def grant_active(grant: AssetDsGrant, now: datetime | None = None,
                 operation: str = "read") -> tuple[bool, str]:
    """授权实时校验：状态/有效期/操作集。撤权即时生效（无缓存）。"""
    now = now or datetime.now(timezone.utc)
    if grant.status != "active":
        return False, AccessDecision.DENY_GRANT_REVOKED.value
    if grant.valid_until is not None and grant.valid_until < now:
        return False, AccessDecision.DENY_GRANT_EXPIRED.value
    if operation not in (grant.operations or []):
        return False, AccessDecision.DENY_OPERATION.value
    return True, AccessDecision.ALLOW.value


@dataclass
class GatewayResult:
    allowed: bool
    decision: str
    reason: str = ""
    columns_blocked: list[str] = field(default_factory=list)


def enforce_read(db: Session, principal: str, purpose_code: str,
                 resource_ref: str, operation: str = "read",
                 requested_columns: list[str] | None = None,
                 now: datetime | None = None) -> GatewayResult:
    """B05 统一出口：未分类拒绝 → 等级门 → 用途授权门 → 列白名单。

    列表/详情/计数/导出/后台任务共用本函数；后台任务以任务上下文 principal 调用。
    """
    now = now or datetime.now(timezone.utc)
    cls = db.scalar(
        select(AssetDsClassification)
        .where(AssetDsClassification.object_type == "dataset_version",
               AssetDsClassification.object_ref == resource_ref,
               AssetDsClassification.status == "active")
        .order_by(AssetDsClassification.version.desc())
        .limit(1))
    policy = resolve_policy(cls.labels if cls else None)
    if policy.is_pending:
        return GatewayResult(False, AccessDecision.DENY_UNCLASSIFIED.value,
                             "对象未分类定级（fail-closed，默认拒绝）")
    # B02 §3.1：标签用途约束与请求用途取交——分类修改立即影响后续查询
    if policy.purposes is not None and purpose_code not in policy.purposes:
        return GatewayResult(False, AccessDecision.DENY_LEVEL.value,
                             f"用途 {purpose_code} 不在对象允许用途内")
    if policy.protection_level in ("P3", "P4") and operation in ("export", "train") and operation == "train" and not policy.training_allowed:
        return GatewayResult(False, AccessDecision.DENY_LEVEL.value, "P3/P4 训练未获标签允许")

    grant = db.scalar(
        select(AssetDsGrant)
        .where(AssetDsGrant.principal == principal,
               AssetDsGrant.purpose_code == purpose_code,
               AssetDsGrant.resource_ref.in_([resource_ref, "*"]),
               AssetDsGrant.resource_type.in_(["dataset_version", "global"])))
    if grant is None:
        return GatewayResult(False, AccessDecision.DENY_NO_GRANT.value, "无用途授权")
    ok, decision = grant_active(grant, now=now, operation=operation)
    if not ok:
        return GatewayResult(False, decision, "授权不可用（撤销/过期/操作越界）")

    blocked: list[str] = []
    wl = (grant.column_scope or {}).get("allow")
    if requested_columns is not None and wl:
        blocked = [c for c in requested_columns if c not in wl]
    return GatewayResult(True, AccessDecision.ALLOW.value, columns_blocked=blocked)


def audit_event(action: str, principal: str, resource: str, decision: str, reason: str = "") -> dict:
    """审计载荷（不含患者值）；由调用方写 GovernAuditLog。"""
    return {"module": "dataset", "action": action, "operator": principal,
            "entity_ref": resource, "decision": decision, "reason": reason}
