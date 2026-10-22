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
    # 目标绑定：TargetConnection 工厂（生产由受控连接器+长期凭据构造）
    target_connection_factory: Callable[[], TargetConnection] | None = None
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

    def require_action(
        self, spec, action: PipelineAction, bindings: Sequence = ()
    ) -> None:
        """K01：enabled 走全链；未 enabled 须有有效动作绑定。"""
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
        if actual != expected or not target.current_identity_verified:
            raise AssemblyRefused("REFUSED_TARGET_BINDING：目标与已核任务配置不符")
        if record is not None and actual != (
            record.target_instance, record.tenant, record.target_table
        ):
            raise AssemblyRefused("REFUSED_BATCH_BINDING：目标与原批次冻结范围不符")
        names = {field.name for field in spec.projection}
        if (not spec.stable_key.verified or tuple(spec.stable_key.candidate) != binding.key_columns
                or not set(binding.key_columns).issubset(binding.write_columns)
                or not binding.write_columns or len(set(binding.write_columns)) != len(binding.write_columns)
                or set(binding.write_columns) != names - {self.inputs.system_time_column}):
            raise AssemblyRefused("REFUSED_COLUMN_BINDING：稳定键或写列不在已核投影中")
        if self.inputs.system_time_column in binding.write_columns:
            raise AssemblyRefused("REFUSED_CLOCK_BINDING：SYSTEM_TIME只能由目标事务生成")

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
        if not self.simulation:
            _require_real(self.inputs, "row_source_factory", self.inputs.row_source_factory)
            if spec.engine.value != "PYTHON" or spec.dual_source():
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
            factory = _require_real(self.inputs, "row_source_factory", self.inputs.row_source_factory)
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
            result = adapter.capture_window(window)
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
            names = [field.name for field in sorted(spec.projection, key=lambda field: field.order)]
            if not names or len(names) != len(set(names)):
                raise AssemblyRefused("REFUSED_PROJECTION：投影为空或列名重复")
            rows = []
            for row in result.rows:
                if len(row) != len(names):
                    raise AssemblyRefused("REFUSED_ROW_WIDTH：源行列数与冻结投影不一致，禁止截断")
                rows.append(dict(zip(names, row)))

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
        manifest = build_manifest(
            batch_id=batch_id,
            attempt_id=attempt_id,
            task_id=table,
            config_version=spec.config_version,
            source_identity=str(
                [s.object_id for s in spec.source_candidates]
            ),
            window=window,
            rows=RowClassification(source_read_rows=len(rows), valid=len(rows)),
            total_bytes=len(payload_bytes),
            payload_sha256=hashlib.sha256(payload_bytes).hexdigest(),
            engine=spec.engine.value,
            definition_fingerprint=spec.definition_fingerprint,
        )
        stage.mark_complete_against_manifest(
            batch_id, attempt_id, manifest,
            source_identity=manifest.source_identity,
            definition_fingerprint=spec.definition_fingerprint,
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
        group_key_columns = tuple(group_key_columns or spec.stable_key.candidate)
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
                "", "", spec.canonical_table, tuple(group_key_columns),
                tuple(field.name for field in spec.projection),
            ), spec)
            rules = [RequiredRule(tuple(group_key_columns))]
            for meta in metas.values():
                expected = {"NUMBER": "decimal", "DECIMAL": "decimal", "NUMERIC": "decimal",
                            "INT": "int", "INTEGER": "int", "DATE": "datetime", "TIMESTAMP": "datetime"}.get(meta.logical_type)
                if meta.logical_type in ("CHAR", "NCHAR", "VARCHAR", "VARCHAR2", "NVARCHAR2", "CLOB", "NCLOB", "TEXT"):
                    expected = "str"
                if expected:
                    rules.append(TypeRule(meta.name, expected))
            for field in spec.projection:
                declared = re.fullmatch(r"(?:VAR)?CHAR2?\((\d+)\s*(?:BYTE)?\)", field.target_type.upper())
                if declared:
                    rules.append(ByteLengthRule(field.name, int(declared.group(1))))
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
        spec = self.resolve_spec(manifest.task_id)
        if (manifest.config_version != spec.config_version
                or manifest.definition_fingerprint != spec.definition_fingerprint):
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

        repo = self._repo()
        record = repo.get_batch(batch_id)
        spec = self.resolve_spec(record.task_id)
        self._check_binding(spec, binding, record)
        if not self.simulation:
            port = _require_real(self.inputs, "production_apply_port", self.inputs.production_apply_port)
            if not port.production_mode or not port.enforce_fence:
                raise AssemblyRefused("REFUSED_PRODUCTION_GATE：禁止模拟批准或关闭围栏")
            expected_resource = f"target:{binding.target_instance}.{binding.tenant}.{binding.table}"
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
            target_object=f"{binding.target_instance}.{binding.tenant}.{binding.table}",
            allowed_operations=("INSERT", "UPDATE"),
            idempotency_key_columns=binding.key_columns,
            rows=tuple(rows),
            column_meta=self._column_meta(binding, spec),
            mode="MERGE",
            lease_resource=lease_resource,
            fencing_token=fencing_token,
        )
        if record.state in (BatchState.VALIDATED, BatchState.WAITING_APPROVAL):
            repo.transition_batch(
                batch_id, BatchState.APPLY_PENDING, reason="apply 门禁启动"
            )
        try:
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
            if repo.get_batch(batch_id).state != BatchState.APPLY_PENDING:
                repo.transition_batch(
                    batch_id, BatchState.APPLY_PENDING,
                    reason=f"apply 被拒: {type(exc).__name__}",
                )
            return {
                "ok": False,
                "batch_id": batch_id,
                "refused": f"apply被拒：{type(exc).__name__}（详情仅在受控审计中查看）",
                "simulation": self.simulation,
            }
        repo.transition_batch(
            batch_id, BatchState.APPLIED, reason="提交回执已确认",
            evidence=result.operation_id,
        )
        return {
            "ok": True,
            "batch_id": batch_id,
            "operation_id": result.operation_id,
            "rows_affected": result.rows_affected,
            "plan_counts": plan.counts,
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
        metas = list(self._column_meta(binding, spec).values())
        diffs: list[dict] = []
        missing = [k for k in keys if k not in target_rows]
        for row in rows:
            key = tuple(row.get(c) for c in binding.key_columns)
            target_row = target_rows.get(key)
            if target_row is None:
                continue
            row_diffs = row_diff(row, target_row, metas)
            if row_diffs:
                diffs.append({"columns": [diff["column"] for diff in row_diffs]})
        ok = not missing and not diffs
        if ok:
            repo.transition_batch(
                batch_id, BatchState.RECONCILED, reason="全键回读一致",
                evidence=f"keys={len(keys)}",
            )
        return {
            "ok": ok,
            "batch_id": batch_id,
            "keys_checked": len(keys),
            "missing_keys": len(missing),
            "content_diffs": len(diffs),
            "diff_sample": diffs[:5],
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
