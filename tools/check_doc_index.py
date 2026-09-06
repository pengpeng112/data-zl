#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_doc_index.py — 开发起步包目录唯一检查器（185 号 C1；183-S2）。

识别五种登记形态：编号正文 `NN_*.md` / 同号配套（`NN_*_结果.json`、
`NN_*_执行报告.md` 等）/ 同号输出目录 `output_rNN/` / README 组合登记
（反引号区间与列表，如 `` `61`–`67`、`71`、`87`–`89` ``）/ `_archive/`
归档条目（归档记录表按编号覆盖，文件名可省编号前缀、允许 28b/29/29c 变体）。

检查：孤儿（实际有、README 未登记）、幽灵（README 登记、任何位置无文件）、
同号多正文（README 同号标记或逐文件登记=已识别形态；否则待人工核对）、
缺类别（首行非 `> 类别：`）、归档孤儿/归档幽灵、主目录与归档同名残留。

`tools/register_doc.py --check` 复用本模块解析函数（唯一规则源，防双检查器漂移）。

默认只读报告；`--fix` 默认 dry-run，写 README 必须显式 `--files`（只补登记
模板行，绝不自动归档、移动或删除）。

已知良性（白名单，勿报）：
- 150 号：用户已确认结束（2026-09-05），正文已删、README 登记行保留作历史说明。
- 根级 CLAUDE.md：AGENTS.md 的纯转发入口，不属于本目录编号体系（扫描范围
  仅为 开发起步包/，不会产生该发现，此处留档防止后续误纳）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# 幽灵白名单：编号 -> 良性原因
GHOST_WHITELIST = {
    150: "已删仍登记：用户确认课题结束（2026-09-05），README 行保留作历史说明",
}

BACKTICK_FILE = re.compile(r"`(\d{1,3})_[^`]+`")
BACKTICK_RANGE = re.compile(r"`(\d{1,3})`\s*[–—-]\s*`(\d{1,3})`")
BACKTICK_BARE = re.compile(r"`(\d{1,3})`")
BACKTICK_OUTDIR = re.compile(r"`output_r(\d{1,3})/?`")
NUM_PREFIX = re.compile(r"^(\d{1,3})_(.+)$")
CATEGORY_LINE = re.compile(r"^>\s*类别[：:]")
OUTDIR_NAME = re.compile(r"^output_r(\d{1,3})$")


def scan_package(pkg: Path) -> dict:
    """扫描 开发起步包/ 实际文件形态（不读 README 内容）。

    返回：
      body          主目录编号正文/同号 .md -> {num: [文件名]}
      companion     主目录同号非 .md 配套（_结果.json 等） -> {num: [文件名]}
      outdirs       同号输出目录 -> {num: 目录名}
      archived      _archive/ 下编号文件（含 .txt 等） -> {num: [文件名]}
      missing_cat   主目录编号 .md 中首行非 `> 类别：` 的文件名列表
    """
    body: dict[int, list[str]] = defaultdict(list)
    companion: dict[int, list[str]] = defaultdict(list)
    for f in sorted(pkg.glob("*")):
        if not f.is_file():
            continue
        m = NUM_PREFIX.match(f.name)
        if not m:
            continue  # README.md、HIS问题表映射.csv、~$ 锁文件等非编号文件
        num = int(m.group(1))
        (body if f.suffix == ".md" else companion)[num].append(f.name)

    outdirs: dict[int, str] = {}
    for d in sorted(pkg.glob("output_r*")):
        m = OUTDIR_NAME.match(d.name)
        if m:
            outdirs[int(m.group(1))] = d.name

    archived: dict[int, list[str]] = defaultdict(list)
    archive_dir = pkg / "_archive"
    if archive_dir.is_dir():
        for f in sorted(archive_dir.glob("*")):
            if not f.is_file():
                continue
            m = NUM_PREFIX.match(f.name)
            if m:
                archived[int(m.group(1))].append(f.name)

    missing_cat: list[str] = []
    for num, names in sorted(body.items()):
        for name in names:
            first = next(
                (ln for ln in (pkg / name).read_text(encoding="utf-8").splitlines() if ln.strip()),
                "",
            )
            if not CATEGORY_LINE.match(first):
                missing_cat.append(name)

    return {
        "body": dict(body),
        "companion": dict(companion),
        "outdirs": dict(outdirs),
        "archived": dict(archived),
        "missing_cat": missing_cat,
    }


def readme_coverage(readme_text: str) -> dict[int, str]:
    """提取主 README 的登记覆盖（编号 -> 依据）。

    只认反引号形态：`` `NN_...` `` 文件名、`` `a`–`b` `` 区间、`` `N` `` 裸编号
    （完成度总览与证据链分组行中的裸编号同样是登记主张）、`` `output_rNN/` ``
    同号输出目录显式登记。目录更新记录中的纯文本历史提及不算登记（历史记录
    提及合法 ≠ 当前清单登记）。
    """
    covered: dict[int, str] = {}
    for m in BACKTICK_FILE.finditer(readme_text):
        covered[int(m.group(1))] = "file"
    for m in BACKTICK_RANGE.finditer(readme_text):
        covered.update(
            {n: f"range:{m.group(1)}-{m.group(2)}" for n in range(int(m.group(1)), int(m.group(2)) + 1)}
        )
    for m in BACKTICK_BARE.finditer(readme_text):
        covered.setdefault(int(m.group(1)), "bare")
    for m in BACKTICK_OUTDIR.finditer(readme_text):
        covered.setdefault(int(m.group(1)), "outdir")
    return covered


def archive_registry_numbers(archive_readme_text: str) -> set[int]:
    r"""提取 _archive/README.md 归档记录表登记的编号集合。

    原序号首格支持 `24`、`28b`、`29/29b/29c`、`96复核`、`41/42` 形态：
    首格须以数字开头，逐 `/` 段取 1–3 位前导数字（`(?!\d)` 排除 2026- 日期段）。
    `根计划`/`临时文件`/`无` 等非数字首格行不产生编号。
    """
    nums: set[int] = set()
    for ln in archive_readme_text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cell = s[1:].split("|", 1)[0].strip()
        if not cell or not cell[0].isdigit():
            continue
        for part in cell.split("/"):
            m = re.match(r"\d{1,3}(?!\d)", part.strip())
            if m:
                nums.add(int(m.group(0)))
    # 归档补充说明段落中的精确文件名提及（如 `91_....md`、`148_原始手写版_....md`）同样算登记
    for m in re.finditer(r"(\d{1,3})_", archive_readme_text):
        nums.add(int(m.group(1)))
    return nums


def run_checks(pkg: Path) -> dict:
    """执行全部检查，返回机器可读报告。发现项 severity：error/warn/info。"""
    readme = pkg / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    state = scan_package(pkg)

    covered = readme_coverage(readme_text)
    arch_reg = archive_registry_numbers(
        (pkg / "_archive" / "README.md").read_text(encoding="utf-8")
    ) if (pkg / "_archive" / "README.md").is_file() else set()

    body = state["body"]
    companion = state["companion"]
    outdirs = state["outdirs"]
    archived = state["archived"]

    findings: list[dict] = []

    # 1) 幽灵：README 反引号登记主张，但主目录/归档均无该编号任何文件
    exists_anywhere = set(body) | set(companion) | set(outdirs) | set(archived)
    for num in sorted(set(covered) - exists_anywhere):
        if num in GHOST_WHITELIST:
            findings.append(
                {"severity": "info", "code": "ghost_whitelisted", "num": num,
                 "detail": f"{num} 登记无文件（白名单：{GHOST_WHITELIST[num]}）"}
            )
        else:
            findings.append(
                {"severity": "error", "code": "ghost", "num": num,
                 "detail": f"README 登记编号 {num}（{covered[num]}），主目录与 _archive 均无文件"}
            )

    # 2) 孤儿：主目录有文件/输出目录，但主 README 未登记（归档登记不算主清单覆盖）
    for num in sorted(set(body) | set(companion)):
        if num not in covered:
            names = body.get(num, []) + companion.get(num, [])
            findings.append(
                {"severity": "error", "code": "orphan_doc", "num": num,
                 "detail": f"主目录文件未在 README 登记：{names}"}
            )
    for num, dname in sorted(outdirs.items()):
        if num not in covered:
            findings.append(
                {"severity": "warn", "code": "orphan_outdir", "num": num,
                 "detail": f"输出目录 {dname}/ 对应编号未在 README 登记"}
            )

    # 3) 同号多正文：README 权威判定（同号标记或逐文件登记）→ 已识别形态；否则待人工核对
    readme_lines = readme_text.splitlines()
    for num, names in sorted(body.items()):
        if len(names) < 2:
            continue
        lines_with_num = [
            ln for ln in readme_lines
            if BACKTICK_FILE.search(ln) and any(f"`{name}`" in ln for name in names)
        ] or [
            ln for ln in readme_lines if f"`{num}`" in ln or f"`{num:02d}`" in ln
        ]
        each_registered = all(
            any(f"`{name}`" in ln for ln in readme_lines) for name in names
        )
        has_tonggao = any("同号" in ln for ln in lines_with_num)
        if has_tonggao or each_registered:
            findings.append(
                {"severity": "info", "code": "multi_form_registered", "num": num,
                 "detail": f"同号多正文（README 同号标记或逐文件登记，已识别形态）：{names}"}
            )
        else:
            findings.append(
                {"severity": "warn", "code": "multi_body_unverified", "num": num,
                 "detail": f"同号多正文待人工核对（无同号标记、未逐文件登记）：{names}"}
            )

    # 4) 缺类别
    for name in state["missing_cat"]:
        findings.append(
            {"severity": "warn", "code": "missing_category", "num": int(name.split("_", 1)[0]),
             "detail": f"{name} 首行缺 `> 类别：`（体例第 3 步）"}
        )

    # 5) 归档孤儿/归档幽灵（_archive/README.md 归档记录表 ↔ 实际归档文件）
    for num, names in sorted(archived.items()):
        if num not in arch_reg:
            findings.append(
                {"severity": "warn", "code": "archive_orphan", "num": num,
                 "detail": f"_archive 文件未在归档记录表登记：{names}"}
            )
    for num in sorted(arch_reg - set(archived)):
        findings.append(
            {"severity": "info", "code": "archive_ghost", "num": num,
                 "detail": f"归档记录登记编号 {num}，_archive 无对应文件（可能以变体名登记，人工核对）"}
            )

    # 6) 主目录与归档同名残留（迁移不完整）
    main_names = {f.name for f in pkg.glob("*") if f.is_file()}
    for num, names in sorted(archived.items()):
        dup = [n for n in names if n in main_names]
        if dup:
            findings.append(
                {"severity": "error", "code": "main_archive_dup", "num": num,
                 "detail": f"同名文件同时存在于主目录与 _archive（迁移不完整）：{dup}"}
            )

    sev_rank = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (sev_rank[f["severity"]], f.get("num", 0), f["code"]))
    return {
        "package": str(pkg),
        "stats": {
            "body_numbers": len(body),
            "companion_numbers": len(companion),
            "outdirs": len(outdirs),
            "archived_numbers": len(archived),
            "readme_covered_numbers": len(covered),
            "findings": {
                sev: sum(1 for f in findings if f["severity"] == sev)
                for sev in ("error", "warn", "info")
            },
        },
        "findings": findings,
    }


def print_report(report: dict) -> None:
    s = report["stats"]
    print(f"目录检查：{report['package']}")
    print(
        f"  编号正文 {s['body_numbers']} 号 / 同号配套 {s['companion_numbers']} 号 / "
        f"输出目录 {s['outdirs']} / 归档 {s['archived_numbers']} 号 / "
        f"README 覆盖 {s['readme_covered_numbers']} 号"
    )
    cnt = s["findings"]
    print(f"  发现：error {cnt['error']} / warn {cnt['warn']} / info {cnt['info']}")
    for f in report["findings"]:
        print(f"  [{f['severity']}] {f['code']}: {f['detail']}")


def build_registration(doc_name: str, top_num: int) -> tuple[str, str]:
    """为 --fix 生成（目录更新记录行, 当前入口行）模板。占位符由人工核对后替换。"""
    num = int(NUM_PREFIX.match(doc_name).group(1))
    changelog_row = (
        f"| 登记日期 | 由 check_doc_index --fix 补登记：{doc_name}；"
        f"用途<一句话>；零越权声明<一句话> |"
    )
    entry_row = f"| P? | `{doc_name}` | <状态> | <一句话用途> |"
    if num <= top_num:
        entry_row += f"（注意：编号 {num} 不大于当前最大 {top_num}，确认为补登记而非撞号）"
    return changelog_row, entry_row


def apply_fix(pkg: Path, files: list[str], dry_run: bool) -> int:
    """--fix：只为显式列出的文件补 README 登记模板行；拒绝未编号/不存在文件，已登记跳过。"""
    readme = pkg / "README.md"
    text = readme.read_text(encoding="utf-8")
    covered = readme_coverage(text)
    state = scan_package(pkg)
    top_num = max(state["body"], default=0)
    rc = 0
    rows_changelog: list[str] = []
    rows_entry: list[str] = []
    for name in files:
        f = pkg / name
        m = NUM_PREFIX.match(Path(name).name)
        if not f.is_file() or not m:
            print(f"  [fix] 拒绝 {name}：不存在或文件名非 NN_ 前缀", file=sys.stderr)
            rc = 2
            continue
        num = int(m.group(1))
        if num in covered:
            print(f"  [fix] 跳过 {name}：编号 {num} 已在 README 登记（幂等）")
            continue
        changelog, entry = build_registration(Path(name).name, top_num)
        rows_changelog.append(changelog)
        rows_entry.append(entry)
        print(f"  [fix] {'DRY-RUN 将' if dry_run else '已'}登记 {name}（编号 {num}）")
    if dry_run or not rows_changelog:
        if dry_run:
            print(f"  [fix] dry-run：{len(rows_changelog)} 条待写（--fix --files 同时给出才实际写 README）")
        return rc
    lines = text.splitlines()

    def insert_after_section(lines: list[str], section: str, rows: list[str]) -> list[str]:
        """在节标题后插入：有 |---| 分隔行的表插分隔行后，否则插首个数据行前（更新记录表无表头）。"""
        for i, ln in enumerate(lines):
            if ln.strip() == section:
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and set(lines[j].strip()) <= {"|", "-", ":", " "}:
                    j += 1
                return lines[:j] + rows + lines[j:]
        return lines + ["", *rows]

    lines = insert_after_section(lines, "## 目录更新记录", rows_changelog)
    lines = insert_after_section(lines, "## 当前入口", rows_entry)
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [fix] README 已写入 {len(rows_changelog)} 条登记模板行（含 <占位>，须人工核对替换）")
    return rc


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="开发起步包目录唯一检查器（只读默认）")
    ap.add_argument("--pkg", default=str(root / "开发起步包"), help="包目录（默认仓库内 开发起步包/）")
    ap.add_argument("--check", action="store_true", help="执行检查并打印报告（默认行为，保留以兼容 register_doc）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（机器可读基线）")
    ap.add_argument("--fix", action="store_true", help="补登记（默认 dry-run；写 README 须同时给 --files）")
    ap.add_argument("--files", default="", help="显式文件列表（逗号分隔，仅相对包目录的编号文件名）")
    args = ap.parse_args(argv)

    pkg = Path(args.pkg)
    if not pkg.is_dir():
        print(f"包目录不存在：{pkg}", file=sys.stderr)
        return 2

    if args.fix:
        files = [x.strip() for x in args.files.split(",") if x.strip()]
        if not files:
            print("--fix 缺少 --files：默认 dry-run，不写任何文件（写 README 须显式文件列表）")
        return apply_fix(pkg, files, dry_run=not files)

    report = run_checks(pkg)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report["stats"]["findings"]["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
