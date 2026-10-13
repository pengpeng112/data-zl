"""193 B04/B05 + 210 S3：数据集分类分级策略、传播引擎与统一授权网关。

核心不变量（B02 契约 + 210 §4 修订）：
- 未分类默认 P4 fail-closed（读/导出默认拒绝，返回 classification_pending）。
- 组合继承：等级取 max，使用条件取交；JOIN/纵向组合结果至少 P3。
- 假名化/掩码不降级；等级下降或任何使用条件放宽（用途/项目扩张、期限延长、
  导出/训练放开）都必须走审批（210 F04）。
- 标签版本冲突失败关闭；无效枚举/类型/结构一律 PolicyValidationError（API 层 422），
  绝不放行也不 500（210 F03）。
- 授权实时校验：valid_from ≤ now < valid_until、状态、操作集；具体授权存在时
  不回退全局授权（撤销墓碑优先）；多授权按确定性优先级解析（210 F06）。
- 行列范围：grant.column_scope.blocked 从投影中剔除且不得被 allow 覆盖；
  row_scope 空不解释为全库，P3/P4 读取要求显式行范围或显式审批全范围。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.dataset import AssetDsClassification, AssetDsGrant

LEVEL_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

# ---- B02 §1 枚举（210 S3 严格化：非法值即拒绝，不静默取默认）----
VALID_OBJECT_TYPES = {"column", "table", "view", "dataset_version", "export"}
VALID_BUSINESS_CATEGORIES = {
    "identity", "visit", "diagnosis", "lab", "exam", "surgery_anesthesia",
    "medication", "nursing", "document", "charge", "followup", "management",
}
VALID_DATA_FORMS = {
    "structured", "free_text", "image", "audio_video", "time_series",
    "derived", "vector", "model_artifact",
}
VALID_PERSONAL_INFO = {"none", "personal", "sensitive_personal", "pending"}
VALID_PI_MARKERS = {"identity_marker", "medical", "minor"}
VALID_LEVELS = {"P1", "P2", "P3", "P4"}
VALID_LEGAL_STATUS = {
    "unidentified", "important_candidate", "core_candidate", "assessed_general",
}
VALID_PROCESSING_STATE = {
    "raw", "de_identified", "masked_display", "anonymization_pending", "anonymization_assessed",
}
VALID_LABEL_KEYS = {
    "business_categories", "data_form", "personal_info", "pi_markers",
    "protection_level", "legal_status", "legal_basis_ref", "processing_state",
    "usage_constraints",
}
VALID_OPERATIONS = {"read", "export", "train", "derive"}
VALID_GRANT_STATUSES = {"pending", "active", "rejected", "revoked", "expired"}

# 受限数据形态：无专项脱敏审批前禁止导出（210 §4.3）
EXPORT_RESTRICTED_DATA_FORMS = {"free_text", "image", "audio_video"}


class PolicyValidationError(ValueError):
    """标签/授权结构非法。API 层转 422，策略层转 deny，绝不放行。"""


def _require_str_list(value, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise PolicyValidationError(f"{field_name} 必须为字符串数组")
    return value


def validate_labels(labels: dict | None) -> dict:
    """严格标签校验（210 F03/T04）：未知键、非法枚举、错误类型一律抛错。"""
    if labels is None:
        return {}
    if not isinstance(labels, dict):
        raise PolicyValidationError("labels 必须为对象")
    unknown = set(labels) - VALID_LABEL_KEYS
    if unknown:
        raise PolicyValidationError(f"labels 含未知键: {sorted(unknown)}")

    if "business_categories" in labels:
        cats = _require_str_list(labels["business_categories"], "business_categories")
        bad = set(cats) - VALID_BUSINESS_CATEGORIES
        if bad:
            raise PolicyValidationError(f"business_categories 非法值: {sorted(bad)}")
    if "data_form" in labels:
        if labels["data_form"] not in VALID_DATA_FORMS:
            raise PolicyValidationError(f"data_form 非法值: {labels['data_form']!r}")
    if "personal_info" in labels and labels["personal_info"] not in VALID_PERSONAL_INFO:
        raise PolicyValidationError(f"personal_info 非法值: {labels['personal_info']!r}")
    if "pi_markers" in labels:
        markers = _require_str_list(labels["pi_markers"], "pi_markers")
        bad = set(markers) - VALID_PI_MARKERS
        if bad:
            raise PolicyValidationError(f"pi_markers 非法值: {sorted(bad)}")
    if "protection_level" in labels and labels["protection_level"] not in VALID_LEVELS:
        raise PolicyValidationError(f"protection_level 非法值: {labels['protection_level']!r}")
    if "legal_status" in labels and labels["legal_status"] not in VALID_LEGAL_STATUS:
        raise PolicyValidationError(f"legal_status 非法值: {labels['legal_status']!r}")
    if "processing_state" in labels and labels["processing_state"] not in VALID_PROCESSING_STATE:
        raise PolicyValidationError(f"processing_state 非法值: {labels['processing_state']!r}")
    if "legal_basis_ref" in labels and not isinstance(labels["legal_basis_ref"], (str, type(None))):
        raise PolicyValidationError("legal_basis_ref 必须为字符串或 null")

    uc = labels.get("usage_constraints")
    if uc is not None:
        if not isinstance(uc, dict):
            raise PolicyValidationError("usage_constraints 必须为对象")
        uc_unknown = set(uc) - {
            "purposes", "projects", "legal_basis_ref", "valid_until",
            "retention_until", "export_allowed", "training_allowed",
        }
        if uc_unknown:
            raise PolicyValidationError(f"usage_constraints 含未知键: {sorted(uc_unknown)}")
        if "purposes" in uc:
            _require_str_list(uc["purposes"], "usage_constraints.purposes")
        if "projects" in uc:
            _require_str_list(uc["projects"], "usage_constraints.projects")
        for key in ("export_allowed", "training_allowed"):
            if key in uc and not isinstance(uc[key], bool):
                raise PolicyValidationError(f"usage_constraints.{key} 必须为布尔值")
        for key in ("valid_until", "retention_until"):
            if key in uc and uc[key] is not None:
                if not isinstance(uc[key], str):
                    raise PolicyValidationError(f"usage_constraints.{key} 必须为 ISO 字符串或 null")
                try:
                    datetime.fromisoformat(uc[key])
                except ValueError as e:
                    raise PolicyValidationError(f"usage_constraints.{key} 非法时间: {uc[key]!r}") from e
    return labels


def canonical_object_ref(object_type: str, physical_key: dict) -> str:
    """结构化物理身份 → 规范对象键（210 §4.1，禁止冒号拼接）。

    physical_key：{source_code, namespace_name?, schema_name, table_name, column_name?}
    """
    if object_type not in VALID_OBJECT_TYPES:
        raise PolicyValidationError(f"object_type 非法值: {object_type!r}")
    if not isinstance(physical_key, dict):
        raise PolicyValidationError("physical_key 必须为对象")
    for required in ("source_code", "schema_name", "table_name"):
        if not isinstance(physical_key.get(required), str) or not physical_key[required]:
            raise PolicyValidationError(f"physical_key.{required} 必填")
    if object_type == "column":
        if not isinstance(physical_key.get("column_name"), str) or not physical_key["column_name"]:
            raise PolicyValidationError("column 对象 physical_key.column_name 必填")
    return json.dumps({"t": object_type, "k": physical_key},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class AccessDecision(str, Enum):
    ALLOW = "allow"
    DENY_UNCLASSIFIED = "deny_unclassified"
    DENY_INVALID_POLICY = "deny_invalid_policy"
    DENY_LEVEL = "deny_level"
    DENY_PURPOSE = "deny_purpose"
    DENY_NO_GRANT = "deny_no_grant"
    DENY_GRANT_PENDING = "deny_grant_pending"
    DENY_GRANT_REVOKED = "deny_grant_revoked"
    DENY_GRANT_EXPIRED = "deny_grant_expired"
    DENY_NOT_YET_VALID = "deny_not_yet_valid"
    DENY_OPERATION = "deny_operation"
    DENY_COLUMN = "deny_column"
    DENY_EXPORT_FORBIDDEN = "deny_export_forbidden"
    DENY_TRAIN_FORBIDDEN = "deny_train_forbidden"
    DENY_P4_PERMISSION = "deny_p4_permission"
    DENY_ROW_SCOPE = "deny_row_scope"


@dataclass
class EffectivePolicy:
    """对象的有效安全策略（继承/组合计算结果）。"""

    protection_level: str = "P4"
    business_categories: list[str] = field(default_factory=list)
    personal_info: str = "pending"
    processing_state: str = "raw"
    purposes: list[str] | None = None      # None=未约束（未分类对象）→ 视为禁止
    projects: list[str] | None = None
    export_allowed: bool = False
    training_allowed: bool = False
    valid_until: str | None = None
    retention_until: str | None = None
    data_form: str | None = None
    re_id_risk_review_required: bool = False
    classified: bool = False               # 是否有任何显式标签

    @property
    def is_pending(self) -> bool:
        return not self.classified or self.personal_info == "pending"


def resolve_policy(labels: dict | None, *, strict: bool = True) -> EffectivePolicy:
    """单个对象的标签 → 有效策略。

    strict=True（默认，API/网关路径）：先 validate_labels，非法即抛
    PolicyValidationError（调用方 422 或 deny）。
    strict=False：仅做宽松读取（历史 16 项纯逻辑测试兼容口径）。
    已分类对象未写 usage_constraints.purposes → purposes=[]（全部禁止，fail-closed）。
    """
    labels = labels or {}
    if strict:
        validate_labels(labels)
    uc = labels.get("usage_constraints") or {}
    has_any = bool(labels)
    purposes = uc.get("purposes")
    projects = uc.get("projects")
    return EffectivePolicy(
        protection_level=labels.get("protection_level", "P4"),
        business_categories=list(labels.get("business_categories") or []),
        personal_info=labels.get("personal_info", "pending"),
        processing_state=labels.get("processing_state", "raw"),
        purposes=list(purposes) if purposes is not None else ([] if has_any else None),
        projects=list(projects) if projects is not None else ([] if has_any else None),
        export_allowed=bool(uc.get("export_allowed", False)),
        training_allowed=bool(uc.get("training_allowed", False)),
        valid_until=uc.get("valid_until"),
        retention_until=uc.get("retention_until"),
        data_form=labels.get("data_form"),
        classified=has_any,
    )


# 个人信息属性保守序：sensitive_personal > personal > pending > none；
# 全部 none 才是 none，混有 pending 视为 pending（210 T08）。
_PI_ORDER = {"sensitive_personal": 3, "personal": 2, "pending": 1, "none": 0}


def combine_policies(policies: list[EffectivePolicy], joined: bool = True) -> EffectivePolicy:
    """组合继承（JOIN/纵向/派生）：等级 max、条件取交、组合触发重评估。

    joined=True 时组合结果至少 P3（识别风险），并置 re_id_risk_review_required。
    假名化（processing_state 变化）不影响等级——调用方不得用本函数做降级。
    用途/项目取交；有效期/保留期限取最早；禁用导出/训练任一输入生效。
    """
    if not policies:
        return EffectivePolicy()
    level = max((p.protection_level for p in policies), key=lambda x: LEVEL_ORDER[x])
    if joined and LEVEL_ORDER[level] < 3:
        level = "P3"
    purpose_sets = [set(p.purposes) for p in policies if p.purposes is not None]
    if purpose_sets and len(purpose_sets) == len(policies):
        purposes: list[str] | None = sorted(set.intersection(*purpose_sets))
    else:
        # 任一输入未约束（无标签）→ 组合结果未约束 → fail-closed（None）
        purposes = None
    project_sets = [set(p.projects) for p in policies if p.projects is not None]
    if project_sets and len(project_sets) == len(policies):
        projects: list[str] | None = sorted(set.intersection(*project_sets))
    else:
        projects = None
    pi = max((p.personal_info for p in policies), key=lambda x: _PI_ORDER[x])
    dates = [p.valid_until for p in policies if p.valid_until]
    retentions = [p.retention_until for p in policies if p.retention_until]
    forms = {p.data_form for p in policies if p.data_form}
    return EffectivePolicy(
        protection_level=level,
        business_categories=sorted({c for p in policies for c in p.business_categories}),
        personal_info=pi,
        # 保守序：任一 raw 即 raw；无 raw 取最保守可用状态（非 raw 输入里取保护最强的）
        processing_state="raw" if any(p.processing_state == "raw" for p in policies)
        else "de_identified",
        purposes=purposes,
        projects=projects,
        export_allowed=all(p.export_allowed for p in policies),
        training_allowed=all(p.training_allowed for p in policies),
        valid_until=min(dates) if dates else None,
        retention_until=min(retentions) if retentions else None,
        data_form=sorted(forms)[0] if len(forms) == 1 else None,
        re_id_risk_review_required=joined,
        classified=all(p.classified for p in policies),
    )


def change_requires_approval(current: EffectivePolicy,
                             proposed: EffectivePolicy) -> tuple[bool, list[str]]:
    """降级/放宽判定（210 F04/T06）：等级下降或任何使用条件放宽都必须走审批。

    返回 (是否需要审批, 原因清单)。用途/项目扩张=放宽；期限延长=放宽；
    导出/训练放开=放宽；保留期限缩短=放宽。
    """
    reasons: list[str] = []
    if LEVEL_ORDER[proposed.protection_level] < LEVEL_ORDER[current.protection_level]:
        reasons.append(
            f"protection_level 下降 {current.protection_level}->{proposed.protection_level}")
    cur_p = set(current.purposes) if current.purposes is not None else None
    new_p = set(proposed.purposes) if proposed.purposes is not None else None
    if cur_p is not None and new_p is not None and (new_p - cur_p):
        reasons.append(f"用途扩张: {sorted(new_p - cur_p)}")
    cur_j = set(current.projects) if current.projects is not None else None
    new_j = set(proposed.projects) if proposed.projects is not None else None
    if cur_j is not None and new_j is not None and (new_j - cur_j):
        reasons.append(f"项目扩张: {sorted(new_j - cur_j)}")
    if not current.export_allowed and proposed.export_allowed:
        reasons.append("放开导出")
    if not current.training_allowed and proposed.training_allowed:
        reasons.append("放开训练")
    if current.valid_until and (proposed.valid_until is None or proposed.valid_until > current.valid_until):
        reasons.append("有效期延长")
    if current.retention_until and (proposed.retention_until is None
                                    or proposed.retention_until < current.retention_until):
        reasons.append("保留期限缩短")
    return (bool(reasons), reasons)


def downgrade_requires_approval(current: EffectivePolicy, proposed: EffectivePolicy) -> bool:
    """兼容旧名：仅等级下降判定。新代码用 change_requires_approval。"""
    return LEVEL_ORDER[proposed.protection_level] < LEVEL_ORDER[current.protection_level]


def grant_active(grant: AssetDsGrant, now: datetime | None = None,
                 operation: str = "read") -> tuple[bool, str]:
    """授权实时校验：状态/时间窗（含 valid_from）/操作集。撤权即时生效（无缓存）。"""
    now = now or datetime.now(timezone.utc)
    if grant.status == "pending":
        return False, AccessDecision.DENY_GRANT_PENDING.value
    if grant.status in ("rejected", "revoked"):
        return False, AccessDecision.DENY_GRANT_REVOKED.value
    if grant.status == "expired":
        return False, AccessDecision.DENY_GRANT_EXPIRED.value
    if grant.valid_from is not None and grant.valid_from > now:
        return False, AccessDecision.DENY_NOT_YET_VALID.value
    if grant.valid_until is not None and grant.valid_until <= now:
        return False, AccessDecision.DENY_GRANT_EXPIRED.value
    if operation not in (grant.operations or []):
        return False, AccessDecision.DENY_OPERATION.value
    return True, AccessDecision.ALLOW.value


def resolve_grant(db: Session, principal: str, purpose_code: str,
                  resource_ref: str, operation: str = "read",
                  now: datetime | None = None) -> tuple[AssetDsGrant | None, str, str]:
    """确定性授权解析（210 F06/T12/T13）。

    优先级：具体授权（resource_ref 精确匹配）> 全局授权（'*'）。
    具体范围存在任何状态的行时，解析封闭在该档内——已撤销的具体授权是墓碑，
    不得回退到全局宽授权；同档多条 active 按 (valid_from 最新, id 最大) 确定。
    返回 (grant|None, decision, reason)。
    """
    now = now or datetime.now(timezone.utc)
    # 单查询取具体+全局两档，内存按确定性优先级分档（避免无序多查询碰运气）
    rows = db.scalars(
        select(AssetDsGrant)
        .where(AssetDsGrant.principal == principal,
               AssetDsGrant.purpose_code == purpose_code,
               AssetDsGrant.resource_ref.in_([resource_ref, "*"]),
               AssetDsGrant.resource_type.in_(["dataset_version", "global"]))
        .order_by(AssetDsGrant.valid_from.desc(), AssetDsGrant.id.desc())).all()
    exact = [g for g in rows if g.resource_ref == resource_ref]
    if exact:
        tier_rows, tier = exact, "exact"
    else:
        tier_rows = [g for g in rows if g.resource_ref == "*"]
        tier = "global" if tier_rows else None
    if not tier_rows:
        return None, AccessDecision.DENY_NO_GRANT.value, "无用途授权"
    # 1) 同档内可用授权优先（后授的有效授权可覆盖更早的撤销）
    for g in tier_rows:
        ok, decision = grant_active(g, now=now, operation=operation)
        if ok:
            return g, AccessDecision.ALLOW.value, f"{tier} 档授权 #{g.id}"
    # 2) 无可用行：撤销墓碑优先（具体档已撤销 → 拒绝且不回退更宽授权）
    for g in tier_rows:
        if g.status in ("revoked", "rejected"):
            return None, AccessDecision.DENY_GRANT_REVOKED.value, \
                f"授权已撤销（{tier} 档，不回退更宽授权）"
    # 3) 其余不可用原因（待审批/未生效/过期/操作越界）按确定性顺序报告首个
    for g in tier_rows:
        ok, decision = grant_active(g, now=now, operation=operation)
        if decision != AccessDecision.DENY_OPERATION.value:
            return None, decision, f"授权不可用（{tier} 档 #{g.id}）"
    return None, AccessDecision.DENY_OPERATION.value, "授权不含该操作"


@dataclass
class GatewayResult:
    allowed: bool
    decision: str
    reason: str = ""
    columns_blocked: list[str] = field(default_factory=list)
    allowed_columns: list[str] | None = None   # None=无列约束；list=许可投影
    row_scope: dict = field(default_factory=dict)
    grant_id: int | None = None
    policy: EffectivePolicy | None = None
    resource_refs: list[str] = field(default_factory=list)


def active_classifications(db: Session, object_refs: list[str]) -> list[AssetDsClassification]:
    """取一组对象键的 active 分类行（多对象组合，210 F01 桥接）。"""
    if not object_refs:
        return []
    return db.scalars(
        select(AssetDsClassification)
        .where(AssetDsClassification.object_type.in_(("column", "table", "view",
                                                      "dataset_version", "export")),
               AssetDsClassification.object_ref.in_(object_refs),
               AssetDsClassification.status == "active")
        .order_by(AssetDsClassification.version.desc())).all()


def combine_object_policies(db: Session, object_refs: list[str]) -> EffectivePolicy:
    """多对象（版本+其成员表/列）标签组合为有效策略；无任何 active 标签→未分类。"""
    rows = active_classifications(db, object_refs)
    if not rows:
        return EffectivePolicy()  # 未分类默认 P4 pending
    return combine_policies([resolve_policy(r.labels) for r in rows], joined=True)


def enforce_read(db: Session, principal: str, purpose_code: str,
                 resource_ref: str | list[str], operation: str = "read",
                 requested_columns: list[str] | None = None,
                 now: datetime | None = None,
                 p4_authorized: bool = False) -> GatewayResult:
    """统一出口网关：未分类/非法标签拒绝 → 等级/用途门 → 授权门（确定性解析）
    → 行范围门 → 列投影门。

    resource_ref 支持单键或多键（多键=版本+成员对象组合有效策略，210 F01/T19）。
    列表/详情/计数/导出/后台任务共用本函数。
    """
    now = now or datetime.now(timezone.utc)
    refs = [resource_ref] if isinstance(resource_ref, str) else list(resource_ref or [])
    refs = [r for r in refs if r]
    result = GatewayResult(allowed=False, decision=AccessDecision.DENY_UNCLASSIFIED.value,
                           resource_refs=refs)
    if not refs:
        return result

    rows = active_classifications(db, refs)
    if not rows:
        result.decision = AccessDecision.DENY_UNCLASSIFIED.value
        result.reason = "对象未分类定级（fail-closed，默认拒绝）"
        return result
    try:
        policies = [resolve_policy(r.labels, strict=True) for r in rows]
    except PolicyValidationError as e:
        result.decision = AccessDecision.DENY_INVALID_POLICY.value
        result.reason = f"标签结构非法（fail-closed）: {e}"
        return result
    policy = combine_policies(policies, joined=len(policies) > 1)
    result.policy = policy
    if policy.is_pending:
        result.decision = AccessDecision.DENY_UNCLASSIFIED.value
        result.reason = "对象未分类定级（fail-closed，默认拒绝）"
        return result

    # 用途/项目约束：标签允许的用途/项目与请求取交（分类修改立即影响后续查询）
    if policy.purposes is not None and purpose_code not in policy.purposes:
        result.decision = AccessDecision.DENY_PURPOSE.value
        result.reason = f"用途 {purpose_code} 不在对象允许用途内"
        return result

    # P4 独立权限（210 §4.2）：独立等级列之上的访问许可
    if policy.protection_level == "P4" and not p4_authorized:
        result.decision = AccessDecision.DENY_P4_PERMISSION.value
        result.reason = "P4 资源需要独立访问权限（ds.p4.access）"
        return result

    # 导出/训练标志对任意等级生效（210 F06/T16）
    if operation == "export" and not policy.export_allowed:
        result.decision = AccessDecision.DENY_EXPORT_FORBIDDEN.value
        result.reason = "对象标签禁止导出"
        return result
    if operation == "train" and not policy.training_allowed:
        result.decision = AccessDecision.DENY_TRAIN_FORBIDDEN.value
        result.reason = "对象标签禁止训练"
        return result

    primary_ref = refs[0]
    grant, decision, reason = resolve_grant(db, principal, purpose_code,
                                            primary_ref, operation=operation, now=now)
    if grant is None:
        result.decision = decision
        result.reason = reason
        return result
    result.grant_id = grant.id
    result.row_scope = dict(grant.row_scope or {})

    # 行范围门：P3/P4 受保护读取要求显式行范围或显式审批全范围（空≠全库）
    if policy.protection_level in ("P3", "P4") and operation in ("read", "export", "train", "derive"):
        explicit_all = result.row_scope.get("all") is True
        has_scope = explicit_all or any(
            k in result.row_scope for k in ("patients", "cohorts", "queue"))
        if not has_scope:
            result.decision = AccessDecision.DENY_ROW_SCOPE.value
            result.reason = "P3/P4 访问需显式行范围（patients/cohorts/queue）或经审批的 all 全范围"
            return result

    # 列投影门：allow 白名单 ∩ 请求列；blocked 永远剔除且不可被 allow 覆盖
    scope = dict(grant.column_scope or {})
    allow = scope.get("allow")
    blocked_set = set(scope.get("blocked") or [])
    if allow is not None and not isinstance(allow, list):
        result.decision = AccessDecision.DENY_COLUMN.value
        result.reason = "column_scope.allow 结构非法（必须为数组）"
        return result
    allowed_cols = [c for c in allow if c not in blocked_set] if allow is not None else None
    result.allowed_columns = allowed_cols
    if requested_columns is not None:
        allowed_set = set(allowed_cols) if allowed_cols is not None else None
        blocked = [c for c in requested_columns
                   if c in blocked_set or (allowed_set is not None and c not in allowed_set)]
        if blocked:
            result.decision = AccessDecision.DENY_COLUMN.value
            result.reason = f"请求列越出许可投影: {blocked}"
            result.columns_blocked = blocked
            return result
        result.columns_blocked = []

    result.allowed = True
    result.decision = AccessDecision.ALLOW.value
    result.reason = reason
    return result


def audit_event(action: str, principal: str, resource: str, decision: str, reason: str = "") -> dict:
    """审计载荷（不含患者值）；由调用方写 GovernAuditLog。"""
    return {"module": "dataset", "action": action, "operator": principal,
            "entity_ref": resource, "decision": decision, "reason": reason}
