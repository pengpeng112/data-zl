#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_repo_manifest.py —— 本地派生视图生成器（round-10 §3.4）。

契约（漂移四要素）：
1. 键=仓库相对路径（编号仅关联字段；同号多文件不覆盖）；
2. 字段白名单：path/category_line/status_hint/title/docstring_first_line/size/mtime；
   标题/docstring 首行做脱敏（身份/患者/凭据模式 → 掩码）；
3. 过期判据：任一源文件 mtime 晚于 manifest.generated_at 即过期，须重生成；
4. 本文件是缓存视图，不是权威入口——状态优先级 55 > README 分组 > 正文类别行；
   "现行查询"路由平台查询资产接口，不靠本地文件名推断。

输出：tools/.cache/repo_manifest.json（gitignored，不入库）。
用法：python tools/build_repo_manifest.py [--output PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SENSITIVE_PATTERNS = [
    (re.compile(r"\d{17}[\dXx]"), "<身份证>"),
    (re.compile(r"1[3-9]\d{9}"), "<手机号>"),
    (re.compile(r"(?i)(password|passwd|secret|token)\s*[:=]\s*\S+"), r"\1=<掩码>"),
]
CATEGORY = re.compile(r"^>\s*类别：(.+)$", re.M)
H1 = re.compile(r"^#\s+(.+)$", re.M)


def sanitize(text: str) -> str:
    for pat, rep in SENSITIVE_PATTERNS:
        text = pat.sub(rep, text)
    return text


def _status_hint(path: Path, category_line: str | None) -> str:
    """条目级状态提示。权威顺序见 contract.authority_priority；此处只落提示，不替代 55/README。"""
    if path.name.startswith("55_"):
        return "权威待办入口"
    if category_line:
        return category_line
    if path.suffix == ".py":
        return "script"
    if path.is_dir():
        return "directory"
    return "未标注"


def entry(path: Path) -> dict:
    rel = path.relative_to(REPO).as_posix()
    e = {
        "path": rel,
        "size": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    }
    category_line = None
    if path.suffix == ".md":
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            head = ""
        m = CATEGORY.search(head)
        if m:
            category_line = sanitize(m.group(1).strip())
            e["category_line"] = category_line
        h = H1.search(head)
        if h:
            e["title"] = sanitize(h.group(1).strip()[:80])
        num = re.match(r"(\d+)_", path.name)
        if num:
            e["num"] = int(num.group(1))  # 关联字段，非键
    elif path.suffix == ".py":
        try:
            doc = (path.read_text(encoding="utf-8", errors="ignore").split('"""')[1:2] or [""])[0]
            first = next((l.strip() for l in doc.splitlines() if l.strip()), "")
            if first:
                e["docstring_first_line"] = sanitize(first[:100])
        except (OSError, IndexError):
            pass
    e["status_hint"] = _status_hint(path, category_line)
    return e


def build(sections: dict[str, list[Path]]) -> dict:
    items: dict[str, dict] = {}
    for section, paths in sections.items():
        for p in paths:
            e = entry(p)
            e["section"] = section
            items[e["path"]] = e
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "key": "relative path",
            "authority_priority": ["55_系统未完成事项统一执行计划.md", "开发起步包/README.md", "正文类别行"],
            "staleness": "任一源文件 mtime 晚于 generated_at 即过期，须重生成",
            "disclaimer": "缓存视图，禁止手改；不得替代 README/55/启动自检；现行查询以平台查询资产为准",
        },
        "sections": {k: len(v) for k, v in sections.items()},
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成本地 repo_manifest.json 缓存视图")
    ap.add_argument("--output", default=str(REPO / "tools/.cache/repo_manifest.json"))
    args = ap.parse_args(argv)

    kb = REPO / "开发起步包"
    sections = {
        "kb_md": sorted(kb.glob("*.md")),
        "kb_asset_pkgs": sorted(kb.glob("数据资产_*")),
        "kb_output_r": sorted(kb.glob("output_r*")),
        "tools_py": sorted((REPO / "tools").glob("*.py")),
        "backend_scripts": sorted((REPO / "backend/scripts").glob("*.py")),
        "exports_tasks": sorted((REPO / "取数/exports").glob("*")),
    }
    manifest = build(sections)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()[:16]
    print(f"manifest: {out} | items={len(manifest['items'])} | sections={manifest['sections']} | sha256[:16]={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
