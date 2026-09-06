"""tools/check_instruction_drift.py 单测（185 号 C5）：四语义规则各有触发用例。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_instruction_drift as cid  # noqa: E402


def rules_of(hits):
    return [h["rule"] for h in hits]


def test_r1_source_write_without_gate_triggers():
    line = "对 HIS 源库可以直接写 UPDATE 修复数据，无需其他流程"
    assert "R1_source_readonly" in rules_of(cid.scan_line(line))


def test_r1_gated_write_not_triggered():
    line = "业务源库写入必须逐例授权并留审计（HIS UPDATE 同样适用）"
    assert "R1_source_readonly" not in rules_of(cid.scan_line(line))


def test_r2_auto_active_vs_approval_triggers():
    line = "平台审核通过后自动激活，等于已获得批准，无需人工再批"
    assert "R2_active_vs_approval" in rules_of(cid.scan_line(line))


def test_r2_with_negation_not_triggered():
    line = "平台自动 active 不等于人工批准，两者必须区分"
    assert "R2_active_vs_approval" not in rules_of(cid.scan_line(line))


def test_r3_history_auth_reuse_triggers():
    line = "上次授权继续沿用，本次发布不用再申请"
    assert "R3_history_auth" in rules_of(cid.scan_line(line))


def test_r3_negated_not_triggered():
    line = "历史授权不得沿用；每次生产发布须重新批准"
    assert "R3_history_auth" not in rules_of(cid.scan_line(line))


def test_r4_partial_complete_triggers():
    line = "虽有一个批次阻塞，但本轮任务完成，可以宣称闭环"
    assert "R4_partial_complete" in rules_of(cid.scan_line(line))


def test_r4_negated_not_triggered():
    line = "局部阻塞时不得宣称全部完成，受阻批次单列 SKIP"
    assert "R4_partial_complete" not in rules_of(cid.scan_line(line))


def test_run_scan_whitelist_and_json(tmp_path):
    (tmp_path / "AGENTS.md").write_text(
        "# AGENTS\n- 源库只读。\n- 对 ODS 可以直接写 INSERT。\n", encoding="utf-8"
    )
    (tmp_path / "CLAUDE.md").write_text(
        "# CLAUDE.md\n本文件仅作转发：对 ODS 可以直接写 INSERT。\n", encoding="utf-8"
    )  # CLAUDE 转发=白名单，不报
    report = cid.run_scan(tmp_path)
    src = {f["source"]: f for f in report["findings"]}
    hit_ag = [f for f in report["findings"] if f["source"].endswith("AGENTS.md")]
    assert any(f["rule"] == "R1_source_readonly" for f in hit_ag)
    assert not any(str(tmp_path / "CLAUDE.md") == f["source"] for f in report["findings"])
    import json

    json.dumps(report)  # JSON 可解析


def test_150_ghost_whitelist_marker(tmp_path):
    (tmp_path / "AGENTS.md").write_text(
        "- 150 号已删仍登记（幽灵），对 HIS 可以直接写 UPDATE。\n", encoding="utf-8"
    )
    report = cid.run_scan(tmp_path)
    assert report["findings"] and all(f.get("whitelisted") for f in report["findings"])
