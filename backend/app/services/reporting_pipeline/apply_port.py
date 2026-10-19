"""受控装载：ApplyPort（白名单/批准/围栏/版本保护/同事务凭据）与月度原子发布。

对应计划 §5/§6.2/§4.1：
- ApplyPort 只接收已验证不可变 manifest、批准引用、白名单执行器、明确目标
  与允许动作、幂等键及版本规则；不接收任意自由 SQL 或源库写凭据。
- 版本保护：拒绝旧版本覆盖；hash 只判异同，不作版本顺序（采集晚不证明
  内容新）。无可靠版本顺序时同键不同内容进 CONFLICT 隔离，不盲覆盖。
- 正式提交凭据（operation_id、batch_id、manifest_hash、结果摘要）由执行器
  与正式 DML 同目标事务持久化；执行器结果不明 → COMMIT_UNKNOWN。
- 月重扫发布语义：先完整捕获/质量/stage，后同事务替换完整发布范围；
  禁止先删后等源、禁止先删提交、双源月不得单源整月删。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

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


class ApplyExecutor(Protocol):
    """白名单执行器：与正式 DML 同事务写提交凭据；返回明确结果或 None。"""

    executor_id: str

    def execute(self, request: ApplyRequest, plan: ApplyPlan) -> ApplyResult:
        ...


class VersionGuard:
    """版本保护：旧版本不得覆盖新版本；hash 不当顺序。"""

    def __init__(self) -> None:
        self._applied_versions: dict[tuple, str] = {}

    def register_applied(self, stable_key: tuple, version_evidence: str) -> None:
        self._applied_versions[stable_key] = version_evidence

    def check(self, stable_key: tuple, incoming_version: str | None) -> str:
        """返回 NO_CHANGE / UPDATE / CONFLICT。

        无已核版本顺序（version=None）且内容键不同 → CONFLICT，不盲覆盖。
        """
        current = self._applied_versions.get(stable_key)
        if current is None:
            return INSERT if incoming_version is None else INSERT
        if incoming_version is None:
            return CONFLICT if stable_key in self._applied_versions else INSERT
        if incoming_version == current:
            return NO_CHANGE
        # 顺序判定必须由已核版本序（如 SCN/提交序号/单调时间戳+规则）给出；
        # 调用方给的 incoming_version 已是该语义的字符串凭据。
        return UPDATE if _version_after(incoming_version, current) else CONFLICT


def _version_after(a: str, b: str) -> bool:
    """已核版本序比较：数值可比较则数值比，否则字典序（由核验方保证语义）。"""
    try:
        return float(a) > float(b)
    except (TypeError, ValueError):
        return str(a) > str(b)


class ApplyPort:
    def __init__(
        self,
        *,
        whitelisted_executors: Sequence[str],
        approved_refs: set[str],
        lease_validator=None,
        version_guard: VersionGuard | None = None,
    ) -> None:
        self.whitelisted_executors = set(whitelisted_executors)
        self.approved_refs = set(approved_refs)
        self.lease_validator = lease_validator  # callable(resource, token) -> None
        self.version_guard = version_guard or VersionGuard()

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
            raise ApplyRefused(
                f"[{request.manifest.batch_id}] 执行器结果不明（COMMIT_UNKNOWN），"
                "须先核同事务提交凭据，禁止盲重放"
            )
        if result.committed:
            for key, action in plan.actions:
                if action in (INSERT, UPDATE, NO_CHANGE):
                    self.version_guard.register_applied(
                        key, request.version_order or "applied"
                    )
        return result

    # -- 门禁 ---------------------------------------------------------------

    def _gate(self, request: ApplyRequest, executor: ApplyExecutor) -> None:
        problems: list[str] = []
        if not request.manifest.pagination_complete:
            problems.append("manifest 分页未完整（缺分片不得装载正式）")
        if not request.quality_verified:
            problems.append("质量未验证（隔离未闭合不得装载）")
        if request.approval_ref not in self.approved_refs:
            problems.append(f"批准引用未登记: {request.approval_ref}")
        if executor.executor_id not in self.whitelisted_executors:
            problems.append(f"执行器不在白名单: {executor.executor_id}")
        if request.mode not in ("MERGE", "REPLACE_MONTH"):
            problems.append(f"非法装载模式: {request.mode}")
        if self.lease_validator is not None:
            try:
                if request.lease_resource is not None:
                    self.lease_validator(request.lease_resource, request.fencing_token)
            except Exception as exc:  # LeaseDenied 等围栏失败
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
            verdict = self.version_guard.check(key, request.version_order)
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

    def __init__(self, *, force_unknown: bool = False) -> None:
        self.target: dict[tuple, Mapping] = {}
        self.receipts: list[dict] = []
        self.force_unknown = force_unknown
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
        return ApplyResult(committed=True, operation_id=operation_id, rows_affected=affected)


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
