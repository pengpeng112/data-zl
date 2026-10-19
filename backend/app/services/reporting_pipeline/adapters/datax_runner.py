"""DataX 适配器：受限模板渲染 + 白名单校验 + 进程结果解析。

对应计划 §2.2/§3.3：
- 模板有版本指纹；只允许白名单 reader/writer 与目标暂存对象；禁任意
  preSql/postSql；进程调用用参数数组，不拼 shell。
- 渲染后的 querySql 必须实际携带投影与窗口范围（防止模板占位被静默丢弃）；
  缺范围即拒绝执行。
- 退出码 0 不等于成功：必须解析读/写/dirty 指标；dirty>0 或缺指标按
  不完整处理。多并发连接不共享快照——窗口一致性由控制层冻结的窗口指纹
  与源可见上界约束，适配器不自行放宽。
- 凭据只在授权 worker 运行时解析为私有短期 job 文件（600 权限、结束清理）；
  本模块仅接受 credential_ref，不接触明文。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation

ALLOWED_READER_PLUGINS = ("oraclereader",)
ALLOWED_WRITER_PLUGINS = ("oraclewriter", "rdbmswriter")
FORBIDDEN_JOB_KEYS = ("preSql", "postSql", "shell", "command")


class DataxTemplateError(ContractViolation):
    """模板/参数不在白名单或渲染产物缺必需谓词。"""


@dataclass(frozen=True)
class DataxJobTemplate:
    """受限模板：版本指纹 + 白名单；不含凭据。"""

    template_id: str
    version: str
    reader_plugin: str
    writer_plugin: str
    target_object_whitelist: tuple[str, ...]
    projection_columns: tuple[str, ...]
    change_time_column: str
    stable_key_columns: tuple[str, ...]
    render_spec: Mapping[str, str]  # 占位符 → 参数类型（date/int/str）

    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "template_id": self.template_id,
                "version": self.version,
                "reader": self.reader_plugin,
                "writer": self.writer_plugin,
                "targets": list(self.target_object_whitelist),
                "projection": list(self.projection_columns),
                "change_time": self.change_time_column,
                "keys": list(self.stable_key_columns),
                "render_spec": dict(sorted(self.render_spec.items())),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_query_sql(
    template: DataxJobTemplate,
    *,
    source_object: str,
    window_start: str,
    window_end_exclusive: str,
) -> str:
    """渲染 querySql：显式投影 + 左闭右开范围。占位缺值即拒绝。"""
    if not window_start or not window_end_exclusive:
        raise DataxTemplateError("渲染缺窗口边界（禁止无范围 querySql）")
    columns = ", ".join(template.projection_columns) or "*"
    return (
        f"SELECT {columns} FROM {source_object} "
        f"WHERE {template.change_time_column} >= TO_DATE('{window_start}', "
        f"'YYYY-MM-DD HH24:MI:SS') "
        f"AND {template.change_time_column} < TO_DATE('{window_end_exclusive}', "
        f"'YYYY-MM-DD HH24:MI:SS')"
    )


def render_job(
    template: DataxJobTemplate,
    *,
    source_object: str,
    stage_object: str,
    window_start: str,
    window_end_exclusive: str,
    credential_ref: str,
    extra: Mapping[str, str] | None = None,
) -> dict:
    """渲染完整 job dict。违规键、越白名单目标、缺范围 → 拒绝。"""
    extra = dict(extra or {})
    for key in FORBIDDEN_JOB_KEYS:
        if key in extra:
            raise DataxTemplateError(f"job 参数禁止携带 {key}")
    if template.reader_plugin not in ALLOWED_READER_PLUGINS:
        raise DataxTemplateError(f"reader 插件不在白名单: {template.reader_plugin}")
    if template.writer_plugin not in ALLOWED_WRITER_PLUGINS:
        raise DataxTemplateError(f"writer 插件不在白名单: {template.writer_plugin}")
    if stage_object not in template.target_object_whitelist:
        raise DataxTemplateError(
            f"目标暂存对象不在白名单: {stage_object}"
        )
    query_sql = render_query_sql(
        template,
        source_object=source_object,
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
    )
    # querySql 实际带范围（防占位丢失）：显式复核渲染产物
    if window_start not in query_sql or window_end_exclusive not in query_sql:
        raise DataxTemplateError("渲染产物未携带窗口字面量")
    return {
        "job": {
            "setting": {"speed": {"channel": 1}},
            "content": [
                {
                    "reader": {
                        "name": template.reader_plugin,
                        "parameter": {
                            "username": "${credential:user}",
                            "password": "${credential:password}",
                            "credentialRef": credential_ref,
                            "querySql": [query_sql],
                        },
                    },
                    "writer": {
                        "name": template.writer_plugin,
                        "parameter": {
                            "username": "${stage:user}",
                            "password": "${stage:password}",
                            "writeMode": "insert",
                            "table": stage_object,
                            "column": list(template.projection_columns),
                        },
                    },
                }
            ],
        },
        "templateFingerprint": template.fingerprint(),
    }


class ProcessRunner(Protocol):
    """进程执行抽象：真实实现启动受限 DataX 进程；测试注入 Fake。"""

    def run(self, argv: Sequence[str], *, timeout_seconds: int) -> "ProcessResult":
        ...


@dataclass
class ProcessResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    argv_sha256: str | None = None


@dataclass
class DataxRunResult:
    attempt_id: str
    success: bool
    rows_read: int | None = None
    rows_written: int | None = None
    dirty_records: int = 0
    metrics_present: bool = False
    end_state: str = "UNKNOWN"  # COMPLETE / DIRTY / METRICS_MISSING / NON_ZERO_EXIT / TIMEOUT
    argv_sha256: str | None = None
    duration_seconds: float | None = None


def parse_datax_metrics(stdout: str) -> dict:
    """解析 DataX 汇总指标（容忍字段差异；只认数值行，不解析业务数据）。"""
    metrics: dict = {}
    for line in (stdout or "").splitlines():
        line = line.strip()
        try:
            if "读出记录总数" in line:
                metrics["rows_read"] = int(line.split(":")[-1].strip())
            elif "读写失败总数" in line or "脏数据条数" in line:
                metrics["dirty"] = int(line.split(":")[-1].strip())
            elif "总计写入总数" in line or "写入总数" in line:
                metrics["rows_written"] = int(line.split(":")[-1].strip())
        except ValueError:
            continue
    return metrics


class DataXRunner:
    """执行渲染后的 job：退出码+指标+dirty 三方判定，不把 0 当成功。"""

    def __init__(
        self,
        process_runner: ProcessRunner,
        datax_home: str = "/opt/datax",
        timeout_seconds: int = 3600,
    ) -> None:
        self.process_runner = process_runner
        self.datax_home = datax_home
        self.timeout_seconds = timeout_seconds

    def run_capture(self, job: dict, attempt_id: str) -> DataxRunResult:
        query_sql = (
            job["job"]["content"][0]["reader"]["parameter"]["querySql"][0]
        )
        # 复核：job 携带的 querySql 必须带范围谓词（防外部构造的 job 绕过渲染）
        if ">= TO_DATE(" not in query_sql or "< TO_DATE(" not in query_sql:
            raise DataxTemplateError(
                f"[{attempt_id}] job querySql 缺范围谓词，拒绝执行"
            )
        argv = [
            f"{self.datax_home}/bin/datax.py",
            "--jobfile", "job.json",  # job 文件由授权 worker 物化，路径不进 argv
            "--mode", "standalone",
        ]
        argv_hash = hashlib.sha256(json.dumps(argv).encode("utf-8")).hexdigest()
        proc = self.process_runner.run(argv, timeout_seconds=self.timeout_seconds)
        result = DataxRunResult(
            attempt_id=attempt_id,
            success=False,
            argv_sha256=argv_hash,
        )
        if proc.timed_out:
            result.end_state = "TIMEOUT"
            return result
        metrics = parse_datax_metrics(proc.stdout)
        result.metrics_present = bool(metrics)
        result.rows_read = metrics.get("rows_read")
        result.rows_written = metrics.get("rows_written")
        result.dirty_records = metrics.get("dirty", 0)
        if proc.exit_code != 0:
            result.end_state = "NON_ZERO_EXIT"
            return result
        if not metrics:
            result.end_state = "METRICS_MISSING"
            return result
        if result.dirty_records and result.dirty_records > 0:
            result.end_state = "DIRTY"
            return result
        if result.rows_written is not None and result.rows_read is not None:
            if result.rows_written != result.rows_read:
                result.end_state = "DIRTY"
                return result
        result.success = True
        result.end_state = "COMPLETE"
        return result


class EngineRouter:
    """固定引擎路由：任务声明 engine；适配器不可用即 BLOCKED，不自动换工具。"""

    def __init__(self, authorized_datax_targets: Sequence[str]) -> None:
        self.authorized_datax_targets = set(authorized_datax_targets)

    def resolve(self, declared_engine: str, stage_object: str | None) -> dict:
        if declared_engine == "DATAX":
            if not stage_object or stage_object not in self.authorized_datax_targets:
                return {
                    "engine": None,
                    "state": "BLOCKED",
                    "reason": "DataX 目标暂存对象未获授权（无授权不 fallback 到 Python）",
                }
            return {"engine": "DATAX", "state": "RESOLVED", "reason": None}
        if declared_engine == "PYTHON":
            return {"engine": "PYTHON", "state": "RESOLVED", "reason": None}
        return {
            "engine": None,
            "state": "BLOCKED",
            "reason": "engine=UNDECIDED（E01 画像后冻结，失败不换工具）",
        }
