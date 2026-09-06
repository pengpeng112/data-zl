#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_instruction_drift.py — 指令层漂移只读检查（185 号 C5；183-S5）。

扫描 AGENTS.md、CLAUDE.md、项目 Skill（.agents/skills/*/SKILL.md）、全局 Skill
（~/.zcode/skills/*/SKILL.md）与 55 号顶部的批准/停止/只读/全量测试/历史授权
关键词，按四条语义规则报告**可能冲突**的行：

  R1 源库只读不放宽：对业务源库（HIS/ODS/Docare/CDMS/JHEMR/移动护理…）出现
     写动作（INSERT/UPDATE/DELETE/TRUNCATE/写入…）且同一行无门禁词
     （须/需/批准/授权/禁止/只读/白名单/受控/审计/默认关）。
  R2 平台自动 active 与人工批准不混用：一行内同时出现自动激活/自动生效类表述
     与批准/审批/授权，且无否定/区分词（不/不得/禁止/区别/区分/而非/≠）。
  R3 历史授权≠当前授权：历史/既往/此前/上次授权被“继续/沿用/自动恢复/无需再批”
     类表述引用，且无否定词。
  R4 局部阻塞不宣称完成：阻塞/受限/跳过/SKIP 语境与完成宣称同现且无否定词。

只报告，不自动改任何自然语言指令。验收不要求零高危：发现项如实留档。
白名单（已知良性，命中不报）：CLAUDE.md 转发行（整个文件是 AGENTS.md 的转发
入口，非独立指令源）；150 号幽灵相关行（C1 白名单同源）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RULES = {
    "R1_source_readonly": {
        "desc": "业务源库只读不得放宽",
        # 门禁前先剔除“无需/不用/免批”等反向词，防止其中的“须/用”字造成假门禁
        "anti_gate_strip": re.compile(r"无需|无须|不用|免批|免审|没有门槛|无门禁"),
        # “写入为 0 / 零写入 / 写入：0”是零写入**断言**（正确指令），非放宽
        "safe_zero_assert": re.compile(r"(写入|UPDATE|INSERT|DELETE|TRUNCATE)[^\n]{0,6}(0|零)|零写入|写入数[^\n]{0,4}0"),
        "gate_words": "须|需|要|批准|授权|禁止|不得|只读|白名单|受控|审计|默认关|严禁|红线|逐例",
        "write_pat": re.compile(
            r"(HIS|ODS|源库|源端|源数据库|业务源库|业务库|Docare|CDMS|JHEMR|LIS|PACS)"
            r"[^\n]{0,40}(INSERT|UPDATE|DELETE|TRUNCATE|DROP|写入|直接写|批量写|自动写|可以写|允许写)",
            re.I,
        ),
    },
    "R2_active_vs_approval": {
        "desc": "平台自动 active 与人工执行批准不得混用",
        # 不用裸“不”：防止“不等于/不用再”类漂移表述被误判为否定；跨句不匹配
        "neg_words": "不得|不能|禁止|严禁|区别|区分|而非|≠|不等于|切勿",
        "pat": re.compile(r"自动[^。；;\n]{0,12}(激活|active|生效|转正)[^。；;\n]{0,30}(批准|审批|授权)|(批准|审批|授权)[^。；;\n]{0,30}自动[^。；;\n]{0,12}(激活|active|生效)", re.I),
    },
    "R3_history_auth": {
        "desc": "历史授权不得成为当前授权",
        # “不自动恢复/不自动沿用”是否定形态（AGENTS 原文），不算触发
        "neg_words": "不得|不能|禁止|严禁|作废|过期|不等于|而非|不自动",
        "pat": re.compile(r"(历史|既往|此前|上次|曾经|已曾)[^。；;\n]{0,12}(授权|批准|确认|许可)[^。；;\n]{0,30}(继续|沿用|自动恢复|自动沿用|无需再|不用再|直接用)", re.I),
    },
    "R4_partial_complete": {
        "desc": "局部阻塞不得宣称全任务完成",
        # “不连坐”是规则本体的否定表述；跨句（。；;）不构成同款宣称
        "neg_words": "不得|不能|禁止|严禁|并非|而不是|不宣称|不连坐|未",
        "pat": re.compile(r"(阻塞|受阻|受限|跳过|SKIP|缺依赖|不可用)[^。；;\n]{0,50}(完成|全部完成|任务完成|已收口|已闭环)|(完成|已收口|已闭环)[^。；;\n]{0,50}(阻塞|受阻|跳过|SKIP)", re.I),
    },
}

KEYWORDS = ["批准", "授权", "停止", "只读", "全量测试", "历史授权", "生产发布", "零写入", "夜跑"]
WHITELIST_MARKERS = ("CLAUDE.md 转发", "150")


def scan_line(line: str) -> list[dict]:
    hits = []
    r1 = RULES["R1_source_readonly"]
    gate_target = r1["anti_gate_strip"].sub("", line)
    if (
        r1["write_pat"].search(line)
        and not r1["safe_zero_assert"].search(line)
        and not re.search(r1["gate_words"], gate_target)
    ):
        hits.append({"rule": "R1_source_readonly", "desc": r1["desc"],
                     "risk": "high", "line": line.strip()[:300]})
    for rid in ("R2_active_vs_approval", "R3_history_auth", "R4_partial_complete"):
        r = RULES[rid]
        if r["pat"].search(line) and not re.search(r["neg_words"], line):
            hits.append({"rule": rid, "desc": r["desc"],
                         "risk": "high" if rid != "R4_partial_complete" else "medium",
                         "line": line.strip()[:300]})
    return hits


def collect_targets(repo_root: Path, top_lines_55: int = 80) -> list[dict]:
    targets = []
    ag = repo_root / "AGENTS.md"
    if ag.is_file():
        targets.append({"path": str(ag), "kind": "agents", "whitelisted": False})
    cl = repo_root / "CLAUDE.md"
    if cl.is_file():
        targets.append({"path": str(cl), "kind": "claude_forward", "whitelisted": True,
                        "why": "CLAUDE.md 转发：整文件为 AGENTS.md 入口转发，非独立指令源"})
    for sk in sorted((repo_root / ".agents" / "skills").glob("*/SKILL.md")):
        targets.append({"path": str(sk), "kind": "project_skill", "whitelisted": False})
    gsk = Path.home() / ".zcode" / "skills"
    if gsk.is_dir():
        for sk in sorted(gsk.glob("*/SKILL.md")):
            targets.append({"path": str(sk), "kind": "global_skill", "whitelisted": False})
    p55 = repo_root / "开发起步包" / "55_系统未完成事项统一执行计划.md"
    if p55.is_file():
        targets.append({"path": str(p55), "kind": "55_top", "whitelisted": False,
                        "line_limit": top_lines_55})
    return targets


def run_scan(repo_root: Path, top_lines_55: int = 80) -> dict:
    findings: list[dict] = []
    keyword_census: dict[str, dict[str, int]] = {}
    scanned = []
    for t in collect_targets(repo_root, top_lines_55):
        path = Path(t["path"])
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            findings.append({"rule": "scan_error", "desc": f"读取失败 {exc}", "risk": "warn",
                             "source": t["path"], "lineno": 0, "line": ""})
            continue
        if "line_limit" in t:
            lines = lines[: t["line_limit"]]
        scanned.append({"path": t["path"], "kind": t["kind"], "lines": len(lines)})
        cens = keyword_census.setdefault(t["path"], {})
        for i, line in enumerate(lines, 1):
            for kw in KEYWORDS:
                if kw in line:
                    cens[kw] = cens.get(kw, 0) + 1
            if t["whitelisted"]:
                continue
            for hit in scan_line(line):
                if "150" in WHITELIST_MARKERS and re.search(r"150[^\n]{0,20}(已删|已结束|幽灵)", line):
                    hit["whitelisted"] = "150 号幽灵：C1 白名单同源，已知良性"
                findings.append({"source": t["path"], "lineno": i, **hit})
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    return {
        "repo": str(repo_root),
        "scanned": scanned,
        "findings": findings,
        "by_rule": by_rule,
        "note": "只报告可能冲突，不自动修改指令；高危项须人工裁决，本工具不裁终态。",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="指令漂移只读检查（四语义规则）")
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--top-55", type=int, default=80, help="55 号只扫顶部 N 行（默认 80）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = run_scan(Path(args.repo), args.top_55)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"指令漂移检查：扫描 {len(report['scanned'])} 个目标")
        print(f"  发现：{json.dumps(report['by_rule'], ensure_ascii=False)}")
        for f in report["findings"]:
            wl = f"（白名单：{f['whitelisted']}）" if f.get("whitelisted") else ""
            print(f"  [{f['risk']}] {f['rule']}{wl} {f['source']}:{f['lineno']}")
            print(f"      {f['line'][:160]}")
    return 0  # 只读报告：发现项不改变退出码（留档即过）


if __name__ == "__main__":
    sys.exit(main())
