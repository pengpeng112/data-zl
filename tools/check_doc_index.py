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


def scan_archive_outdirs(pkg: Path) -> list[str]:
    """round-10 扩展：_archive/ 下 output_r*/ 等子目录（归档证据目录形态，目录级登记即可）。"""
    archive_dir = pkg / "_archive"
    if not archive_dir.is_dir():
        return []
    return sorted([d.name for d in archive_dir.iterdir() if d.is_dir()])


EXPORTS_TASK = re.compile(r"^(\d+)、")
EXPORTS_WHITELIST = {"_templates"}


def check_exports_numbering(repo: Path) -> tuple[list[dict], str]:
    """round-10 扩展（仅本机有效）：取数/exports 任务目录编号合规。

    规则（AGENTS 2026-09-08）：任务目录须 `序号、中文名`；`_templates` 为白名单；
    编号缺位合法（历史空号）仅提示。取数/ 属 gitignored 区，克隆后本项无效。
    """
    exp = repo / "取数" / "exports"
    if not exp.is_dir():
        return [], "取数/exports 不存在（非本仓布局，跳过）"
    findings: list[dict] = []
    nums: set[int] = set()
    for d in sorted(exp.iterdir()):
        if not d.is_dir():
            continue
        m = EXPORTS_TASK.match(d.name)
        if m:
            nums.add(int(m.group(1)))
        elif d.name not in EXPORTS_WHITELIST:
            findings.append({"severity": "error", "code": "exports_unnumbered", "num": 0,
                             "detail": f"exports 任务目录无编号：{d.name}/（规则：序号、中文名；白名单 {sorted(EXPORTS_WHITELIST)}）"})
    for n in sorted(nums):
        if n > 1 and (n - 1) not in nums and n not in (1,):
            findings.append({"severity": "info", "code": "exports_gap", "num": n,
                             "detail": f"exports 编号 {n} 前存在空号 {n-1}（历史空号合法，仅提示）"})
    note = "exports 联检仅本机工作区有效（取数/ 为 gitignored）"
    return findings, note


INDEX_ARROW_LINK = re.compile(r"→\s*`([^`]+)`")
INDEX_BACKTICK = re.compile(r"`([^`]+)`")
INDEX_CMD = re.compile(r"^(python|pnpm|npm|npx|git|bash|cd|pip|poetry)\b", re.I)
INDEX_CACHE_PREFIXES = ("tools/.cache/",)
INDEX_ROOT_FILES = {
    "AGENTS.md", "INDEX.md", "CLAUDE.md", "GIT_SETUP.md", ".gitignore",
}
INDEX_ROOT_DIRS = {
    "review", "verify", "artifacts", "_scratch", "backend", "frontend",
    "tools", "取数", "deploy", "drivers",
}

# 兼容旧名：历史测试/调用若引用 INDEX_LINK，等同箭头形式
INDEX_LINK = INDEX_ARROW_LINK


def _index_is_command(s: str) -> bool:
    s = s.strip()
    if INDEX_CMD.match(s):
        return True
    parts = s.split()
    return bool(parts) and bool(INDEX_CMD.match(parts[0]))


def _index_looks_like_path(s: str) -> bool:
    raw = s.strip()
    if not raw or raw.startswith("http") or _index_is_command(raw):
        return False
    if any(ch in raw for ch in "*?"):
        return False
    core = raw.rstrip("/")
    if "/" in raw or raw.endswith((".md", ".py", ".json", ".ts", ".vue", ".sh", ".bat", ".txt")):
        return True
    if core in INDEX_ROOT_FILES or core in INDEX_ROOT_DIRS:
        return True
    return False


def extract_index_link_targets(text: str) -> list[str]:
    """抽出 INDEX 应校验的路径：想做X表第二列反引号 + 全文箭头形式路径。"""
    seen: list[str] = []

    def add(raw: str) -> None:
        t = raw.split("#")[0].strip().split("（")[0].strip()
        if t and t not in seen and not _index_is_command(t):
            seen.append(t)

    for raw in INDEX_ARROW_LINK.findall(text):
        add(raw)

    in_route = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_route = "想做" in line
            continue
        if not in_route or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if "想做什么" in cells[0] or cells[0].startswith("---"):
            continue
        for raw in INDEX_BACKTICK.findall(cells[1]):
            add(raw)
    return seen


def check_index_links(repo: Path) -> list[dict]:
    """round-10 扩展：INDEX「想做X读Y」表第二列路径 + 箭头形式路径存在性（断链=warn）。

    环境相关 `~/...`、gitignored 本地缓存缺失记 info，不升 warn。
    """
    idx = repo / "INDEX.md"
    if not idx.is_file():
        return []
    findings: list[dict] = []
    for t in extract_index_link_targets(idx.read_text(encoding="utf-8")):
        if not _index_looks_like_path(t):
            continue
        posix = t.replace("\\", "/")
        if t.startswith("~"):
            if Path(t).expanduser().exists():
                continue
            findings.append({
                "severity": "info", "code": "index_env_link", "num": 0,
                "detail": f"INDEX.md 环境相关路径本机不存在（不记断链）：{t}",
            })
            continue
        if (repo / t).exists():
            continue
        if posix.startswith(INDEX_CACHE_PREFIXES):
            findings.append({
                "severity": "info", "code": "index_cache_missing", "num": 0,
                "detail": f"INDEX.md 指向本地缓存未生成（可运行 build_repo_manifest.py）：{t}",
            })
            continue
        findings.append({
            "severity": "warn", "code": "index_broken_link", "num": 0,
            "detail": f"INDEX.md 指向不存在：{t}",
        })
    return findings


H1_TITLE = re.compile(r"^#\s+(.*)$")


def check_number_title(pkg: Path, state: dict) -> list[dict]:
    """round-10 扩展：编号-标题一致性（文件名 NN_标题 vs 正文一级标题前导编号，错配=warn 提示）。

    实证样例：187 号文件正文一级标题仍为"150、…"（187 号纪要 §0 已登记）。
    规则：一级标题存在前导数字且 ≠ 文件编号 → warn；无前导数字不判（标题自由）。
    """
    findings: list[dict] = []
    h1_num = re.compile(r"^(\d+)")
    for num, names in sorted(state["body"].items()):
        for name in names:
            try:
                text = (pkg / name).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            h1 = next((H1_TITLE.match(ln).group(1).strip() for ln in text.splitlines() if H1_TITLE.match(ln)), "")
            if not h1:
                continue
            m2 = h1_num.match(h1)
            if m2 and len(m2.group(1)) >= 4:
                continue  # 4 位以上前导数字视为年份（如 2026…），非编号
            if m2 and int(m2.group(1)) != num:
                findings.append({"severity": "warn", "code": "number_title_mismatch", "num": num,
                                 "detail": f"{name} 正文一级标题前导编号「{m2.group(1)}」≠ 文件编号 {num}（疑似沿用旧标题）"})
    return findings


def run_checks(pkg: Path, repo: Path | None = None) -> dict:
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

    # 7) round-10 扩展：_archive 子目录（归档证据目录，info 登记）
    for dname in scan_archive_outdirs(pkg):
        findings.append({"severity": "info", "code": "archive_subdir", "num": 0,
                         "detail": f"_archive/ 含子目录 {dname}/（归档证据目录，目录级登记）"})

    # 8) round-10 扩展：exports 编号联检（仅本机）+ INDEX 断链 + 编号-标题一致性
    ext_note = ""
    if repo is not None:
        exp_findings, ext_note = check_exports_numbering(repo)
        findings.extend(exp_findings)
        findings.extend(check_index_links(repo))
    findings.extend(check_number_title(pkg, state))

    sev_rank = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (sev_rank[f["severity"]], f.get("num", 0), f["code"]))
    report = {
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
    if ext_note:
        report["extensions_note"] = ext_note
    return report


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

    report = run_checks(pkg, repo=root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report["stats"]["findings"]["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
