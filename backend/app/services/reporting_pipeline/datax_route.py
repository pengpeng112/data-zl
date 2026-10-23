"""DataX 采集路由（第一批批1-3）：与 Python 路线同一流程。

DataX 只走固定 MySQL 暂存路线（MysqlStageRoute）：
1. 渲染受限 job（白名单模板 + 路线指纹 + 范围谓词复核）；
2. 授权 worker 把凭据占位解析进 0600 私有 job 文件（结束清理）；
3. 真实进程执行（参数数组无 shell；读/写/dirty 指标三条件齐全才算成功）；
4. 从暂存表回收行 → 行数与 DataX 写入指标核对（少一行都算不完整）；
5. 映射为冻结投影命名行 → 交统一耐久暂存与装载端；
6. 导出回收：装载核验后清理暂存表（表级隔离，防串批）。

超预算继续拆窗（月→日→小时递归二分）；最小粒度仍超限且模板不支持
keyset 时 PARKED 转工单，不截断成功。真实 DataX 引擎实测须 8.53
环境（本机隔离验收用受控假进程 + 假暂存访问器，如实标注）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from app.services.reporting_pipeline.adapters.datax_runner import (
    DataXRunner,
    DataxJobTemplate,
    JobFileWorkspace,
    MysqlStageRoute,
    render_job_for_stage_route,
)
from app.services.reporting_pipeline.adapters.python_reader import ReadBudget
from app.services.reporting_pipeline.planner import SplitNode, TimeWindow


class DataxRouteError(Exception):
    """DataX 路由执行失败（安全错误码，不含 SQL/患者数据）。"""


@dataclass
class DataxCaptureOutcome:
    complete: bool
    rows: list[dict]
    total_bytes: int
    end_reason: str  # WINDOW_COMPLETE / SPLIT_REQUIRED / DATAX_* / PARKED
    rows_read: int | None = None
    rows_written: int | None = None
    split_root: SplitNode | None = None


class StageTableAccess:
    """暂存表访问协议：读回收 + 清理（生产=8.53 MySQL；隔离=假实现）。"""

    def read_rows(self, stage_table: str, columns: Sequence[str]) -> list[tuple]: ...
    def drop_table(self, stage_table: str) -> None: ...


class DataXCaptureRoute:
    """单表 DataX 采集路由（模板+路线+执行器+暂存访问全部注入）。"""

    def __init__(
        self,
        *,
        template: DataxJobTemplate,
        route: MysqlStageRoute,
        runner: DataXRunner,
        workspace: JobFileWorkspace,
        stage_access: StageTableAccess,
        source_object: str,
        stage_table_prefix: str,
        column_names: Sequence[str],
        budget: ReadBudget | None = None,
    ) -> None:
        self.template = template
        self.route = route
        self.runner = runner
        self.workspace = workspace
        self.stage_access = stage_access
        self.source_object = source_object
        self.stage_table_prefix = stage_table_prefix
        self.column_names = tuple(column_names)
        self.budget = budget or ReadBudget()

    def capture_window(
        self, window: TimeWindow, *, attempt_id: str, harvest: bool = True
    ) -> DataxCaptureOutcome:
        stage_table = self._stage_table(attempt_id)
        job = render_job_for_stage_route(
            self.template,
            route=self.route,
            source_object=self.source_object,
            stage_table=stage_table,
            window_start=self._fmt(window.start),
            window_end_exclusive=self._fmt(window.end_exclusive),
        )
        job_file = self.workspace.materialize(job, attempt_id)
        try:
            run = self.runner.run_capture(job, attempt_id, job_file=job_file)
        finally:
            self.workspace.cleanup(job_file)
        if not run.success:
            return DataxCaptureOutcome(
                complete=False, rows=[], total_bytes=0,
                end_reason=f"DATAX_{run.end_state}",
                rows_read=run.rows_read, rows_written=run.rows_written,
            )
        rows_written = run.rows_written or 0
        if rows_written > self.budget.max_rows_per_slice:
            # 超行预算：拆窗重跑（本窗结果弃用，不回收装载）
            self.stage_access.drop_table(stage_table)
            return self._split_window(window, attempt_id)
        if not harvest:
            self.stage_access.drop_table(stage_table)
            return DataxCaptureOutcome(
                complete=True, rows=[], total_bytes=0,
                end_reason="WINDOW_COMPLETE",
                rows_read=run.rows_read, rows_written=rows_written,
            )
        raw_rows = self.stage_access.read_rows(stage_table, self.column_names)
        try:
            if len(raw_rows) != rows_written:
                raise DataxRouteError(
                    f"STAGE_ROW_MISMATCH: 暂存回收 {len(raw_rows)} 行 != "
                    f"DataX 写入 {rows_written} 行（不完整，禁止装载）"
                )
            rows = [
                dict(zip(self.column_names, raw)) for raw in raw_rows
            ]
            total_bytes = sum(
                len(str(value).encode("utf-8")) for row in rows for value in row.values()
            )
            return DataxCaptureOutcome(
                complete=True, rows=rows, total_bytes=total_bytes,
                end_reason="WINDOW_COMPLETE",
                rows_read=run.rows_read, rows_written=rows_written,
            )
        finally:
            # 导出回收：行已进入进程内结果，暂存表即弃（耐久暂存在上层）
            self.stage_access.drop_table(stage_table)

    # -- 内部 ---------------------------------------------------------------

    def _split_window(self, window: TimeWindow, attempt_id: str) -> DataxCaptureOutcome:
        """整窗超限后的拆分：不再重读根窗（根结果已弃用），直接对半拆子窗。"""
        root = SplitNode(window=window)
        if not window.can_split():
            root.status = "PARKED"
            root.reason = "最小粒度仍超限且 DataX 模板无 keyset，转待处理工单"
            return DataxCaptureOutcome(
                complete=False, rows=[], total_bytes=0,
                end_reason="SPLIT_REQUIRED", split_root=root,
            )
        root.split(max_depth=self.budget.max_split_depth)
        collected = []
        for child in root.children:
            part = self._split_collect(child, attempt_id)
            if part is None:
                return DataxCaptureOutcome(
                    complete=False, rows=[], total_bytes=0,
                    end_reason="SPLIT_REQUIRED", split_root=root,
                )
            collected.extend(part)
        rows = [row for part in collected for row in part]
        return DataxCaptureOutcome(
            complete=True, rows=rows,
            total_bytes=sum(
                len(str(v).encode("utf-8")) for row in rows for v in row.values()
            ),
            end_reason="WINDOW_COMPLETE", split_root=root,
        )

    def _split_collect(self, node: SplitNode, attempt_id: str):
        window = node.window
        leaf_attempt = f"{attempt_id}-{id(node):x}"
        stage_table = self._stage_table(leaf_attempt)
        job = render_job_for_stage_route(
            self.template,
            route=self.route,
            source_object=self.source_object,
            stage_table=stage_table,
            window_start=self._fmt(window.start),
            window_end_exclusive=self._fmt(window.end_exclusive),
        )
        job_file = self.workspace.materialize(job, leaf_attempt)
        try:
            run = self.runner.run_capture(job, leaf_attempt, job_file=job_file)
        finally:
            self.workspace.cleanup(job_file)
        written = run.rows_written or 0
        if not run.success:
            self.stage_access.drop_table(stage_table)
            node.status = "PENDING"
            node.reason = f"DATAX_{run.end_state}"
            return None
        if written <= self.budget.max_rows_per_slice:
            node.status = "LEAF_COMPLETE"
            raw_rows = self.stage_access.read_rows(stage_table, self.column_names)
            self.stage_access.drop_table(stage_table)
            if len(raw_rows) != written:
                node.status = "PENDING"
                node.reason = "STAGE_ROW_MISMATCH"
                return None
            return [[dict(zip(self.column_names, raw)) for raw in raw_rows]]
        # 超限：弃用本窗暂存再拆分
        self.stage_access.drop_table(stage_table)
        if not window.can_split():
            node.status = "PARKED"
            node.reason = "最小粒度仍超限且 DataX 模板无 keyset，转待处理工单"
            return None
        node.split(max_depth=self.budget.max_split_depth)
        if node.status != "SPLIT":
            node.status = "PARKED"
            node.reason = node.reason or "拆分预算耗尽"
            return None
        collected = []
        for child in node.children:
            part = self._split_collect(child, attempt_id)
            if part is None:
                return None
            collected.extend(part)
        return collected

    def _stage_table(self, attempt_id: str) -> str:
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in attempt_id)
        return f"{self.stage_table_prefix}_{safe}".lower()

    @staticmethod
    def _fmt(moment) -> str:
        from app.services.reporting_pipeline.source_factory import _wall_clock

        return _wall_clock(moment).strftime("%Y-%m-%d %H:%M:%S")


def build_datax_route_factory(
    *,
    route: MysqlStageRoute,
    runner: DataXRunner,
    workspace_root: str,
    stage_access: StageTableAccess,
    runtime_tables,
    credential_resolver: Callable | None = None,
) -> Callable[[str, TimeWindow, str], DataxCaptureOutcome]:
    """按 canonical_table 构造 DataX 路由闭包（capture 装配用）。

    模板按表冻结投影生成（列序=投影序）；stage_table_prefix 含表名
    与批次隔离（防串批）。
    """
    from app.services.reporting_pipeline.adapters.datax_runner import DataxJobTemplate

    def factory(canonical_table: str, window: TimeWindow, attempt_id: str):
        spec = runtime_tables[canonical_table]
        template = DataxJobTemplate(
            template_id=f"t1-{canonical_table}-stageroute",
            version="v1",
            reader_plugin="oraclereader",
            writer_plugin="mysqlwriter",
            # 固定暂存路线按 route.allows_table 白名单核表；模板层占位
            # 仅作指纹成分
            target_object_whitelist=(f"t1_{spec.canonical_table.lower()}",),
            projection_columns=tuple(f.name for f in spec.projection),
            change_time_column=spec.anchor_column or "",
            stable_key_columns=tuple(spec.stable_key),
            render_spec={},
        )
        workspace = JobFileWorkspace(workspace_root, credential_resolver)
        route_runner = DataXCaptureRoute(
            template=template,
            route=route,
            runner=runner,
            workspace=workspace,
            stage_access=stage_access,
            source_object=spec.source_object,
            stage_table_prefix=f"t1_{spec.canonical_table.lower()}",
            column_names=[f.name for f in spec.projection],
            budget=ReadBudget(
                **{
                    name: value
                    for name, value in spec.budget.items()
                    if name in ReadBudget.__dataclass_fields__
                }
            ) if spec.budget else None,
        )
        return route_runner.capture_window(window, attempt_id=attempt_id)

    return factory
