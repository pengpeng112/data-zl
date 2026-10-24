"""真实装配（A02）：六真实动作命令的统一装配与拒绝语义。

对应主计划 §四-A02 与启动说明真实缺口 1：
- capture/verify/apply/reconcile/delivery/retry 六个真实动作的装配入口；
- 正式运行缺状态库、暂存根目录、源绑定、目标连接绑定或批准配置即拒绝
  （REFUSED_*），不退回内存模拟、不落假 capture；模拟模式必须显式
  allow_simulation=True（CLI --allow-simulation），输出整体带 simulation
  标记；
- delivery 在省端无实际接口时如实返回 PENDING_RECEIPT（未接通），
  保留非完成状态，不伪造调用；
- batch 身份稳定：{目标实例|机构|表|模式|业务日}；attempt 版本化；
  同清单重试保持 stable_operation_id（target_executor）；
- 真实读取/装载的授权不在本模块产生：ActionBinding（K01）与
  PlatformApprovalVerifier（R04）由调用方注入，程序不得自批。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.services.reporting_pipeline.adapters.python_reader import (
    ReadBudget,
    RowSource,
)
from app.services.reporting_pipeline.apply_port import (
    ApplyPort,
    ApplyRequest,
    CommitUnknownRaised,
    StaticApprovalVerifier,
)
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    BatchState,
    ContractViolation,
    EndReason,
    PipelineAction,
    RowClassification,
)
from app.services.reporting_pipeline.durable_staging import DurableFileStageStore
from app.services.reporting_pipeline.planner import TimeWindow
from app.services.reporting_pipeline.readback_types import ColumnMeta
from app.services.reporting_pipeline.repositories import (
    ControlRepository,
    InMemoryControlRepository,
)
from app.services.reporting_pipeline.seed_loader import SeedBundle
from app.services.reporting_pipeline.target_executor import (
    ExecutorTargetConfig,
    SqlTargetApplyExecutor,
    TargetConnection,
)


class AssemblyRefused(ContractViolation):
    """装配被拒：缺真实输入，不得静默降级模拟。"""


@dataclass
class AssemblyInputs:
    """真实装配输入（CLI/调用方提供；None = 缺失即拒）。"""

    bundle: SeedBundle
    repository: ControlRepository | None = None
    stage_store: DurableFileStageStore | None = None
    # 源绑定：物理源 -> RowSource 工厂（生产由受控连接器构造）
    row_source_factory: Callable[[str], RowSource] | None = None
    # 表级 RowSource 工厂（批1-2a：按 canonical_table 解析冻结投影；
    # 与 row_source_factory 二选一，表级优先）
    table_row_source_factory: Callable[[str], RowSource] | None = None
    # 目标绑定：TargetConnection 工厂（生产由受控连接器+长期凭据构造）
    target_connection_factory: Callable[[], TargetConnection] | None = None
    # DataX 路由工厂（批1-3：engine=DATAX 表的固定暂存路线）
    datax_route_factory: Callable | None = None
    # 冻结运行配置（批1-1）：候选转完整 TaskSpec + 哈希冻结
    runtime_config: object | None = None
    # 版本账只读器（批1-4 CAS：键 → 上次登记源内容哈希）
    version_reader: Callable | None = None
    # 执行器/批准
    executor_id: str | None = None
    approval_refs: Sequence[str] = ()
    receipt_table: str | None = None
    system_time_column: str | None = None
    # 必须由平台装配；静态 approval_refs 仅供模拟，不能产生生产批准。
    production_apply_port: ApplyPort | None = None
    allow_simulation: bool = False


@dataclass
class TargetBindingConfig:
    target_instance: str
    tenant: str
    table: str
    key_columns: tuple[str, ...]
    write_columns: tuple[str, ...]


def logical_target_object(binding: TargetBindingConfig) -> str:
    """逻辑目标三元组：{instance}.{tenant}.{table末段}（表名可带 schema 前缀，
    身份取末段；SQL 对象名另用 binding.table 全名）。"""
    return (
        f"{binding.target_instance}.{binding.tenant}."
        f"{binding.table.rsplit('.', 1)[-1]}"
    )


def stable_batch_id(
    binding: TargetBindingConfig, mode: str, business_day: str
) -> str:
    """稳定批次身份（K04/A02）：目标三元组+模式+业务日，重试不重建。"""
    raw = "|".join(
        (binding.target_instance, binding.tenant, binding.table, mode, business_day)
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{binding.table}.{mode}.{business_day}.{digest}"


def next_attempt_id(repository: ControlRepository, batch_id: str) -> str:
    record = repository.get_batch(batch_id)
    return f"att{len(record.attempts) + 1:03d}"


def business_window(business_day: str, timezone_name: str = "Asia/Shanghai") -> TimeWindow:
    day = date.fromisoformat(business_day)
    start = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(timezone_name))
    return TimeWindow(start, start + timedelta(days=1))


def build_manifest(
    *,
    batch_id: str,
    attempt_id: str,
    task_id: str,
    config_version: str,
    source_identity: str,
    window: TimeWindow,
    rows: RowClassification,
    total_bytes: int,
    payload_sha256: str,
    engine: str = "PYTHON",
    source_visibility_cutoff: str | None = None,
    definition_fingerprint: str | None = None,
) -> BatchManifest:
    from app.services.reporting_pipeline.contracts import Engine

    return BatchManifest(
        batch_id=batch_id,
        attempt_id=attempt_id,
        task_id=task_id,
        config_version=config_version,
        definition_fingerprint=definition_fingerprint,
        source_identity=source_identity,
        window_fingerprint=window.fingerprint(),
        source_visibility_cutoff=(
            source_visibility_cutoff
            or datetime.now(timezone.utc).isoformat(timespec="seconds")
        ),
        rows=rows,
        pagination_complete=True,
        end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1,
        file_count=1,
        total_bytes=total_bytes,
        schema_version="v1",
        type_contract_version="v1",
        payload_sha256=payload_sha256,
        engine=Engine(engine),
    )


def _require_real(
    inputs: AssemblyInputs, what: str, value
):
    if value is None:
        raise AssemblyRefused(
            f"真实运行缺 {what}（REFUSED_MISSING_{what.upper()}）；"
            "不退回内存模拟。显式隔离验证请使用 --allow-simulation。"
        )
    return value


def _simulation_or_real(inputs: AssemblyInputs, what: str, value, simulator):
    if value is not None:
        return value
    if inputs.allow_simulation:
        return simulator()
    raise AssemblyRefused(
        f"真实运行缺 {what}（REFUSED_MISSING_{what.upper()}）；"
        "不退回内存模拟。显式隔离验证请使用 --allow-simulation。"
    )




def _coerce_time_like(name, value, time_like: dict):
    """视图把时间列暴露为 VARCHAR2(19) 字符串时按冻结目标类型转 datetime；
    解析失败原样返回（交质量门隔离，不静默丢弃）。"""
    if not time_like or name not in time_like or not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    from datetime import datetime

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return value

class ProductionAssembly:
    """六真实动作的装配与执行（repository 为唯一事实源）。"""

    def __init__(self, inputs: AssemblyInputs, *, simulation: bool) -> None:
        self.inputs = inputs
        self.simulation = simulation
        self.bundle = inputs.bundle

    # -- 装配 ------------------------------------------------------------

    @classmethod
    def build(
        cls,
        inputs: AssemblyInputs,
        *,
        real: bool = True,
    ) -> "ProductionAssembly":
        if real:
            _require_real(inputs, "state_db_repository", inputs.repository)
            _require_real(inputs, "stage_root", inputs.stage_store)
            if isinstance(inputs.repository, InMemoryControlRepository):
                raise AssemblyRefused("REFUSED_VOLATILE_STATE：真实运行禁止使用内存仓储")
            return cls(inputs, simulation=False)
        if not inputs.allow_simulation:
            raise AssemblyRefused(
                "模拟模式必须显式 allow_simulation=True（拒绝静默回退模拟）"
            )
        inputs.repository = inputs.repository or InMemoryControlRepository()
        if inputs.stage_store is None:
            import tempfile

            inputs.stage_store = DurableFileStageStore(
                tempfile.mkdtemp(prefix="r189t1-sim-stage-")
            )
        return cls(inputs, simulation=True)

    def _repo(self) -> ControlRepository:
        return self.inputs.repository  # build 已保证非空

    def resolve_spec(self, table: str):
        for spec in self.bundle.tasks:
            if spec.canonical_table == table:
                return spec
        raise AssemblyRefused(f"任务包中不存在表: {table}")

    def runtime_spec(self, table: str):
        """冻结运行配置的单表完整 TaskSpec（批1-1）；无冻结配置返回 None。"""
        if self.inputs.runtime_config is None:
            return None
        try:
            return self.inputs.runtime_config.table(table)
        except Exception as exc:  # RuntimeConfigError 等
            raise AssemblyRefused(f"冻结运行配置解析失败 [{table}]: {exc}") from exc

    def _config_identity(self, table: str) -> tuple[str, str | None]:
        """配置身份：(config_version, definition_fingerprint)。

        有冻结运行配置时以冻结件为准（版本+表指纹），否则回退种子包。
        """
        spec_rt = self.runtime_spec(table)
        if spec_rt is not None:
            rc = self.inputs.runtime_config
            return f"{rc.version}:{rc.file_sha256[:12]}", spec_rt.fingerprint
        spec = self.resolve_spec(table)
        return spec.config_version, spec.definition_fingerprint

    def require_action(
        self, spec, action: PipelineAction, bindings: Sequence = ()
    ) -> None:
        """K01：enabled 走全链；未 enabled 须有有效动作绑定。

        冻结运行配置在档时按冻结件合成已核规格校验（verified 事实来自
        冻结件与核验证据，非放宽门禁）。
        """
        spec_rt = self.runtime_spec(spec.canonical_table)
        if spec_rt is not None:
            from app.services.reporting_pipeline.runtime_config import (
                synthesize_task_spec,
            )

            spec = synthesize_task_spec(spec_rt, seed_spec=spec)
        if spec.enabled:
            spec.validate_action(action)
            return
        from app.services.reporting_pipeline.runtime import ActionBinding

        now = datetime.now(timezone.utc)
        ok = any(
            isinstance(b, ActionBinding)
            and b.canonical_table == spec.canonical_table
            and b.active(now)
            and b.covers(action)
            for b in bindings
        )
        if not ok:
            raise AssemblyRefused(
                f"[{spec.canonical_table}] 未 enabled 且无有效 {action.value} "
                "动作绑定（K01：不得绕过整链门禁派发本地动作）"
            )
        spec.validate_action(action)

    def _check_binding(self, spec, binding: TargetBindingConfig, record=None) -> None:
        if self.simulation:
            return
        target = spec.target
        expected = (f"{target.host}:{target.port}/{target.service}", target.owner, target.table)
        actual = (binding.target_instance, binding.tenant, binding.table)
        spec_rt = self.runtime_spec(spec.canonical_table)
        if spec_rt is not None:
            # 冻结运行配置（批1-1）为目标绑定权威：身份/稳定键/写列
            # 全部以哈希冻结件为准（隔离验收冻结件的目标身份与种子包
            # 不同属正常，由 environment 标记区分）。
            frozen = (
                spec_rt.target_instance, spec_rt.tenant, spec_rt.target_table
            )
            if actual != frozen:
                raise AssemblyRefused("REFUSED_TARGET_BINDING：目标与冻结运行配置不符")
            write_cols = spec_rt.write_columns()
            if (not spec_rt.stable_key
                    or tuple(spec_rt.stable_key) != binding.key_columns
                    or not set(binding.key_columns).issubset(binding.write_columns)
                    or not binding.write_columns
                    or len(set(binding.write_columns)) != len(binding.write_columns)
                    or tuple(sorted(binding.write_columns)) != tuple(sorted(write_cols))):
                raise AssemblyRefused("REFUSED_COLUMN_BINDING：稳定键或写列与冻结投影不符")
            if self.inputs.system_time_column in binding.write_columns:
                raise AssemblyRefused("REFUSED_CLOCK_BINDING：SYSTEM_TIME只能由目标事务生成")
        else:
            if actual != expected or not target.current_identity_verified:
                raise AssemblyRefused("REFUSED_TARGET_BINDING：目标与已核任务配置不符")
            names = {field.name for field in spec.projection}
            if (not spec.stable_key.verified or tuple(spec.stable_key.candidate) != binding.key_columns
                    or not set(binding.key_columns).issubset(binding.write_columns)
                    or not binding.write_columns or len(set(binding.write_columns)) != len(binding.write_columns)
                    or set(binding.write_columns) != names - {self.inputs.system_time_column}):
                raise AssemblyRefused("REFUSED_COLUMN_BINDING：稳定键或写列不在已核投影中")
            if self.inputs.system_time_column in binding.write_columns:
                raise AssemblyRefused("REFUSED_CLOCK_BINDING：SYSTEM_TIME只能由目标事务生成")
        if record is not None and actual != (
            record.target_instance, record.tenant, record.target_table
        ):
            raise AssemblyRefused("REFUSED_BATCH_BINDING：目标与原批次冻结范围不符")

    def _read_target_snapshot(self, binding, keys):
        factory = _require_real(self.inputs, "target_connection_factory", self.inputs.target_connection_factory)
        conn = factory()
        close = getattr(conn, "close", None)
        if not callable(close):
            raise AssemblyRefused("REFUSED_CONNECTION_LIFECYCLE：目标连接必须支持close")
        try:
            conn.begin()
            # 在第二条写连接开始前释放预览锁，避免同进程互相等待。
            return {key: dict(row) for key, row in conn.lock_and_read_rows(
                binding.table, binding.key_columns, keys
            ).items()}
        finally:
            try:
                conn.rollback()
            finally:
                close()

    def _compute_partition(self, spec_rt, binding, rows, target_rows):
        """批1-4：SNAPSHOT_DIFF CAS + 父存在性分区（真实模式专用）。"""
        from app.services.reporting_pipeline.apply_policy import (
            build_parent_presence,
            snapshot_diff_partition,
        )

        metas = list(self._column_meta(binding, spec_rt).values())
        target_object = logical_target_object(binding)
        version_reader = self.inputs.version_reader
        if version_reader is None:
            raise AssemblyRefused(
                "REFUSED_VERSION_READER：SNAPSHOT_DIFF 分区需版本账只读器（耐久）"
            )

        def registered(key: tuple) -> str | None:
            return version_reader(target_object, key)

        parent_present = None
        if spec_rt.parent_table and spec_rt.parent_key_column:
            parent_spec = self.runtime_spec(spec_rt.parent_table)
            if parent_spec is None:
                raise AssemblyRefused(
                    f"冻结配置缺父表 {spec_rt.parent_table}，父存在性无法核验"
                )
            parent_binding = TargetBindingConfig(
                target_instance=binding.target_instance,
                tenant=binding.tenant,
                table=parent_spec.target_table,
                key_columns=tuple(parent_spec.stable_key),
                write_columns=parent_spec.write_columns(),
            )
            parent_values = sorted(
                {
                    row.get(spec_rt.parent_key_column)
                    for row in rows
                    if row.get(spec_rt.parent_key_column) is not None
                },
                key=str,
            )
            parent_keys = [(value,) for value in parent_values]
            parent_rows = self._read_target_snapshot(parent_binding, parent_keys)
            parent_present = build_parent_presence(
                parent_rows=parent_rows,
                parent_key_columns=tuple(parent_spec.stable_key),
            )
        return snapshot_diff_partition(
            rows=rows,
            key_columns=binding.key_columns,
            metas=metas,
            target_rows=target_rows,
            registered_version=registered,
            parent_present=parent_present,
            parent_key_column=spec_rt.parent_key_column,
        )

    # -- capture -----------------------------------------------------------

    def capture(
        self,
        *,
        table: str,
        business_day: str,
        binding: TargetBindingConfig,
        mode: str = "T1",
        bindings: Sequence = (),
        dry_run: bool = False,
        read_budget: ReadBudget | None = None,
        sim_rows_provider: Callable[[], list[dict]] | None = None,
    ) -> dict:
        from app.services.reporting_pipeline.adapters.python_reader import (
            PythonReaderAdapter,
        )

        spec = self.resolve_spec(table)
        self._check_binding(spec, binding)
        batch_id = stable_batch_id(binding, mode, business_day)
        window = business_window(business_day, spec.time_semantics.timezone or "Asia/Shanghai")
        plan_doc = {
            "batch_id": batch_id,
            "table": table,
            "business_day": business_day,
            "mode": mode,
            "window": window.fingerprint(),
            "target_binding": {
                "target_instance": binding.target_instance,
                "tenant": binding.tenant,
                "table": binding.table,
            },
            "engine": "PYTHON" if self.inputs.row_source_factory else (
                "PYTHON(sim)" if self.simulation else None
            ),
            "dry_run": dry_run,
        }
        if dry_run:
            # dry-run 不授予任何动作：只给出可派发性判定（K01 门禁结果）
            try:
                self.require_action(spec, PipelineAction.CAPTURE, bindings)
                dispatchable, blocked_by = True, None
            except AssemblyRefused as exc:
                dispatchable, blocked_by = False, str(exc)
            plan_doc["dispatchable"] = dispatchable
            plan_doc["blocked_by"] = blocked_by
            plan_doc["action_readiness"] = spec.action_readiness()
            return {"ok": True, "dry_run": True, "plan": plan_doc}

        self.require_action(spec, PipelineAction.CAPTURE, bindings)
        spec_rt = self.runtime_spec(table)
        if not self.simulation:
            if spec_rt is not None and spec_rt.engine == "DATAX":
                if self.inputs.datax_route_factory is None:
                    raise AssemblyRefused(
                        "REFUSED_CAPTURE_ROUTE：engine=DATAX 须装配 DataX 固定暂存路线工厂"
                    )
            elif self.inputs.row_source_factory is None and self.inputs.table_row_source_factory is None:
                raise AssemblyRefused(
                    "真实运行缺 row_source_factory/table_row_source_factory"
                    "（REFUSED_MISSING_ROW_SOURCE_FACTORY）；不退回内存模拟"
                )
            if spec_rt is None and (
                spec.engine.value != "PYTHON" or spec.dual_source()
            ):
                raise AssemblyRefused("REFUSED_CAPTURE_ROUTE：DataX或双源任务须接专用路由，禁止按单源Python读取")

        repo = self._repo()
        try:
            record = repo.get_batch(batch_id)
            if record.state not in (
                BatchState.PLANNED, BatchState.RETRYABLE,
                BatchState.CAPTURING, BatchState.WAITING_SOURCE,
            ):
                return {
                    "ok": False,
                    "refused": f"批次 {batch_id} 处于 {record.state.value}，"
                    "不允许重复 capture（按 resume/retry 语义续跑）",
                    "batch_id": batch_id,
                }
        except ContractViolation:
            record = repo.create_batch(
                batch_id, table, business_day,
                target_instance=binding.target_instance,
                tenant=binding.tenant,
                target_table=binding.table,
            )
        if record.state != BatchState.CAPTURING:
            repo.transition_batch(batch_id, BatchState.CAPTURING, reason="capture 启动")

        if self.simulation:
            if sim_rows_provider is None:
                repo.transition_batch(
                    batch_id, BatchState.WAITING_INPUT,
                    reason="模拟 capture 缺 sim_rows_provider",
                )
                return {"ok": False, "refused": "模拟 capture 需要 sim_rows_provider", "batch_id": batch_id}
            rows = sim_rows_provider()
        else:
            attempt_hint = next_attempt_id(repo, batch_id)
            if spec_rt is not None and spec_rt.engine == "DATAX":
                outcome = self.inputs.datax_route_factory(table, window, attempt_hint)
                if not outcome.complete:
                    repo.record_gap(
                        table, window, f"capture 不完整: {outcome.end_reason}"
                    )
                    repo.transition_batch(
                        batch_id, BatchState.RETRYABLE,
                        reason=f"DataX 捕获不完整: {outcome.end_reason}",
                    )
                    return {
                        "ok": False, "batch_id": batch_id,
                        "state": outcome.end_reason, "window": window.fingerprint(),
                    }
                rows = list(outcome.rows)
            else:
                if spec_rt is not None and self.inputs.table_row_source_factory is not None:
                    source = self.inputs.table_row_source_factory(table)
                    budget_kwargs = {
                        name: spec_rt.budget.get(name)
                        for name in (
                            "max_rows_per_slice", "max_bytes_per_slice", "max_attempts",
                        )
                        if spec_rt.budget.get(name) is not None
                    }
                    budget = read_budget or ReadBudget(**budget_kwargs)
                else:
                    factory = _require_real(
                        self.inputs, "row_source_factory", self.inputs.row_source_factory
                    )
                    physical = next(
                        (s.source_group for s in spec.source_candidates if s.role == "primary"),
                        None,
                    )
                    if physical is None:
                        repo.transition_batch(
                            batch_id, BatchState.WAITING_INPUT, reason="无 primary 源"
                        )
                        return {"ok": False, "refused": "无 primary 源候选", "batch_id": batch_id}
                    source = factory(physical)
                    budget = read_budget or ReadBudget(**{
                        name: getattr(spec.resource_budget, name)
                        for name in ("max_rows_per_slice", "max_bytes_per_slice", "max_attempts")
                        if getattr(spec.resource_budget, name) is not None
                    })
                adapter = PythonReaderAdapter(source, budget)
                keyset_kwargs = {}
                if spec_rt is not None:
                    keyset_kwargs = {
                        "keyset_columns": tuple(spec_rt.stable_key),
                        "keyset_unique_verified": True,
                    }
                result = adapter.capture_window(window, **keyset_kwargs)
                if not result.complete:
                    repo.record_gap(
                        table, window, f"capture 不完整: {result.error_class}"
                    )
                    repo.transition_batch(
                        batch_id, BatchState.RETRYABLE, reason="捕获不完整已记缺口"
                    )
                    return {
                        "ok": False, "batch_id": batch_id,
                        "state": result.error_class, "window": window.fingerprint(),
                    }
            if spec_rt is not None:
                names = [field.name for field in spec_rt.projection]
            else:
                names = [field.name for field in sorted(spec.projection, key=lambda field: field.order)]
            if not names or len(names) != len(set(names)):
                raise AssemblyRefused("REFUSED_PROJECTION：投影为空或列名重复")
            staged_rows = []
            time_like = {}
            if spec_rt is not None:
                from app.services.reporting_pipeline.readback_types import TIME_LIKE

                time_like = {
                    field.name: field.target_type.upper().split("(")[0].strip()
                    for field in spec_rt.projection
                    if field.target_type.upper().split("(")[0].strip() in TIME_LIKE
                }
            for row in (rows if spec_rt is not None and spec_rt.engine == "DATAX" else result.rows):
                if isinstance(row, dict):
                    if set(row.keys()) != set(names):
                        raise AssemblyRefused("REFUSED_ROW_WIDTH：源行列集与冻结投影不一致，禁止截断")
                    staged_rows.append({
                        name: _coerce_time_like(name, row.get(name), time_like)
                        for name in names
                    })
                else:
                    if len(row) != len(names):
                        raise AssemblyRefused("REFUSED_ROW_WIDTH：源行列数与冻结投影不一致，禁止截断")
                    staged_rows.append({
                        name: _coerce_time_like(name, value, time_like)
                        for name, value in zip(names, row)
                    })
            rows = staged_rows

        attempt_id = next_attempt_id(repo, batch_id)
        stage = self.inputs.stage_store
        stage.begin_attempt(batch_id, attempt_id)
        # 暂存格式：JSON 行（每行一条记录）——与 iter_chunk_rows 流式读一致
        from app.services.reporting_pipeline.durable_staging import encode_json_rows
        payload_bytes = encode_json_rows(rows)
        stage.write_chunk(
            batch_id, attempt_id, "chunk-0001", payload_bytes,
            row_count=len(rows),
        )
        config_version, definition_fingerprint = self._config_identity(table)
        manifest = build_manifest(
            batch_id=batch_id,
            attempt_id=attempt_id,
            task_id=table,
            config_version=config_version,
            source_identity=str(
                [s.object_id for s in spec.source_candidates]
            ) if spec_rt is None else (
                f"{spec_rt.source_group}:{spec_rt.source_object}"
                + (f"@sha256:{spec_rt.object_sha256[:12]}" if spec_rt.object_sha256 else "")
            ),
            window=window,
            rows=RowClassification(source_read_rows=len(rows), valid=len(rows)),
            total_bytes=len(payload_bytes),
            payload_sha256=hashlib.sha256(payload_bytes).hexdigest(),
            engine=spec_rt.engine if spec_rt is not None else spec.engine.value,
            definition_fingerprint=definition_fingerprint,
        )
        stage.mark_complete_against_manifest(
            batch_id, attempt_id, manifest,
            source_identity=manifest.source_identity,
            definition_fingerprint=definition_fingerprint,
        )
        repo.attach_attempt_manifest(batch_id, manifest)
        # 推进 CAPTURED 前必须选中完整 attempt（状态机要求 manifest 在档）
        repo.select_manifest(batch_id)
        repo.transition_batch(
            batch_id, BatchState.CAPTURED, reason="capture 完整",
            evidence=manifest.attempt_id,
        )
        return {
            "ok": True,
            "batch_id": batch_id,
            "attempt_id": attempt_id,
            "rows": len(rows),
            "plan": plan_doc,
            "simulation": self.simulation,
        }

    # -- verify ------------------------------------------------------------

    def verify(
        self,
        *,
        batch_id: str,
        column_meta: Mapping[str, ColumnMeta] | None = None,
        group_key_columns: Sequence[str] | None = None,
        sim_quality_check: Callable[[list[dict]], dict] | None = None,
    ) -> dict:
        from app.services.reporting_pipeline.quality import QualityService

        repo = self._repo()
        record = repo.get_batch(batch_id)
        spec = self.resolve_spec(record.task_id)
        spec_rt = self.runtime_spec(record.task_id)
        # 质量规则按冻结运行配置投影（种子包投影可能为空）
        verify_spec = spec_rt if spec_rt is not None else spec
        group_key_columns = tuple(
            group_key_columns
            or (spec_rt.stable_key if spec_rt is not None else spec.stable_key.candidate)
        )
        if not group_key_columns:
            raise AssemblyRefused("REFUSED_QUALITY_KEY：缺少已核稳定键")
        if record.state not in (
            BatchState.CAPTURED, BatchState.RETRYABLE,
        ):
            return {
                "ok": False,
                "refused": f"批次状态 {record.state.value} 不允许 verify（须 CAPTURED）",
                "batch_id": batch_id,
            }
        manifest = repo.select_manifest(batch_id)
        stage = self.inputs.stage_store
        if not stage.is_complete(batch_id, manifest.attempt_id):
            repo.transition_batch(
                batch_id, BatchState.RETRYABLE, reason="暂存不完整"
            )
            return {"ok": False, "refused": "暂存不完整，不能验证", "batch_id": batch_id}
        self._check_staged_manifest(manifest)
        rows = self._staged_rows(batch_id, manifest.attempt_id)
        repo.transition_batch(batch_id, BatchState.VALIDATING, reason="verify 启动")
        if self.simulation and sim_quality_check is not None:
            outcome_summary = sim_quality_check(rows)
        else:
            service = QualityService(
                group_key_columns=group_key_columns,
                column_meta=column_meta,
            )
            from app.services.reporting_pipeline.quality import RequiredRule, TypeRule, ByteLengthRule
            metas = column_meta or self._column_meta(TargetBindingConfig(
                "", "", verify_spec.canonical_table if hasattr(verify_spec, "canonical_table") else record.task_id,
                tuple(group_key_columns),
                tuple(field.name for field in verify_spec.projection),
            ), verify_spec)
            rules = [RequiredRule(tuple(group_key_columns))]
            for meta in metas.values():
                expected = {"NUMBER": "decimal", "DECIMAL": "decimal", "NUMERIC": "decimal",
                            "INT": "int", "INTEGER": "int", "DATE": "datetime", "TIMESTAMP": "datetime"}.get(meta.logical_type)
                if meta.logical_type in ("CHAR", "NCHAR", "VARCHAR", "VARCHAR2", "NVARCHAR2", "CLOB", "NCLOB", "TEXT"):
                    expected = "str"
                if expected:
                    rules.append(TypeRule(meta.name, expected))
            charset = (
                getattr(verify_spec, "target_charset", None) or "utf-8"
            )
            for field in verify_spec.projection:
                declared = re.fullmatch(r"(?:VAR)?CHAR2?\((\d+)\s*(?:BYTE)?\)", field.target_type.upper())
                if declared:
                    rules.append(
                        ByteLengthRule(field.name, int(declared.group(1)), charset)
                    )
            service.column_meta = dict(metas)
            outcome = service.verify(rows, rules=rules)
            outcome_summary = outcome.summary()
            outcome_summary["valid_rows"] = sum(
                classification == "VALID" for classification in outcome.classifications.values()
            )
        ok = bool(outcome_summary.get("valid_rows") == len(rows)) if outcome_summary else False
        if ok:
            repo.transition_batch(
                batch_id, BatchState.VALIDATED, reason="质量全通过",
                evidence=json.dumps(outcome_summary, ensure_ascii=False),
            )
        else:
            repo.transition_batch(
                batch_id, BatchState.QUARANTINED, reason="存在隔离组",
                evidence=json.dumps(outcome_summary, ensure_ascii=False),
            )
        return {
            "ok": ok,
            "batch_id": batch_id,
            "state": "VALIDATED" if ok else "QUARANTINED",
            "quality": outcome_summary,
            "rows": len(rows),
            "record_state_before": record.state.value,
            "simulation": self.simulation,
        }

    def _staged_rows(self, batch_id: str, attempt_id: str) -> list[dict]:
        """从耐久暂存流式读行（JSON 行分块；完整清单已由调用方核验）。"""
        stage = self.inputs.stage_store
        return list(stage.iter_chunk_rows(batch_id, attempt_id))

    def _check_staged_manifest(self, manifest: BatchManifest) -> None:
        config_version, definition_fingerprint = self._config_identity(manifest.task_id)
        if (manifest.config_version != config_version
                or manifest.definition_fingerprint != definition_fingerprint):
            raise AssemblyRefused("REFUSED_CONFIG_DRIFT：暂存后配置或视图定义变了，须复核后重新捕获")
        stage = self.inputs.stage_store
        document = stage.load_complete_document(manifest.batch_id, manifest.attempt_id)
        if (document.get("source_identity") != manifest.source_identity
                or document.get("window_fingerprint") != manifest.window_fingerprint
                or document.get("payload_sha256") != manifest.payload_sha256
                or document.get("definition_fingerprint") != manifest.definition_fingerprint):
            raise AssemblyRefused("REFUSED_STAGE_BINDING：暂存完整清单与原批次不符")
        # COMPLETE只证明当时完整；读取和写入前重算字节/行数/哈希。
        stage.mark_complete_against_manifest(
            manifest.batch_id, manifest.attempt_id, manifest,
            source_identity=manifest.source_identity,
            definition_fingerprint=manifest.definition_fingerprint,
        )

    # -- apply -------------------------------------------------------------

    def apply(
        self,
        *,
        batch_id: str,
        binding: TargetBindingConfig,
        approval_ref: str,
        executor_id: str | None = None,
        lease_resource: str | None = None,
        fencing_token: int | None = None,
        sim_target_rows: Mapping[tuple, Mapping] | None = None,
    ) -> dict:
        from datetime import datetime as _dt

        from app.services.reporting_pipeline.target_executor import (
            FakeTargetConnection,
        )
        from app.services.reporting_pipeline.apply_policy import record_partition_ledger

        repo = self._repo()
        record = repo.get_batch(batch_id)
        spec = self.resolve_spec(record.task_id)
        self._check_binding(spec, binding, record)
        if not self.simulation:
            port = _require_real(self.inputs, "production_apply_port", self.inputs.production_apply_port)
            if not port.production_mode or not port.enforce_fence:
                raise AssemblyRefused("REFUSED_PRODUCTION_GATE：禁止模拟批准或关闭围栏")
            expected_resource = f"target:{logical_target_object(binding)}"
            if lease_resource != expected_resource or fencing_token is None:
                raise AssemblyRefused("REFUSED_TARGET_LEASE：须提供本表有效写租约及围栏token")
            port.lease_validator(lease_resource, fencing_token)
        if record.state not in (
            BatchState.VALIDATED, BatchState.APPLY_PENDING,
        ):
            return {
                "ok": False,
                "refused": (
                    f"批次状态 {record.state.value} 不允许 apply"
                    "（须先 VALIDATED；跳过质量验证的装载被拒绝）"
                ),
                "batch_id": batch_id,
            }
        manifest = repo.select_manifest(batch_id)
        self._check_staged_manifest(manifest)
        rows = self._staged_rows(batch_id, manifest.attempt_id)
        # 目标既有行（生产=受控目标读；模拟=注入快照）
        if self.simulation:
            target_rows = dict(sim_target_rows or {})
        else:
            target_rows = self._read_target_snapshot(binding,
                [tuple(r.get(c) for c in binding.key_columns) for r in rows],
            )
        # 批1-4 SNAPSHOT_DIFF CAS 分区：坏组隔离留账、合法组继续
        spec_rt = self.runtime_spec(record.task_id)
        partition = None
        ledger_records: list[dict] = []
        if (not self.simulation and spec_rt is not None
                and spec_rt.change_mode == "SNAPSHOT_DIFF"):
            partition = self._compute_partition(
                spec_rt, binding, rows, target_rows,
            )
            ledger_records = record_partition_ledger(
                repo,
                batch_id=batch_id,
                canonical_table=record.task_id,
                partition=partition,
            )
            if not partition.ok_rows and (partition.conflict_keys or partition.missing_parent_keys):
                repo.transition_batch(
                    batch_id, BatchState.QUARANTINED,
                    reason="CAS/缺父分组后无合法组可装载",
                    evidence=json.dumps(partition.ledger_summary(), ensure_ascii=False),
                )
                return {
                    "ok": False,
                    "batch_id": batch_id,
                    "state": "QUARANTINED",
                    "partition": partition.ledger_summary(),
                    "quarantine_ledger": ledger_records,
                    "refused": "全部行进隔离组（CAS 冲突/缺父）：留账待处置，不整批盲写",
                    "simulation": self.simulation,
                }
            rows = list(partition.ok_rows)
        if self.simulation:
            port = ApplyPort(
                whitelisted_executors=[executor_id or "sql-target-apply-1"],
                approval_verifier=StaticApprovalVerifier(set(self.inputs.approval_refs)),
                enforce_fence=False,
            )
        if self.simulation:
            fake_conn = FakeTargetConnection(
                dict(target_rows), key_columns=binding.key_columns,
            )
            def executor_conn_factory() -> TargetConnection:
                return fake_conn
        else:
            executor_conn_factory = _require_real(
                self.inputs, "target_connection_factory",
                self.inputs.target_connection_factory,
            )
        config = ExecutorTargetConfig(
            target_instance=binding.target_instance,
            tenant=binding.tenant,
            table=binding.table,
            key_columns=binding.key_columns,
            write_columns=binding.write_columns,
            system_time_column=self.inputs.system_time_column,
            receipt_table=self.inputs.receipt_table,
        )
        executor = SqlTargetApplyExecutor(
            executor_conn_factory, config, simulation=self.simulation,
            fence_check=(lambda: port.lease_validator(lease_resource, fencing_token)) if not self.simulation else None,
            expected_target_rows=target_rows,
        )
        request = ApplyRequest(
            manifest=manifest,
            quality_verified=True,
            approval_ref=approval_ref,
            executor_id=executor_id or executor.executor_id,
            target_object=logical_target_object(binding),
            allowed_operations=("INSERT", "UPDATE"),
            idempotency_key_columns=binding.key_columns,
            rows=tuple(rows),
            # 列型以冻结件为准（种子包投影为空→默认 VARCHAR 会漏 CHAR 空格规整）
            column_meta=self._column_meta(binding, spec_rt if spec_rt is not None else spec),
            mode="MERGE",
            lease_resource=lease_resource,
            fencing_token=fencing_token,
            cas_preverified=partition is not None,
            row_version_evidences=(
                dict(partition.row_version_evidences) if partition is not None else None
            ),
        )
        if record.state in (BatchState.VALIDATED, BatchState.WAITING_APPROVAL):
            repo.transition_batch(
                batch_id, BatchState.APPLY_PENDING, reason="apply 门禁启动"
            )
        try:
            if not self.simulation:
                port.precheck(request, executor)
            plan = port.preview(request, target_rows)
            if plan.counts.get("CONFLICT"):
                raise AssemblyRefused("REFUSED_VERSION_CONFLICT：存在版本冲突，需隔离后续跑")
            repo.transition_batch(
                batch_id, BatchState.APPLYING, reason="apply 执行中"
            )
            result = port.apply(request, executor, target_rows=target_rows)
            if not result.committed:
                raise AssemblyRefused("REFUSED_NOT_COMMITTED：目标已回滚，不能标记APPLIED")
        except CommitUnknownRaised:
            # COMMIT_UNKNOWN：冻结该表（含依赖链）重叠写，先核目标凭据
            repo.transition_batch(
                batch_id, BatchState.COMMIT_UNKNOWN,
                reason="提交结果不明，冻结同表写者",
            )
            return {
                "ok": False,
                "batch_id": batch_id,
                "state": "COMMIT_UNKNOWN",
                "refused": "执行器结果不明：先核同事务提交凭据（回执表按 "
                           "operation_id 查），确认后再 APPLIED/APPLY_PENDING",
                "simulation": self.simulation,
            }
        except Exception as exc:  # ApplyRefused 等：不写目标，回 APPLY_PENDING
            import os as _os

            if _os.environ.get("T1_DEBUG_TRACEBACK"):
                import traceback as _tb

                _tb.print_exc()
            if repo.get_batch(batch_id).state != BatchState.APPLY_PENDING:
                try:
                    repo.transition_batch(
                        batch_id, BatchState.APPLY_PENDING,
                        reason=f"apply 被拒: {type(exc).__name__}",
                    )
                except Exception:  # noqa: BLE001 - APPLYING 后回退非法：留待恢复矩阵
                    pass
            return {
                "ok": False,
                "batch_id": batch_id,
                "refused": f"apply被拒：{type(exc).__name__}（详情仅在受控审计中查看）",
                "simulation": self.simulation,
            }
        repo.transition_batch(
            batch_id, BatchState.APPLIED, reason="提交回执已确认",
            evidence=(
                result.operation_id
                if partition is None
                else f"{result.operation_id}|partition={json.dumps(partition.ledger_summary(), ensure_ascii=False)}"
            ),
        )
        return {
            "ok": True,
            "batch_id": batch_id,
            "operation_id": result.operation_id,
            "rows_affected": result.rows_affected,
            "plan_counts": plan.counts,
            "partition": partition.ledger_summary() if partition is not None else None,
            "quarantine_ledger": ledger_records or None,
            "credential": {
                "operation_id": result.credential.operation_id,
                "manifest_hash": result.credential.manifest_hash,
                "rows_affected": result.credential.rows_affected,
            },
            "simulation": self.simulation,
            "applied_at": _dt.now(timezone.utc).isoformat(timespec="seconds"),
        }

    @staticmethod
    def _column_meta(binding: TargetBindingConfig, spec=None) -> dict[str, ColumnMeta]:
        types = {field.name: field.target_type for field in spec.projection} if spec else {}
        return {
            col: ColumnMeta(name=col, logical_type=re.split(r"[ (]", types.get(col, "VARCHAR").upper())[0])
            for col in binding.write_columns
        }

    # -- reconcile -----------------------------------------------------------

    def reconcile(
        self,
        *,
        batch_id: str,
        binding: TargetBindingConfig,
        sim_target_rows: Mapping[tuple, Mapping] | None = None,
    ) -> dict:
        from app.services.reporting_pipeline.readback_types import row_diff

        repo = self._repo()
        record = repo.get_batch(batch_id)
        spec = self.resolve_spec(record.task_id)
        self._check_binding(spec, binding, record)
        if record.state != BatchState.APPLIED:
            return {
                "ok": False,
                "refused": f"批次状态 {record.state.value} 不允许 reconcile（须 APPLIED）",
                "batch_id": batch_id,
            }
        manifest = repo.select_manifest(batch_id)
        self._check_staged_manifest(manifest)
        rows = self._staged_rows(batch_id, manifest.attempt_id)
        keys = [tuple(r.get(c) for c in binding.key_columns) for r in rows]
        if self.simulation:
            target_rows = dict(sim_target_rows or {})
        else:
            target_rows = self._read_target_snapshot(binding, keys)
        spec_rt = self.runtime_spec(record.task_id)
        metas = list(
            self._column_meta(binding, spec_rt if spec_rt is not None else spec).values()
        )
        # 批1-4/批1-5：开隔离组的键不计入 missing（留账未闭合单列），
        # 但存在未闭合隔离组时不转 RECONCILED（报送未闭合）。
        quarantined_keys: set[tuple] = set()
        if not self.simulation and spec_rt is not None and spec_rt.change_mode == "SNAPSHOT_DIFF":
            partition = self._compute_partition(spec_rt, binding, rows, target_rows)
            quarantined_keys = set(partition.conflict_keys) | set(partition.missing_parent_keys)
        diffs: list[dict] = []
        missing = [
            k for k in keys if k not in target_rows and k not in quarantined_keys
        ]
        quarantined_pending = sum(1 for k in keys if k in quarantined_keys)
        for row in rows:
            key = tuple(row.get(c) for c in binding.key_columns)
            if key in quarantined_keys:
                continue
            target_row = target_rows.get(key)
            if target_row is None:
                continue
            row_diffs = row_diff(row, target_row, metas)
            if row_diffs:
                diffs.append({"columns": [diff["column"] for diff in row_diffs]})
        ok = not missing and not diffs and not quarantined_pending
        recovery_result = None
        if ok:
            repo.transition_batch(
                batch_id, BatchState.RECONCILED, reason="全键回读一致",
                evidence=f"keys={len(keys)}",
            )
            # 批1-5 恢复执行化：回读一致后关对应缺口、按门禁推水位、
            # 补发 RECOVERED（如有 OPEN 事件）
            from app.services.reporting_pipeline.recovery import RecoveryExecutor

            executor = RecoveryExecutor(repo)
            recovery_result = executor.close_success(
                batch_id=batch_id,
                task_id=record.task_id,
                business_day=record.business_day,
                window_fingerprint=manifest.window_fingerprint,
                evidence=f"reconcile:keys={len(keys)}",
            )
        return {
            "ok": ok,
            "batch_id": batch_id,
            "keys_checked": len(keys),
            "missing_keys": len(missing),
            "content_diffs": len(diffs),
            "quarantined_pending": quarantined_pending,
            "diff_sample": diffs[:5],
            "recovery": recovery_result,
            "state_before": record.state.value,
            "simulation": self.simulation,
        }

    # -- delivery -----------------------------------------------------------

    def delivery(self, *, batch_id: str) -> dict:
        """省端无实际接口：如实 PENDING_RECEIPT，不伪造调用（A02）。"""
        repo = self._repo()
        record = repo.get_batch(batch_id)
        if record.state != BatchState.RECONCILED:
            return {
                "ok": False,
                "refused": f"批次 {record.state.value} 未闭合到 RECONCILED，"
                "不进入报送；省端接口未接通，delivery 不伪造调用",
                "batch_id": batch_id,
            }
        return {
            "ok": True,
            "batch_id": batch_id,
            "delivery_state": "PENDING_RECEIPT",
            "note": "省端逐表回执接口未接通：保持非完成状态（NOT_SUBMITTED），"
                    "不得把 REPORT_READY 涂绿；B04 接口确认后接入",
            "simulation": self.simulation,
        }

    # -- retry --------------------------------------------------------------

    def retry(self, *, batch_id: str) -> dict:
        from app.services.reporting_pipeline.recovery import RecoveryService

        repo = self._repo()
        record = repo.get_batch(batch_id)
        service = RecoveryService(repo)
        action = service.resume(batch_id)
        return {
            "ok": True,
            "batch_id": batch_id,
            "state": record.state.value,
            "next_action": action.to_dict(),
            "note": "按恢复矩阵续跑；capture/apply 由调用方按 next_action 重新"
                    "发起（同稳定 batch_id，attempt 版本化，operation_id 不变）",
            "simulation": self.simulation,
        }
