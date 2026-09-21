# -*- coding: utf-8 -*-
"""186 号纯逻辑测试：tools/morning_summary_identity.py 晨检汇总只读工具。

合成 JSON 样例（sample_evidence.json，全部虚构）覆盖：
两模式（文件/API）、计数口径（人员与动作分开、去重、partial/blocked 单列）、
60 人单列、无证据留痕（无记录/不插值）、enable 警告、无进度推算、输出脱敏。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[3] / "tools" / "morning_summary_identity.py"
SAMPLE = Path(__file__).resolve().parent / "sample_evidence.json"


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "morning_summary_identity_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tool():
    return load_tool()


def sample_raw():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


# ---------------- 1. 文件模式：计数口径 ----------------

def test_file_mode_person_and_action_counts(tool):
    ev = tool.normalize_evidence(sample_raw())
    s = tool.summarize(ev)
    # 人员（跨窗口去重，p0001 两窗出现只计 1 人）：5/230；partial 2；blocked 1
    assert s["baseline_progress"] == "5/230"
    assert s["baseline_persons"] == {"executed": 5, "partial": 2, "blocked": 1,
                                     "failed": 0, "skipped": 0}
    # 动作与人员分开计数（JHEMR/CDMS 双目标）
    assert s["action_totals"]["JHEMR"] == {"executed": 7, "attempted": 8,
                                           "blocked": 0, "failed": 0, "skipped": 1}
    assert s["action_totals"]["CDMS"] == {"executed": 5, "attempted": 7,
                                          "blocked": 2, "failed": 0, "skipped": 0}
    # 窗口级：W1 planned 4/executed 4/partial 1；W2 planned 4/executed 3/partial 1/blocked 1
    w1, w2 = s["windows"]
    assert (w1["date"], w1["run_id"], w1["status"]) == ("2026-09-10", "RUN-synth-001", "success")
    assert w1["persons"]["planned"] == 4 and w1["persons"]["partial"] == 1
    assert w2["persons"] == {"planned": 4, "executed": 3, "partial": 1,
                             "blocked": 1, "failed": 0, "skipped": 0}


def test_cli_file_mode_output(tool, capsys):
    code = tool.main(["-i", str(SAMPLE)])
    assert code == 0
    out = capsys.readouterr().out
    assert "已执行 5/230" in out
    assert "partial 2" in out and "blocked 1" in out
    assert "JHEMR 已执行 7/8" in out and "CDMS 已执行 5/7" in out
    assert "RUN-synth-002" in out and "partial_success" in out
    # 期望核对日期中无证据 → 无记录
    assert "2026-09-12：无记录" in out and "2026-09-13：无记录" in out
    # 60 人类目单独一节 + 不并入 230
    assert "待裁决，未纳入 230 批准基线" in out
    assert "已执行 1/60" in out
    # enable 固定展示且无警告（样例关闭）
    assert "enable 状态（预期关闭）" in out
    assert tool.WARNING_MARK not in out


# ---------------- 2. API 模式（fake fetch，无网络） ----------------

def _make_api_fetch(sample):
    calls = []

    def _attempts(window):
        return window["attempts"]

    items = [{"run_id": w["run_id"], "status": w["status"], "started_at": w["started_at"]}
             for w in sample["windows"]]
    details = {w["run_id"]: {"data": {"account_state_attempts": _attempts(w)}}
               for w in sample["windows"]}
    runs_payload = {"data": {"items": items}}
    status_payload = {"data": {"scheduler": {"run_mode": "disable_only"}}}

    def fetch(url, headers=None, timeout=30):
        calls.append((url, dict(headers or {})))
        if "/runs?" in url:
            return runs_payload
        if "/nightly/status" in url:
            return status_payload
        for rid, payload in details.items():
            if url.endswith(f"/runs/{rid}"):
                return payload
        raise AssertionError(f"unexpected url {url}")

    return fetch, calls


def test_api_mode_counts_and_token_handling(tool, monkeypatch, capsys):
    sample = sample_raw()
    fetch, calls = _make_api_fetch(sample)
    monkeypatch.setattr(tool, "_http_get_json", fetch)
    monkeypatch.setenv("SYNTH_TOKEN", "secret-token-do-not-leak")
    code = tool.main(["--api", "http://synth.invalid", "--token-env", "SYNTH_TOKEN"])
    assert code == 0
    out = capsys.readouterr().out
    # 与文件模式同口径
    assert "已执行 5/230" in out
    assert "待裁决，未纳入 230 批准基线" in out
    # run_mode=disable_only → enable 证据显示关闭
    assert "证据显示关闭" in out
    # token 绝不回显；请求都带 Bearer 头；只读 GET 两个端点族
    assert "secret-token-do-not-leak" not in out
    assert all(u.startswith("http://synth.invalid/api/v1/identity-sync/") for u, _ in calls)
    assert all(h.get("Authorization") == "Bearer secret-token-do-not-leak" for _, h in calls)
    assert any("/runs?" in u for u, _ in calls)
    assert sum(1 for u, _ in calls if "/runs?" not in u and "/nightly/status" not in u) == 2


def test_api_mode_raw_envelope_accepted(tool):
    # 直接吃平台 GET /runs + /runs/{id} 导出的原始 JSON（本地证据文件兼容）
    sample = sample_raw()
    raw = {"data": {"items": [
        {**w, "account_state_attempts": w["attempts"]} for w in sample["windows"]]}}
    s = tool.summarize(tool.normalize_evidence(raw))
    assert s["baseline_progress"] == "5/230"


# ---------------- 3. 60 人类目：单独一节、不并入 230 ----------------

def test_pending_category_not_merged_into_230(tool):
    raw = sample_raw()
    # 追加 5 个待裁决人员（有 person_categories 映射，无 attempt 级 category）
    w = raw["windows"][0]
    for i in range(5):
        code = f"extra{i}"
        raw["person_categories"]["pending_adjudication"].append(code)
        w["attempts"].append({"person_code": code, "target_system": "JHEMR",
                              "action": "disable", "status": "executed"})
    s = tool.summarize(tool.normalize_evidence(raw))
    assert s["baseline_progress"] == "5/230"  # 基线不动
    assert s["pending_persons"]["executed"] == 6  # q0001 + 5


# ---------------- 4. 无证据留痕：无记录、不插值 ----------------

def test_missing_dates_show_no_record_no_interpolation(tool, capsys):
    code = tool.main(["-i", str(SAMPLE), "--dates", "2026-09-09,2026-09-11,2026-09-14"])
    assert code == 0
    out = capsys.readouterr().out
    assert "2026-09-09：无记录" in out
    assert "2026-09-14：无记录" in out
    # 明确列出的日期才有行；09-10/09-12/09-13 未列 → 不在按日期核对节出现（不插值）
    assert "2026-09-10：" not in out
    assert "2026-09-12：" not in out


def test_no_evidence_at_all_shows_no_record(tool, capsys, tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"windows": []}), encoding="utf-8")
    code = tool.main(["-i", str(p)])
    assert code == 0
    out = capsys.readouterr().out
    assert f"各窗口明细\n{tool.NO_RECORD}" in out.replace("\r\n", "\n")
    assert "已执行 0/230" in out


# ---------------- 5. enable 警告 ----------------

def test_enable_executed_action_triggers_warning(tool, capsys, tmp_path):
    raw = sample_raw()
    raw["windows"][1]["attempts"].append(
        {"person_code": "p0009", "target_system": "JHEMR", "action": "enable",
         "status": "executed"})
    p = tmp_path / "warn.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    code = tool.main(["-i", str(p)])
    assert code == 0
    out = capsys.readouterr().out
    assert tool.WARNING_MARK in out
    assert "enable" in out
    assert "立即人工核对" in out


def test_enable_config_true_triggers_warning(tool, capsys, tmp_path):
    raw = sample_raw()
    raw["config_evidence"] = {"enable_enabled": True}
    p = tmp_path / "warn2.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    code = tool.main(["-i", str(p)])
    assert code == 0
    assert tool.WARNING_MARK in capsys.readouterr().out


def test_enable_section_always_present(tool, capsys, tmp_path):
    raw = {"windows": []}
    p = tmp_path / "bare.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    assert tool.main(["-i", str(p)]) == 0
    out = capsys.readouterr().out
    assert "enable 状态（预期关闭）" in out
    assert "无记录" in out  # 配置证据无记录
    assert tool.WARNING_MARK not in out


# ---------------- 6. 禁止进度推算 ----------------

def test_no_progress_projection(tool, capsys):
    assert tool.main(["-i", str(SAMPLE)]) == 0
    out = capsys.readouterr().out
    for banned in ("预计", "还需", "剩余窗口", "ETA"):
        assert banned not in out, banned
    # “预期进度/完成日期”字样仅允许出现在口径声明行（声明本身即禁止推算，不是推算结果）
    assert out.count("预期进度") == 1
    assert out.count("完成日期") == 1
    assert "不按天数/窗口数推算预期进度或完成日期" in out


# ---------------- 7. 输出脱敏：无凭据/身份证/姓名/工号 ----------------

def test_output_never_leaks_sensitive_fields(tool, capsys, tmp_path):
    raw = sample_raw()
    raw["windows"][0]["attempts"].append({
        "person_code": "p0099", "target_system": "JHEMR", "action": "disable",
        "status": "executed", "name": "张三", "id_card": "370104199001011234",
        "password": "pw-secret-1", "token": "tok-secret-2"})
    p = tmp_path / "leak.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    code = tool.main(["-i", str(p)])
    assert code == 0
    out = capsys.readouterr().out
    for secret in ("张三", "370104199001011234", "pw-secret-1", "tok-secret-2"):
        assert secret not in out
    # 工号不进输出（只输出聚合计数）
    for code_ in ("p0001", "p0005", "q0001", "p0099"):
        assert code_ not in out


# ---------------- 8. JSON 格式与用法错误 ----------------

def test_json_format_output(tool, capsys):
    assert tool.main(["-i", str(SAMPLE), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["baseline_progress"] == "5/230"
    assert data["enable"]["expected"] == "closed"
    assert data["enable"]["warning"] is False


def test_usage_errors(tool, capsys, monkeypatch):
    assert tool.main([]) == 2                      # 未指定模式
    assert tool.main(["-i", "a.json", "--api", "http://x"]) == 2   # 双模式
    assert tool.main(["--api", "http://x"]) == 2   # 缺 token-env
    monkeypatch.delenv("NO_SUCH_TOKEN_VAR", raising=False)
    assert tool.main(["--api", "http://x", "--token-env", "NO_SUCH_TOKEN_VAR"]) == 2
    err = capsys.readouterr().err
    assert "FAIL code=2" in err


def test_missing_input_file_exit_3(tool, capsys, tmp_path):
    assert tool.main(["-i", str(tmp_path / "nope.json")]) == 3
    assert "FAIL code=3" in capsys.readouterr().err
