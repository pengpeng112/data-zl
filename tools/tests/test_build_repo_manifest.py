"""Check navigation classifications and bounded metadata reads without a database."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_repo_manifest as manifest


@pytest.mark.parametrize("path, expected", [
    ("AGENTS.md", "启动与规则"),
    ("开发起步包/55_系统未完成事项统一执行计划.md", "权威目录或待办入口"),
    ("开发起步包/_archive/55_旧计划.md", "历史归档"),
    ("开发起步包/output_r204", "专题运行证据"),
    ("开发起步包/204_计划_结果.json", "机器可读资产或配套结果"),
    (".workbuddy", "工具私有域（保持原位）"),
    (".agents", "共享技能与协作配置"),
    ("backend/scripts/probe.py", "运行代码与部署"),
    ("取数/exports/12、统计", "受控查询与交付目录"),
])
def test_path_role_is_not_execution_status(path, expected):
    assert manifest.artifact_class(path) == expected


def test_number_family_does_not_overwrite_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "REPO", tmp_path)
    plan = tmp_path / "204_计划.md"
    report = tmp_path / "204_报告.md"
    plan.write_text("> 类别：模块计划\n# 204 计划\n", encoding="utf-8")
    report.write_text("> 类别：证据\n# 204 报告\n", encoding="utf-8")
    result = manifest.build({"kb_md": [plan, report]})
    assert len(result["items"]) == 2
    assert {item["num"] for item in result["items"].values()} == {204}
    assert "55_系统未完成事项统一执行计划.md" in result["contract"]["authority_priority"]


def test_private_directory_does_not_read_members(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "REPO", tmp_path)
    private = tmp_path / ".workbuddy"
    private.mkdir()
    (private / "secret.md").write_text("# DO_NOT_COPY_THIS_MEMBER", encoding="utf-8")
    result = manifest.entry(private)
    assert "title" not in result
    assert "DO_NOT_COPY" not in str(result)


def test_only_bounded_head_is_read_and_credentials_are_masked(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "REPO", tmp_path)
    doc = tmp_path / "204_参考.md"
    doc.write_text("# password=example\n" + "a" * 5000 + "\n> 类别：尾部不应读取", encoding="utf-8")
    result = manifest.entry(doc)
    assert "example" not in result["title"]
    assert "category_line" not in result
