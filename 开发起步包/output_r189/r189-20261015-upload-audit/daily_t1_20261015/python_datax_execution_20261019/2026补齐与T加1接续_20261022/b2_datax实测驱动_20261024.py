"""B2 DataX 真实引擎实测驱动（2026-10-24；跑前须用户批准+MPW）。

目标：让生产代码路径（MysqlStageRoute→render_job_for_stage_route→
JobFileWorkspace 语义→DataXRunner）在真实 8.53 DataX 引擎 + 真实 MySQL
暂存上跑通一次，并完成成功判据与两类失败样例（dirty>0、超预算拆窗）。

执行位置（按提示词 B2 记录）：本地/容器编排——job 文件经 SFTP 落 8.53
（0600，跑完即删），python3 + /home/datax/bin/datax.py 以 8.53 本地进程
执行（RemoteExecRunner 满足 ProcessRunner 协议）；暂存回收走 8.53 mysql
CLI（SQL 一律 base64 管道，防反引号 shell 坑，10-20 手册先例）。

凭据（零落盘）：源 ODS 凭据在 8.53 datax_web.job_jdbc_datasource 表内查
（服务器内存使用，禁导出）；暂存 MySQL root 密码经环境变量 MPW 注入，
只进 0600 job 文件与 mysql 调用，不进日志/证据。

用法（仓库根）：
  MPW=<pw> backend/.venv/Scripts/python.exe <本文件> --output <证据json>
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[6] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.reporting_pipeline.adapters.datax_runner import (
    DataxJobTemplate,
    DataXRunner,
    MysqlStageRoute,
    ProcessResult,
    render_job_for_stage_route,
)
from app.services.reporting_pipeline.adapters.python_reader import ReadBudget
from app.services.reporting_pipeline.datax_route import (
    DataXCaptureRoute,
    StageTableAccess,
)
from app.services.reporting_pipeline.planner import TimeWindow

HOST = "10.10.8.53"
SSH_PORT = 40022
DATAX_HOME = "/home/datax"
STAGE_DB = "t1_stage"
REMOTE_JOB_DIR = "/root"
REMOTE_EXEC = "/root/.t1_remote_exec.py"
TEST_TABLE = "EMR_ICH_OPERATION"
SOURCE_OBJECT = "ODS.V_EMR_ICH_OPERATION"
ANCHOR = "DATETIME"
STABLE_KEY = ("ID",)
PROJECTION = (
    "ID", "ICH_ID", "DATETIME", "OPERATION_CODE", "OPERATION_NAME",
    "OPERATION_DATE", "OPERATION_LEVEL_CODE", "OPERATION_LEVEL_NAME",
    "INCISION_CATEGORY", "OPERATION_GRADE", "OPERATOR_ID", "OPERATOR_NAME",
)
WHITELIST = (f"t1_{TEST_TABLE.lower()}",)

REMOTE_EXEC_SRC = """import base64, json, subprocess, sys
argv = json.loads(base64.b64decode(sys.argv[1]))
timeout = int(sys.argv[2])
try:
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    code, out, err = r.returncode, r.stdout or "", r.stderr or ""
except subprocess.TimeoutExpired as exc:
    code, out, err = 124, exc.stdout or "", "REMOTE_TIMEOUT"
sys.stdout.write(out[-65536:])
sys.stderr.write(err[-16384:])
sys.exit(code)
"""


class SshSession:
    """8.53 SSH 会话（公钥免密）。"""

    def __init__(self) -> None:
        import paramiko

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            HOST, port=SSH_PORT, username="root",
            key_filename=os.path.expanduser(r"~/.ssh/id_ed25519_ai"),
            timeout=20,
        )

    def run(self, command: str, timeout: int = 180) -> tuple[int, str, str]:
        _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        code = stdout.channel.recv_exit_status()
        return code, stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")

    def mysql(self, sql: str, mpw: str, timeout: int = 180) -> tuple[int, str]:
        b64 = base64.b64encode(sql.encode("utf-8")).decode("ascii")
        command = (
            f"echo {b64} | base64 -d | MYSQL_PWD='{mpw}' mysql -uroot -h127.0.0.1 "
            "--batch -N 2>&1"
        )
        code, out, _ = self.run(command, timeout=timeout)
        return code, out

    def sftp_write(self, content: str, remote_path: str, mode: int = 0o600) -> None:
        sftp = self.client.open_sftp()
        try:
            with sftp.open(remote_path, "w") as handle:
                handle.write(content)
            try:
                sftp.chmod(remote_path, mode)
            except OSError:
                pass
        finally:
            sftp.close()

    def sftp_unlink(self, remote_path: str) -> None:
        sftp = self.client.open_sftp()
        try:
            sftp.remove(remote_path)
        finally:
            sftp.close()

    def close(self) -> None:
        self.client.close()


class RemoteExecRunner:
    """ProcessRunner 协议实现：argv 经 base64 交 8.53 本地 python 执行。"""

    def __init__(self, session: SshSession) -> None:
        self._session = session
        session.sftp_write(REMOTE_EXEC_SRC, REMOTE_EXEC, 0o700)

    def run(self, argv, *, timeout_seconds: int) -> ProcessResult:
        import hashlib

        from app.services.reporting_pipeline.adapters.datax_runner import (
            DataxTemplateError,
        )

        if not argv or not all(isinstance(a, str) for a in argv):
            raise DataxTemplateError("argv 必须为非空字符串数组")
        argv_sha256 = hashlib.sha256(json.dumps(list(argv)).encode("utf-8")).hexdigest()
        payload = base64.b64encode(json.dumps(list(argv)).encode("utf-8")).decode()
        code, out, err = self._session.run(
            f"python3 {REMOTE_EXEC} '{payload}' {int(timeout_seconds)}",
            timeout=timeout_seconds + 120,
        )
        return ProcessResult(
            exit_code=code, stdout=out, stderr=err,
            timed_out="REMOTE_TIMEOUT" in err, argv_sha256=argv_sha256,
        )


class MysqlCliStageAccess(StageTableAccess):
    """暂存表访问生产实现：8.53 mysql CLI（batch 模式转义解析）。"""

    def __init__(self, session: SshSession, mpw: str) -> None:
        self._session = session
        self._mpw = mpw

    @staticmethod
    def _unescape(value: str):
        if value == "NULL":
            return None
        out = value.replace("\\\\", "\x00").replace("\\t", "\t").replace("\\n", "\n")
        return out.replace("\x00", "\\")

    def create_table(self, stage_table: str, columns, narrow_first: bool = False) -> None:
        if narrow_first:
            cols = f"`{columns[0]}` VARCHAR(2), " + ", ".join(
                f"`{c}` MEDIUMTEXT" for c in columns[1:]
            )
        else:
            cols = ", ".join(f"`{c}` MEDIUMTEXT" for c in columns)
        code, out = self._session.mysql(
            f"CREATE TABLE IF NOT EXISTS `{STAGE_DB}`.`{stage_table}` ({cols}) "
            "DEFAULT CHARSET=utf8mb4", self._mpw)
        if code != 0:
            raise RuntimeError(f"暂存建表失败: {out[:300]}")

    def read_rows(self, stage_table, columns):
        sql = f"SELECT {', '.join(columns)} FROM `{STAGE_DB}`.`{stage_table}`"
        code, out = self._session.mysql(sql, self._mpw)
        if code != 0:
            raise RuntimeError(f"暂存读取失败: {out[:300]}")
        return [
            tuple(self._unescape(v) for v in line.split("\t"))
            for line in out.splitlines() if line
        ]

    def count_rows(self, stage_table) -> int:
        code, out = self._session.mysql(
            f"SELECT COUNT(*) FROM `{STAGE_DB}`.`{stage_table}`", self._mpw)
        if code != 0:
            raise RuntimeError(f"暂存计数失败: {out[:300]}")
        return int(out.strip().splitlines()[-1])

    def drop_table(self, stage_table) -> None:
        code, out = self._session.mysql(
            f"DROP TABLE IF EXISTS `{STAGE_DB}`.`{stage_table}`", self._mpw)
        if code != 0:
            raise RuntimeError(f"暂存清理失败: {out[:300]}")


def _safe(attempt_id: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in attempt_id)


def fetch_source_credentials(session: SshSession, mpw: str) -> dict:
    """ODS 源凭据：8.53 datax_web.job_jdbc_datasource（内存使用，禁导出）。"""
    code, out = session.mysql(
        "SELECT jdbc_username, jdbc_password FROM datax_web.job_jdbc_datasource "
        "WHERE datasource_name='数据中心ODS_ORACLE'", mpw)
    if code != 0 or not out.strip():
        raise RuntimeError(f"ODS 源凭据获取失败: {out[:200]}")
    user, _, password = out.strip().splitlines()[0].partition("\t")
    return {"user": user, "password": password}


def resolve_document(job: dict, source_creds: dict, mpw: str) -> str:
    document = json.dumps(job, ensure_ascii=False)
    document = document.replace("${credential:user}", source_creds["user"])
    document = document.replace("${credential:password}", source_creds["password"])
    document = document.replace("${stage:user}", "root")
    document = document.replace("${stage:password}", mpw)
    if "${" in document:
        raise RuntimeError("job 仍含未解析占位")
    return document


class RemoteStageWorkspace:
    """JobFileWorkspace 语义的远端实现：解析占位→SFTP 0600→跑完即删。

    materialize 同时负责暂存子表预建（全列 MEDIUMTEXT）——拆窗子表必须
    在 DataX 进程运行前存在。
    """

    def __init__(self, session: SshSession, source_creds: dict, mpw: str,
                 stage_access: MysqlCliStageAccess, columns) -> None:
        self._session = session
        self._source_creds = source_creds
        self._mpw = mpw
        self._stage_access = stage_access
        self._columns = list(columns)
        self.touched_tables: list[str] = []

    def materialize(self, job: dict, attempt_id: str) -> str:
        stage_table = job["job"]["content"][0]["writer"]["parameter"][
            "connection"][0]["table"][0]
        self._stage_access.create_table(stage_table, self._columns)
        self.touched_tables.append(stage_table)
        document = resolve_document(job, self._source_creds, self._mpw)
        path = f"{REMOTE_JOB_DIR}/.t1_job_{_safe(attempt_id)}.json"
        self._session.sftp_write(document, path, 0o600)
        return path

    def cleanup(self, path: str) -> None:
        try:
            self._session.sftp_unlink(path)
        except OSError:
            pass  # 清理尽力而为（残留审计靠文件名前缀 .t1_job_）


def make_route() -> MysqlStageRoute:
    return MysqlStageRoute(
        route_id="route-853",
        version="v1",
        host="127.0.0.1",  # DataX 引擎与 MySQL 同机（8.53 本地跑）
        port=3306,
        database=STAGE_DB,
        table_whitelist=WHITELIST,
        credential_ref="853:datax_web.job_jdbc_datasource/数据中心ODS_ORACLE",
    )


def make_template() -> DataxJobTemplate:
    return DataxJobTemplate(
        template_id=f"t1-{TEST_TABLE}-stageroute",
        version="v1",
        reader_plugin="oraclereader",
        writer_plugin="mysqlwriter",
        target_object_whitelist=WHITELIST,
        projection_columns=PROJECTION,
        change_time_column=ANCHOR,
        stable_key_columns=STABLE_KEY,
        render_spec={},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="证据 JSON 输出路径")
    parser.add_argument("--business-day", default="2026-10-23")
    parser.add_argument("--skip-split-sample", action="store_true")
    args = parser.parse_args()

    mpw = os.environ.get("MPW", "")
    if not mpw:
        print(json.dumps({"ok": False, "error": "缺 MPW 环境变量（8.53 MySQL root 密码）"}))
        return 2

    tz = timezone(timedelta(hours=8))
    day = datetime.strptime(args.business_day, "%Y-%m-%d").replace(tzinfo=tz)
    window = TimeWindow(start=day, end_exclusive=day + timedelta(days=1))

    evidence: dict = {
        "as_of": datetime.now(tz).isoformat(timespec="seconds"),
        "engine": f"ssh:{HOST}:{SSH_PORT} → 8.53本地进程 python3 {DATAX_HOME}/bin/datax.py",
        "stage": f"mysql 127.0.0.1:3306/{STAGE_DB}（白名单前缀 {WHITELIST[0]}_，用完即drop）",
        "table": TEST_TABLE,
        "source_object": SOURCE_OBJECT,
        "window": window.fingerprint(),
        "business_day": args.business_day,
        "samples": [],
    }

    session = SshSession()
    try:
        code, out = session.mysql(
            f"CREATE DATABASE IF NOT EXISTS `{STAGE_DB}` DEFAULT CHARSET utf8mb4", mpw)
        if code != 0:
            evidence.update(ok=False, error=f"暂存库创建失败: {out[:200]}")
            Path(args.output).write_text(
                json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8")
            return 3
        source_creds = fetch_source_credentials(session, mpw)
        stage_access = MysqlCliStageAccess(session, mpw)
        route = make_route()
        template = make_template()
        runner = DataXRunner(RemoteExecRunner(session), datax_home=DATAX_HOME,
                             timeout_seconds=1800)
        workspace = RemoteStageWorkspace(
            session, source_creds, mpw, stage_access, PROJECTION)

        def render(attempt_label: str, stage_table: str) -> dict:
            return render_job_for_stage_route(
                template, route=route, source_object=SOURCE_OBJECT,
                stage_table=stage_table,
                window_start=window.start.strftime("%Y-%m-%d %H:%M:%S"),
                window_end_exclusive=window.end_exclusive.strftime("%Y-%m-%d %H:%M:%S"),
            )

        # ---- 样例1：正常（读=写、dirty=0、暂存回收行数一致） ----------------
        attempt = _safe(f"normal-{args.business_day}")
        stage_table = f"{WHITELIST[0]}_{attempt}".lower()
        job = render(attempt, stage_table)
        job_file = workspace.materialize(job, attempt)
        try:
            run = runner.run_capture(job, attempt, job_file=job_file)
        finally:
            workspace.cleanup(job_file)
        sample = {
            "label": "normal", "stage_table": stage_table,
            "success": run.success, "end_state": run.end_state,
            "rows_read": run.rows_read, "rows_written": run.rows_written,
            "dirty_records": run.dirty_records,
        }
        if run.success:
            count = stage_access.count_rows(stage_table)
            rows = stage_access.read_rows(stage_table, list(PROJECTION))
            sample.update(
                stage_count=count, count_match=count == run.rows_written,
                recycle_rows=len(rows), recycle_match=len(rows) == run.rows_written,
            )
        stage_access.drop_table(stage_table)
        sample["stage_dropped"] = True
        evidence["samples"].append(sample)
        evidence["normal_pass"] = bool(
            sample["success"] and sample.get("count_match")
            and sample.get("recycle_match"))

        # ---- 样例2：失败① dirty>0（首列 VARCHAR(2) 容纳不了真实 ID） --------
        attempt2 = _safe(f"dirty-{args.business_day}")
        stage_table2 = f"{WHITELIST[0]}_{attempt2}".lower()
        job2 = render(attempt2, stage_table2)
        stage_access.create_table(stage_table2, list(PROJECTION), narrow_first=True)
        document = resolve_document(job2, source_creds, mpw)
        path2 = f"{REMOTE_JOB_DIR}/.t1_job_{attempt2}.json"
        session.sftp_write(document, path2, 0o600)
        try:
            run2 = runner.run_capture(job2, attempt2, job_file=path2)
        finally:
            session.sftp_unlink(path2)
        sample2 = {
            "label": "dirty-sabotage", "stage_table": stage_table2,
            "success": run2.success, "end_state": run2.end_state,
            "rows_read": run2.rows_read, "rows_written": run2.rows_written,
            "dirty_records": run2.dirty_records,
        }
        stage_access.drop_table(stage_table2)
        sample2["stage_dropped"] = True
        evidence["samples"].append(sample2)
        evidence["dirty_sample_refused"] = bool(
            (not run2.success) and run2.end_state == "DIRTY"
            and (run2.dirty_records or 0) > 0)

        # ---- 样例3：失败② 超行预算 → 拆窗重跑收集 ---------------------------
        if not args.skip_split_sample:
            capture = DataXCaptureRoute(
                template=template, route=route, runner=runner,
                workspace=workspace, stage_access=stage_access,
                source_object=SOURCE_OBJECT,
                stage_table_prefix=WHITELIST[0],
                column_names=list(PROJECTION),
                budget=ReadBudget(
                    max_rows_per_slice=10, max_bytes_per_slice=268435456,
                    max_attempts=3),
            )
            outcome = capture.capture_window(
                window, attempt_id=f"split-{args.business_day}")
            # 拆窗全程子表已 drop；根窗表若残留也清理
            evidence["split_sample"] = {
                "complete": outcome.complete,
                "end_reason": outcome.end_reason,
                "rows_collected": len(outcome.rows),
                "rows_read": outcome.rows_read,
                "rows_written": outcome.rows_written,
                "split_children": len(outcome.split_root.children)
                if outcome.split_root else 0,
                "stage_tables_touched": sorted(set(workspace.touched_tables)),
            }
            evidence["split_sample_pass"] = bool(
                outcome.complete and outcome.rows
                and len(outcome.rows) == (sample.get("rows_written") or 0))
            for leftover in set(workspace.touched_tables):
                stage_access.drop_table(leftover)

        evidence["ok"] = bool(
            evidence.get("normal_pass") and evidence.get("dirty_sample_refused")
            and (args.skip_split_sample or evidence.get("split_sample_pass")))
        evidence["conclusion"] = (
            "DataX 真实引擎+真实 MySQL 暂存实测通过：生产代码路径"
            "（render→受限job→0600远端文件→真实进程→指标三条件→暂存回收对账）"
            "全链走通" if evidence["ok"] else "存在未过样例，见 samples")
    finally:
        session.close()
    Path(args.output).write_text(
        json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": evidence.get("ok"), "output": args.output},
                     ensure_ascii=False))
    return 0 if evidence.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
