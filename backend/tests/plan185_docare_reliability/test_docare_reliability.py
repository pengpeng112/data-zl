# -*- coding: utf-8 -*-
"""185 号纯逻辑测试：docare_mismatch_daily.py 可靠性层。

不连库、不触生产路径：fake connector + monkeypatch sleep/clock + tmp_path。
覆盖：重试后成功 / 重试耗尽退出非零 / 防重入二次启动退出 / stale 锁接管 /
原子输出失败无 0 字节残留 / 凭据脱敏 / 总超时 / 写入类不重试 / 告警适配器。
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[3] / "开发起步包" / "output_r177"
          / "docare_mismatch_daily.py")

# 真实 dry-run 副本同形态的扫描行：FBINCU 已与 HIS 一致 + 编号体系不一致 → 仅人工裁决
SCAN_ROWS_MANUAL = [
    {"PATIENTID": "00705241", "FBIHID": "0476581", "REG_V": "4", "LOCAL_REAL": "1",
     "REPORTNAME": "麻醉总结", "PDFNAME": "r_00705241_1_1.PDF", "FUPDATE": "2026-09-17 14:20:00"},
]
# 满足 v3 自动判据的扫描行：登记=1、本地落窗=HIS 真实号 3、FBINCU=1≠3
SCAN_ROWS_AUTO = [
    {"PATIENTID": "0099001", "FBIHID": "0470001", "REG_V": "1", "LOCAL_REAL": "3",
     "REPORTNAME": "麻醉总结", "PDFNAME": "a_0099001_7_2.PDF", "FUPDATE": "2026-09-17 10:00:00"},
]
HIS_VISITS_AUTO = [
    {"VISIT_ID": "1", "ADMISSION_DATE_TIME": "2026-01-01 00:00:00"},
    {"VISIT_ID": "3", "ADMISSION_DATE_TIME": "2026-09-01 00:00:00"},
]
HIS_VISITS_MANUAL = [
    {"VISIT_ID": "4", "ADMISSION_DATE_TIME": "2026-09-01 08:00:00"},
]

ORA_12541 = RuntimeError("DPY-4011: ORA-12541: TNS:no listener")
ORA_12543 = RuntimeError("ORA-12543: TNS:destination unreachable")
ORA_12170 = RuntimeError("ORA-12170: TNS:Connect timeout occurred")


class FlakyConnector:
    """按 SQL 标记路由行；failures 队列耗尽前抛连接类异常（None=永远失败）。"""

    def __init__(self, failures=None, rows_by_marker=None):
        self.failures = list(failures) if failures is not None else None
        self.rows_by_marker = rows_by_marker or {}
        self.calls = 0

    def execute_readonly(self, sql, params=None, max_rows=1000):
        self.calls += 1
        if self.failures is not None:
            if self.failures:
                raise self.failures.pop(0)
            if self.failures == [] and self._always:
                raise ORA_12541
        for marker, rows in self.rows_by_marker.items():
            if marker in sql:
                return rows
        return []

    @property
    def _always(self):
        return getattr(self, "always_fail", False)


class AlwaysFailConnector(FlakyConnector):
    def __init__(self):
        super().__init__(rows_by_marker={})
        self.always_fail = True

    def execute_readonly(self, sql, params=None, max_rows=1000):
        self.calls += 1
        raise ORA_12541


def load_script():
    spec = importlib.util.spec_from_file_location(
        f"docare_daily_under_test_{time.monotonic_ns()}", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def script():
    return load_script()


def manual_dc(failures=None):
    return FlakyConnector(failures, {
        "T_ITF_SM": SCAN_ROWS_MANUAL,
        "MED_VS_HIS": [{"C": 0}],
        "FROM DUAL": [{"PROBE": 1}],
    })


def manual_ods(failures=None):
    return FlakyConnector(failures, {
        "PAT_VISIT WHERE": HIS_VISITS_MANUAL,
        "FROM DUAL": [{"PROBE": 1}],
    })


class FakeSleep:
    def __init__(self):
        self.seconds = []

    def __call__(self, s):
        self.seconds.append(s)


# ---------------- 1. 重试后成功 ----------------

def test_transient_errors_retried_then_success(script, monkeypatch, tmp_path, capsys):
    dc = manual_dc(failures=[ORA_12541, ORA_12543])
    ods = manual_ods()
    monkeypatch.setattr(script, "ro_conn", lambda: dc)
    monkeypatch.setattr(script, "ods_conn", lambda: ods)
    fake_sleep = FakeSleep()
    monkeypatch.setattr(script.time, "sleep", fake_sleep)

    out = tmp_path / "list.md"
    lock = tmp_path / "daily.lock"
    code = script.main(["--dry-run", "--out", str(out), "--lock", str(lock),
                        "--retry-budget", "60", "--timeout", "300"])
    assert code == 0
    # 探活两次瞬时失败后被退避重试（5s、10s），随后成功
    assert fake_sleep.seconds[0] == pytest.approx(5.0)
    assert fake_sleep.seconds[1] == pytest.approx(10.0)
    text = out.read_text(encoding="utf-8")
    assert "手麻住院次错配" in text
    assert "00705241" in text  # 患者号按既定口径保留
    assert "仅清单" in text
    stderr = capsys.readouterr().err
    assert "retry probe_docare" in stderr
    assert "OK out=" in stderr
    # 锁正常释放
    assert not lock.exists()


# ---------------- 2. 重试耗尽 → 退出非零、无 0 字节残留 ----------------

def test_retry_exhausted_nonzero_exit_no_residue(script, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "ro_conn", lambda: AlwaysFailConnector())
    monkeypatch.setattr(script, "ods_conn", lambda: AlwaysFailConnector())
    out = tmp_path / "list.md"
    lock = tmp_path / "daily.lock"
    code = script.main(["--dry-run", "--out", str(out), "--lock", str(lock),
                        "--retry-budget", "0.05", "--timeout", "60"])
    assert code == 3
    stderr = capsys.readouterr().err
    assert "FAIL code=3" in stderr
    assert "ORA-12541" in stderr  # 摘要保留错误码供 cron.log 定位
    # 清单未创建、无 .tmp 残留（0 字节问题不复现）
    assert not out.exists()
    assert list(tmp_path.glob("*.tmp")) == []
    # 失败也释放锁
    assert not lock.exists()


def test_non_transient_error_not_retried(script, monkeypatch, tmp_path, capsys):
    dc = FlakyConnector(None, {"T_ITF_SM": SCAN_ROWS_MANUAL, "FROM DUAL": [{"PROBE": 1}]})
    calls = {"n": 0}
    orig_execute = dc.execute_readonly

    def counting_execute(sql, params=None, max_rows=1000):
        calls["n"] += 1
        if "T_ITF_SM" in sql:  # 扫描阶段抛非连接类错误（探活正常）
            raise RuntimeError("ORA-00942: table or view does not exist")
        return orig_execute(sql, params, max_rows)

    dc.execute_readonly = counting_execute
    monkeypatch.setattr(script, "ro_conn", lambda: dc)
    monkeypatch.setattr(script, "ods_conn", lambda: manual_ods())
    out = tmp_path / "list.md"
    code = script.main(["--dry-run", "--out", str(out), "--lock", str(tmp_path / "l.lock"),
                        "--retry-budget", "60"])
    assert code == 1  # 非连接类错误：其他失败
    assert calls["n"] == 2  # probe 成功 1 次 + scan 失败 1 次，无重试
    assert not out.exists()


# ---------------- 3. 防重入：锁占用二次启动退出 ----------------

def test_second_run_blocked_by_fresh_lock(script, monkeypatch, tmp_path, capsys):
    def must_not_connect():
        raise AssertionError("lock contention must abort before any connection")

    monkeypatch.setattr(script, "ro_conn", must_not_connect)
    lock = tmp_path / "daily.lock"
    lock.write_text("999@0", encoding="utf-8")
    code = script.main(["--dry-run", "--out", str(tmp_path / "list.md"),
                        "--lock", str(lock), "--stale-lock", "1800"])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "FAIL code=2" in stderr and "lock busy" in stderr
    assert not (tmp_path / "list.md").exists()


def test_stale_lock_taken_over_and_reported(script, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "ro_conn", lambda: manual_dc())
    monkeypatch.setattr(script, "ods_conn", lambda: manual_ods())
    lock = tmp_path / "daily.lock"
    lock.write_text("123@0", encoding="utf-8")
    stale = time.time() - 7200
    import os as _os
    _os.utime(lock, (stale, stale))
    out = tmp_path / "list.md"
    code = script.main(["--dry-run", "--out", str(out), "--lock", str(lock),
                        "--stale-lock", "1800", "--retry-budget", "5"])
    assert code == 0
    stderr = capsys.readouterr().err
    assert "stale lock taken over" in stderr and "123@0" in stderr
    assert out.exists()
    assert not lock.exists()  # 结束后释放


# ---------------- 4. 原子输出失败：无 0 字节残留 ----------------

def test_atomic_output_failure_keeps_old_file(script, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "ro_conn", lambda: manual_dc())
    monkeypatch.setattr(script, "ods_conn", lambda: manual_ods())
    out = tmp_path / "list.md"
    out.write_text("PREVIOUS DAY LIST", encoding="utf-8")

    import os as _os
    real_replace = _os.replace

    def broken_replace(src, dst, *a, **kw):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(_os, "replace", broken_replace)
    code = script.main(["--dry-run", "--out", str(out), "--lock", str(tmp_path / "l.lock")])
    monkeypatch.setattr(_os, "replace", real_replace)
    assert code == 5
    stderr = capsys.readouterr().err
    assert "FAIL code=5" in stderr and "atomic write failed" in stderr
    # 原文件内容原样保留，绝无 0 字节清单、无 .tmp 残留
    assert out.read_text(encoding="utf-8") == "PREVIOUS DAY LIST"
    assert list(tmp_path.glob("*.tmp")) == []


def test_scan_failure_stdout_mode_prints_nothing(script, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "ro_conn", lambda: AlwaysFailConnector())
    monkeypatch.setattr(script, "ods_conn", lambda: AlwaysFailConnector())
    code = script.main(["--dry-run", "--lock", str(tmp_path / "l.lock"),
                        "--retry-budget", "0.05"])
    assert code == 3
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout 整段打印：失败时不输出半截/空清单


# ---------------- 5. 凭据脱敏 ----------------

def test_sanitize_masks_credentials_keeps_patient_id(script):
    text = "connect password=SuperSecret123 failed for user ops$docare, patient 00705241, ORA-12541"
    out = script.sanitize(text, limit=400)
    assert "SuperSecret123" not in out
    assert "00705241" in out  # 患者号按既定口径保留
    assert "ORA-12541" in out


def test_failure_summary_is_sanitized(script, monkeypatch, tmp_path, capsys):
    boom = RuntimeError("ORA-12541 after password=TopSecret456")
    monkeypatch.setattr(script, "ro_conn", lambda: AlwaysFailConnector())

    def fail_with_secret(sql, params=None, max_rows=1000):
        raise boom

    conn = AlwaysFailConnector()
    conn.execute_readonly = fail_with_secret
    monkeypatch.setattr(script, "ods_conn", lambda: conn)
    code = script.main(["--dry-run", "--lock", str(tmp_path / "l.lock"),
                        "--retry-budget", "0.05"])
    assert code == 3
    stderr = capsys.readouterr().err
    assert "TopSecret456" not in stderr


# ---------------- 6. 总超时（软 deadline，注入时钟） ----------------

def test_retry_controller_deadline_raises_timeout(script):
    t = {"now": 1000.0}

    def clock():
        return t["now"]

    rc = script.RetryController(budget_seconds=600, deadline=1005.0,
                                clock=clock, sleep=lambda s: None)
    def fail_transient():
        t["now"] += 10  # 每次调用推进 10 秒
        raise ORA_12170
    with pytest.raises(script.ScriptTimeoutError):
        rc.call(fail_transient, label="unit")


def test_retry_controller_budget_exhausted(script):
    t = {"now": 0.0}
    rc = script.RetryController(budget_seconds=1.0, deadline=None,
                                clock=lambda: t["now"], sleep=lambda s: None)
    attempts = {"n": 0}

    def fail_transient():
        attempts["n"] += 1
        t["now"] += 0.6
        raise ORA_12541

    with pytest.raises(script.TransientRetryExhausted):
        rc.call(fail_transient, label="unit")
    assert attempts["n"] >= 2  # 确实重试过


def test_retry_controller_shared_budget_across_calls(script):
    t = {"now": 0.0}
    rc = script.RetryController(budget_seconds=2.0, deadline=None,
                                clock=lambda: t["now"], sleep=lambda s: None)
    calls = {"a": 0, "b": 0}

    def flaky_a():
        calls["a"] += 1
        if calls["a"] == 1:
            t["now"] += 1.5
            raise ORA_12541
        return "ok-a"

    def always_b():
        calls["b"] += 1
        t["now"] += 0.1
        raise ORA_12541

    assert rc.call(flaky_a, label="a") == "ok-a"
    # 第二个调用共享同一预算：a 已耗 1.5s，b 只剩 0.5s
    with pytest.raises(script.TransientRetryExhausted):
        rc.call(always_b, label="b")
    assert calls["a"] == 2 and calls["b"] >= 2


# ---------------- 7. 写入类操作绝不自动重试 ----------------

def test_retry_controller_retryable_false_single_attempt(script):
    rc = script.RetryController(budget_seconds=60, deadline=None,
                                clock=lambda: 0.0, sleep=lambda s: None)
    calls = {"n": 0}

    def transient():
        calls["n"] += 1
        raise ORA_12541

    with pytest.raises(RuntimeError):
        rc.call(transient, label="apply_fix", retryable=False)
    assert calls["n"] == 1


def test_fix_pipeline_not_retried_on_transient_error(script, monkeypatch, tmp_path, capsys):
    dc = FlakyConnector(None, {
        "T_ITF_SM": SCAN_ROWS_AUTO,
        "MED_VS_HIS": [{"C": 0}],
        "FROM DUAL": [{"PROBE": 1}],
    })
    monkeypatch.setattr(script, "ro_conn", lambda: dc)
    monkeypatch.setattr(script, "ods_conn", lambda: FlakyConnector(None, {
        "PAT_VISIT WHERE": HIS_VISITS_AUTO, "FROM DUAL": [{"PROBE": 1}]}))
    monkeypatch.setattr(script, "plan_fix", lambda conn, pid, reg_v, oper: {"MEDSURGERY.T_DEMO": 2})
    monkeypatch.setattr(script, "backup_group",
                        lambda conn, pid, tag, tables: ("fix_backup_x.json", 2))
    apply_calls = {"n": 0}

    def apply_fix_never_retry(pid, tag, tables):
        apply_calls["n"] += 1
        raise ORA_12543  # 写入阶段连接失败：必须直接失败，绝不重试

    monkeypatch.setattr(script, "apply_fix", apply_fix_never_retry)
    out = tmp_path / "list.md"
    code = script.main(["--patient", "0099001", "--fix", "--out", str(out),
                        "--lock", str(tmp_path / "l.lock"), "--retry-budget", "60"])
    assert code == 1  # 写入管线异常 → 其他失败（非重试耗尽）
    assert apply_calls["n"] == 1
    stderr = capsys.readouterr().err
    assert "ORA-12543" in stderr
    assert not out.exists()  # 修订失败不出清单


# ---------------- 8. 告警适配器 ----------------

def test_alert_disabled_by_default(script):
    adapter = script.build_alert_adapter("")
    assert isinstance(adapter, script.NullAlertAdapter)
    assert adapter.alert("t", "b") is False


def test_local_file_alert_writes_sanitized_line(script, tmp_path):
    path = tmp_path / "alerts.log"
    adapter = script.build_alert_adapter(str(path))
    assert isinstance(adapter, script.LocalFileAlertAdapter)
    assert adapter.alert("docare fail", "password=abc ORA-12541") is True
    text = path.read_text(encoding="utf-8")
    assert "ORA-12541" in text
    assert "abc" not in text


def test_failure_fires_local_alert(script, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "ro_conn", lambda: AlwaysFailConnector())
    monkeypatch.setattr(script, "ods_conn", lambda: AlwaysFailConnector())
    alert_path = tmp_path / "alerts.log"
    code = script.main(["--dry-run", "--lock", str(tmp_path / "l.lock"),
                        "--retry-budget", "0.05", "--alert-file", str(alert_path)])
    assert code == 3
    line = alert_path.read_text(encoding="utf-8")
    assert "FAIL code=3" in line and "ORA-12541" in line


# ---------------- 9. 业务逻辑回归：v3 判据仍产出与旧版一致的清单 ----------------

def test_dry_run_list_matches_v3_format(script, monkeypatch, tmp_path):
    monkeypatch.setattr(script, "ro_conn", lambda: manual_dc())
    monkeypatch.setattr(script, "ods_conn", lambda: manual_ods())
    out = tmp_path / "list.md"
    code = script.main(["--dry-run", "--out", str(out), "--lock", str(tmp_path / "l.lock")])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "# 手麻住院次错配 · 每日（HIS 核验自动修订，dry-run）" in text
    assert "- 窗口：昨日全天" in text
    assert "候选错配文书行数：1；患者×住院次组合：1" in text
    assert "FBINCU=4，本地落窗=1，HIS 真实=4" in text
    assert "编号体系不一致，人工裁决" in text


def test_dry_run_auto_candidate_shows_dry_plan(script, monkeypatch, tmp_path):
    dc = FlakyConnector(None, {
        "T_ITF_SM": SCAN_ROWS_AUTO,
        "MED_VS_HIS": [{"C": 0}],
        "FROM DUAL": [{"PROBE": 1}],
    })
    monkeypatch.setattr(script, "ro_conn", lambda: dc)
    monkeypatch.setattr(script, "ods_conn", lambda: FlakyConnector(None, {
        "PAT_VISIT WHERE": HIS_VISITS_AUTO, "FROM DUAL": [{"PROBE": 1}]}))
    monkeypatch.setattr(script, "plan_fix", lambda conn, pid, reg_v, oper: {"MEDSURGERY.T_DEMO": 2})
    out = tmp_path / "list.md"
    code = script.main(["--patient", "0099001", "--fix", "--dry-run",
                        "--out", str(out), "--lock", str(tmp_path / "l.lock")])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "FBINCU=1，本地落窗=3，HIS 真实=3" in text
    assert "dry-run 受影响 1 表/2 行（未写入）" in text


# ---------------- 10. 锁释放归属：不误删接管者的锁 ----------------

def test_release_lock_only_removes_own_token(script, tmp_path):
    lock = tmp_path / "l.lock"
    lock.write_text("other@123", encoding="utf-8")
    script.release_lock(lock, "mine@456")
    assert lock.read_text(encoding="utf-8") == "other@123"
    script.release_lock(lock, "other@123")
    assert not lock.exists()
