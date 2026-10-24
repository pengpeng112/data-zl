"""R03/R06 离线回归：真实子进程 DataX 判定 / 阻塞 fetch 硬取消 / 运行用例串联。

对应补充验收 RT1-009（exit0 但 dirty/缺指标 → 拒绝 COMPLETE）、
RT1-011（通道不擅自 fallback）、RT1-022（周期如实）与 R05 运行用例
（runtime 模拟日轮：token 贯穿 + simulation 标记 + 日报来自仓储）。
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.adapters.datax_runner import (
    DataXRunner,
    DataxJobTemplate,
    JobFileWorkspace,
    SubprocessProcessRunner,
    render_job,
)
from app.services.reporting_pipeline.adapters.python_reader import (
    CancellationToken,
    ControlledConnectorRowSource,
    FetchTimeoutReached,
    OperationCancelled,
)
from app.services.reporting_pipeline.planner import TimeWindow


def _template() -> DataxJobTemplate:
    return DataxJobTemplate(
        template_id="tpl-1", version="v1",
        reader_plugin="oraclereader", writer_plugin="rdbmswriter",
        target_object_whitelist=("STAGE.EMR_X",),
        projection_columns=("ID", "AMOUNT"),
        change_time_column="DATETIME",
        stable_key_columns=("ID",),
        render_spec={"window_start": "date", "window_end_exclusive": "date"},
    )


def _job() -> dict:
    return render_job(
        _template(),
        source_object="HIS.EMR_X",
        stage_object="STAGE.EMR_X",
        window_start="2026-10-19 00:00:00",
        window_end_exclusive="2026-10-20 00:00:00",
        credential_ref="secret-ref-1",
    )


class _FakeDataxBinary:
    """伪 datax 脚本：按参数打印汇总指标，可注入脏数据/缺指标/超时。"""

    def __init__(self, *, dirty: int = 0, rows: int = 10, omit_metrics: bool = False,
                 sleep_seconds: float = 0.0) -> None:
        self.dirty = dirty
        self.rows = rows
        self.omit_metrics = omit_metrics
        self.sleep_seconds = sleep_seconds

    def write(self, directory: str) -> str:
        script = textwrap.dedent(
            f"""
            import sys, time
            time.sleep({self.sleep_seconds})
            if {int(self.omit_metrics)}:
                print("job done")
                sys.exit(0)
            print("读出记录总数 : {self.rows}")
            print("总计写入总数 : {self.rows - self.dirty}")
            print("脏数据条数 : {self.dirty}")
            sys.exit(0)
            """
        )
        path = Path(directory) / "fake_datax.py"
        path.write_text(script, encoding="utf-8")
        return str(path)


class TestRealSubprocessDataX(unittest.TestCase):
    """RT1-009：真实子进程 exit0 + dirty>0 / 缺指标 / 超时全部拒绝。"""

    def _runner(self, binary: _FakeDataxBinary, timeout: int = 30) -> DataXRunner:
        class BinRunner(SubprocessProcessRunner):
            def __init__(self, script: str) -> None:
                super().__init__()
                self.script = script

            def run(self, argv, *, timeout_seconds: int):
                import sys as _sys

                return super().run(
                    [_sys.executable, self.script, *argv[1:]],
                    timeout_seconds=timeout_seconds,
                )

        return DataXRunner(
            BinRunner(binary.write(tempfile.mkdtemp())),
            datax_home="unused",
            timeout_seconds=timeout,
        )

    def test_exit0_dirty_rejected(self):
        runner = self._runner(_FakeDataxBinary(dirty=3))
        result = runner.run_capture(_job(), "att-1")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "DIRTY")

    def test_exit0_metrics_missing_rejected(self):
        runner = self._runner(_FakeDataxBinary(omit_metrics=True))
        result = runner.run_capture(_job(), "att-2")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "METRICS_MISSING")

    def test_clean_run_completes(self):
        runner = self._runner(_FakeDataxBinary(dirty=0, rows=7))
        result = runner.run_capture(_job(), "att-3")
        self.assertTrue(result.success)
        self.assertEqual(result.end_state, "COMPLETE")
        self.assertEqual(result.rows_read, 7)

    def test_timeout_killed_and_reported(self):
        runner = self._runner(_FakeDataxBinary(sleep_seconds=10.0), timeout=1)
        result = runner.run_capture(_job(), "att-4")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "TIMEOUT")

    def test_job_file_workspace_materializes_and_cleans(self):
        with tempfile.TemporaryDirectory() as root:
            ws = JobFileWorkspace(
                root,
                credential_resolver=lambda job: {"user": "u1", "password": "p1", "stage_user": "su1", "stage_password": "sp1"},
            )
            path = ws.materialize(_job(), "att-5")
            content = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("${credential:user}", content)
            self.assertNotIn("${credential:password}", content)
            ws.cleanup(path)
            self.assertFalse(Path(path).exists())

    def test_job_file_resolves_stage_placeholders(self):
        with tempfile.TemporaryDirectory() as root:
            ws = JobFileWorkspace(
                root,
                credential_resolver=lambda job: {"user": "u1", "password": "p1", "stage_user": "su1", "stage_password": "sp1"},
            )
            path = ws.materialize(_job(), "att-stage-1")
            content = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("${stage:user}", content)
            self.assertNotIn("${stage:password}", content)
            ws.cleanup(path)

    def test_job_file_refuses_incomplete_stage_resolver(self):
        with tempfile.TemporaryDirectory() as root:
            ws = JobFileWorkspace(
                root,
                credential_resolver=lambda job: {"user": "u1", "password": "p1"},
            )
            from app.services.reporting_pipeline.adapters.datax_runner import (
                DataxTemplateError,
            )

            with self.assertRaises(DataxTemplateError):
                ws.materialize(_job(), "att-stage-2")

    def test_job_file_refuses_placeholder_without_resolver(self):
        with tempfile.TemporaryDirectory() as root:
            ws = JobFileWorkspace(root)
            from app.services.reporting_pipeline.adapters.datax_runner import (
                DataxTemplateError,
            )

            with self.assertRaises(DataxTemplateError):
                ws.materialize(_job(), "att-6")


class _BlockingCursor:
    """可被 close() 中断的阻塞游标（模拟驱动在连接关闭时打断 socket 读）。"""

    def __init__(self, block_seconds: float) -> None:
        import threading

        self._block = block_seconds
        self._interrupted = threading.Event()
        self.closed = False

    def execute(self, sql, params) -> None:
        if self.closed or self._interrupted.wait(self._block):
            if self.closed:
                raise RuntimeError("cursor closed")

    def fetchmany(self, size: int) -> list[tuple]:
        if self.closed:
            raise RuntimeError("cursor closed")
        return [(1, "a"), (2, "b")]

    def close(self) -> None:
        self.closed = True
        self._interrupted.set()


class _FakeProvider:
    def __init__(self, cursor) -> None:
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class TestBlockingFetchHardCancel(unittest.TestCase):
    """阻塞 fetch 的硬取消：看门狗关连接打断，attempt 不发布。"""

    def _source(self, cursor) -> ControlledConnectorRowSource:
        return ControlledConnectorRowSource(
            physical_source="ods__V",
            provider=_FakeProvider(cursor),
            query_builder=lambda w, k, n: ("SELECT 1 FROM dual", ()),
            fetch_timeout_seconds=0.5,
        )

    def test_timeout_cancels_blocking_fetch(self):
        source = self._source(_BlockingCursor(block_seconds=5.0))
        window = TimeWindow(
            datetime(2026, 10, 19), datetime(2026, 10, 20)
        )
        started = time.monotonic()
        with self.assertRaises(FetchTimeoutReached):
            source.fetch_page(window, limit_rows=10)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0)  # 5 秒阻塞被 0.5s 超时打断

    def test_cooperative_cancel_between_pages(self):
        token = CancellationToken()
        token.cancel()
        source = ControlledConnectorRowSource(
            physical_source="ods__V",
            provider=_FakeProvider(_BlockingCursor(block_seconds=0.0)),
            query_builder=lambda w, k, n: ("SELECT 1", ()),
            cancellation=token,
        )
        with self.assertRaises(OperationCancelled):
            source.fetch_page(
                TimeWindow(datetime(2026, 10, 19), datetime(2026, 10, 20)),
                limit_rows=10,
            )


class TestRuntimeSimulationCycle(unittest.TestCase):
    """R05 运行用例：模拟日轮 token 贯穿 + simulation 标记 + 日报来自仓储。"""

    @staticmethod
    def _bundle():

        return None  # bundle 由真实种子构造，见 test_runtime_with_seed

    def test_simulation_cycle_tokens_and_honest_state(self):
        from app.services.reporting_pipeline.runtime import (
            DailyCycleConfig,
            PipelineTask,
        )
        from app.services.reporting_pipeline.repositories import (
            InMemoryControlRepository,
        )

        repo = InMemoryControlRepository()
        seen_tokens = []

        class SpecStub:
            canonical_table = "EMR_X"

            def validate_action(self, action):
                return None  # 就绪（stub）

        def capture_fn(context, task):
            seen_tokens.append(context.fencing_token)
            return {"ok": True, "rows": 5}

        def task_factory(anchor):
            return [
                PipelineTask(
                    canonical_table="EMR_X", mode="T1",
                    physical_sources=("ods__V",), target_resource=None,
                    spec=SpecStub(), capture_fn=capture_fn,
                )
            ]

        from app.services.reporting_pipeline.runtime import DailyCycleService

        class _BundleStub:
            tasks = []

            def rescan_tasks(self):
                return []

        service = DailyCycleService(
            repository=repo, bundle=_BundleStub(), task_factory=task_factory,
            config=DailyCycleConfig(), simulation=True,
        )
        outcome = service.run_day(datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc))
        self.assertTrue(outcome["simulation"])
        self.assertEqual(outcome["cycle"]["overall"], "SUCCESS")
        self.assertEqual(len(seen_tokens), 1)
        self.assertIsNotNone(seen_tokens[0])
        # 日报来自同一仓储（per_table 可见）
        self.assertIn("per_table_daily", outcome["daily_report"])
        self.assertTrue(outcome["daily_report"]["simulation"])


if __name__ == "__main__":
    unittest.main()
