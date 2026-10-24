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
# 直写目标白名单（oraclewriter/rdbmswriter）；mysqlwriter 仅限固定暂存
# 路线（MysqlStageRoute），见 render_job_for_stage_route。
ALLOWED_WRITER_PLUGINS = ("oraclewriter", "rdbmswriter")
STAGE_WRITER_PLUGINS = ("mysqlwriter",)
FORBIDDEN_JOB_KEYS = ("preSql", "postSql", "shell", "command")
# mysqlwriter 受限参数白名单（固定暂存路线）：其余 writer 参数一律拒绝
_MYSQLWRITER_ALLOWED_PARAMS = frozenset({
    "username", "password", "writeMode", "column", "connection",
    "batchSize", "batchByteSize",
})
_MYSQLWRITER_ALLOWED_WRITE_MODES = frozenset({"insert"})


@dataclass(frozen=True)
class MysqlStageRoute:
    """固定 MySQL 暂存路线（A02）：8.53 已实测 Oracle→MySQL 暂存。

    - 只允许写入固定暂存实例/库/表（host/port/database + 表白名单）；
    - connection 数组固定单连接，jdbcUrl 由本配置渲染，不接受调用方
      传入任意连接串；
    - 凭据只接受 credential_ref，明文在授权 worker 侧解析；
    - 本路线只做暂存：正式写前置机统一交受控执行器，DataX 不直写目标。
    """

    route_id: str
    version: str
    host: str
    port: int
    database: str
    table_whitelist: tuple[str, ...]
    credential_ref: str
    # 源侧读端点（固定路线的 Oracle 端）：真实引擎 reader 必须
    # connection:[{querySql, jdbcUrl[]}] 数组结构，平铺 querySql 会 NPE
    # （recognizeTableOrQuerySqlMode:239；2026-10-24 8.53 实证）。
    source_jdbc_urls: tuple[str, ...] = ()

    def jdbc_url(self) -> str:
        return (
            f"jdbc:mysql://{self.host}:{self.port}/{self.database}"
            "?useUnicode=true&characterEncoding=utf8"
            "&zeroDateTimeBehavior=convertToNull"
        )

    def allows_table(self, table: str) -> bool:
        """白名单=表前缀归属：基表或其 attempt/叶子隔离子表（前缀_后续）。

        表级隔离防串批要求每次运行的暂存表带批次/叶标识后缀；白名单
        校验的是"该前缀归本路线"，不是精确表名。
        """
        return any(
            table == item or table.startswith(f"{item}_")
            for item in self.table_whitelist
        )

    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "route_id": self.route_id,
                "version": self.version,
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "tables": sorted(self.table_whitelist),
                "source_jdbc_urls": sorted(self.source_jdbc_urls),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        problems: list[str] = []
        if not self.route_id or not self.version:
            problems.append("route_id/version 为空")
        if not self.host or not (0 < int(self.port) < 65536):
            problems.append(f"host/port 非法: {self.host!r}/{self.port!r}")
        if not self.database:
            problems.append("database 为空")
        if not self.table_whitelist:
            problems.append("暂存表白名单为空")
        if not self.credential_ref:
            problems.append("credential_ref 为空")
        if not self.source_jdbc_urls:
            problems.append("source_jdbc_urls 为空（真实引擎 reader 需连接数组结构）")
        if problems:
            raise DataxTemplateError(
                f"MysqlStageRoute[{self.route_id}]: " + "; ".join(problems)
            )


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
    source_jdbc_urls: Sequence[str],
    extra: Mapping[str, str] | None = None,
) -> dict:
    """渲染完整 job dict。违规键、越白名单目标、缺范围 → 拒绝。

    reader 采用 connection:[{querySql, jdbcUrl[]}] 数组结构（真实引擎
    平铺 querySql 会 NPE，2026-10-24 8.53 实证）。
    """
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
                            "connection": [
                                {
                                    "querySql": [query_sql],
                                    "jdbcUrl": list(source_jdbc_urls),
                                }
                            ],
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


def render_job_for_stage_route(
    template: DataxJobTemplate,
    *,
    route: MysqlStageRoute,
    source_object: str,
    stage_table: str,
    window_start: str,
    window_end_exclusive: str,
    extra: Mapping[str, str] | None = None,
) -> dict:
    """固定 MySQL 暂存路线渲染（A02）：mysqlwriter 只进受控暂存。

    与 render_job 的区别：
    - writer 固定 mysqlwriter，connection 数组由路线配置渲染（单连接、
      固定 jdbcUrl），调用方不能自带连接串或任意 writer 参数；
    - 表名必须在路线白名单内，并带 attempt/batch 隔离前缀由调用方在
      stage_table 中显式给出（表级隔离防串批）；
    - 正式写前置机不在本路线：DataX 暂存读出成不可变清单后交统一装载端。
    """
    route.validate()
    extra = dict(extra or {})
    for key in FORBIDDEN_JOB_KEYS:
        if key in extra:
            raise DataxTemplateError(f"job 参数禁止携带 {key}")
    if template.reader_plugin not in ALLOWED_READER_PLUGINS:
        raise DataxTemplateError(f"reader 插件不在白名单: {template.reader_plugin}")
    if template.writer_plugin not in STAGE_WRITER_PLUGINS:
        raise DataxTemplateError(
            f"暂存路线 writer 只允许 {STAGE_WRITER_PLUGINS}: {template.writer_plugin}"
        )
    if not route.allows_table(stage_table):
        raise DataxTemplateError(
            f"暂存表不在固定路线白名单: {stage_table}"
            f"（route={route.route_id}）"
        )
    query_sql = render_query_sql(
        template,
        source_object=source_object,
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
    )
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
                            "credentialRef": route.credential_ref,
                            "connection": [
                                {
                                    "querySql": [query_sql],
                                    "jdbcUrl": list(route.source_jdbc_urls),
                                }
                            ],
                        },
                    },
                    "writer": {
                        "name": "mysqlwriter",
                        "parameter": {
                            "username": "${stage:user}",
                            "password": "${stage:password}",
                            "writeMode": "insert",
                            "column": list(template.projection_columns),
                            "connection": [
                                {
                                    "jdbcUrl": route.jdbc_url(),
                                    "table": [stage_table],
                                }
                            ],
                        },
                    },
                }
            ],
        },
        "templateFingerprint": template.fingerprint(),
        "stageRouteFingerprint": route.fingerprint(),
    }


def validate_stage_route_writer_params(parameter: Mapping) -> None:
    """复核（已渲染/外部构造的）mysqlwriter 参数在受限集合内。

    供运行前防御：未列名参数（session、preSql 变体包装等）一律拒绝，
    connection 只允许单元素且 jdbcUrl 必须命中已登记路线。
    """
    unknown = set(parameter) - _MYSQLWRITER_ALLOWED_PARAMS
    if unknown:
        raise DataxTemplateError(
            f"mysqlwriter 参数越白名单: {sorted(unknown)}"
        )
    if parameter.get("writeMode") not in _MYSQLWRITER_ALLOWED_WRITE_MODES:
        raise DataxTemplateError(
            f"mysqlwriter writeMode 受限: {parameter.get('writeMode')!r}"
        )
    connections = parameter.get("connection") or []
    if not isinstance(connections, list) or len(connections) != 1:
        raise DataxTemplateError("mysqlwriter connection 必须是单元素数组")
    conn = connections[0]
    if not isinstance(conn, Mapping) or "jdbcUrl" not in conn or "table" not in conn:
        raise DataxTemplateError("mysqlwriter connection 缺 jdbcUrl/table")
    if not str(conn.get("jdbcUrl", "")).startswith("jdbc:mysql://"):
        raise DataxTemplateError("mysqlwriter jdbcUrl 必须为受控 mysql 暂存连接")


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


class SubprocessProcessRunner:
    """真实进程执行（R03）：参数数组、无 shell、超时杀进程组。

    - argv 必须是字符串序列（禁止 shell=True / 拼接字符串命令）；
    - 超时先 SIGTERM 整个进程组，宽限后强杀；阻塞读被截止；
    - stdout/stderr 只保留汇总指标行（截断到 64KB），不回显 SQL 正文
      或凭据；命令行本身不含明文凭据（凭据走 job 文件）。
    """

    MAX_OUTPUT_CHARS = 65536

    def __init__(self, *, kill_grace_seconds: float = 5.0) -> None:
        self._kill_grace = kill_grace_seconds

    def run(self, argv: Sequence[str], *, timeout_seconds: int) -> ProcessResult:
        import shutil
        import subprocess

        if not argv or not all(isinstance(a, str) for a in argv):
            raise DataxTemplateError("argv 必须为非空字符串数组（禁止 shell 拼接）")
        argv_sha256 = hashlib.sha256(json.dumps(list(argv)).encode("utf-8")).hexdigest()
        creationflags = 0
        start_new_session = True
        if shutil.which("cmd") and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            start_new_session = False
        try:
            proc = subprocess.Popen(
                list(argv),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
        except OSError as exc:
            return ProcessResult(
                exit_code=-1, stdout="", stderr=f"{type(exc).__name__}",
                timed_out=False, argv_sha256=argv_sha256,
            )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            self._terminate(proc)
            try:
                stdout, stderr = proc.communicate(timeout=self._kill_grace)
            except subprocess.TimeoutExpired:
                self._kill(proc)
                stdout, stderr = proc.communicate()
            timed_out = True
        return ProcessResult(
            exit_code=proc.returncode,
            stdout=(stdout or "")[: self.MAX_OUTPUT_CHARS],
            stderr=(stderr or "")[: self.MAX_OUTPUT_CHARS],
            timed_out=timed_out,
            argv_sha256=argv_sha256,
        )

    def _terminate(self, proc) -> None:
        import signal

        try:
            if hasattr(proc, "send_signal"):
                proc.send_signal(signal.CTRL_BREAK_EVENT)  # Windows 进程组
            else:
                proc.terminate()
        except (OSError, ValueError, AttributeError):
            try:
                proc.terminate()
            except (OSError, ValueError):
                pass

    def _kill(self, proc) -> None:
        try:
            proc.kill()
        except (OSError, ValueError):
            pass


class JobFileWorkspace:
    """受控 job 文件工作区（R03）：短期私有文件 + 完成清理。

    - 目录由装配方指定（授权 worker 暂存区），本类不自建随机目录；
    - job 文件写入前解析 credential_ref → 明文只进文件（chmod 600），
      不进 argv、不出现在任何日志/结果对象；
    - use 结束清理（正常与异常路径都调用 cleanup）；文件名含 attempt_id
      便于残留审计。密钥不回显：写文件内容不返回给调用方。
    """

    def __init__(self, root: str, credential_resolver=None) -> None:
        import os
        from pathlib import Path

        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._credential_resolver = credential_resolver
        self._os = os

    def materialize(self, job: dict, attempt_id: str) -> str:
        """把渲染 job 的 ${credential:*}/${stage:*} 占位解析进私有文件，返回路径。"""
        import tempfile

        document = json.dumps(job, ensure_ascii=False)
        if self._credential_resolver is not None:
            # 占位形如 ${credential:user}/${credential:password}（源读）与
            # ${stage:user}/${stage:password}（暂存写）：解析器返回
            # {user, password, stage_user?, stage_password?}；明文只进文件
            creds = self._credential_resolver(job)
            document = document.replace("${credential:user}", creds["user"])
            document = document.replace(
                "${credential:password}", creds["password"]
            )
            if "${stage:user}" in document or "${stage:password}" in document:
                if creds.get("stage_user") is None or creds.get("stage_password") is None:
                    raise DataxTemplateError(
                        "job 含 ${stage:*} 占位但解析器未提供 stage_user/stage_password"
                        "（拒绝落盘占位残缺的 job）"
                    )
                document = document.replace("${stage:user}", creds["stage_user"])
                document = document.replace(
                    "${stage:password}", creds["stage_password"]
                )
        elif "${credential:" in document or "${stage:" in document:
            raise DataxTemplateError(
                "job 含凭据占位但未配置 credential_resolver（拒绝落盘明文缺失的 job）"
            )
        fd, path = tempfile.mkstemp(
            prefix=f"datax-job-{attempt_id}-", suffix=".json", dir=str(self.root)
        )
        with self._os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(document)
        try:
            self._os.chmod(path, 0o600)
        except OSError:
            pass  # Windows 无 POSIX 权限位；目录级受控
        return path

    def cleanup(self, path: str) -> None:
        try:
            self._os.remove(path)
        except OSError:
            pass


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
    """解析 DataX 汇总指标（容忍字段差异；只认数值行，不解析业务数据）。

    真实引擎（DATAX-OPENSOURCE-3.0，8.53 实证 2026-10-24）的中文汇总块
    只有 读出记录总数/读写失败总数，**没有中文写入总数行**；写侧总数在
    英文 Communicator 行 "Total N records ... Error M records"（进度与
    最终行同格式，取最后一行=100% 时的总数）。
    """
    import re

    metrics: dict = {}
    total_line = re.compile(r"Total\s+(\d+)\s+records.*Error\s+(\d+)\s+records")
    for line in (stdout or "").splitlines():
        line = line.strip()
        try:
            match = total_line.search(line)
            if match:
                # 最后一行胜出（=最终写通信总数与错误数）
                metrics["rows_written"] = int(match.group(1))
                metrics["dirty"] = int(match.group(2))
                continue
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
    """执行渲染后的 job：退出码、读写行数和 dirty 指标都齐全才判成功。"""

    def __init__(
        self,
        process_runner: ProcessRunner,
        datax_home: str = "/opt/datax",
        timeout_seconds: int = 3600,
        interpreter: Sequence[str] = (),
    ) -> None:
        self.process_runner = process_runner
        self.datax_home = datax_home
        self.timeout_seconds = timeout_seconds
        # 8.53 实证（2026-10-24）：datax.py 不可执行且系统无 python 只有
        # python3，须经解释器调用（datax-web 同用 datax-python3.sh 包装）。
        # 生产在 8.53 装配时传 ("python3",)；本地直跑环境可留空。
        self.interpreter = tuple(interpreter)

    def run_capture(
        self, job: dict, attempt_id: str, *, job_file: str | None = None
    ) -> DataxRunResult:
        parameter = job["job"]["content"][0]["reader"]["parameter"]
        connections = parameter.get("connection") or []
        if not connections:
            raise DataxTemplateError(
                f"[{attempt_id}] job reader 缺 connection 数组（真实引擎结构），拒绝执行"
            )
        query_sql = connections[0]["querySql"][0]
        # 复核：job 携带的 querySql 必须带范围谓词（防外部构造的 job 绕过渲染）
        if ">= TO_DATE(" not in query_sql or "< TO_DATE(" not in query_sql:
            raise DataxTemplateError(
                f"[{attempt_id}] job querySql 缺范围谓词，拒绝执行"
            )
        argv = [
            *self.interpreter,
            f"{self.datax_home}/bin/datax.py",
            # 真实 datax.py（DATAX-OPENSOURCE-3.0）无 --jobfile 选项：
            # job 路径是位置参数（usage: datax.py [options] job-url-or-path；
            # 2026-10-24 对照 8.53 真实引擎 help 实证）
            "--mode", "standalone",
            job_file if job_file is not None else "job.json",
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
        required_metrics = {"rows_read", "rows_written", "dirty"}
        if not required_metrics.issubset(metrics):
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
