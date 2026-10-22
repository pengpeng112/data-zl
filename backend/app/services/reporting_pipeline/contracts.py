"""契约层：TaskSpec / BatchManifest / 分层就绪校验 / 批次与反馈状态机。

对应《Python与DataX统一T加1顶层设计及长任务执行计划.md》§3、§5：
- TaskSpec 承载77项配置模型，关联 failure_policy、performance_profile、LIS
  双源 route、DATETIME 依赖、monthly_rescan、长期凭据、写者交接与 deadline。
- 就绪校验按动作分层（CONFIG_VALID / READ_READY / STAGE_READY / APPLY_READY /
  REPORT_READY），未知输入只能产出 UNKNOWN，不能变 READY；层内矛盾产出
  NOT_READY 并给原因。
- BatchManifest 行分类互斥且守恒；分页未完整不得推进 CAPTURED。
- 批次主链、反馈链与附加状态的允许转换显式列表；非法转换抛
  ContractViolation，不静默纠正。
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

PACKAGE_ID = "R189-T1-ENGINEERING-20261019-v1.2"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OBJECT_ID_RE = re.compile(r"^[a-z0-9_]+__[A-Za-z0-9_$]+$")


class ContractViolation(ValueError):
    """契约校验失败。message 汇总全部原因，调用方据此生成工单/拒绝原因。"""


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class Engine(str, enum.Enum):
    PYTHON = "PYTHON"
    DATAX = "DATAX"
    UNDECIDED = "UNDECIDED"


class IncrementalStrategy(str, enum.Enum):
    CHANGE_WATERMARK = "CHANGE_WATERMARK"
    CHANGED_KEYS = "CHANGED_KEYS"
    SNAPSHOT_DIFF = "SNAPSHOT_DIFF"
    CDC_KEYS = "CDC_KEYS"
    UNRESOLVED = "UNRESOLVED"


class Applicability(str, enum.Enum):
    APPLICABLE = "APPLICABLE"
    TO_VERIFY = "TO_VERIFY"
    WAITING_BUSINESS_CONFIRMATION = "WAITING_BUSINESS_CONFIRMATION"


class DeadlineState(str, enum.Enum):
    CONFIGURED = "CONFIGURED"
    UNCONFIGURED = "UNCONFIGURED"


class ReadinessLayer(str, enum.Enum):
    CONFIG_VALID = "CONFIG_VALID"
    READ_READY = "READ_READY"
    STAGE_READY = "STAGE_READY"
    APPLY_READY = "APPLY_READY"
    REPORT_READY = "REPORT_READY"


class PipelineAction(str, enum.Enum):
    """具体执行动作（R05 动作级就绪：只核该动作实际需要的层）。

    全链启用（enabled=True）仍走 validate_enable() 的五层 READY 门禁；
    动作级校验解决的是"省端回执未知（REPORT_READY=UNKNOWN）不应连带
    阻塞院内读取/暂存"——读取只核 CONFIG+READ，逐动作递进。
    """

    CAPTURE = "CAPTURE"      # 源读取：CONFIG_VALID + READ_READY
    STAGE = "STAGE"          # 受控暂存：+ STAGE_READY
    APPLY = "APPLY"          # 正式装载：+ APPLY_READY（真实批准另核）
    REPORT = "REPORT"        # 省端报送：+ REPORT_READY（= 全链）

    def required_layers(self) -> tuple[ReadinessLayer, ...]:
        if self is PipelineAction.CAPTURE:
            return (ReadinessLayer.CONFIG_VALID, ReadinessLayer.READ_READY)
        if self is PipelineAction.STAGE:
            return (
                ReadinessLayer.CONFIG_VALID, ReadinessLayer.READ_READY,
                ReadinessLayer.STAGE_READY,
            )
        if self is PipelineAction.APPLY:
            return (
                ReadinessLayer.CONFIG_VALID, ReadinessLayer.READ_READY,
                ReadinessLayer.STAGE_READY, ReadinessLayer.APPLY_READY,
            )
        return tuple(ReadinessLayer)  # REPORT = 全链


class LayerStatus(str, enum.Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class BatchState(str, enum.Enum):
    # 主链：PLANNED → ... → RECONCILED
    PLANNED = "PLANNED"
    CAPTURING = "CAPTURING"
    CAPTURED = "CAPTURED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    APPLY_PENDING = "APPLY_PENDING"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    RECONCILED = "RECONCILED"
    # 附加状态（可与失败/等待语义共存，由状态机管转换）
    WAITING_SOURCE = "WAITING_SOURCE"
    WAITING_VIEW_FIX = "WAITING_VIEW_FIX"
    WAITING_INPUT = "WAITING_INPUT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RETRYABLE = "RETRYABLE"
    QUARANTINED = "QUARANTINED"
    COMMIT_UNKNOWN = "COMMIT_UNKNOWN"
    BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    CANCELLED = "CANCELLED"


class FeedbackState(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    WAITING = "WAITING"


class EndReason(str, enum.Enum):
    WINDOW_COMPLETE = "WINDOW_COMPLETE"
    ROW_CAP = "ROW_CAP"
    BYTE_CAP = "BYTE_CAP"
    CANCELLED = "CANCELLED"
    SOURCE_ERROR = "SOURCE_ERROR"
    SPLIT_REQUIRED = "SPLIT_REQUIRED"


# ---------------------------------------------------------------------------
# 身份/投影/键/时间/变更/装载/资源
# ---------------------------------------------------------------------------


@dataclass
class SourceRef:
    """源对象候选。current_identity_verified=False 时一切生产读校验为 UNKNOWN。"""

    object_id: str
    role: str  # primary / history / comparison（ODS对照单列，不参与路由）
    source_group: str
    host: str
    port: int
    object_name_candidates: list[str]
    owner_hint: str | None = None
    database_hint: str | None = None
    current_identity_verified: bool = False

    def validate(self) -> None:
        problems: list[str] = []
        if not self.object_id or not _OBJECT_ID_RE.match(self.object_id):
            problems.append(f"object_id 非法: {self.object_id!r}")
        if self.role not in ("primary", "history", "comparison"):
            problems.append(f"role 非法: {self.role!r}")
        if not self.source_group:
            problems.append("source_group 为空")
        if not self.host or not isinstance(self.port, int) or not (0 < self.port < 65536):
            problems.append(f"host/port 非法: {self.host!r}/{self.port!r}")
        if not self.object_name_candidates:
            problems.append("object_name_candidates 为空")
        if problems:
            raise ContractViolation(f"SourceRef[{self.object_id}]: " + "; ".join(problems))


@dataclass
class TargetRef:
    host: str
    port: int
    service: str
    owner: str
    table: str
    current_identity_verified: bool = False

    def validate(self) -> None:
        problems: list[str] = []
        if not self.host or not (0 < int(self.port) < 65536):
            problems.append("host/port 非法")
        if not self.owner or not self.table:
            problems.append("owner/table 为空")
        if problems:
            raise ContractViolation(f"TargetRef[{self.owner}.{self.table}]: " + "; ".join(problems))


@dataclass
class StableKey:
    candidate: list[str]
    verified: bool = False

    def validate(self) -> None:
        if not self.candidate:
            raise ContractViolation("stable_key.candidate 为空")


@dataclass
class ProjectionField:
    name: str
    target_type: str
    order: int
    source_expression: str | None = None
    type_verified: bool = False

    def validate(self) -> None:
        if not self.name or not self.target_type:
            raise ContractViolation(f"投影字段不完整: {self.name!r}/{self.target_type!r}")


@dataclass
class TimeSemantics:
    """业务时间语义与变更捕获时间分开（§4）。"""

    business_time_expression: str | None = None
    business_time_verified: bool = False
    change_time_expression: str | None = None
    change_time_verified: bool = False
    visibility_cutoff_rule: str | None = None
    overlap_seconds: int | None = None
    timezone: str | None = None
    same_second_cursor_rule: str | None = None

    def validate(self) -> None:
        if self.overlap_seconds is not None and self.overlap_seconds < 0:
            raise ContractViolation("overlap_seconds 不能为负")


@dataclass
class ChangePolicy:
    strategy: IncrementalStrategy = IncrementalStrategy.UNRESOLVED
    insert_evidence: str | None = None
    update_evidence: str | None = None
    retract_evidence: str | None = None
    child_only_change_trigger: list[str] = field(default_factory=list)
    source_version_order: str | None = None
    version_order_verified: bool = False


@dataclass
class ApplyPolicy:
    executor_ref: str | None = None
    allowed_operations: list[str] = field(default_factory=list)
    idempotency_key: list[str] = field(default_factory=list)
    txn_row_budget: int | None = None
    txn_byte_budget: int | None = None
    commit_receipt_mode: str | None = None  # SAME_TARGET_TXN / EXTERNAL_RECEIPT / NONE
    approval_refs: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.txn_row_budget is not None and self.txn_row_budget <= 0:
            raise ContractViolation("txn_row_budget 必须为正")
        if self.txn_byte_budget is not None and self.txn_byte_budget <= 0:
            raise ContractViolation("txn_byte_budget 必须为正")


@dataclass
class ResourceBudget:
    per_source_concurrency: int | None = None
    max_rows_per_slice: int | None = None
    max_bytes_per_slice: int | None = None
    query_timeout_seconds: int | None = None
    cancel_supported: bool = False
    max_attempts: int | None = None
    max_elapsed_seconds: int | None = None

    def validate(self) -> None:
        for name in ("per_source_concurrency", "max_rows_per_slice", "max_bytes_per_slice",
                     "query_timeout_seconds", "max_attempts", "max_elapsed_seconds"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ContractViolation(f"{name} 必须为正")


@dataclass
class TaskAssociations:
    """v1.2 关联：失败策略/画像/路由/重扫/凭据/写者交接/deadline/人工工单。"""

    failure_policy_ref: str = "故障隔离与继续执行规则.json"
    alert_policy_ref: str = "告警触发与升级规则.json"
    performance_profile_id: str | None = None
    route_policy_ref: str | None = None
    monthly_rescan_policy_ref: str | None = None
    datetime_dependency_ticket: str | None = None
    long_lived_credential_ref: str | None = None
    running_writer_handoff_state: str = "NOT_LIVE_VERIFIED"
    deadline_state: DeadlineState = DeadlineState.UNCONFIGURED
    deadline: str | None = None
    human_view_ticket_state: str = "TO_REVIEW"


# ---------------------------------------------------------------------------
# TaskSpec 与分层就绪
# ---------------------------------------------------------------------------


@dataclass
class TaskSpec:
    canonical_table: str
    business_name: str
    index: int
    enabled: bool
    applicability: Applicability
    engine: Engine
    incremental_strategy: IncrementalStrategy
    source_candidates: list[SourceRef]
    target: TargetRef
    stable_key: StableKey
    associations: TaskAssociations
    projection: list[ProjectionField] = field(default_factory=list)
    time_semantics: TimeSemantics = field(default_factory=TimeSemantics)
    change_policy: ChangePolicy = field(default_factory=ChangePolicy)
    apply_policy: ApplyPolicy = field(default_factory=ApplyPolicy)
    resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    definition_fingerprint: str | None = None
    dependency_fingerprints: dict[str, str] = field(default_factory=dict)
    declared_parent_candidates: list[str] = field(default_factory=list)
    config_version: str = "v0-seed"
    note: str | None = None

    # -- 结构校验（CONFIG_VALID 层） -----------------------------------

    def validate_structure(self) -> None:
        problems: list[str] = []
        if not self.canonical_table or not re.match(r"^[A-Z0-9_]+$", self.canonical_table):
            problems.append(f"canonical_table 非法: {self.canonical_table!r}")
        if self.engine not in tuple(Engine):
            problems.append(f"engine 非法: {self.engine!r}")
        if self.applicability not in tuple(Applicability):
            problems.append(f"applicability 非法: {self.applicability!r}")
        if self.incremental_strategy not in tuple(IncrementalStrategy):
            problems.append(f"incremental_strategy 非法: {self.incremental_strategy!r}")
        if self.associations.deadline_state not in tuple(DeadlineState):
            problems.append("deadline_state 非法")
        if self.associations.deadline_state == DeadlineState.CONFIGURED and not self.associations.deadline:
            problems.append("deadline_state=CONFIGURED 但 deadline 为空")
        routing_sources = [s for s in self.source_candidates if s.role in ("primary", "history")]
        if not self.source_candidates and self.applicability != Applicability.WAITING_BUSINESS_CONFIRMATION:
            problems.append("无源候选且非适用性待确认项")
        roles = [s.role for s in self.source_candidates]
        if roles.count("primary") > 1:
            problems.append("primary 源多于一个（双源应使用 route_policy 分段）")
        object_ids = [s.object_id for s in self.source_candidates]
        if len(object_ids) != len(set(object_ids)):
            problems.append("source_candidates object_id 重复")
        if self.associations.route_policy_ref and len(routing_sources) < 2:
            problems.append("声明 route_policy_ref 但路由源候选不足两个")
        if not self.associations.route_policy_ref and len(routing_sources) > 1:
            problems.append("多路由源但无 route_policy_ref（禁止隐式双源合并；ODS对照源不参与路由）")
        for src in self.source_candidates:
            try:
                src.validate()
            except ContractViolation as exc:
                problems.append(str(exc))
        try:
            self.target.validate()
        except ContractViolation as exc:
            problems.append(str(exc))
        try:
            self.stable_key.validate()
        except ContractViolation as exc:
            problems.append(str(exc))
        for proj in self.projection:
            try:
                proj.validate()
            except ContractViolation as exc:
                problems.append(str(exc))
        if self.projection:
            orders = sorted(p.order for p in self.projection)
            if orders != list(range(1, len(orders) + 1)):
                problems.append("投影 order 必须为 1..n 连续")
        if self.definition_fingerprint and not _SHA256_RE.match(self.definition_fingerprint):
            problems.append("definition_fingerprint 非 sha256")
        for dep_name, fp in self.dependency_fingerprints.items():
            if not dep_name:
                problems.append("依赖指纹名为空")
            if not _SHA256_RE.match(fp):
                problems.append(f"依赖 {dep_name} 指纹非 sha256")
        try:
            self.apply_policy.validate()
            self.resource_budget.validate()
            self.time_semantics.validate()
        except ContractViolation as exc:
            problems.append(str(exc))
        if problems:
            raise ContractViolation(f"TaskSpec[{self.canonical_table}]: " + "; ".join(problems))

    # -- 分层就绪（§3.1：UNKNOWN 只能阻塞相应层，不能变 READY） --------

    def layer_verdicts(self) -> dict[ReadinessLayer, "LayerVerdict"]:
        verdicts: dict[ReadinessLayer, LayerVerdict] = {}
        try:
            self.validate_structure()
            verdicts[ReadinessLayer.CONFIG_VALID] = LayerVerdict(
                ReadinessLayer.CONFIG_VALID, LayerStatus.READY, []
            )
        except ContractViolation as exc:
            verdicts[ReadinessLayer.CONFIG_VALID] = LayerVerdict(
                ReadinessLayer.CONFIG_VALID, LayerStatus.NOT_READY, [str(exc)]
            )
            # 结构不合法时后续层全部 NOT_READY，不再重复罗列同一原因。
            for layer in (ReadinessLayer.READ_READY, ReadinessLayer.STAGE_READY,
                          ReadinessLayer.APPLY_READY, ReadinessLayer.REPORT_READY):
                verdicts[layer] = LayerVerdict(layer, LayerStatus.NOT_READY, ["CONFIG_VALID 未通过"])
            return verdicts

        for layer in (ReadinessLayer.READ_READY, ReadinessLayer.STAGE_READY,
                      ReadinessLayer.APPLY_READY, ReadinessLayer.REPORT_READY):
            checks = _production_layer_checks(layer, self)
            reasons_unknown = [c.reason for c in checks if c.status == LayerStatus.UNKNOWN]
            reasons_blocked = [c.reason for c in checks if c.status == LayerStatus.NOT_READY]
            if reasons_blocked:
                status = LayerStatus.NOT_READY
            elif reasons_unknown:
                status = LayerStatus.UNKNOWN
            else:
                status = LayerStatus.READY
            verdicts[layer] = LayerVerdict(layer, status, reasons_blocked + reasons_unknown)
        return verdicts

    def validate_enable(self) -> None:
        """启用（enabled=True）前置门禁：任何层 UNKNOWN/NOT_READY 都拒绝。

        这保证“未知不能变 READY”：种子未核身份/投影/变更依据前无法启用。
        """
        problems: list[str] = []
        if self.applicability == Applicability.WAITING_BUSINESS_CONFIRMATION:
            problems.append("适用性待业务确认，禁止启用")
        for layer, verdict in self.layer_verdicts().items():
            if verdict.status != LayerStatus.READY:
                problems.append(f"{layer.value}={verdict.status.value}: {verdict.reasons[:3]}")
        if problems:
            raise ContractViolation(
                f"TaskSpec[{self.canonical_table}] 禁止启用: " + "; ".join(problems)
            )

    def validate_action(self, action: "PipelineAction") -> None:
        """动作级就绪（R05）：只核该动作所需层；UNKNOWN 层阻塞但不出 READY。

        与 validate_enable 的区别：全链启用仍要求五层 READY；本方法允许在
        REPORT_READY=UNKNOWN（省端回执未知）时执行院内读取/暂存/装载动作，
        但每个动作仍须其所需层全部 READY。LIS 历史段路由未知只阻塞依赖该
        路由的动作（调用方按 route 解析结果决定），本方法不放宽任何层。
        """
        verdicts = self.layer_verdicts()
        problems: list[str] = []
        for layer in action.required_layers():
            verdict = verdicts[layer]
            if verdict.status != LayerStatus.READY:
                problems.append(
                    f"{layer.value}={verdict.status.value}: {verdict.reasons[:3]}"
                )
        if problems:
            raise ContractViolation(
                f"TaskSpec[{self.canonical_table}] 动作 {action.value} 未就绪: "
                + "; ".join(problems)
            )

    def action_readiness(self) -> dict[str, str]:
        """四类动作的就绪概览（list/CLI 用；不改变 UNKNOWN 语义）。"""
        out: dict[str, str] = {}
        for action in PipelineAction:
            verdicts = self.layer_verdicts()
            worst = LayerStatus.READY
            for layer in action.required_layers():
                status = verdicts[layer].status
                if status == LayerStatus.NOT_READY:
                    worst = LayerStatus.NOT_READY
                    break
                if status == LayerStatus.UNKNOWN:
                    worst = LayerStatus.UNKNOWN
            out[action.value] = worst.value
        return out

    def dual_source(self) -> bool:
        return len([s for s in self.source_candidates if s.role in ("primary", "history")]) > 1


@dataclass
class LayerVerdict:
    layer: ReadinessLayer
    status: LayerStatus
    reasons: list[str]


@dataclass(frozen=True)
class _LayerCheck:
    status: LayerStatus
    reason: str


def _production_layer_checks(layer: ReadinessLayer, spec: TaskSpec) -> list[_LayerCheck]:
    """生产层检查：未核/未配 → UNKNOWN（阻塞该层）；结构性矛盾 → NOT_READY。

    UNKNOWN 是种子的合法常态（身份/画像/凭据等未核），只阻塞相应生产层，
    不阻塞 CONFIG_VALID 与本地开发；NOT_READY 表示配置自相矛盾。
    """
    checks: list[_LayerCheck] = []

    def unknown(reason: str) -> None:
        checks.append(_LayerCheck(LayerStatus.UNKNOWN, reason))

    def conflict(reason: str) -> None:
        checks.append(_LayerCheck(LayerStatus.NOT_READY, reason))

    if layer == ReadinessLayer.READ_READY:
        for src in spec.source_candidates:
            if not src.current_identity_verified:
                unknown(f"源 {src.object_id} 身份未核")
        if spec.engine == Engine.UNDECIDED:
            unknown("engine=UNDECIDED")
        if spec.incremental_strategy == IncrementalStrategy.UNRESOLVED:
            unknown("增量策略 UNRESOLVED")
        tm = spec.time_semantics
        if not tm.business_time_expression or not tm.business_time_verified:
            unknown("业务时间语义未核")
        if not tm.change_time_expression or not tm.change_time_verified:
            unknown("变更时间依据未核")
        cp = spec.change_policy
        if not cp.insert_evidence:
            unknown("新增依据缺失")
        if not cp.update_evidence:
            unknown("修改依据缺失")
        if not spec.stable_key.verified:
            unknown("稳定键未核")
        if not spec.associations.performance_profile_id:
            unknown("未关联性能画像")
        if spec.associations.route_policy_ref:
            dual = [s for s in spec.source_candidates if s.role in ("primary", "history")]
            if len(dual) < 2:
                conflict("route_policy_ref 已声明但双源候选不足")
            elif not all(s.current_identity_verified for s in dual):
                unknown("双源路由时钟/边界未核")
        rb = spec.resource_budget
        if rb.query_timeout_seconds is None or not rb.cancel_supported:
            unknown("查询超时/取消能力未配置")

    elif layer == ReadinessLayer.STAGE_READY:
        if not spec.projection:
            unknown("投影为空")
        elif not all(p.type_verified for p in spec.projection):
            unknown("投影类型未逐列核验")
        if not spec.associations.long_lived_credential_ref:
            unknown("长期凭据 secret_ref 未配置（禁止沿用 /tmp 补抽环境）")

    elif layer == ReadinessLayer.APPLY_READY:
        ap = spec.apply_policy
        if not ap.executor_ref:
            unknown("装载执行器未配置")
        if not ap.allowed_operations:
            unknown("允许操作白名单为空")
        if not ap.idempotency_key:
            unknown("幂等键未配置")
        if not ap.approval_refs:
            unknown("未关联已获批准引用")
        if not spec.change_policy.version_order_verified:
            unknown("源版本顺序未核（旧批不得覆盖新版本的前提）")
        if ap.commit_receipt_mode != "SAME_TARGET_TXN":
            unknown("提交凭据未要求同目标事务")
        if spec.associations.running_writer_handoff_state != "HANDOFF_VERIFIED":
            unknown("旧写者交接未核（同表单写者前提）")
        if not spec.target.current_identity_verified:
            unknown("目标身份未核")

    elif layer == ReadinessLayer.REPORT_READY:
        if spec.associations.deadline_state != DeadlineState.CONFIGURED:
            unknown("deadline 未配置（SLA_UNKNOWN，禁止伪算 SLA_AT_RISK）")
        if not spec.dependency_fingerprints:
            unknown("依赖指纹未登记")

    return checks


# ---------------------------------------------------------------------------
# BatchManifest（§3.3）
# ---------------------------------------------------------------------------


@dataclass
class RowClassification:
    """源行互斥分类：read == valid + duplicate + quarantined + pending + unreadable。"""

    source_read_rows: int
    valid: int = 0
    duplicate_conflict: int = 0
    quarantined: int = 0
    pending_apply: int = 0
    unreadable_partial: int = 0

    def conservation_ok(self) -> bool:
        return (
            self.source_read_rows
            == self.valid
            + self.duplicate_conflict
            + self.quarantined
            + self.pending_apply
            + self.unreadable_partial
        )


@dataclass
class BatchManifest:
    batch_id: str
    attempt_id: str
    task_id: str
    config_version: str
    definition_fingerprint: str | None
    source_identity: str
    window_fingerprint: str
    source_visibility_cutoff: str  # 源可见上界（ISO 时间或显式哨兵）
    rows: RowClassification
    pagination_complete: bool
    end_reason: EndReason
    shard_count: int
    file_count: int
    total_bytes: int
    schema_version: str
    type_contract_version: str
    payload_sha256: str
    source_version_min: str | None = None
    source_version_max: str | None = None
    engine: Engine = Engine.UNDECIDED
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def validate(self) -> None:
        problems: list[str] = []
        for name in ("batch_id", "attempt_id", "task_id", "source_identity"):
            if not getattr(self, name):
                problems.append(f"{name} 为空")
        if not self.window_fingerprint:
            problems.append("window_fingerprint 为空（固定窗或 keyset 指纹必须冻结）")
        if not self.source_visibility_cutoff:
            problems.append("source_visibility_cutoff 为空")
        if not _SHA256_RE.match(self.payload_sha256 or ""):
            problems.append("payload_sha256 非 sha256hex")
        if self.rows is None or not self.rows.conservation_ok():
            problems.append(
                f"行分类不守恒: read={self.rows.source_read_rows if self.rows else None} "
                f"vs 分类和={_classified_sum(self.rows) if self.rows else None}"
            )
        if self.shard_count < 1 or self.file_count < 1:
            problems.append("分片/文件数必须>=1")
        if self.total_bytes < 0:
            problems.append("total_bytes 为负")
        if self.end_reason == EndReason.WINDOW_COMPLETE and not self.pagination_complete:
            problems.append("end_reason=WINDOW_COMPLETE 但 pagination_complete=False")
        if any(
            v is not None and not isinstance(v, str)
            for v in (self.source_version_min, self.source_version_max)
        ):
            problems.append("版本范围必须为字符串凭据")
        if problems:
            raise ContractViolation(f"BatchManifest[{self.batch_id}]: " + "; ".join(problems))

    def can_promote_to_captured(self) -> bool:
        """缺任何分片/未持久载荷不得推进捕获水位（§4）。"""
        return (
            self.pagination_complete
            and self.rows.conservation_ok()
            and self.rows.unreadable_partial == 0
        )


def _classified_sum(rows: RowClassification | None) -> int | None:
    if rows is None:
        return None
    return (
        rows.valid + rows.duplicate_conflict + rows.quarantined
        + rows.pending_apply + rows.unreadable_partial
    )


# ---------------------------------------------------------------------------
# 状态机（§5）
# ---------------------------------------------------------------------------

# 主链顺序（允许从任意主链态进入相应附加态再回，见 ALLOWED_TRANSITIONS）
_MAIN_CHAIN: list[BatchState] = [
    BatchState.PLANNED,
    BatchState.CAPTURING,
    BatchState.CAPTURED,
    BatchState.VALIDATING,
    BatchState.VALIDATED,
    BatchState.APPLY_PENDING,
    BatchState.APPLYING,
    BatchState.APPLIED,
    BatchState.RECONCILED,
]

# 附加态：从哪个主链态允许进入（打断点）
_ADDITIONAL_ENTRY_FROM: dict[BatchState, set[BatchState]] = {
    BatchState.WAITING_SOURCE: {BatchState.PLANNED, BatchState.CAPTURING},
    BatchState.WAITING_VIEW_FIX: {BatchState.PLANNED, BatchState.CAPTURING},
    BatchState.WAITING_INPUT: set(_MAIN_CHAIN),
    BatchState.WAITING_APPROVAL: {BatchState.VALIDATED, BatchState.APPLY_PENDING},
    BatchState.RETRYABLE: set(_MAIN_CHAIN),
    BatchState.QUARANTINED: {BatchState.VALIDATING, BatchState.VALIDATED},
    BatchState.COMMIT_UNKNOWN: {BatchState.APPLYING},
    BatchState.BLOCKED_DEPENDENCY: {BatchState.PLANNED, BatchState.CAPTURING},
    BatchState.DRIFT_DETECTED: {BatchState.CAPTURED, BatchState.VALIDATED, BatchState.APPLIED},
    BatchState.CANCELLED: set(_MAIN_CHAIN),
}

# 附加态退出：允许回到的主链态（恢复语义）
_ADDITIONAL_EXIT_TO: dict[BatchState, set[BatchState]] = {
    BatchState.WAITING_SOURCE: {BatchState.PLANNED, BatchState.CAPTURING},
    BatchState.WAITING_VIEW_FIX: {BatchState.PLANNED, BatchState.CAPTURING},
    BatchState.WAITING_INPUT: set(_MAIN_CHAIN),
    BatchState.WAITING_APPROVAL: {BatchState.APPLY_PENDING, BatchState.CANCELLED},
    BatchState.RETRYABLE: set(_MAIN_CHAIN),
    BatchState.QUARANTINED: {BatchState.VALIDATED, BatchState.CANCELLED},
    # COMMIT_UNKNOWN：先对账；确认已提交→APPLIED，确认回滚→APPLY_PENDING，禁止盲重放
    BatchState.COMMIT_UNKNOWN: {BatchState.APPLIED, BatchState.APPLY_PENDING, BatchState.CANCELLED},
    BatchState.BLOCKED_DEPENDENCY: {BatchState.PLANNED, BatchState.CAPTURING, BatchState.CANCELLED},
    BatchState.DRIFT_DETECTED: {BatchState.CAPTURED, BatchState.VALIDATED, BatchState.QUARANTINED},
    BatchState.CANCELLED: set(),  # 终态
}

# 附加态之间仅允许的有限转换（升级/收口路径）
_ADDITIONAL_TO_ADDITIONAL: dict[BatchState, set[BatchState]] = {
    BatchState.RETRYABLE: {BatchState.QUARANTINED, BatchState.CANCELLED, BatchState.WAITING_SOURCE,
                           BatchState.WAITING_VIEW_FIX, BatchState.WAITING_INPUT,
                           BatchState.BLOCKED_DEPENDENCY},
    BatchState.WAITING_SOURCE: {BatchState.CANCELLED},
    BatchState.WAITING_VIEW_FIX: {BatchState.CANCELLED},
    BatchState.WAITING_INPUT: {BatchState.CANCELLED},
    BatchState.QUARANTINED: {BatchState.CANCELLED},
    BatchState.BLOCKED_DEPENDENCY: {BatchState.CANCELLED},
}


class BatchStateMachine:
    """批次状态机：转换必须显式合法，且带证据引用；非法转换抛错。"""

    def __init__(self, state: BatchState = BatchState.PLANNED) -> None:
        if state not in tuple(BatchState):
            raise ContractViolation(f"初始状态非法: {state!r}")
        self.state = state
        self.history: list[dict[str, Any]] = [
            {"from": None, "to": state.value, "reason": "init", "evidence": None}
        ]

    def allowed(self, target: BatchState) -> bool:
        return self._guard(self.state, target) is None

    def transition(
        self,
        target: BatchState,
        *,
        reason: str,
        evidence: str | None = None,
        manifest: BatchManifest | None = None,
    ) -> BatchState:
        problem = self._guard(self.state, target, manifest)
        if problem is not None:
            raise ContractViolation(
                f"非法状态转换 {self.state.value} -> {target.value}: {problem}"
            )
        self.history.append(
            {
                "from": self.state.value,
                "to": target.value,
                "reason": reason,
                "evidence": evidence,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        self.state = target
        return target

    @staticmethod
    def _guard(
        current: BatchState,
        target: BatchState,
        manifest: BatchManifest | None = None,
    ) -> str | None:
        if current == target:
            return "自转换无意义"
        if current == BatchState.CANCELLED:
            return "CANCELLED 是终态"
        if current in _MAIN_CHAIN and target in _MAIN_CHAIN:
            cur_idx = _MAIN_CHAIN.index(current)
            tgt_idx = _MAIN_CHAIN.index(target)
            if tgt_idx == cur_idx + 1:
                if target == BatchState.CAPTURED:
                    if manifest is None:
                        return "推进 CAPTURED 必须携带 manifest"
                    if not manifest.can_promote_to_captured():
                        return "分页未完整或行分类不守恒，禁止推进 CAPTURED"
                return None
            if current == BatchState.APPLIED and target == BatchState.RECONCILED:
                return None
            return "主链只允许前进一格或 APPLIED->RECONCILED"
        if current in _MAIN_CHAIN and target in _ADDITIONAL_ENTRY_FROM:
            if current not in _ADDITIONAL_ENTRY_FROM[target]:
                return f"{target.value} 不允许从 {current.value} 进入"
            return None
        if current in _ADDITIONAL_EXIT_TO:
            if target in _MAIN_CHAIN:
                if target not in _ADDITIONAL_EXIT_TO[current]:
                    return f"{current.value} 只允许回到 {_sorted_names(_ADDITIONAL_EXIT_TO[current])}"
                return None
            allowed_extra = _ADDITIONAL_TO_ADDITIONAL.get(current, set())
            if target in allowed_extra:
                return None
            return f"{current.value} 不允许直接转到 {target.value}"
        return "未定义的转换"

    def main_chain_reached(self) -> int:
        """当前在主链上的最远进度（附加态回看最近主链记录）。"""
        for record in reversed(self.history):
            state = BatchState(record["to"])
            if state in _MAIN_CHAIN:
                return _MAIN_CHAIN.index(state)
        return -1


def _sorted_names(states: Iterable[BatchState]) -> list[str]:
    return sorted(s.value for s in states)


# ---------------------------------------------------------------------------
# 反馈链（省端回执：不捏造 ACCEPTED）
# ---------------------------------------------------------------------------

_FEEDBACK_TRANSITIONS: dict[FeedbackState, set[FeedbackState]] = {
    FeedbackState.NOT_SUBMITTED: {FeedbackState.SUBMITTED},
    FeedbackState.SUBMITTED: {FeedbackState.RECEIVED, FeedbackState.WAITING, FeedbackState.UNKNOWN},
    FeedbackState.RECEIVED: {FeedbackState.ACCEPTED, FeedbackState.REJECTED, FeedbackState.UNKNOWN},
    FeedbackState.ACCEPTED: set(),
    FeedbackState.REJECTED: {FeedbackState.SUBMITTED},  # 修正版本重传，单独新版本
    FeedbackState.UNKNOWN: {FeedbackState.RECEIVED, FeedbackState.WAITING},
    FeedbackState.WAITING: {FeedbackState.RECEIVED, FeedbackState.UNKNOWN},
}


class FeedbackStateMachine:
    def __init__(self, state: FeedbackState = FeedbackState.NOT_SUBMITTED) -> None:
        self.state = state
        self.history: list[dict[str, Any]] = [
            {"from": None, "to": state.value, "reason": "init", "evidence": None}
        ]

    def transition(self, target: FeedbackState, *, reason: str, evidence: str | None = None) -> FeedbackState:
        if target not in _FEEDBACK_TRANSITIONS[self.state]:
            raise ContractViolation(
                f"非法反馈转换 {self.state.value} -> {target.value}"
            )
        self.history.append(
            {
                "from": self.state.value,
                "to": target.value,
                "reason": reason,
                "evidence": evidence,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        self.state = target
        return target


def summarize_verdicts(
    specs: Sequence[TaskSpec],
) -> dict[str, dict[str, int]]:
    """按层聚合：READY/NOT_READY/UNKNOWN 计数（验收场景 AT-001 的机器口径）。"""
    summary: dict[str, dict[str, int]] = {}
    for layer in ReadinessLayer:
        summary[layer.value] = {s.value: 0 for s in LayerStatus}
    for spec in specs:
        for layer, verdict in spec.layer_verdicts().items():
            summary[layer.value][verdict.status.value] += 1
    return summary


def as_dict(obj: Any) -> dict[str, Any]:
    """契约对象 → 可 JSON 化 dict（枚举取 value，dataclass 递归）。"""
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, LayerVerdict):
        return {
            "layer": as_dict(obj.layer),
            "status": as_dict(obj.status),
            "reasons": list(obj.reasons),
        }
    if hasattr(obj, "__dataclass_fields__"):
        out: dict[str, Any] = {}
        for name in obj.__dataclass_fields__:
            out[name] = as_dict(getattr(obj, name))
        return out
    if isinstance(obj, Mapping):
        return {str(k): as_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [as_dict(v) for v in obj]
    return obj
