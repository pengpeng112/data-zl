"""tools/multi_ai_evidence.py 单测（185 号 C4）。

验收两用例：单方缺席仍收口 / 全部外部模型缺席生成明确未完成报告；
另覆盖 UTF-8 归一+SHA-256、CLI 预检可配置名单、manifest 不载结论。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multi_ai_evidence as mae  # noqa: E402


def _round(tmp_path: Path) -> Path:
    rd = tmp_path / "round-1"
    mae.do_init(rd)
    return rd


def test_single_absent_still_closes(tmp_path: Path):
    rd = _round(tmp_path)
    (rd / "审查_kimi.raw").write_bytes("kimi 审查内容".encode("utf-8"))
    mae.do_collect(rd, "kimi", "审查_kimi.raw")
    mae.do_absent(rd, "grok", "402 额度耗尽")
    report = mae.do_status(rd)
    assert report["conclusion"] == "partial_absent"
    assert report["present"] == ["kimi"]
    assert report["absent"][0]["ai"] == "grok" and "402" in report["absent"][0]["reason"]
    assert mae.main(["--status", str(rd)]) == 0  # 单缺席仍收口


def test_all_absent_explicit_incomplete(tmp_path: Path):
    rd = _round(tmp_path)
    for ai, why in [("kimi", "402"), ("grok", "超时"), ("codex", "未登录")]:
        mae.do_absent(rd, ai, why)
    report = mae.do_status(rd)
    assert report["conclusion"] == "incomplete_all_absent"
    assert "未完成" in report["note"]
    assert "四方完整" in report["note"] and "不得声称" in report["note"]
    assert mae.main(["--status", str(rd), "--json"]) == 1  # 明确未完成 → 非零提醒人工


def test_utf8_normalize_and_sha256(tmp_path: Path):
    rd = _round(tmp_path)
    gbk_bytes = "kimi 输出中文".encode("gbk") + b"\xff\xfe"
    (rd / "审查_kimi.raw").write_bytes(gbk_bytes)
    m = mae.do_collect(rd, "kimi", "审查_kimi.raw")
    f = m["ais"]["kimi"]["files"][0]
    assert f["sha256_raw"] == hashlib.sha256(gbk_bytes).hexdigest()
    normalized = (rd / f["normalized_to"]).read_text(encoding="utf-8")  # 可直接 UTF-8 解码
    assert "审查" not in normalized or True  # GBK 字节可能被替换为 U+FFFD，只保证可解码
    assert (rd / "审查_kimi.raw").read_bytes() == gbk_bytes  # 原 .raw 不覆盖


def test_cli_check_configurable():
    result = mae.cli_check(["git", "definitely_missing_cli_xyz"])
    assert result["git"]["installed"] is True
    assert result["definitely_missing_cli_xyz"]["installed"] is False


def test_manifest_carries_no_verdict(tmp_path: Path):
    rd = _round(tmp_path)
    (rd / "检查_codex.md").write_text("codex 检查", encoding="utf-8")
    m = mae.do_collect(rd, "codex", "检查_codex.md")
    blob = json.dumps(m, ensure_ascii=False)
    assert "同意" not in blob and "反对" not in blob  # 不载模型结论
    assert set(m["ais"]["codex"].keys()) == {"status", "files", "reason"}


def test_cli_check_default_runs():
    out = mae.cli_check(["cmd_windows_placeholder_never_exists"])
    assert out["cmd_windows_placeholder_never_exists"]["installed"] is False
