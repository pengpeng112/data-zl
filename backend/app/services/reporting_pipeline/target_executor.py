"""正式目标执行器（A03）：受控 INSERT/UPDATE + 同事务回执 + SYSTEM_TIME。

对应计划 §四-A03 与系统补充：
- 单个目标事务包含：目标侧围栏（行锁/唯一约束）→ 业务 DML＋目标
  SYSTEM_TIME＋提交回执 → COMMIT；回执与业务 DML 必须同一事务，以
  operation_id（批次+manifest 全内容哈希派生，重试不变）唯一定位。
- SYSTEM_TIME 只在真实 INSERT/UPDATE 的目标事务内取目标当前时间
  （connection.current_timestamp()），每批事务取一次并保存批次时间；
  不预选整点、不用采集时刻冒充。
- COMMIT 结果不明（网络断在提交应答上）→ committed=None（COMMIT_UNKNOWN），
  由上层冻结该表重叠写并查目标凭据，禁止盲重试；确认已提交后重放同
  operation_id 幂等返回原回执，不重复写业务行。
- 目标已有同键同内容 → NO_CHANGE 不写；确有差异只按 plan 允许列 UPDATE；
  CONFLICT 行隔离跳过，不静默覆盖。
- 本模块只依赖注入的 TargetConnection 协议：真实装配绑定受控连接器
  （长期凭据引用解析，禁止 /tmp 临时环境）；辅助回执表需先获 DDL 批准，
  未配置 receipt_table 时生产装配必须拒绝（ApplyPort production 门禁）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping, Protocol, Sequence

from app.services.reporting_pipeline.apply_port import (
    ApplyPlan,
    ApplyRequest,
    ApplyResult,
    INSERT,
    UPDATE,
    TargetCommitCredential,
)
from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.readback_types import content_fingerprint


class AmbiguousCommit(RuntimeError):
    """提交结果不明：COMMIT 已发出但应答丢失/连接断开。"""


class TargetConnection(Protocol):
    """目标库事务连接协议（生产由受控连接器实现；测试注入 Fake）。"""

    def begin(self) -> None: ...

    def lock_and_read_rows(
        self, table: str, key_columns: Sequence[str], keys: Sequence[tuple]
    ) -> Mapping[tuple, Mapping]:
        """事务内锁定并读目标既有行（行锁围栏：阻止旧写者并发改同键）。"""
        ...

    def current_timestamp(self) -> datetime:
        """目标库当前时间（SYSTEM_TIME 唯一来源；每事务调用一次）。"""
        ...

    def insert_rows(
        self, table: str, columns: Sequence[str], rows: Sequence[Mapping]
    ) -> int: ...

    def update_rows(
        self,
        table: str,
        columns: Sequence[str],
        rows: Sequence[Mapping],
        *,
        key_columns: Sequence[str],
    ) -> int: ...

    def find_receipt(self, receipt_table: str, operation_id: str) -> Mapping | None: ...

    def insert_receipt(
        self, receipt_table: str, receipt: Mapping
    ) -> None: ...

    def commit(self) -> bool:
        """True=已提交；False=已回滚；结果不明抛 AmbiguousCommit。"""
        ...

    def rollback(self) -> None: ...


def stable_operation_id(batch_id: str, manifest_hash: str) -> str:
    """稳定操作身份：同清单重试保持同一 operation_id（幂等重放前提）。"""
    return f"OPR-{batch_id}-{manifest_hash[:12]}"


@dataclass(frozen=True)
class ExecutorTargetConfig:
    """执行器目标绑定（A03 请求绑定项的落点）。"""

    target_instance: str
    tenant: str
    table: str
    key_columns: tuple[str, ...]
    write_columns: tuple[str, ...]          # 白名单投影（允许写列）
    system_time_column: str | None = None   # 目标无该列则不插
    receipt_table: str | None = None        # 已获 DDL 批准的回执表


class SqlTargetApplyExecutor:
    """白名单执行器：与正式 DML 同目标事务写提交回执。

    生产装配四要件（缺一由 ApplyPort/装配方拒绝）：
    - PlatformApprovalVerifier（真实批准核验）；
    - receipt_table（已批准 DDL）；未配置时本执行器拒绝正式执行；
    - 目标侧围栏：事务内 lock_and_read_rows 行锁 + 唯一键约束；
    - 长期凭据引用解析的连接工厂（不落明文）。
    """

    executor_id = "sql-target-apply-1"

    def __init__(
        self,
        connection_factory: Callable[[], TargetConnection],
        config: ExecutorTargetConfig,
        *,
        simulation: bool = False,
        fence_check: Callable[[], None] | None = None,
        expected_target_rows: Mapping[tuple, Mapping] | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._config = config
        self._simulation = simulation
        self._fence_check = fence_check
        self._expected_target_rows = expected_target_rows
        if not simulation and not config.receipt_table:
            raise ContractViolation(
                "正式执行器必须配置已批准的 receipt_table（同事务回执）；"
                "辅助表 DDL 未获批前不得正式装载"
            )

    def execute(self, request: ApplyRequest, plan: ApplyPlan) -> ApplyResult:
        cfg = self._config
        if request.mode != "MERGE":
            raise ContractViolation("当前SQL执行器仅实现MERGE；禁止将月替换伪装为成功")
        if tuple(request.idempotency_key_columns) != cfg.key_columns:
            raise ContractViolation("请求稳定键与执行器绑定不一致")
        requested_target = request.target_object.rsplit(".", 2)
        if (len(requested_target) != 3 or requested_target[0] != cfg.target_instance
                or requested_target[1].upper() != cfg.tenant.upper()
                or requested_target[2].upper() != cfg.table.rsplit(".", 1)[-1].upper()):
            raise ContractViolation("请求目标与执行器冻结绑定不一致")
        if any(action not in (INSERT, UPDATE, "NO_CHANGE") for _, action in plan.actions):
            raise ContractViolation("存在冲突或未知装载动作，须先隔离，不能签发成功回执")
        planned_keys = [key for key, _ in plan.actions]
        row_keys = [tuple(row.get(column) for column in cfg.key_columns) for row in request.rows]
        if (len(planned_keys) != len(set(planned_keys)) or len(row_keys) != len(set(row_keys))
                or set(planned_keys) != set(row_keys)):
            raise ContractViolation("装载计划与暂存键集不完整或有重复")
        operation_id = stable_operation_id(
            request.manifest.batch_id, request.manifest.payload_sha256
        )
        conn = self._connection_factory()
        try:
            conn.begin()
            if self._fence_check:
                self._fence_check()
            # 幂等重放：目标侧回执已存在 → 返回原回执，不再写业务行
            if cfg.receipt_table:
                existing = conn.find_receipt(cfg.receipt_table, operation_id)
                if existing is not None:
                    conn.rollback()
                    return ApplyResult(
                        committed=True,
                        operation_id=operation_id,
                        rows_affected=int(existing.get("rows_affected", 0)),
                        credential=TargetCommitCredential(
                            operation_id=operation_id,
                            batch_id=request.manifest.batch_id,
                            manifest_hash=request.manifest.payload_sha256,
                            target_object=request.target_object,
                            scope_summary=str(existing.get("scope_summary", "")),
                            rows_affected=int(existing.get("rows_affected", 0)),
                            committed=True,
                        ),
                    )
            # 目标侧围栏：事务内锁定本批涉及键的既有行（旧写者并发同键写
            # 被行锁挡住）；INSERT 行由唯一键约束兜底
            plan_keys = [key for key, _ in plan.actions]
            locked = conn.lock_and_read_rows(cfg.table, cfg.key_columns, plan_keys)
            rows_by_key = {}
            for row in request.rows:
                key = tuple(row.get(c) for c in request.idempotency_key_columns)
                if key in rows_by_key:
                    raise ContractViolation("执行器拒绝重复稳定键，须先完成质量去重")
                rows_by_key[key] = row
            # 执行分类动作：只写白名单列；NO_CHANGE 不写；CONFLICT 隔离跳过
            inserts: list[Mapping] = []
            updates: list[Mapping] = []
            for key, action in plan.actions:
                if key not in rows_by_key:
                    raise ContractViolation("装载计划与暂存键集不一致")
                row = rows_by_key[key]
                if ((action == INSERT and key in locked)
                        or (action in (UPDATE, "NO_CHANGE") and key not in locked)):
                    raise ContractViolation("TARGET_CHANGED：预览后目标键发生变化，回滚并重新对账")
                metas = list(request.column_meta.values())
                if self._expected_target_rows is not None:
                    expected = self._expected_target_rows.get(key)
                    current = locked.get(key)
                    if ((expected is None) != (current is None) or
                            (expected is not None and content_fingerprint(expected, metas) != content_fingerprint(current, metas))):
                        raise ContractViolation("TARGET_CHANGED：预览后目标内容发生变化，回滚并重新对账")
                if action == "NO_CHANGE" and content_fingerprint(row, metas) != content_fingerprint(locked[key], metas):
                    raise ContractViolation("TARGET_CHANGED：无需更新的记录已发生变化")
                if action == INSERT and key not in locked:
                    inserts.append(row)
                elif action == UPDATE and key in locked:
                    updates.append(row)
                # NO_CHANGE / CONFLICT / 重复键错分类：跳过（隔离账在控制面）
            system_time = (
                conn.current_timestamp() if cfg.system_time_column else None
            )
            columns = list(cfg.write_columns)
            if cfg.system_time_column and cfg.system_time_column not in columns:
                columns = columns + [cfg.system_time_column]

            def _with_system_time(row: Mapping) -> dict:
                if not cfg.system_time_column:
                    return dict(row)
                out = dict(row)
                out[cfg.system_time_column] = system_time
                return out

            affected = 0
            if inserts:
                affected += conn.insert_rows(
                    cfg.table, columns,
                    [_with_system_time(r) for r in inserts],
                )
            if updates:
                affected += conn.update_rows(
                    cfg.table, columns,
                    [_with_system_time(r) for r in updates],
                    key_columns=cfg.key_columns,
                )
            if affected != len(inserts) + len(updates):
                raise ContractViolation("DML_ROWCOUNT_MISMATCH：实际写入行数与计划不符，回滚")
            # 同事务回执：与业务 DML 同一事务持久化（COMMIT 前写入）
            if cfg.receipt_table:
                conn.insert_receipt(cfg.receipt_table, {
                    "operation_id": operation_id,
                    "batch_id": request.manifest.batch_id,
                    "manifest_hash": request.manifest.payload_sha256,
                    "target_object": request.target_object,
                    "scope_summary": (
                        f"{request.mode}:keys={len(plan.actions)}"
                    ),
                    "rows_affected": affected,
                    "system_time": (
                        system_time.isoformat() if system_time else None
                    ),
                    "committed_at": (
                        conn.current_timestamp().isoformat()
                        if cfg.receipt_table else None
                    ),
                })
            if self._fence_check:
                self._fence_check()
            committed = conn.commit()
        except AmbiguousCommit:
            return ApplyResult(
                committed=None, operation_id=operation_id, rows_affected=0
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 - 回滚失败保留原异常
                pass
            raise
        finally:
            close = getattr(conn, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass  # 关闭失败不能把明确提交重新判为失败并触发重放。
        if not committed:
            return ApplyResult(
                committed=False, operation_id=operation_id, rows_affected=0
            )
        return ApplyResult(
            committed=True,
            operation_id=operation_id,
            rows_affected=affected,
            credential=TargetCommitCredential(
                operation_id=operation_id,
                batch_id=request.manifest.batch_id,
                manifest_hash=request.manifest.payload_sha256,
                target_object=request.target_object,
                scope_summary=f"{request.mode}:keys={len(plan.actions)}",
                rows_affected=affected,
                committed=True,
            ),
        )


class FakeTargetConnection:
    """内存目标连接（隔离验证用）：实现 TargetConnection 协议。"""

    def __init__(
        self,
        rows: dict[tuple, Mapping] | None = None,
        *,
        key_columns: Sequence[str] = ("K1",),
        ambiguous_commit: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.rows: dict[tuple, Mapping] = dict(rows or {})
        self.key_columns = tuple(key_columns)
        self.receipts: dict[str, Mapping] = {}
        self.locked_keys: list[tuple] = []
        self.in_transaction = False
        self.inserted_count = 0
        self.updated_count = 0
        self._ambiguous_commit = ambiguous_commit
        self._clock = clock or datetime.now
        self._snapshot: dict[tuple, Mapping] | None = None
        self._pending_receipts: dict[str, Mapping] = {}

    def begin(self) -> None:
        self.in_transaction = True
        self._snapshot = dict(self.rows)

    def lock_and_read_rows(
        self, table: str, key_columns: Sequence[str], keys: Sequence[tuple]
    ) -> Mapping[tuple, Mapping]:
        self.locked_keys.extend(keys)
        return {k: self.rows[k] for k in keys if k in self.rows}

    def current_timestamp(self) -> datetime:
        return self._clock()

    def insert_rows(
        self, table: str, columns: Sequence[str], rows: Sequence[Mapping]
    ) -> int:
        count = 0
        for row in rows:
            key = tuple(row.get(c) for c in self.key_columns)
            if key in self.rows:
                raise ContractViolation(f"唯一键冲突（INSERT 撞既有键）: {key}")
            self.rows[key] = {c: row.get(c) for c in columns}
            count += 1
        self.inserted_count += count
        return count

    def update_rows(
        self,
        table: str,
        columns: Sequence[str],
        rows: Sequence[Mapping],
        *,
        key_columns: Sequence[str],
    ) -> int:
        count = 0
        for row in rows:
            key = tuple(row.get(c) for c in key_columns)
            if key not in self.rows:
                raise ContractViolation(f"UPDATE 目标键不存在: {key}")
            merged = dict(self.rows[key])
            for c in columns:
                if c in row:
                    merged[c] = row.get(c)
            self.rows[key] = merged
            count += 1
        self.updated_count += count
        return count

    def find_receipt(self, receipt_table: str, operation_id: str) -> Mapping | None:
        return self.receipts.get(operation_id)

    def insert_receipt(self, receipt_table: str, receipt: Mapping) -> None:
        if not self.in_transaction:
            raise ContractViolation("回执必须在事务内写入")
        self._pending_receipts[receipt["operation_id"]] = dict(receipt)

    def commit(self) -> bool:
        if self._ambiguous_commit:
            self._ambiguous_commit = False
            # 测试地设为"实际已回滚"：恢复事务起点快照（真实场景结果未知，
            # 由裁定流程查回执表确认；本 Fake 只提供确定性ground truth）
            self.rows = dict(self._snapshot or {})
            self._pending_receipts = {}
            self.in_transaction = False
            self._snapshot = None
            raise AmbiguousCommit("提交应答丢失（测试注入）")
        if not self.in_transaction:
            raise ContractViolation("无事务可提交")
        self.receipts.update(self._pending_receipts)
        self._pending_receipts = {}
        self.in_transaction = False
        self._snapshot = None
        return True

    def rollback(self) -> None:
        if self._snapshot is not None:
            self.rows = dict(self._snapshot)
        self._pending_receipts = {}
        self.in_transaction = False
        self._snapshot = None
