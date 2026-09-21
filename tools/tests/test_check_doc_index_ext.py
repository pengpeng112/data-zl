# -*- coding: utf-8 -*-
"""round-10 扩展检查测试：exports 编号 / INDEX 断链 / 编号-标题一致性 / archive 子目录。

纯逻辑（tmp fixture），不依赖仓库现状。运行：backend/.venv pytest 本文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_doc_index import (  # noqa: E402
    check_exports_numbering,
    check_index_links,
    check_number_title,
    extract_index_link_targets,
    scan_archive_outdirs,
)
import check_doc_index as cdi  # noqa: E402


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "取数" / "exports").mkdir(parents=True)
    return tmp_path


def mk(d: Path, name: str):
    p = d / name
    p.mkdir(exist_ok=True)
    (p / "README.md").write_text("# x", encoding="utf-8")
    return p


class TestExportsNumbering:
    def test_numbered_ok(self, repo):
        mk(repo / "取数/exports", "1、医保")
        mk(repo / "取数/exports", "3、移动护理")
        f, note = check_exports_numbering(repo)
        assert [x["code"] for x in f] == ["exports_gap"] and f[0]["severity"] == "info"
        assert "仅本机" in note

    def test_unnumbered_error(self, repo):
        mk(repo / "取数/exports", "20260730某某")
        f, _ = check_exports_numbering(repo)
        assert any(x["code"] == "exports_unnumbered" and x["severity"] == "error" for x in f)

    def test_template_whitelisted(self, repo):
        mk(repo / "取数/exports", "_templates")
        f, _ = check_exports_numbering(repo)
        assert f == []

    def test_missing_exports_dir(self, tmp_path):
        f, note = check_exports_numbering(tmp_path)
        assert f == [] and "跳过" in note


class TestIndexLinks:
    def test_broken_link_warn(self, repo):
        (repo / "INDEX.md").write_text("取数 → `取数/START_HERE.md`\n坏链 → `不存在/xx.md`", encoding="utf-8")
        (repo / "取数/START_HERE.md").parent.mkdir(exist_ok=True)
        (repo / "取数/START_HERE.md").write_text("x", encoding="utf-8")
        f = check_index_links(repo)
        assert len(f) == 1 and f[0]["code"] == "index_broken_link" and f[0]["severity"] == "warn"

    def test_table_second_column(self, repo):
        (repo / "INDEX.md").write_text(
            "## 想做 X → 读 Y\n\n"
            "| 想做什么 | 去哪里 |\n"
            "|---|---|\n"
            "| 安全 | `AGENTS.md`（根） |\n"
            "| 脚本 | `tools/.cache/repo_manifest.json`（本地缓存，`python tools/build_repo_manifest.py` 重生成） |\n"
            "| 坏链 | `不存在/xx.md` |\n",
            encoding="utf-8",
        )
        (repo / "AGENTS.md").write_text("x", encoding="utf-8")
        targets = extract_index_link_targets((repo / "INDEX.md").read_text(encoding="utf-8"))
        assert "python tools/build_repo_manifest.py" not in targets
        f = check_index_links(repo)
        codes = {(x["code"], x["severity"], x["detail"].split("：")[-1]) for x in f}
        assert ("index_broken_link", "warn", "不存在/xx.md") in codes
        assert ("index_cache_missing", "info", "tools/.cache/repo_manifest.json") in codes
        assert not any(x["code"] == "index_broken_link" and "build_repo_manifest" in x["detail"] for x in f)

    def test_no_index_ok(self, repo):
        assert check_index_links(repo) == []

    def test_real_index_routing_no_warn(self):
        repo = Path(__file__).resolve().parents[2]
        idx = repo / "INDEX.md"
        if not idx.is_file():
            pytest.skip("仓库无 INDEX.md")
        targets = extract_index_link_targets(idx.read_text(encoding="utf-8"))
        assert "AGENTS.md" in targets
        assert any(t.endswith("README.md") for t in targets)
        warns = [x for x in check_index_links(repo) if x["severity"] == "warn"]
        assert warns == [], warns


class TestNumberTitle:
    def test_mismatch_warn(self, tmp_path):
        (tmp_path / "187_多任务取数会话纪要与挂起事项.md").write_text(
            "# 150、多任务取数会话纪要\n正文", encoding="utf-8")
        state = {"body": {187: ["187_多任务取数会话纪要与挂起事项.md"]}}
        f = check_number_title(tmp_path, state)
        assert len(f) == 1 and f[0]["code"] == "number_title_mismatch"

    def test_match_ok(self, tmp_path):
        (tmp_path / "150_取数.md").write_text("# 150、取数纪要\n正文", encoding="utf-8")
        state = {"body": {150: ["150_取数.md"]}}
        assert check_number_title(tmp_path, state) == []


class TestArchiveSubdirs:
    def test_scan(self, tmp_path):
        (tmp_path / "_archive/output_r99").mkdir(parents=True)
        assert scan_archive_outdirs(tmp_path) == ["output_r99"]
        assert scan_archive_outdirs(tmp_path / "_archive") == []


def test_exports_regex_accepts_fullwidth():
    assert cdi.EXPORTS_TASK.match("14、市场监督管理费用明细").group(1) == "14"
    assert cdi.EXPORTS_TASK.match("20260730市场") is None


def test_year_prefix_exempt(tmp_path):
    (tmp_path / "160_2026新取得职称.md").write_text("# 2026新取得职称人员…执行包\n正文", encoding="utf-8")
    state = {"body": {160: ["160_2026新取得职称.md"]}}
    assert check_number_title(tmp_path, state) == []
