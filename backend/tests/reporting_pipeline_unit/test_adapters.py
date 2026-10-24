"""适配器测试：拆窗/熔断/keyset 回退（Python 路线）+ 白名单/退出0≠成功（DataX）。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.adapters.datax_runner import (
    DataXRunner,
    DataxJobTemplate,
    DataxTemplateError,
    EngineRouter,
    ProcessResult,
    render_job,
    render_query_sql,
)
from app.services.reporting_pipeline.adapters.python_reader import (
    CancellationToken,
    PythonReaderAdapter,
    ReadBudget,
    ReadPage,
    SourceCircuitBreaker,
    SourceError,
    classify_source_error,
)
from app.services.reporting_pipeline.planner import TimeWindow


class SimulatedRowSource:
    """确定性行源：按窗口/keyset 过滤；可注入故障与行字节。"""

    physical_source = "ods__V_TEST"

    def __init__(
        self,
        rows: list[tuple],
        *,
        row_bytes: int = 100,
        failure_message: str | None = None,
        fail_first_n: int = 0,
    ) -> None:
        # rows: (change_time: datetime, id: str, payload)
        self.rows = sorted(rows, key=lambda r: (r[0], r[1]))
        self.row_bytes = row_bytes
        self.failure_message = failure_message
        self.fail_first_n = fail_first_n
        self.calls = 0

    def fetch_page(self, window, *, limit_rows, keyset=None):
        self.calls += 1
        if self.failure_message and self.calls <= self.fail_first_n:
            raise SourceError(
                classify_source_error(self.failure_message),
                "SAFE_CODE",
                "injected",
            )
        selected = [
            r for r in self.rows
            if window.contains(r[0])
            and (keyset is None or keyset.row_after((r[0].isoformat(), r[1])))
        ]
        page = selected[:limit_rows]
        has_more = len(selected) > limit_rows
        last = page[-1] if page else None
        return ReadPage(
            rows=page,
            row_bytes=self.row_bytes * len(page),
            last_key=(last[0].isoformat(), last[1]) if last else None,
            has_more=has_more,
        )


def _surge_rows(count: int, start: datetime, hours: float = 6.0) -> list[tuple]:
    """结算潮行集：count 行落在 [start, start+hours) 左闭右开区间内。"""
    span = timedelta(hours=hours)
    step = span / max(count, 1)  # 最后一行在 start + span*(count-1)/count < end
    return [
        (start + step * i, f"ROW{i:06d}", f"payload-{i}")
        for i in range(count)
    ]


class TestPythonReaderSplit(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 18, 18, 0, 0)  # 六小时结算潮窗口

    def test_settlement_surge_50k_split(self):
        """6小时窗口 50001 行、上限 5 万：递归二分，完整叶合计守恒。"""
        rows = _surge_rows(50_001, self.start)
        source = SimulatedRowSource(rows)
        adapter = PythonReaderAdapter(
            source, ReadBudget(max_rows_per_slice=50_000, page_size=5_000)
        )
        result = adapter.capture_window(
            TimeWindow(self.start, self.start + timedelta(hours=6))
        )
        self.assertTrue(result.complete)
        self.assertEqual(len(result.rows), 50_001)
        # 守恒：拆分叶行数合计 == 源行数（不重不漏）
        self.assertIsNotNone(result.split_root)
        self.assertTrue(result.split_root.all_leaves_complete())

    def test_byte_cap_split(self):
        rows = _surge_rows(100, self.start, hours=2)
        source = SimulatedRowSource(rows, row_bytes=1000)
        adapter = PythonReaderAdapter(
            source, ReadBudget(max_rows_per_slice=1000, max_bytes_per_slice=60_000)
        )
        result = adapter.capture_window(
            TimeWindow(self.start, self.start + timedelta(hours=2))
        )
        self.assertTrue(result.complete)
        self.assertEqual(len(result.rows), 100)

    def test_min_granularity_keyset_fallback(self):
        """最小粒度仍超限：已核唯一稳定键 → keyset 分页收全。"""
        # 18 秒微窗 < 60 秒最小拆分粒度：拆不动，只能 keyset 或待处理
        rows = _surge_rows(10, self.start, hours=18 / 3600)
        source = SimulatedRowSource(rows)
        adapter = PythonReaderAdapter(
            source, ReadBudget(max_rows_per_slice=5, page_size=3)
        )
        result = adapter.capture_window(
            TimeWindow(self.start, self.start + timedelta(seconds=18)),
            keyset_columns=("CHANGE_TIME", "ID"),
            keyset_unique_verified=True,
        )
        self.assertTrue(result.complete)
        self.assertEqual(len(result.rows), 10)
        self.assertTrue(result.keyset_fallback_used)

    def test_min_granularity_parked_without_verified_keyset(self):
        rows = _surge_rows(10, self.start, hours=18 / 3600)
        source = SimulatedRowSource(rows)
        adapter = PythonReaderAdapter(
            source, ReadBudget(max_rows_per_slice=5, page_size=3)
        )
        result = adapter.capture_window(
            TimeWindow(self.start, self.start + timedelta(seconds=18))
        )
        self.assertFalse(result.complete)
        self.assertEqual(result.error_class, "SPLIT_EXHAUSTED_PARKED")

    def test_cancel_mid_read(self):
        rows = _surge_rows(20_000, self.start)
        source = SimulatedRowSource(rows)
        adapter = PythonReaderAdapter(
            source, ReadBudget(max_rows_per_slice=50_000, page_size=100)
        )
        cancel = CancellationToken()
        cancel.cancel()  # 首页前即取消：协作式检查立即生效
        result = adapter.capture_window(
            TimeWindow(self.start, self.start + timedelta(hours=6)), cancel=cancel
        )
        self.assertFalse(result.complete)


class TestCircuitBreaker(unittest.TestCase):
    def _breaker_with_clock(self):
        breaker = SourceCircuitBreaker(failure_threshold=3, open_seconds=60)
        now = {"t": datetime(2026, 10, 19, 12, 0, 0)}
        breaker.use_clock(lambda: now["t"])
        return breaker, now

    def test_transient_disconnect_classification(self):
        self.assertEqual(classify_source_error("ORA-12541 TNS:no listener"), "TRANSIENT_DISCONNECT")
        self.assertEqual(classify_source_error("ORA-12547: TNS:lost contact"), "TRANSIENT_DISCONNECT")
        self.assertEqual(classify_source_error("DPY-4011: not connected"), "TRANSIENT_DISCONNECT")
        self.assertEqual(classify_source_error("ORA-00942: table or view does not exist"), "READ_SQL_OR_VIEW_ERROR")

    def test_open_after_consecutive_failures(self):
        breaker, _ = self._breaker_with_clock()
        for _ in range(2):
            breaker.record_failure("ods__A", "TRANSIENT_DISCONNECT")
        self.assertEqual(breaker.state("ods__A"), "CLOSED")
        breaker.record_failure("ods__A", "TRANSIENT_DISCONNECT")
        self.assertEqual(breaker.state("ods__A"), "OPEN")
        # 其他物理源不受影响
        self.assertEqual(breaker.state("lis__B"), "CLOSED")
        self.assertFalse(breaker.allow("ods__A"))

    def test_half_open_single_probe(self):
        breaker, now = self._breaker_with_clock()
        for _ in range(3):
            breaker.record_failure("ods__A", "TRANSIENT_DISCONNECT")
        now["t"] += timedelta(seconds=120)  # 越过 open 窗口
        self.assertTrue(breaker.allow("ods__A"))  # 第一探针放行
        self.assertFalse(breaker.allow("ods__A"))  # 第二请求熔断（单探针）
        self.assertEqual(breaker.state("ods__A"), "HALF_OPEN_PROBE")
        breaker.record_success("ods__A")
        self.assertEqual(breaker.state("ods__A"), "CLOSED")

    def test_sql_error_does_not_trip_breaker(self):
        breaker, _ = self._breaker_with_clock()
        for _ in range(5):
            backoff = breaker.record_failure("ods__A", "READ_SQL_OR_VIEW_ERROR")
        self.assertEqual(backoff, 0.0)
        self.assertEqual(breaker.state("ods__A"), "CLOSED")

    def test_reader_respects_open_breaker(self):
        rows = _surge_rows(10, datetime(2026, 10, 18))
        source = SimulatedRowSource(
            rows, failure_message="ORA-12541 no listener", fail_first_n=3
        )
        breaker, _ = self._breaker_with_clock()
        adapter = PythonReaderAdapter(
            source, ReadBudget(max_rows_per_slice=100), breaker=breaker
        )
        window = TimeWindow(datetime(2026, 10, 18), datetime(2026, 10, 19))
        r1 = adapter.capture_window(window)
        self.assertFalse(r1.complete)
        self.assertEqual(r1.error_class, "TRANSIENT_DISCONNECT")
        r2 = adapter.capture_window(window)
        self.assertFalse(r2.complete)
        self.assertEqual(r2.error_class, "TRANSIENT_DISCONNECT")
        r3 = adapter.capture_window(window)
        self.assertFalse(r3.complete)
        r4 = adapter.capture_window(window)  # 已熔断：直接 SOURCE_CIRCUIT_OPEN
        self.assertFalse(r4.complete)
        self.assertEqual(r4.error_class, "SOURCE_CIRCUIT_OPEN")


def _template() -> DataxJobTemplate:
    return DataxJobTemplate(
        template_id="tpl_doc_order_check",
        version="v1",
        reader_plugin="oraclereader",
        writer_plugin="oraclewriter",
        target_object_whitelist=("DBOPER.STAGE_EMR_DOC_ORDER_CHECK",),
        projection_columns=("ID", "ORDER_NO", "AMOUNT"),
        change_time_column="MODIFIED_AT",
        stable_key_columns=("ID",),
        render_spec={"window_start": "date", "window_end_exclusive": "date"},
    )


class FakeProcessRunner:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.argv_seen: list[str] | None = None

    def run(self, argv, *, timeout_seconds):
        self.argv_seen = list(argv)
        return self.result


class TestDataxRunner(unittest.TestCase):
    def test_render_job_happy_path(self):
        job = render_job(
            _template(),
            source_object="ODS.V_EMR_DOC_ORDER_CHECK",
            stage_object="DBOPER.STAGE_EMR_DOC_ORDER_CHECK",
            window_start="2026-10-18 00:00:00",
            window_end_exclusive="2026-10-19 00:00:00",
            credential_ref="vault:reporting/ods",
            source_jdbc_urls=("jdbc:oracle:thin:@10.10.8.216:1521/orcl",),
        )
        query = job["job"]["content"][0]["reader"]["parameter"]["connection"][0]["querySql"][0]
        self.assertIn("TO_DATE('2026-10-18 00:00:00'", query)
        self.assertIn("MODIFIED_AT <", query)
        self.assertIn("credentialRef", json_dumps(job))
        # 凭据只以占位引用出现，不存在明文 password 值
        rendered = json_dumps(job)
        self.assertIn('"password": "${credential:password}"', rendered)
        self.assertIn('"password": "${stage:password}"', rendered)

    def test_render_rejects_forbidden_keys(self):
        with self.assertRaises(DataxTemplateError):
            render_job(
                _template(),
                source_object="ODS.V",
                stage_object="DBOPER.STAGE_EMR_DOC_ORDER_CHECK",
                window_start="2026-10-18 00:00:00",
                window_end_exclusive="2026-10-19 00:00:00",
                credential_ref="vault:x",
                source_jdbc_urls=("jdbc:oracle:thin:@10.10.8.216:1521/orcl",),
                extra={"preSql": "DELETE FROM real_table"},
            )

    def test_render_rejects_off_whitelist_target(self):
        with self.assertRaises(DataxTemplateError):
            render_job(
                _template(),
                source_object="ODS.V",
                stage_object="DBOPER.REAL_EMR_DOC_ORDER_CHECK",
                window_start="2026-10-18 00:00:00",
                window_end_exclusive="2026-10-19 00:00:00",
                credential_ref="vault:x",
                source_jdbc_urls=("jdbc:oracle:thin:@10.10.8.216:1521/orcl",),
            )

    def test_render_rejects_missing_window(self):
        with self.assertRaises(DataxTemplateError):
            render_query_sql(_template(), source_object="ODS.V",
                             window_start="", window_end_exclusive="2026-10-19 00:00:00")

    def _job(self) -> dict:
        return render_job(
            _template(),
            source_object="ODS.V_EMR_DOC_ORDER_CHECK",
            stage_object="DBOPER.STAGE_EMR_DOC_ORDER_CHECK",
            window_start="2026-10-18 00:00:00",
            window_end_exclusive="2026-10-19 00:00:00",
            credential_ref="vault:reporting/ods",
            source_jdbc_urls=("jdbc:oracle:thin:@10.10.8.216:1521/orcl",),
        )

    def test_exit_zero_with_metrics_success(self):
        runner = DataXRunner(FakeProcessRunner(ProcessResult(
            0,
            "任务启动时刻: x\n读出记录总数 : 100\n总计写入总数 : 100\n读写失败总数 : 0\n",
            "",
        )))
        result = runner.run_capture(self._job(), "A1")
        self.assertTrue(result.success)
        self.assertEqual(result.end_state, "COMPLETE")

    def test_exit_zero_dirty_not_success(self):
        runner = DataXRunner(FakeProcessRunner(ProcessResult(
            0,
            "读出记录总数 : 100\n总计写入总数 : 95\n读写失败总数 : 5\n",
            "",
        )))
        result = runner.run_capture(self._job(), "A1")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "DIRTY")

    def test_exit_zero_no_metrics_not_success(self):
        runner = DataXRunner(FakeProcessRunner(ProcessResult(0, "", "")))
        result = runner.run_capture(self._job(), "A1")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "METRICS_MISSING")

    def test_non_zero_exit(self):
        runner = DataXRunner(FakeProcessRunner(ProcessResult(
            1, "读出记录总数 : 10\n总计写入总数 : 0\n读写失败总数 : 10\n", "boom"
        )))
        result = runner.run_capture(self._job(), "A1")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "NON_ZERO_EXIT")

    def test_timeout(self):
        runner = DataXRunner(FakeProcessRunner(ProcessResult(0, "", "", timed_out=True)))
        result = runner.run_capture(self._job(), "A1")
        self.assertFalse(result.success)
        self.assertEqual(result.end_state, "TIMEOUT")

    def test_job_without_range_predicate_rejected(self):
        job = self._job()
        job["job"]["content"][0]["reader"]["parameter"]["connection"][0]["querySql"] = [
            "SELECT ID FROM ODS.V"
        ]
        runner = DataXRunner(FakeProcessRunner(ProcessResult(0, "x", "")))
        with self.assertRaises(DataxTemplateError):
            runner.run_capture(job, "A1")

    def test_argv_is_parameter_array(self):
        fake = FakeProcessRunner(ProcessResult(0, "读出记录总数 : 1\n总计写入总数 : 1\n读写失败总数 : 0\n", ""))
        runner = DataXRunner(fake)
        runner.run_capture(self._job(), "A1")
        self.assertEqual(fake.argv_seen[0].endswith("datax.py"), True)
        # 真实引擎 job 路径是位置参数（无 --jobfile 选项；8.53 实证 2026-10-24）
        self.assertNotIn("--jobfile", fake.argv_seen)
        self.assertIn("--mode", fake.argv_seen)
        self.assertTrue(fake.argv_seen[-1].endswith(".json"))

    def test_interpreter_prefix_prepended(self):
        fake = FakeProcessRunner(ProcessResult(0, "读出记录总数 : 1\n总计写入总数 : 1\n读写失败总数 : 0\n", ""))
        runner = DataXRunner(fake, interpreter=("python3",))
        runner.run_capture(self._job(), "A2")
        self.assertEqual(fake.argv_seen[0], "python3")
        self.assertTrue(fake.argv_seen[1].endswith("datax.py"))

    def test_real_engine_metric_wording_parsed(self):
        # 8.53 真实引擎（DATAX-OPENSOURCE-3.0，2026-10-24 实测）措辞：
        # 中文汇总块无写入总数行；写侧在英文 Communicator 行（多行进度
        # 取最后一行）；读侧=读出记录总数。
        real_stdout = (
            "2026-10-24 15:26:29.458 [job-0] INFO  StandAloneJobContainerCommunicator"
            " - Total 50 records, 6000 bytes | Speed 0.6KB/s | Error 0 records"
            " | Percentage 50.00%\n"
            "2026-10-24 15:26:29.458 [job-0] INFO  StandAloneJobContainerCommunicator"
            " - Total 131 records, 12586 bytes | Speed 1.23KB/s | Error 0 records"
            " | Percentage 100.00%\n"
            "记录写入速度                    :             13rec/s\n"
            "读出记录总数                    :                 131\n"
            "读写失败总数                    :                   0\n"
        )
        from app.services.reporting_pipeline.adapters.datax_runner import (
            parse_datax_metrics,
        )

        metrics = parse_datax_metrics(real_stdout)
        self.assertEqual(metrics["rows_read"], 131)
        self.assertEqual(metrics["rows_written"], 131)  # 最后一行 English total
        self.assertEqual(metrics["dirty"], 0)
        # 全链：三条件齐 → COMPLETE
        fake = FakeProcessRunner(ProcessResult(0, real_stdout, ""))
        result = DataXRunner(fake).run_capture(self._job(), "A3")
        self.assertTrue(result.success)
        self.assertEqual(result.end_state, "COMPLETE")


class TestEngineRouter(unittest.TestCase):
    def test_datax_unauthorized_target_blocked_no_fallback(self):
        router = EngineRouter(authorized_datax_targets=[])
        verdict = router.resolve("DATAX", "DBOPER.STAGE_X")
        self.assertEqual(verdict["state"], "BLOCKED")
        self.assertIn("不 fallback", verdict["reason"])

    def test_datax_authorized(self):
        router = EngineRouter(authorized_datax_targets=["DBOPER.STAGE_X"])
        self.assertEqual(router.resolve("DATAX", "DBOPER.STAGE_X")["state"], "RESOLVED")

    def test_python_resolved(self):
        router = EngineRouter(authorized_datax_targets=[])
        self.assertEqual(router.resolve("PYTHON", None)["state"], "RESOLVED")

    def test_undecided_blocked(self):
        router = EngineRouter(authorized_datax_targets=["DBOPER.STAGE_X"])
        verdict = router.resolve("UNDECIDED", "DBOPER.STAGE_X")
        self.assertEqual(verdict["state"], "BLOCKED")


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
