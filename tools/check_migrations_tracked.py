#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_migrations_tracked.py — 迁移链 git 跟踪对拍检查器（215 号 E1）。

背景：三条生产已应用迁移（c4d5e6f7b8a9/a9b8c7d6e5f4/c0d1e2f3a4b5）曾长期
未跟踪——干净克隆缺链环、回滚/审计断裂。本工具把「alembic heads 涉及的
迁移文件必须已被 git 跟踪」固化为可重复执行的检查。

规则（单一来源，不 import alembic、不连数据库、离线可跑）：
- 解析 backend/alembic/versions/*.py 的 ``revision`` / ``down_revision``
  （支持 None 与元组分叉），重建版本图；
- head = 未被任何 down_revision 引用的 revision；对每个 head 沿
  down_revision 走到 base，得到「heads 涉及的迁移链」全环；
- 对拍 ``git ls-files``：链上任一文件未被跟踪 = ERROR；
- 链环断裂（引用的 revision 无对应文件）/ 文件解析失败 = ERROR；
- versions/ 下不在链上的未跟踪文件不计错（非链环不承重），仅 INFO。

用法：
  python tools/check_migrations_tracked.py          # 文本报告
  python tools/check_migrations_tracked.py --json   # 机器可读
退出码：0=全绿，1=存在 ERROR。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT / "backend" / "alembic" / "versions"

REVISION_RE = re.compile(r"^revision\s*[:=]\s*(.+)$", re.MULTILINE)
DOWN_REVISION_RE = re.compile(r"^down_revision\s*[:=]\s*(.+)$", re.MULTILINE)
QUOTED = re.compile(r"""["']([^"']+)["']""")


def _parse_rhs(raw: str) -> list[str] | None:
    """revision 赋值 RHS -> 引用列表；None 表示 base（down_revision = None）。"""
    raw = raw.strip()
    if raw == "None" or not raw:
        return None
    return QUOTED.findall(raw)


def load_version_graph(versions_dir: Path) -> tuple[dict[str, Path], dict[str, list[str] | None], list[str]]:
    """返回 (revision -> 文件, revision -> down 引用列表, 解析失败文件名)。"""
    rev_to_file: dict[str, Path] = {}
    rev_to_down: dict[str, list[str] | None] = {}
    broken: list[str] = []
    for py in sorted(versions_dir.glob("*.py")):
        text = py.read_text(encoding="utf-8", errors="replace")
        m_rev = REVISION_RE.search(text)
        m_down = DOWN_REVISION_RE.search(text)
        if not m_rev or not m_down:
            broken.append(py.name)
            continue
        revs = _parse_rhs(m_rev.group(1))
        if not revs or len(revs) != 1:
            broken.append(py.name)
            continue
        rev = revs[0]
        rev_to_file[rev] = py
        rev_to_down[rev] = _parse_rhs(m_down.group(1))
    return rev_to_file, rev_to_down, broken


def head_chain_revisions(rev_to_down: dict[str, list[str] | None]) -> tuple[list[str], list[str], list[str]]:
    """返回 (heads, 链上 revision 列表, 引用缺失的 revision 去重列表)。"""
    referenced: set[str] = set()
    for downs in rev_to_down.values():
        if downs:
            referenced.update(downs)
    heads = [rev for rev in rev_to_down if rev not in referenced]
    chain: list[str] = []
    missing: set[str] = set()
    seen: set[str] = set()
    queue = list(heads)
    while queue:
        rev = queue.pop()
        if rev in seen:
            continue
        seen.add(rev)
        if rev not in rev_to_down:
            missing.add(rev)
            continue
        chain.append(rev)
        downs = rev_to_down[rev]
        if downs:
            queue.extend(downs)
    return heads, chain, sorted(missing)


def git_tracked_files(pathspec: str) -> set[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", pathspec],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def run_checks(versions_dir: Path = VERSIONS_DIR) -> dict:
    errors: list[str] = []
    infos: list[str] = []
    try:
        rel_dir = versions_dir.relative_to(ROOT).as_posix()
    except ValueError:  # 仓库外目录（自测/离线场景）：一切视为未跟踪
        rel_dir = None
    if not versions_dir.is_dir():
        return {"errors": [f"versions dir not found: {versions_dir}"], "infos": infos,
                "heads": [], "chain_count": 0, "tracked": 0, "untracked": []}

    def _rel(py: Path) -> str:
        if rel_dir is None:
            return py.name
        return py.relative_to(ROOT).as_posix()

    rev_to_file, rev_to_down, broken = load_version_graph(versions_dir)
    for name in broken:
        errors.append(f"unparseable migration file: {name} (revision/down_revision not readable)")

    heads, chain, missing = head_chain_revisions(rev_to_down)
    for rev in missing:
        errors.append(f"chain broken: revision {rev} referenced but no file in {versions_dir}")

    tracked = git_tracked_files(rel_dir) if rel_dir is not None else set()
    untracked_chain: list[str] = []
    for rev in chain:
        rel = _rel(rev_to_file[rev])
        if rel not in tracked:
            untracked_chain.append(rel)
            errors.append(f"untracked migration in head chain: {rel} (revision {rev})")

    chain_files = {_rel(rev_to_file[rev]) for rev in chain}
    off_chain_untracked = sorted(
        rel
        for rel in (_rel(p) for p in versions_dir.glob("*.py"))
        if rel not in chain_files and rel not in tracked
    )
    if off_chain_untracked:
        infos.append(
            "off-chain untracked files (not load-bearing, INFO only): "
            + ", ".join(off_chain_untracked)
        )

    return {
        "heads": heads,
        "chain_count": len(chain),
        "tracked_chain_files": len(chain_files) - len(untracked_chain),
        "untracked": untracked_chain,
        "errors": errors,
        "infos": infos,
    }


def print_report(report: dict) -> None:
    print(f"迁移跟踪对拍：heads={','.join(report['heads']) or '(none)'} "
          f"链上迁移 {report['chain_count']} 个，未跟踪 {len(report['untracked'])} 个")
    for rel in report["untracked"]:
        print(f"  [ERROR] head 链上未跟踪: {rel}")
    for err in report["errors"]:
        print(f"  [ERROR] {err}")
    for info in report["infos"]:
        print(f"  [INFO] {info}")
    if not report["errors"]:
        print("  结果：全绿（head 链全环已被 git 跟踪）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args(argv)

    try:
        report = run_checks()
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] git ls-files failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
