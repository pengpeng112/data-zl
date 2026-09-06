#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multi_ai_evidence.py — multi-review/multi-verify 证据流程薄包装（185 号 C4；183-S4）。

只做机械证据管理：CLI 存在性预检、round 编号、UTF-8 编码归一（errors=replace）、
SHA-256、缺席状态与结果清单。**不把模型输出自动裁成最终结论**；无法证据裁决的
冲突、高危项和不可逆决策继续交人工；普通修复和常规回归不得调用本包装器。

子命令（多选一）：
  --cli-check [--clis codex,kimi,grok]        CLI 存在性预检（--version 只测存在，不调用模型）
  --init DIR [--base review]                   建 round 目录与 manifest.json 骨架
  --collect DIR --ai NAME --file F             归一 .raw → .md + SHA-256 + 登记在席
  --absent DIR --ai NAME --reason TEXT         登记缺席（402/超时/未登录等，如实写原因）
  --status DIR [--json]                        出清单：在席/缺席、文件哈希、完整性判定；
                                               全部外部模型缺席 → 输出明确「未完成」报告，
                                               绝不声称「四方完整」
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_CLIS = "codex,kimi,grok"
MANIFEST = "manifest.json"


def cli_check(clis: list[str]) -> dict:
    """只测 CLI 是否可执行（--version），不调用任何模型。"""
    result = {}
    for cli in clis:
        path = shutil.which(cli)
        version = ""
        if path:
            try:
                proc = subprocess.run(
                    [cli, "--version"], capture_output=True, text=True,
                    timeout=20, encoding="utf-8", errors="replace",
                )
                version = (proc.stdout or proc.stderr).strip()[:120]
            except Exception as exc:
                version = f"探测失败：{type(exc).__name__}"
        result[cli] = {"installed": bool(path), "version": version}
    return result


def load_manifest(round_dir: Path) -> dict:
    mf = round_dir / MANIFEST
    if mf.is_file():
        return json.loads(mf.read_text(encoding="utf-8"))
    return {
        "round": None,
        "created_at": None,
        "tool": "tools/multi_ai_evidence.py",
        "ais": {},
        "note": "本 manifest 只登记文件级证据（哈希/在席/缺席），不载结论；终审归人工。",
    }


def save_manifest(round_dir: Path, manifest: dict) -> None:
    (round_dir / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def do_init(round_dir: Path) -> dict:
    round_dir.mkdir(parents=True, exist_ok=True)
    m = load_manifest(round_dir)
    if m["round"] is None:
        num = re.search(r"round-(\d+)$", round_dir.name)
        m["round"] = int(num.group(1)) if num else round_dir.name
        m["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_manifest(round_dir, m)
    return m


def do_collect(round_dir: Path, ai: str, file: str) -> dict:
    src = round_dir / file
    if not src.is_file():
        raise SystemExit(f"[collect] 文件不存在：{src}")
    raw = src.read_bytes()
    # UTF-8 归一（errors=replace），原 .raw 保留不覆盖
    normalized = raw.decode("utf-8", errors="replace")
    dst = src.with_suffix("") if src.suffix == ".raw" else src.with_name(src.stem + ".md")
    if dst == src:
        dst = src.with_name(src.stem + "_normalized.md")
    dst.write_text(normalized, encoding="utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    m = load_manifest(round_dir)
    entry = m["ais"].setdefault(ai, {"status": "present", "files": [], "reason": ""})
    entry["status"] = "present"
    entry["reason"] = ""
    entry["files"] = [f for f in entry["files"] if f["file"] != src.name]
    entry["files"].append(
        {"file": src.name, "normalized_to": dst.name, "sha256_raw": sha, "bytes": len(raw)}
    )
    save_manifest(round_dir, m)
    return m


def do_absent(round_dir: Path, ai: str, reason: str) -> dict:
    m = load_manifest(round_dir)
    entry = m["ais"].setdefault(ai, {"status": "absent", "files": [], "reason": ""})
    entry["status"] = "absent"
    entry["reason"] = reason or "未注明原因（应如实记录：402/超时/未登录等）"
    save_manifest(round_dir, m)
    return m


def do_status(round_dir: Path) -> dict:
    m = load_manifest(round_dir)
    ais = m["ais"]
    present = sorted(a for a, v in ais.items() if v["status"] == "present")
    absent = sorted(a for a, v in ais.items() if v["status"] == "absent")
    unreported = sorted(a for a, v in ais.items() if v["status"] not in ("present", "absent"))
    all_absent = bool(ais) and not present
    conclusion = (
        "incomplete_all_absent"
        if all_absent
        else ("partial_absent" if absent else "all_reported")
    )
    if all_absent:
        note = (
            "明确未完成：全部外部模型缺席，本轮无外部证据可用；不得声称「四方完整」，"
            "须人工决定重试或升级，不得由本工具自动裁结论。"
        )
    elif absent:
        note = f"单方/部分缺席仍收口：缺席={absent}；在席证据已登记哈希；终审归人工。"
    else:
        note = "全部登记方在席；证据仅文件级登记，结论仍归人工终审。"
    return {
        "round": m["round"],
        "present": present,
        "absent": [{"ai": a, "reason": ais[a]["reason"]} for a in absent],
        "unreported": unreported,
        "files": {a: ais[a]["files"] for a in present},
        "conclusion": conclusion,
        "note": note,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="multi-review/multi-verify 证据薄包装（不裁结论）")
    ap.add_argument("--cli-check", action="store_true")
    ap.add_argument("--clis", default=DEFAULT_CLIS, help=f"CLI 名单，逗号分隔（默认 {DEFAULT_CLIS}）")
    ap.add_argument("--init", metavar="DIR")
    ap.add_argument("--collect", metavar="DIR")
    ap.add_argument("--absent", metavar="DIR")
    ap.add_argument("--status", metavar="DIR")
    ap.add_argument("--ai", help="collect/absent 的 AI 名")
    ap.add_argument("--file", help="collect 的产物文件（.raw 相对 round 目录）")
    ap.add_argument("--reason", default="", help="absent 原因（如实）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cli_check:
        out = {"cli_check": cli_check([c.strip() for c in args.clis.split(",") if c.strip()])}
        print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else "\n".join(
            f"  {k}: {'在席' if v['installed'] else '缺席'} {v['version']}" for k, v in out["cli_check"].items()
        ) or "  （空名单）")
        return 0
    if args.init:
        m = do_init(Path(args.init))
        print(f"[init] round={m['round']} -> {args.init}/{MANIFEST}")
        return 0
    if args.collect:
        if not args.ai or not args.file:
            raise SystemExit("[collect] 需要 --ai 与 --file")
        m = do_collect(Path(args.collect), args.ai, args.file)
        f = m["ais"][args.ai]["files"][-1]
        print(f"[collect] {args.ai} {f['file']} -> {f['normalized_to']} sha256={f['sha256_raw'][:16]}…")
        return 0
    if args.absent:
        if not args.ai:
            raise SystemExit("[absent] 需要 --ai")
        m = do_absent(Path(args.absent), args.ai, args.reason)
        print(f"[absent] {args.ai}：{m['ais'][args.ai]['reason']}")
        return 0
    if args.status:
        report = do_status(Path(args.status))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"round={report['round']} 结论={report['conclusion']}")
            print(f"  在席：{report['present'] or '无'}")
            for a in report["absent"]:
                print(f"  缺席：{a['ai']}（{a['reason']}）")
            print(f"  {report['note']}")
        # 全缺席=明确未完成，返回码 1 提醒人工；部分缺席/全在席=0
        return 1 if report["conclusion"] == "incomplete_all_absent" else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
