"""tools/check_doc_index.py 单测（185 号 C1）。

用临时目录构造微型 开发起步包 形态，覆盖验收场景：
组合登记不算幽灵/其覆盖编号不算孤儿、150 白名单、180 同号多文件形态、
--fix 默认 dry-run、--files 显式写入、--check 幂等。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_doc_index as cdi  # noqa: E402


@pytest.fixture()
def pkg(tmp_path: Path) -> Path:
    """微型包：两个登记文档 + 组合区间 + 归档区。"""
    (tmp_path / "01_已登记文档.md").write_text("> 类别：当前\n\n正文\n", encoding="utf-8")
    (tmp_path / "02_区间文档A.md").write_text("> 类别：证据\n\n正文\n", encoding="utf-8")
    (tmp_path / "03_区间文档B.md").write_text("> 类别：证据\n\n正文\n", encoding="utf-8")
    (tmp_path / "03_区间文档B_结果.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# 目录\n\n## 当前入口\n\n"
        "| 优先级 | 文件 | 状态 | 用途 |\n|---|---|---|---|\n"
        "| P0 | `01_已登记文档.md` | 进行中 | 用途 |\n\n"
        "## 证据链\n\n"
        "| 编号 | 状态 | 用途 |\n|---|---|---|\n"
        "| `02`–`03`（同号报告/结果配套） | 证据 | 区间组合登记 |\n\n"
        "## 目录更新记录\n\n"
        "| 2026-09-06 | 建档 | 说明 |\n",
        encoding="utf-8",
    )
    arch = tmp_path / "_archive"
    arch.mkdir()
    (arch / "88_旧文档.md").write_text("旧\n", encoding="utf-8")
    (arch / "README.md").write_text(
        "# 归档区\n\n## 归档记录\n\n| 原序号 | 文件名 | 原因 | 日期 |\n|---|---|---|---|\n"
        "| 88 | 88_旧文档.md | 被取代 | 2026-07-06 |\n",
        encoding="utf-8",
    )
    return tmp_path


def codes(report: dict, *sev: str) -> list[str]:
    return [f["code"] for f in report["findings"] if f["severity"] in sev]


def test_combo_rows_cover_files(pkg: Path):
    """验收：区间组合登记（`02`–`03`）覆盖的编号文件不算孤儿，也不产生幽灵。"""
    report = cdi.run_checks(pkg)
    assert "orphan_doc" not in codes(report, "error", "warn")
    assert "ghost" not in codes(report, "error", "warn")


def test_orphan_and_ghost_detection(pkg: Path):
    (pkg / "99_未登记.md").write_text("> 类别：当前\n", encoding="utf-8")
    readme = pkg / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\n| P1 | `77_不存在.md` | 历史 | 已归档 |\n",
        encoding="utf-8",
    )
    report = cdi.run_checks(pkg)
    assert any(f["code"] == "orphan_doc" and f["num"] == 99 for f in report["findings"])
    assert any(f["code"] == "ghost" and f["num"] == 77 for f in report["findings"])


def test_ghost_whitelist_150(pkg: Path):
    readme = pkg / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\n| P1 | `150_已结束课题.md` | 已结束 | 白名单 |\n",
        encoding="utf-8",
    )
    report = cdi.run_checks(pkg)
    assert any(f["code"] == "ghost_whitelisted" and f["num"] == 150 for f in report["findings"])
    assert not any(f["code"] == "ghost" for f in report["findings"])


def test_180_style_multi_file_with_tonggao(pkg: Path):
    """验收：180 形态=计划+同号 _执行报告.md/_结果.json，README 有“同号”标记 → 已识别形态。"""
    (pkg / "10_计划.md").write_text("> 类别：待办\n", encoding="utf-8")
    (pkg / "10_报告_执行报告.md").write_text("> 类别：执行报告\n", encoding="utf-8")
    (pkg / "10_报告_结果.json").write_text("{}", encoding="utf-8")
    readme = pkg / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n| P0 | `10_计划.md` + 同号 `_执行报告.md`/`_结果.json` | 完成 | 组合 |\n",
        encoding="utf-8",
    )
    report = cdi.run_checks(pkg)
    assert any(
        f["code"] == "multi_form_registered" and f["num"] == 10 for f in report["findings"]
    )
    assert not any(f["code"] == "multi_body_unverified" for f in report["findings"])


def test_multi_body_unverified_warn(pkg: Path):
    (pkg / "10_A主题.md").write_text("> 类别：当前\n", encoding="utf-8")
    (pkg / "10_B主题.md").write_text("> 类别：当前\n", encoding="utf-8")
    readme = pkg / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\n| P1 | `10_A主题.md` | 进行中 | 说明 |\n",
        encoding="utf-8",
    )
    report = cdi.run_checks(pkg)
    assert any(f["code"] == "multi_body_unverified" and f["num"] == 10 for f in report["findings"])


def test_missing_category(pkg: Path):
    (pkg / "20_无类别.md").write_text("# 标题\n\n没有类别行\n", encoding="utf-8")
    readme = pkg / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\n| P1 | `20_无类别.md` | 进行中 | 说明 |\n",
        encoding="utf-8",
    )
    report = cdi.run_checks(pkg)
    assert any(f["code"] == "missing_category" for f in report["findings"])


def test_outdir_covered_and_orphan(pkg: Path):
    (pkg / "output_r01").mkdir()   # 1：`01_已登记文档.md` 反引号登记 → 覆盖
    (pkg / "output_r05").mkdir()   # 5：无任何登记 → 孤儿输出目录
    report = cdi.run_checks(pkg)
    orphans = [f["num"] for f in report["findings"] if f["code"] == "orphan_outdir"]
    assert 5 in orphans and 1 not in orphans


def test_archive_registry_variant_forms():
    text = (
        "| 原序号 | 文件名 | 原因 | 日期 |\n|---|---|---|---|\n"
        "| 24 | a.md | x | 2026-07-06 |\n"
        "| 29/29b/29c | b.md | x | 2026-07-11 |\n"
        "| 96复核 | c.md | x | 2026-07-29 |\n"
        "| 41/42 | d.md | x | 2026-07-11 |\n"
        "| 根计划 | e.md | x | 2026-07-11 |\n"
        "| 2026-09-05 | f.md | 日期行 | 2026-09-05 |\n"
        "- 补充说明：`91_复核.md` 移入归档。\n"
    )
    nums = cdi.archive_registry_numbers(text)
    assert {24, 29, 96, 41, 42, 91} <= nums
    assert 2026 not in nums  # 日期段被 (?!\d) 排除


def test_check_idempotent(pkg: Path):
    r1 = cdi.run_checks(pkg)
    r2 = cdi.run_checks(pkg)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_fix_dry_run_by_default(pkg: Path, capsys):
    (pkg / "30_新文档.md").write_text("> 类别：当前\n", encoding="utf-8")
    before = (pkg / "README.md").read_text(encoding="utf-8")
    rc = cdi.main(["--pkg", str(pkg), "--fix"])  # 无 --files：纯提示，不写
    assert rc == 0
    assert (pkg / "README.md").read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert "dry-run" in out or "--files" in out


def test_fix_requires_explicit_files(pkg: Path):
    (pkg / "30_新文档.md").write_text("> 类别：当前\n", encoding="utf-8")
    before = (pkg / "README.md").read_text(encoding="utf-8")
    # --fix 不带 --files：不写
    cdi.main(["--pkg", str(pkg), "--fix"])
    assert (pkg / "README.md").read_text(encoding="utf-8") == before
    # --files 带存在文件：写入登记模板行
    rc = cdi.main(["--pkg", str(pkg), "--fix", "--files", "30_新文档.md"])
    assert rc == 0
    after = (pkg / "README.md").read_text(encoding="utf-8")
    assert "30_新文档.md" in after and len(after) > len(before)
    # 幂等：再次执行跳过
    rc2 = cdi.main(["--pkg", str(pkg), "--fix", "--files", "30_新文档.md"])
    assert rc2 == 0
    assert (pkg / "README.md").read_text(encoding="utf-8") == after


def test_fix_rejects_bad_names(pkg: Path):
    rc = cdi.main(["--pkg", str(pkg), "--fix", "--files", "不存在的_文件.md,README.md"])
    assert rc == 2


def test_main_exit_code(pkg: Path):
    assert cdi.main(["--pkg", str(pkg)]) == 0  # 干净包：无 error
