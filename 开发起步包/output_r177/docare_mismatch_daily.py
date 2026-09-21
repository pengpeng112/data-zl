#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""182 方案二 v3：手麻急诊登记住院次错配·每日扫描 + 受控自动修订。

【185 可靠性改进版（仓库副本，未部署）】
生产 8.83 cron 00:10 仍运行旧版；本改进版部署需用户点名批准（含 cron 行改为 --out 原子写）。
故障背景（185 §10/§11）：ODS 8.216 在 00:10 前后监听不可用（ORA-12541），连续两晚
his_visits 步骤连接失败 → 清单 0 字节且退出码未暴露。本版叠加可靠性层：

  1) 连接类错误（ORA-12541/12543/12170 等网络/监听类）有界重试：指数退避
     （5s 起步、上限 60s），总预算默认 600 秒（--retry-budget / DOCARE_RETRY_BUDGET_SECONDS），
     全程共享同一预算；仅覆盖只读扫描/核验阶段。
  2) 脚本总超时默认 1800 秒（--timeout / DOCARE_DAILY_TIMEOUT_SECONDS）：
     POSIX 下 SIGALRM 硬超时 + 全程 deadline 软超时（重试与逐组循环检查）。
  3) 锁文件防重入（--lock）：已持锁且未超过 stale 阈值 → 立即退出码 2；
     stale 超时自动接管并在 stderr 报告（释放时仅删自己的锁，防误删接管者）。
  4) 清单原子输出（--out）：同目录 .tmp 写完 fsync 后 os.replace；任何失败
     不产生 0 字节清单、不留 .tmp 残留；stdout 模式仍整段打印（不半写）。
  5) 任何失败 exit 非零且 stderr 有摘要：1=其他 2=锁占用 3=重试耗尽 4=总超时 5=输出失败。
  6) 日志/清单凭据脱敏（复用平台 sanitize_text；患者号按既定口径保留——
     清单本就含患者号/病案号，落在受控证据目录，文件权限 0600）。
  7) 告警适配器：仅接口 + 本地文件实现（--alert-file / DOCARE_ALERT_FILE），
     默认关闭，无生产配置；接生产告警渠道需新增实现并另行批准。
  8) 写入类操作（UPDATE 修订/备份/审计）绝不自动重试；重试仅覆盖只读阶段。

相对 v2 的关键修正（00344476 解剖发现）——业务逻辑四重判据保持不动：
  手麻本地住院次（MED_PAT_VISIT/MED_OPERATION_MASTER.VISIT_ID）与 HIS 真实住院次
  是两套编号，部分患者一致（c0632940）、部分不一致（00344476 本地 1=HIS 3）。
  视图 FBINCU = NVL(申请反查 his_visit_id, 登记本地值)。因此：
  - FBINCU 来源为申请反查 → 基本正确，不算错配；
  - 错配确认必须以 ODS HIS.PAT_VISIT 落窗算出的真实 HIS 号为基准；
  - 自动修订仅当：FBINCU=登记值 且 ≠HIS真实号 且 该患者本地号==HIS号 且 登记值为默认 1；
    其余形态（本地/HIS 编号不一致、登记非 1 等）只出清单人工裁决。

模式：无参=每日自动（cron 00:10，建议配 --out 原子写）；--dry-run；--patient P（只读）；--patient P --fix（点名修订）。
护栏：每例先备份（可回滚）、单晚上限 10 组、单事务 rowcount 对账、逐例平台审计。
"""
import argparse
import json
import os
import re
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from app.services.db_connectors import OracleConnector

EV_DIR = Path("/opt/data-asset/evidence/docare_mismatch")
DAILY_FIX_LIMIT = 10
VISIT_WINDOW = (
    "(SELECT PATIENT_ID, VISIT_ID AS real_visit, ADMISSION_DATE_TIME, "
    "LEAD(ADMISSION_DATE_TIME) OVER (PARTITION BY PATIENT_ID ORDER BY ADMISSION_DATE_TIME) AS next_adm "
    "FROM MEDCOMM.MED_PAT_VISIT)"
)

# ---------------- 185 可靠性层：脱敏 / 错误分类 / 重试 / 锁 / 原子输出 / 告警 ----------------

try:  # 复用平台统一脱敏；脚本独立运行环境缺失时回退最小实现
    from app.services.data_masking import sanitize_text as _sanitize_text

    def sanitize(text, limit=200):
        try:
            return _sanitize_text(text, limit=limit)
        except Exception:
            return re.sub(r"\s+", " ", str(text))[:limit]
except Exception:  # pragma: no cover - 独立部署回退
    _FALLBACK_SECRET = re.compile(r"(?i)(password|passwd|pwd|token|secret)\s*[:=]\s*\S+")

    def sanitize(text, limit=200):
        cleaned = _FALLBACK_SECRET.sub("[REDACTED]", str(text or ""))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def err_summary(exc):
    return sanitize(f"{type(exc).__name__}: {exc}", limit=200)


# 连接类（网络/监听）瞬时错误：只读阶段可安全重试；写入阶段一律不重试。
_TRANSIENT_ORA_CODES = (
    "12541",  # TNS:no listener
    "12543",  # TNS:destination unreachable
    "12170",  # TNS:Connect timeout
    "12514",  # TNS:listener does not currently know of service
    "12545",  # TNS:target host or object does not exist
    "12560",  # TNS:protocol adapter error
    "12154",  # TNS:could not resolve the connect identifier
    "12537",  # TNS:connection closed
    "3113",   # end-of-file on communication channel
    "3114",   # not connected to ORACLE
    "17002",  # network connection reset
)
_TRANSIENT_PHRASES = (
    "tns:no listener",
    "tns:destination unreachable",
    "tns:connect timeout",
    "connection timed out",
    "connection reset by peer",
    "network adapter could not establish the connection",
)


def is_transient_connection_error(exc):
    txt = f"{type(exc).__name__}: {exc}".lower()
    if any(f"ora-{c}" in txt for c in _TRANSIENT_ORA_CODES):
        return True
    return any(p in txt for p in _TRANSIENT_PHRASES)


class ScriptTimeoutError(RuntimeError):
    """总超时（--timeout）到期。"""


class TransientRetryExhausted(RuntimeError):
    """连接类错误重试预算耗尽（--retry-budget）。"""


class OutputWriteError(RuntimeError):
    """清单原子输出失败。"""


def _stderr_log(msg):
    print(f"[docare_daily] {msg}", file=sys.stderr)


class RetryController:
    """有界指数退避重试（仅只读阶段调用 retryable=True）。

    - 预算全程共享：从第一次瞬时失败起算，累计退避+耗时至多 budget_seconds；
    - deadline 为脚本总超时软限，重试前检查；
    - clock/sleep 可注入，供纯逻辑测试；
    - retryable=False 直通单次执行（写入类操作固定走该语义：绝不自动重试）。
    """

    def __init__(self, budget_seconds=600.0, deadline=None,
                 clock=None, sleep=None,
                 initial_backoff=5.0, max_backoff=60.0, max_attempts=32,
                 log=None):
        self.budget_seconds = float(budget_seconds)
        self.deadline = deadline
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.initial_backoff = float(initial_backoff)
        self.max_backoff = float(max_backoff)
        self.max_attempts = int(max_attempts)
        self._log = log or _stderr_log
        self._retry_started = None

    def check_deadline(self):
        if self.deadline is not None and self.clock() >= self.deadline:
            raise ScriptTimeoutError("total timeout (--timeout) reached")

    def call(self, fn, *, label, retryable=True):
        if not retryable:
            return fn()
        attempt = 0
        while True:
            try:
                return fn()
            except ScriptTimeoutError:
                raise
            except Exception as exc:
                attempt += 1
                if not is_transient_connection_error(exc):
                    raise
                now = self.clock()
                if self._retry_started is None:
                    self._retry_started = now
                self.check_deadline()
                remaining = self.budget_seconds - (now - self._retry_started)
                if remaining <= 0 or attempt >= self.max_attempts:
                    raise TransientRetryExhausted(
                        f"{label}: transient connection retry budget "
                        f"{self.budget_seconds:.0f}s exhausted after {attempt} failures "
                        f"(last: {err_summary(exc)})") from exc
                backoff = min(self.initial_backoff * (2 ** (attempt - 1)), self.max_backoff)
                sleep_for = min(backoff, remaining)
                if self.deadline is not None:
                    sleep_for = min(sleep_for, max(0.0, self.deadline - now))
                if sleep_for <= 0:
                    raise TransientRetryExhausted(
                        f"{label}: no retry window left before deadline "
                        f"(last: {err_summary(exc)})") from exc
                self._log(f"retry {label} attempt={attempt} transient={err_summary(exc)} "
                          f"backoff={sleep_for:.1f}s budget_left={remaining:.1f}s")
                self.sleep(sleep_for)


class _HardAlarm:
    """POSIX SIGALRM 硬超时；Windows/无信号环境自动降级为仅软 deadline。"""

    def __init__(self):
        self.armed = False

    def install(self, seconds):
        if not hasattr(signal, "SIGALRM"):
            return
        def _handler(signum, frame):  # pragma: no cover - 信号路径
            raise ScriptTimeoutError(f"SIGALRM hard timeout after {seconds:.0f}s")
        try:
            signal.signal(signal.SIGALRM, _handler)
            signal.alarm(max(1, int(seconds)))
            self.armed = True
        except Exception:
            self.armed = False

    def cancel(self):
        if self.armed and hasattr(signal, "SIGALRM"):
            try:
                signal.alarm(0)
            except Exception:
                pass
        self.armed = False


def acquire_lock(path, *, stale_seconds, now_fn=time.time):
    """O_CREAT|O_EXCL 防重入锁；stale 超时自动接管。返回 (acquired, message, token)。"""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    token = f"{os.getpid()}@{now_fn():.0f}"
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            age = now_fn() - path.stat().st_mtime
            holder = path.read_text(encoding="utf-8", errors="replace").strip() or "<empty>"
        except OSError:
            age, holder = stale_seconds + 1, "<unreadable>"
        if age <= stale_seconds:
            return False, (f"lock busy: another run active (age {age:.0f}s <= "
                           f"stale {stale_seconds:.0f}s, holder {holder})"), None
        try:
            path.unlink()
        except OSError:
            pass
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False, "lock busy: lost stale-takeover race", None
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token)
        return True, (f"stale lock taken over (age {age:.0f}s > stale {stale_seconds:.0f}s, "
                      f"prev holder {holder})"), token
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    return True, "lock acquired", token


def release_lock(path, token):
    """只删除自己写入的锁，避免误删接管者的锁。"""
    path = Path(path)
    try:
        if token is not None and path.read_text(encoding="utf-8", errors="replace").strip() == token:
            path.unlink(missing_ok=True)
    except OSError:
        pass


def atomic_write_text(path, text, *, mode=0o600):
    """同目录 .tmp 写完 fsync 后 os.replace；失败清理 .tmp 且不动原文件。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, mode)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise OutputWriteError(f"atomic write failed for {path}: {err_summary(exc)}") from exc


class AlertAdapter:
    """告警适配器接口。仅提供本地实现；生产渠道接入需新增子类并另行批准部署。"""

    name = "interface"

    def alert(self, title, body):  # pragma: no cover - 接口
        raise NotImplementedError


class NullAlertAdapter(AlertAdapter):
    """默认：关闭（无任何副作用）。"""

    name = "disabled"

    def alert(self, title, body):
        return False


class LocalFileAlertAdapter(AlertAdapter):
    """本地文件告警：追加一行脱敏摘要。默认关闭，仅 --alert-file 显式开启。"""

    name = "local_file"

    def __init__(self, path):
        self.path = Path(path)

    def alert(self, title, body):
        try:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            with self.path.open("a", encoding="utf-8") as f:
                f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {sanitize(title, 120)} | "
                        f"{sanitize(body, 400)}\n")
            return True
        except Exception:
            return False


def build_alert_adapter(path):
    if not path:
        return NullAlertAdapter()
    return LocalFileAlertAdapter(path)


def _env_float(name, default):
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        _stderr_log(f"invalid env {name}={sanitize(raw, 40)}, fallback to {default}")
        return float(default)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="docare mismatch daily scan (185 reliability improved, NOT deployed)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--patient", default=None)
    p.add_argument("--fix", action="store_true")
    p.add_argument("--out", default=os.environ.get("DOCARE_DAILY_OUT", ""),
                   help="清单原子输出路径（推荐 cron 使用；缺省=stdout 整段打印）")
    p.add_argument("--lock", default=os.environ.get("DOCARE_DAILY_LOCK",
                   str(EV_DIR / ".docare_mismatch_daily.lock")))
    p.add_argument("--timeout", type=float,
                   default=_env_float("DOCARE_DAILY_TIMEOUT_SECONDS", 1800.0),
                   help="脚本总超时秒数（默认 1800）")
    p.add_argument("--retry-budget", type=float,
                   default=_env_float("DOCARE_RETRY_BUDGET_SECONDS", 600.0),
                   help="连接类错误重试总预算秒数（默认 600）")
    p.add_argument("--stale-lock", type=float,
                   default=_env_float("DOCARE_STALE_LOCK_SECONDS", 1800.0),
                   help="锁 stale 阈值秒数（默认 1800，与总超时一致）")
    p.add_argument("--alert-file", default=os.environ.get("DOCARE_ALERT_FILE", ""),
                   help="本地文件告警路径；缺省=告警关闭")
    return p.parse_args(argv)


def fail(code, phase, message, alert=None):
    """统一失败出口：exit 非零 + stderr 脱敏摘要 +（可选）告警。"""
    msg = f"[docare_daily] FAIL code={code} phase={phase}: {sanitize(message, 400)}"
    print(msg, file=sys.stderr)
    if isinstance(alert, AlertAdapter) and not isinstance(alert, NullAlertAdapter):
        try:
            alert.alert("docare_mismatch_daily failure", msg)
        except Exception:
            pass
    return code


# ---------------- 以下为 182 v3 业务逻辑（保持不动） ----------------


def creds():
    raw = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip()
    u, p = raw.split(":", 1)
    return u, p


def ro_conn():
    u, p = creds()
    return OracleConnector(host="10.10.10.68", port=1521, database="docare",
                           user=u, password=p, connection_mode="direct",
                           oracle_client_lib_dir="/opt/oracle", timeout_ms=120000)


def ods_conn():
    raw = Path("/etc/data-asset/credentials/ods_8_216").read_text(encoding="utf-8").strip()
    u, p = raw.split(":", 1)
    return OracleConnector(host="10.10.8.216", port=1521, database="orcl",
                           user=u, password=p, connection_mode="direct",
                           oracle_client_lib_dir="/opt/oracle", timeout_ms=60000)


def rw_conn():
    import oracledb
    try:
        oracledb.init_oracle_client(lib_dir="/opt/oracle")
    except Exception:
        pass
    u, p = creds()
    c = oracledb.connect(user=u, password=p, dsn="10.10.10.68:1521/docare")
    c.autocommit = False
    return c


def norm(v):
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:2000]
    if type(v).__name__ == "LOB":
        try:
            d = v.read()
            return bytes(d).hex()[:2000] if isinstance(d, (bytes, memoryview)) else str(d)[:8000]
        except Exception:
            return "<LOB>"
    return str(v)[:8000]


def oper_of(pdfname):
    try:
        return str(pdfname).rsplit(".", 1)[0].split("_")[-2]
    except Exception:
        return None


def fall_in(visits, when):
    """visits=[(visit, adm_dt_str)] 升序；返回 when 落入的 visit（区间=本次入院≤when<下次入院）。"""
    v = None
    for visit, adm in visits:
        if when >= str(adm):
            v = str(visit)
    return v


def scan(conn, patient=None):
    if patient:
        where = "s.PATIENTID=:p AND v.real_visit IS NOT NULL AND v.real_visit <> s.FBINCU"
        params = {"p": patient}
        window = "单人全时段"
    else:
        where = ("s.FUPDATE >= TRUNC(SYSDATE-1) AND s.FUPDATE < TRUNC(SYSDATE) "
                 "AND v.real_visit IS NOT NULL AND v.real_visit <> s.FBINCU")
        params = {}
        window = "昨日全天"
    sql = f"""
        SELECT s.PATIENTID, s.FBIHID, s.FBINCU AS reg_v, v.real_visit AS local_real,
               s.reportname, s.pdfname, s.FUPDATE
        FROM MEDSURGERY.T_ITF_SM s
        LEFT JOIN {VISIT_WINDOW} v
          ON v.PATIENT_ID = s.PATIENTID
         AND s.FUPDATE >= v.ADMISSION_DATE_TIME
         AND (v.next_adm IS NULL OR s.FUPDATE < v.next_adm)
        WHERE s.FREPORTSTYLE='住院' AND {where}
    """
    rows = conn.execute_readonly(sql, params, max_rows=10000)
    groups = {}
    bad = 0
    for r in rows:
        op = oper_of(r["PDFNAME"])
        if op is None:
            bad += 1
            continue
        key = (str(r["PATIENTID"]), str(r["REG_V"]), str(r["LOCAL_REAL"]))
        g = groups.setdefault(key, {"fbihid": str(r["FBIHID"]), "opers": {}, "docs": 0,
                                    "when": str(r["FUPDATE"])})
        g["opers"][op] = g["opers"].get(op, 0) + 1
        g["docs"] += 1
    return window, rows, groups, bad


def apply_hit(conn, pid, fbincu, oper):
    n = conn.execute_readonly(
        "SELECT COUNT(*) c FROM MEDCOMM.MED_VS_HIS_OPER_APPLY_V2 "
        "WHERE MED_PATIENT_ID=:p AND MED_VISIT_ID=:v AND MED_SCHEDULE_ID=:o",
        {"p": pid, "v": fbincu, "o": oper}, max_rows=2)[0]["C"]
    return int(n) > 0


DICT_TABLES = None


def dict_tables(conn):
    global DICT_TABLES
    if DICT_TABLES is None:
        rows = conn.execute_readonly(
            "SELECT owner, table_name FROM all_tab_columns "
            "WHERE owner IN ('MEDSURGERY','MEDCOMM','MEDICU') AND column_name IN ('PATIENT_ID','VISIT_ID','OPER_ID') "
            "GROUP BY owner, table_name HAVING COUNT(DISTINCT column_name)=3 AND table_name NOT LIKE 'V\\_%' ESCAPE '\\'",
            None, max_rows=300)
        DICT_TABLES = [(r["OWNER"], r["TABLE_NAME"]) for r in rows]
    return DICT_TABLES


def plan_fix(conn, pid, reg_v, oper):
    hits = {}
    for o, t in dict_tables(conn):
        fq = f"{o}.{t}"
        n = conn.execute_readonly(
            f"SELECT COUNT(*) c FROM {fq} WHERE PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o",
            {"p": pid, "v": reg_v, "o": oper}, max_rows=2)[0]["C"]
        if int(n) > 0:
            hits[fq] = int(n)
    n = conn.execute_readonly(
        "SELECT COUNT(*) c FROM MEDCOMM.MED_EMR_ARCHIVE_DETIAL "
        "WHERE PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o",
        {"p": pid, "v": reg_v, "o": oper}, max_rows=2)[0]["C"]
    if int(n) > 0:
        hits["MEDCOMM.MED_EMR_ARCHIVE_DETIAL"] = int(n)
    return hits


def backup_group(conn, pid, tag, tables):
    payload = {"pid": pid, "tag": {k: tag[k] for k in ("reg_v", "real_v", "oper")}, "tables": {}}
    for fq in tables:
        w = ("PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o"
             if fq == "MEDCOMM.MED_EMR_ARCHIVE_DETIAL"
             else "PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o")
        rows = conn.execute_readonly(f"SELECT * FROM {fq} WHERE {w}", tag["bind"], max_rows=5000)
        payload["tables"][fq] = [{k: norm(v) for k, v in r.items()} for r in rows]
    payload["counts"] = {k: len(v) for k, v in payload["tables"].items()}
    payload["total"] = sum(payload["counts"].values())
    fname = EV_DIR / f"fix_backup_{datetime.now():%Y%m%d}_{pid}_{tag['reg_v']}to{tag['real_v']}_oper{tag['oper']}.json"
    fname.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    fname.chmod(0o600)
    return fname.name, payload["total"]


def apply_fix(pid, tag, tables):
    conn = rw_conn()
    res = {"tag": f"{tag['reg_v']}->{tag['real_v']} oper{tag['oper']}", "tables": len(tables)}
    try:
        cur = conn.cursor()
        expect = 0
        for fq, n in tables.items():
            if fq == "MEDCOMM.MED_EMR_ARCHIVE_DETIAL":
                src, dst = ("PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o",
                            "PATIENT_ID=:p AND VISIT_ID=:nv AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o")
            else:
                src, dst = "PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o", "PATIENT_ID=:p AND VISIT_ID=:nv AND OPER_ID=:o"
            b2 = dict(tag["bind"], nv=tag["real_v"])
            cur.execute(f"SELECT COUNT(*) FROM {fq} WHERE {dst}", b2)
            if cur.fetchone()[0]:
                raise RuntimeError(f"{fq}: target clash")
            cur.execute(f"SELECT COUNT(*) FROM {fq} WHERE {src}", tag["bind"])
            if cur.fetchone()[0] != n:
                raise RuntimeError(f"{fq}: src drift")
            expect += n
        done = 0
        for fq in tables:
            sql = ("UPDATE MEDCOMM.MED_EMR_ARCHIVE_DETIAL SET VISIT_ID=:nv "
                   "WHERE PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o"
                   if fq == "MEDCOMM.MED_EMR_ARCHIVE_DETIAL" else
                   f"UPDATE {fq} SET VISIT_ID=:nv WHERE PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o")
            cur.execute(sql, dict(tag["bind"], nv=tag["real_v"]))
            done += cur.rowcount
        if done != expect:
            raise RuntimeError(f"rowcount {done} != {expect}")
        conn.commit()
        res.update({"status": "fixed", "rows": done})
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        res.update({"status": "rolled_back", "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
    finally:
        conn.close()
    return res


def audit_platform(pid, info):
    try:
        from app.core.db import SessionLocal
        from app.models.governance_base import GovernAuditLog
        db = SessionLocal()
        try:
            db.add(GovernAuditLog(
                module="docare", entity_type="MED_OPERATION_MASTER+children", entity_ref=pid,
                action="auto_fix_visit_id_daily", operator="docare-auto-fix-daily",
                reason="182 v3: HIS-verified emergency visit-id auto fix "
                       "(backup-first, single txn, rowcount reconciled, local==HIS numbering required)",
                after_data=info))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


# ---------------- 主流程（可靠性层包裹，业务判据与清单内容不动） ----------------


def main(argv=None):
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    opts = parse_args(argv)
    patient = opts.patient
    dry = opts.dry_run

    alarm = _HardAlarm()
    alarm.install(opts.timeout)
    deadline = time.monotonic() + opts.timeout
    alert = build_alert_adapter(opts.alert_file)

    acquired, lock_msg, lock_token = acquire_lock(opts.lock, stale_seconds=opts.stale_lock)
    if not acquired:
        return fail(2, "lock", lock_msg, alert=alert)
    if lock_msg != "lock acquired":
        _stderr_log(lock_msg)
        try:
            alert.alert("docare_mismatch_daily stale lock takeover", lock_msg)
        except Exception:
            pass

    try:
        retry = RetryController(budget_seconds=opts.retry_budget, deadline=deadline)
        dc = ro_conn()
        ods = ods_conn()
        # 连接探活 + 扫描/核验（只读阶段，允许有界重试）
        retry.call(lambda: dc.execute_readonly("SELECT 1 AS PROBE FROM DUAL", None, max_rows=1),
                   label="probe_docare")
        retry.call(lambda: ods.execute_readonly("SELECT 1 AS PROBE FROM DUAL", None, max_rows=1),
                   label="probe_ods")
        window, rows, groups, bad = retry.call(lambda: scan(dc, patient), label="scan")
        L = [f"# 手麻住院次错配 · {'单人' if patient else '每日'}"
             f"{'（HIS 核验自动修订' + ('，dry-run' if dry else '') + '）' if (not patient or opts.fix) else '（只读清单）'}",
             "", f"- 窗口：{window}",
             f"- 候选错配文书行数：{len(rows)}；患者×住院次组合：{len(groups)}",
             f"- 自动条件：登记=1 且 FBINCU≠HIS 真实号 且 本地号==HIS号；上限 {DAILY_FIX_LIMIT} 组/晚", ""]
        if not groups:
            L.append("（无错配）")
            _write_output(opts, "\n".join(L), groups=0, rows=len(rows))
            return 0

        his_visits_cache = {}

        def his_visits(pid):
            if pid not in his_visits_cache:
                r = retry.call(lambda: ods.execute_readonly(
                    "SELECT VISIT_ID, ADMISSION_DATE_TIME FROM HIS.PAT_VISIT WHERE UPPER(PATIENT_ID)=UPPER(:p) ORDER BY ADMISSION_DATE_TIME",
                    {"p": pid}, max_rows=50), label=f"his_visits")
                his_visits_cache[pid] = [(str(x["VISIT_ID"]), str(x["ADMISSION_DATE_TIME"])) for x in r]
            return his_visits_cache[pid]

        auto_all = (not patient and not dry) or (patient and opts.fix)
        if auto_all and len(groups) > DAILY_FIX_LIMIT:
            L.append(f"**⚠ 组合数 {len(groups)} > 上限 {DAILY_FIX_LIMIT}：只出清单（NEED_MANUAL）**")
            auto_all = False

        fixed_groups = 0
        for (pid, reg_v, local_real) in sorted(groups):
            retry.check_deadline()
            g = groups[(pid, reg_v, local_real)]
            his_real = fall_in(his_visits(pid), g["when"])
            apply_src = retry.call(lambda: apply_hit(dc, pid, reg_v, sorted(g["opers"])[0]),
                                   label="apply_hit")
            reasons = []
            if apply_src:
                reasons.append("FBINCU 来自申请反查（视为正确）")
            if his_real is None:
                reasons.append("HIS 无落窗住院")
            auto = (auto_all and not apply_src and his_real is not None
                    and reg_v != his_real and reg_v == "1" and local_real == his_real)
            if apply_src or his_real is None or reg_v == his_real or local_real != his_real:
                if "FBINCU 来自申请反查（视为正确）" not in reasons and reg_v == his_real:
                    reasons.append("FBINCU 已与 HIS 一致")
                if local_real != his_real and his_real is not None:
                    reasons.append(f"本地号 {local_real} ≠ HIS 号 {his_real}（编号体系不一致，人工裁决）")
                if reg_v != "1" and not apply_src and his_real is not None and reg_v != his_real:
                    reasons.append(f"登记非默认 1（{reg_v}），形态未知")
            L.append(f"## {pid}（病案号 {g['fbihid']}）：FBINCU={reg_v}，本地落窗={local_real}，"
                     f"HIS 真实={his_real}（OPER {','.join(sorted(g['opers']))}；文书 {g['docs']} 份；{g['when']}）")
            if not auto:
                L.append("- 状态：仅清单（" + ("；".join(reasons) or "未满足自动条件") + "）")
                L.append("")
                continue
            target = his_real
            for oper in sorted(g["opers"]):
                tag = {"reg_v": reg_v, "real_v": target, "oper": oper,
                       "bind": {"p": pid, "v": reg_v, "o": oper}}
                # ↓↓↓ 写入类管线（plan_fix/backup/apply_fix/audit）：绝不自动重试 ↓↓↓
                tables = plan_fix(dc, pid, reg_v, oper)
                if not tables:
                    L.append(f"- OPER {oper}：⚠ 未发现存数表，跳过")
                    continue
                if dry:
                    L.append(f"- OPER {oper}：dry-run 受影响 {len(tables)} 表/{sum(tables.values())} 行（未写入）")
                    continue
                try:
                    bname, total = backup_group(dc, pid, tag, tables)
                except Exception as exc:
                    L.append(f"- OPER {oper}：⚠ 备份失败 {type(exc).__name__}，跳过")
                    continue
                res = apply_fix(pid, tag, tables)
                L.append(f"- OPER {oper}：修订 {res['status']}"
                         + (f"（{res.get('rows')} 行，备份 {bname}）" if res["status"] == "fixed"
                            else f"（{res.get('error')}）"))
                audit_platform(pid, {"tag": res["tag"], "status": res["status"], "rows": res.get("rows"), "backup": bname})
            fixed_groups += 1
            L.append("")
        if bad:
            L.append(f"⚠ {bad} 行文书 PDFNAME 无法解析 OPER_ID，未处理，需人工查看")
        _write_output(opts, "\n".join(L), groups=len(groups), rows=len(rows))
        return 0
    except ScriptTimeoutError as exc:
        return fail(4, "run", str(exc), alert=alert)
    except TransientRetryExhausted as exc:
        return fail(3, "connection", str(exc), alert=alert)
    except OutputWriteError as exc:
        return fail(5, "output", str(exc), alert=alert)
    except Exception as exc:
        return fail(1, "run", f"{err_summary(exc)}\n{sanitize(traceback.format_exc(), 600)}", alert=alert)
    finally:
        release_lock(opts.lock, lock_token)
        alarm.cancel()


def _write_output(opts, text, *, groups, rows):
    if opts.out:
        atomic_write_text(Path(opts.out), text)
        print(f"[docare_daily] OK out={opts.out} groups={groups} rows={rows}", file=sys.stderr)
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
