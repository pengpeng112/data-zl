"""受控装载：ApplyPort（白名单/批准/围栏/版本保护/同事务凭据）与月度原子发布。

对应计划 §5/§6.2/§4.1 与 R04 整改（F05/F06/F07）：
- ApplyPort 只接收已验证不可变 manifest、批准引用、白名单执行器、明确目标
  与允许动作、幂等键及版本规则；不接收任意自由 SQL 或源库写凭据。
- 批准由可信核验器裁决（ApprovalVerifier）：静态集合仅模拟；生产装配
  用 PlatformApprovalVerifier 查平台白名单与批准登记，调用方传入的
  approval_ref 只是引用，不是凭据。
- 围栏强制成体系：enforce_fence=True（默认）时缺 lease_validator、缺
  lease_resource/fencing_token 均拒绝；production_mode 再要求平台级批准
  核验与耐久版本账。
- 版本保护：精确比较（int/Decimal/规范化时间戳），不再转 float（大整数
  丢精度）也不回退字典序；无法建立可靠顺序 → CONFLICT。版本键带
  VersionScope（目标实例/租户/表），跨表同 ID 不互相污染。
- 正式提交凭据（operation_id、batch_id、manifest_hash、范围、结果摘要）
  由执行器与正式 DML 同目标事务持久化；执行器结果不明 → COMMIT_UNKNOWN。
- 月重扫发布语义：先完整捕获/质量/stage，后同事务替换完整发布范围；
  禁止先删后等源、禁止先删提交、双源月不得单源整月删。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Mapping, Protocol, Sequence

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    ContractViolation,
)
from app.services.reporting_pipeline.readback_types import (
    ColumnMeta,
    content_fingerprint,
)

# 装载动作（§6.2：按稳定键分类）
INSERT = "INSERT"
UPDATE = "UPDATE"
NO_CHANGE = "NO_CHANGE"
RETRACT = "RETRACT"
CONFLICT = "CONFLICT"


class ApplyRefused(ContractViolation):
    """装载被拒绝（门禁未满足）。"""


class CommitUnknownRaised(ApplyRefused):
    """执行器提交结果不明：冻结该表重叠写并先核目标凭据，禁止盲重放。

    独立子类让装配层能区分"门禁拒绝（回 APPLY_PENDING）"与
    "COMMIT_UNKNOWN（进 COMMIT_UNKNOWN 状态冻结）"。
    """


# ---------------------------------------------------------------------------
# 版本键作用域与精确比较（R04/F07：float 精度与字典序回退整改）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionScope:
    """版本键作用域：目标实例/租户/表 + 业务稳定键。

    跨表相同业务 ID 不得互相污染：版本账必须按 (目标实例, 租户, 表, 键)
    分账登记（RT1-014）。
    """

    target_instance: str
    tenant: str
    table: str

    def full_key(self, stable_key: tuple) -> tuple:
        return (self.target_instance, self.tenant, self.table, stable_key)


@dataclass(frozen=True)
class TargetCommitCredential:
    """同事务提交凭据：由执行器与正式 DML 在同一目标事务内持久化。

    恢复/COMMIT_UNKNOWN 裁定时查目标侧同事务凭据（operation_id +
    manifest_hash + 范围 + 结果摘要），不能拿 PG 控制面状态当 Oracle
    已提交证明。
    """

    operation_id: str
    batch_id: str
    manifest_hash: str
    target_object: str
    scope_summary: str
    rows_affected: int
    committed: bool | None  # None = COMMIT_UNKNOWN


class VersionRegistry(Protocol):
    """版本账仓储（耐久实现见 pg_repository；内存版仅模拟）。"""

    def current_version(self, scope: VersionScope, stable_key: tuple) -> str | None: ...

    def register_version(
        self,
        scope: VersionScope,
        stable_key: tuple,
        version: str,
        *,
        operation_id: str,
    ) -> None: ...


class InMemoryVersionRegistry:
    """内存版本账（模拟）：生产装配必须换耐久实现。"""

    def __init__(self) -> None:
        self._versions: dict[tuple, str] = {}

    def current_version(self, scope: VersionScope, stable_key: tuple) -> str | None:
        return self._versions.get(scope.full_key(stable_key))

    def register_version(
        self,
        scope: VersionScope,
        stable_key: tuple,
        version: str,
        *,
        operation_id: str,
    ) -> None:
        self._versions[scope.full_key(stable_key)] = version


# 已核版本类型：调用方按核验结论声明；未声明时按保守精确尝试
VERSION_KIND_INT = "int"
VERSION_KIND_DECIMAL = "decimal"
VERSION_KIND_TIMESTAMP = "timestamp"


def compare_versions(a: str, b: str, kind: str | None = None) -> int | None:
    """精确版本比较：返回 >0/<0/=0；无法建立可靠顺序返回 None。

    F07 整改：
    - 不再先转 float（9007199254740992 与 ...93 会误判相等）；
    - 整数走 int，小数走 Decimal，时间戳走规范化 datetime；
    - 未声明类型时按 int → decimal → timestamp 依次**精确**尝试；
    - 全部失败返回 None（调用方必须按 CONFLICT 处理，不得回退字典序
      冒充顺序，也不用采集时间冒充版本）。
    """
    if kind == VERSION_KIND_INT:
        return _cmp_exact(int(a), int(b))
    if kind == VERSION_KIND_DECIMAL:
        return _cmp_exact(Decimal(str(a)), Decimal(str(b)))
    if kind == VERSION_KIND_TIMESTAMP:
        ta, tb = _parse_ts(a), _parse_ts(b)
        if ta is None or tb is None:
            return None
        return _cmp_exact(ta, tb)
    # 未声明：精确尝试链（int 优先，避免 "10" < "9" 的字典序假序）
    try:
        return _cmp_exact(int(a), int(b))
    except (TypeError, ValueError):
        pass
    try:
        return _cmp_exact(Decimal(str(a)), Decimal(str(b)))
    except (InvalidOperation, ValueError, TypeError):
        pass
    ta, tb = _parse_ts(a), _parse_ts(b)
    if ta is not None and tb is not None:
        return _cmp_exact(ta, tb)
    return None


def _cmp_exact(a, b) -> int:
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ApplyRequest:
    manifest: BatchManifest
    quality_verified: bool
    approval_ref: str
    executor_id: str
    target_object: str
    allowed_operations: tuple[str, ...]
    idempotency_key_columns: tuple[str, ...]
    rows: tuple[Mapping, ...]
    column_meta: Mapping[str, ColumnMeta]
    mode: str = "MERGE"  # MERGE / REPLACE_MONTH
    replace_scope_keys: tuple[tuple, ...] | None = None  # REPLACE_MONTH 显式键清单
    lease_resource: str | None = None
    fencing_token: int | None = None
    version_order: str | None = None  # 已核源版本顺序说明
    version_kind: str | None = None  # int/decimal/timestamp（已核类型）
    # 批1-4 SNAPSHOT_DIFF CAS：调用方已完成"目标内容=上次登记内容"核验，
    # _classify 对内容差异直接 UPDATE（内容哈希不可排序，CAS 即安全依据；
    # 执行器仍在提交前做 TARGET_CHANGED 复核）。
    cas_preverified: bool = False
    # 逐键版本证据（SNAPSHOT_DIFF=源内容哈希；不用采集时间冒充源版本）。
    row_version_evidences: Mapping[tuple, str] | None = None


@dataclass
class ApplyPlan:
    actions: list[tuple[tuple, str]]  # (稳定键, 动作)
    counts: dict[str, int]
    preview_only: bool = True

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, action in self.actions:
            counts[action] = counts.get(action, 0) + 1
        return counts


@dataclass
class ApplyResult:
    committed: bool | None  # None = COMMIT_UNKNOWN
    operation_id: str
    rows_affected: int
    credential: TargetCommitCredential | None = None  # 同事务提交凭据


class ApplyExecutor(Protocol):
    """白名单执行器：与正式 DML 同事务写提交凭据；返回明确结果或 None。"""

    executor_id: str

    def execute(self, request: ApplyRequest, plan: ApplyPlan) -> ApplyResult: ...


# ---------------------------------------------------------------------------
# 批准校验器（R04/F06：批准由可信平台核验，调用方字符串不作凭据）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    trust_level: str  # platform / simulation
    reason: str


class ApprovalVerifier(Protocol):
    """批准核验协议：复核对象/实例/操作/范围/调用身份。"""

    trust_level: str

    def verify(
        self,
        *,
        approval_ref: str,
        executor_id: str,
        target_object: str,
        allowed_operations: Sequence[str],
    ) -> ApprovalDecision: ...


class StaticApprovalVerifier:
    """静态集合校验（模拟）：调用方自报批准集合，不作生产权限边界。"""

    trust_level = "simulation"

    def __init__(self, approved_refs: set[str]) -> None:
        self.approved_refs = set(approved_refs)

    def verify(
        self,
        *,
        approval_ref: str,
        executor_id: str,
        target_object: str,
        allowed_operations: Sequence[str],
    ) -> ApprovalDecision:
        if approval_ref in self.approved_refs:
            return ApprovalDecision(True, self.trust_level, "静态集合登记（模拟）")
        return ApprovalDecision(
            False, self.trust_level, f"批准引用未登记: {approval_ref}"
        )


class PlatformApprovalVerifier:
    """平台侧批准核验：查 asset_action_executors 白名单 + 批准登记。

    生产装配注入两个只读查询（由 session 工厂构造的 callable）：
    - executor_lookup(executor_code, target_object) -> 启用的执行器记录；
    - approval_lookup(approval_ref, executor_code) -> 有效批准记录。
    调用方传入的 approval_ref 只是引用；是否真的被批准由平台数据决定，
    不存在"传一组字符串就自认已批准"的路径。查询本身只读，不产生授权。
    """

    trust_level = "platform"

    def __init__(
        self,
        *,
        executor_lookup: Callable[[str, str], Mapping | None],
        approval_lookup: Callable[[str, str], Mapping | None],
    ) -> None:
        self._executor_lookup = executor_lookup
        self._approval_lookup = approval_lookup

    def verify(
        self,
        *,
        approval_ref: str,
        executor_id: str,
        target_object: str,
        allowed_operations: Sequence[str],
    ) -> ApprovalDecision:
        executor = self._executor_lookup(executor_id, target_object)
        if executor is None:
            return ApprovalDecision(
                False, self.trust_level,
                f"执行器不在平台白名单或未启用: {executor_id}",
            )
        if not executor.get("enabled", False):
            return ApprovalDecision(
                False, self.trust_level, f"执行器已停用: {executor_id}"
            )
        approval = self._approval_lookup(approval_ref, executor_id)
        if approval is None:
            return ApprovalDecision(
                False, self.trust_level, f"批准引用在平台无有效记录: {approval_ref}"
            )
        if not approval.get("valid", False):
            return ApprovalDecision(
                False, self.trust_level, f"批准已失效或范围不符: {approval_ref}"
            )
        return ApprovalDecision(
            True, self.trust_level, "平台白名单+批准登记核验通过"
        )


class VersionGuard:
    """版本保护：旧版本不得覆盖新版本；hash 不当顺序。

    R04 整改：
    - 键必须带 VersionScope（目标/租户/表），跨表同 ID 不互污染；
    - 比较走 compare_versions 精确路径；无法建立顺序 → CONFLICT；
    - 可注入耐久 VersionRegistry（生产），内存账仅模拟。
    """

    def __init__(self, registry: VersionRegistry | None = None) -> None:
        self._registry = registry or InMemoryVersionRegistry()
        self._registry_is_memory = isinstance(self._registry, InMemoryVersionRegistry)

    @property
    def durable(self) -> bool:
        return not self._registry_is_memory

    def register_applied(
        self,
        stable_key: tuple,
        version_evidence: str,
        *,
        scope: VersionScope | None = None,
        operation_id: str = "sim",
    ) -> None:
        scope = scope or VersionScope("_sim", "_sim", "_sim")
        self._registry.register_version(
            scope, stable_key, version_evidence, operation_id=operation_id
        )

    def check(
        self,
        stable_key: tuple,
        incoming_version: str | None,
        *,
        scope: VersionScope | None = None,
        version_kind: str | None = None,
    ) -> str:
        """返回 NO_CHANGE / UPDATE / CONFLICT。

        无已核版本顺序（version=None）且内容键不同 → CONFLICT，不盲覆盖。
        """
        scope = scope or VersionScope("_sim", "_sim", "_sim")
        current = self._registry.current_version(scope, stable_key)
        if current is None:
            return INSERT
        if incoming_version is None:
            return CONFLICT
        if incoming_version == current:
            return NO_CHANGE
        verdict = compare_versions(incoming_version, current, version_kind)
        if verdict is None:
            # 无法建立可靠顺序：不按采集时间/字典序冒充，进冲突隔离
            return CONFLICT
        return UPDATE if verdict > 0 else CONFLICT


class ApplyPort:
    def __init__(
        self,
        *,
        whitelisted_executors: Sequence[str],
        approved_refs: set[str] | None = None,
        lease_validator: Callable[[str, int], None] | None = None,
        version_guard: VersionGuard | None = None,
        approval_verifier: ApprovalVerifier | None = None,
        enforce_fence: bool = True,
        production_mode: bool = False,
    ) -> None:
        self.whitelisted_executors = set(whitelisted_executors)
        self.approval_verifier = approval_verifier or StaticApprovalVerifier(
            approved_refs or set()
        )
        self.lease_validator = lease_validator  # callable(resource, token) -> None
        self.version_guard = version_guard or VersionGuard()
        self.enforce_fence = enforce_fence
        self.production_mode = production_mode
        if production_mode:
            # 生产模式硬性要求：平台级批准核验 + 耐久版本账 + 围栏校验器
            if self.approval_verifier.trust_level != "platform":
                raise ApplyRefused(
                    "生产装载禁止使用静态批准集合（须 PlatformApprovalVerifier）"
                )
            if not self.version_guard.durable:
                raise ApplyRefused("生产装载禁止内存版本账（须耐久 VersionRegistry）")
            if self.lease_validator is None:
                raise ApplyRefused("生产装载必须提供 lease_validator（目标侧围栏）")

    def preview(self, request: ApplyRequest, target_rows: Mapping[tuple, Mapping]) -> ApplyPlan:
        actions = self._classify(request, target_rows)
        plan = ApplyPlan(actions=actions, counts={}, preview_only=True)
        plan.counts = plan.summary()
        return plan

    def apply(
        self,
        request: ApplyRequest,
        executor: ApplyExecutor,
        target_rows: Mapping[tuple, Mapping],
    ) -> ApplyResult:
        self._gate(request, executor)
        plan = self.preview(request, target_rows)
        if request.mode == "REPLACE_MONTH":
            self._gate_month_replace(request)
        result = executor.execute(request, plan)
        if result.committed is None:
            # COMMIT_UNKNOWN：冻结同表写者是上层调度职责；此处不再重放
            raise CommitUnknownRaised(
                f"[{request.manifest.batch_id}] 执行器结果不明（COMMIT_UNKNOWN），"
                "须先核同事务提交凭据，禁止盲重放"
            )
        if result.committed:
            if result.credential is None:
                raise ApplyRefused(
                    f"[{request.manifest.batch_id}] 执行器未提供同事务提交凭据"
                    "（TargetCommitCredential），不能当作已确认提交"
                )
            scope = self._version_scope(request)
            evidences = request.row_version_evidences or {}
            for key, action in plan.actions:
                if action in (INSERT, UPDATE, NO_CHANGE):
                    self.version_guard.register_applied(
                        key,
                        evidences.get(key) or request.version_order or "applied",
                        operation_id=result.operation_id,
                        scope=scope,
                    )
        return result

    def _version_scope(self, request: ApplyRequest) -> VersionScope | None:
        if not self.production_mode:
            return None
        # 实例自身可能含点号，只有最右侧的 owner/table 是拆分边界。
        parts = request.target_object.rsplit(".", 2)
        if len(parts) != 3 or not all(parts):
            raise ApplyRefused("生产版本账须绑定目标实例、机构和表")
        return VersionScope(*parts)

    # -- 门禁 ---------------------------------------------------------------

    def _gate(self, request: ApplyRequest, executor: ApplyExecutor) -> None:
        problems: list[str] = []
        if self.production_mode:
            self._version_scope(request)
            if request.executor_id != executor.executor_id:
                problems.append("请求执行器与实际白名单执行器不一致")
        if not request.manifest.pagination_complete:
            problems.append("manifest 分页未完整（缺分片不得装载正式）")
        if not request.quality_verified:
            problems.append("质量未验证（隔离未闭合不得装载）")
        decision = self.approval_verifier.verify(
            approval_ref=request.approval_ref,
            executor_id=executor.executor_id,
            target_object=request.target_object,
            allowed_operations=request.allowed_operations,
        )
        if not decision.approved:
            problems.append(f"批准核验未通过: {decision.reason}")
        if executor.executor_id not in self.whitelisted_executors:
            problems.append(f"执行器不在白名单: {executor.executor_id}")
        if request.mode not in ("MERGE", "REPLACE_MONTH"):
            problems.append(f"非法装载模式: {request.mode}")
        # 围栏（R04/F09：生产路径不得缺省 lease_validator / token）
        if self.enforce_fence:
            if self.lease_validator is None:
                problems.append("未配置 lease_validator（禁止无围栏装载）")
            elif request.lease_resource is None or request.fencing_token is None:
                problems.append(
                    "装载请求缺 lease_resource/fencing_token（禁止无 token 正式写）"
                )
            else:
                try:
                    self.lease_validator(request.lease_resource, request.fencing_token)
                except Exception as exc:  # LeaseDenied 等围栏失败
                    problems.append(f"围栏校验失败: {exc}")
        elif self.lease_validator is not None:
            # 显式声明模拟（enforce_fence=False）：给了校验器仍然执行
            try:
                if request.lease_resource is not None:
                    self.lease_validator(request.lease_resource, request.fencing_token)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"围栏校验失败: {exc}")
        if problems:
            raise ApplyRefused(
                f"[{request.manifest.batch_id}] 装载被拒: " + "; ".join(problems)
            )

    def _gate_month_replace(self, request: ApplyRequest) -> None:
        if request.replace_scope_keys is None:
            raise ApplyRefused(
                "REPLACE_MONTH 需要显式发布范围键清单（目标无已证 DATETIME 列，"
                "不得按不存在列删除）"
            )
        # 双源月保护：发布范围必须覆盖全部来源归属（由调用方按来源账本给出），
        # 单源完成不能整月删另一源——本口只验"范围键来自完整来源账本"的标记。
        if not request.manifest.pagination_complete:
            raise ApplyRefused("月替换前置：源未完整，禁止先删目标")

    def _classify(
        self, request: ApplyRequest, target_rows: Mapping[tuple, Mapping]
    ) -> list[tuple[tuple, str]]:
        metas = sorted(request.column_meta.values(), key=lambda m: m.name)
        actions: list[tuple[tuple, str]] = []
        for row in request.rows:
            key = tuple(row.get(c) for c in request.idempotency_key_columns)
            target_row = target_rows.get(key)
            if target_row is None:
                actions.append((key, INSERT))
                continue
            source_fp = content_fingerprint(row, metas)
            target_fp = content_fingerprint(target_row, metas)
            if source_fp == target_fp:
                actions.append((key, NO_CHANGE))
                continue
            if request.cas_preverified:
                # 批1-4 SNAPSHOT_DIFF：调用方分区已核"目标内容=上次登记
                # 内容"（CAS 通过）；内容差异合法 UPDATE，不按内容哈希
                # 不可比而误判 CONFLICT。提交前执行器仍复核 TARGET_CHANGED。
                actions.append((key, UPDATE))
                continue
            verdict = self.version_guard.check(
                key, request.version_order, version_kind=request.version_kind,
                scope=self._version_scope(request),
            )
            if verdict == CONFLICT:
                actions.append((key, CONFLICT))
            elif verdict == NO_CHANGE:
                actions.append((key, NO_CHANGE))
            else:
                actions.append((key, UPDATE))
        return actions


class InMemoryApplyExecutor:
    """模拟执行器：同'事务'更新目标并登记提交凭据；可注入 UNKNOWN。"""

    executor_id = "sim-apply-1"

    def __init__(self, *, force_unknown: bool = False, omit_credential: bool = False) -> None:
        self.target: dict[tuple, Mapping] = {}
        self.receipts: list[dict] = []
        self.force_unknown = force_unknown
        self.omit_credential = omit_credential
        self._seq = 0

    def execute(self, request: ApplyRequest, plan: ApplyPlan) -> ApplyResult:
        if self.force_unknown:
            return ApplyResult(committed=None, operation_id="OP-UNKNOWN", rows_affected=0)
        self._seq += 1
        operation_id = f"OP-{self._seq:08d}"
        affected = 0
        if request.mode == "REPLACE_MONTH":
            # 同事务：删发布范围 + 插 stage 全量
            for key in request.replace_scope_keys or ():
                self.target.pop(key, None)
            for row in request.rows:
                key = tuple(row.get(c) for c in request.idempotency_key_columns)
                self.target[key] = dict(row)
                affected += 1
        else:
            for key, action in plan.actions:
                matching = [
                    r for r in request.rows
                    if tuple(r.get(c) for c in request.idempotency_key_columns) == key
                ]
                if action == INSERT and matching:
                    self.target[key] = dict(matching[0])
                    affected += 1
                elif action == UPDATE and matching:
                    self.target[key] = dict(matching[0])
                    affected += 1
        credential = None
        if not self.omit_credential:
            credential = TargetCommitCredential(
                operation_id=operation_id,
                batch_id=request.manifest.batch_id,
                manifest_hash=request.manifest.payload_sha256,
                target_object=request.target_object,
                scope_summary=(
                    f"{request.mode}:{len(request.replace_scope_keys or ())}"
                    if request.mode == "REPLACE_MONTH" else request.mode
                ),
                rows_affected=affected,
                committed=True,
            )
        self.receipts.append(
            {
                "operation_id": operation_id,
                "batch_id": request.manifest.batch_id,
                "manifest_hash": request.manifest.payload_sha256,
                "rows_affected": affected,
                "mode": request.mode,
                "target": request.target_object,
            }
        )
        return ApplyResult(
            committed=True, operation_id=operation_id,
            rows_affected=affected, credential=credential,
        )


@dataclass
class MonthPublishPlan:
    """月重扫发布编排（§4.1 publish_order 的机器化检查单）。"""

    table: str
    business_month: str
    route_origins: tuple[str, ...]
    stage_complete: bool
    quality_unexplained_isolated: bool
    scope_keys: tuple[tuple, ...]
    writer_lease_resource: str | None = None

    def readiness(self) -> dict:
        checks = {
            "freeze_routes_and_scope": bool(self.route_origins),
            "complete_bounded_source_capture": self.stage_complete,
            "manifest_and_quality": not self.quality_unexplained_isolated,
            "stage_verify": self.stage_complete,
            "obtain_same_table_writer_and_version_guard": self.writer_lease_resource is not None,
            "approved_atomic_replace": False,  # 由 ApplyPort.apply 实际发生
            "readback_and_receipt": False,
            "close_all_slices_then_business_month": False,
        }
        return checks

    def can_publish(self) -> bool:
        checks = self.readiness()
        return all(
            checks[k] for k in (
                "freeze_routes_and_scope",
                "complete_bounded_source_capture",
                "manifest_and_quality",
                "stage_verify",
                "obtain_same_table_writer_and_version_guard",
            )
        )
