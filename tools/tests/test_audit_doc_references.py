"""Reference inventory must preserve scope limits and avoid false path matches."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_doc_references import inventory


def setup_repo(tmp_path):
    kb = tmp_path / "开发起步包"
    kb.mkdir()
    plan = kb / "183_计划.md"
    plan.write_text("# historical plan", encoding="utf-8")
    (kb / "183_结果.json").write_text("{}", encoding="utf-8")
    (kb / "output_r20").mkdir()
    (kb / "output_r200").mkdir()
    return kb, plan


def test_exact_names_windows_paths_and_explicit_family_aliases(tmp_path):
    setup_repo(tmp_path)
    (tmp_path / "consumer.py").write_text("p = '开发起步包\\183_计划.md'\n# 183_*\n", encoding="utf-8")
    result = inventory(tmp_path)
    ref = next(row for row in result["references"] if row["referrer"] == "consumer.py")
    assert ref["target"] == "开发起步包/183_计划.md"
    assert ref["line"] == 1
    assert result["family_aliases"][0]["family"] == 183
    assert "# historical plan" not in json.dumps(result)


def test_directory_prefix_does_not_match_another_plan(tmp_path):
    setup_repo(tmp_path)
    (tmp_path / "consumer.md").write_text("output_r200/report.md", encoding="utf-8")
    refs = inventory(tmp_path)["references"]
    assert [row["target"] for row in refs] == ["开发起步包/output_r200"]


def test_json_escaped_unicode_reference_is_found(tmp_path):
    setup_repo(tmp_path)
    (tmp_path / "consumer.json").write_text(json.dumps({"path": "183_计划.md"}), encoding="utf-8")
    assert any(row["referrer"] == "consumer.json" for row in inventory(tmp_path)["references"])


def test_private_patient_generated_domains_and_large_files_are_not_read(tmp_path):
    setup_repo(tmp_path)
    for folder in ("取数", ".workbuddy", ".ssh", "开发起步包/output_r204", "开发起步包/数据资产_机器包"):
        dest = tmp_path / folder
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "secret.md").write_text("183_计划.md", encoding="utf-8")
    (tmp_path / "large.md").write_text("183_计划.md" * 100, encoding="utf-8")
    result = inventory(tmp_path, max_bytes=80)
    assert not result["references"]
    assert any(row["path"] == "large.md" and row["reason"] == "text_size_budget" for row in result["uninspected"])


def test_unreadable_text_is_reported_and_keeps_other_references(tmp_path):
    setup_repo(tmp_path)
    (tmp_path / "bad.md").write_bytes(b"\xff183_\xff")
    (tmp_path / "good.md").write_text("183_计划.md", encoding="utf-8")
    result = inventory(tmp_path)
    assert any(row["path"] == "bad.md" and row["reason"] == "unreadable_utf8" for row in result["uninspected"])
    assert any(row["referrer"] == "good.md" for row in result["references"])


def test_bulk_json_has_a_separate_budget(tmp_path):
    setup_repo(tmp_path)
    (tmp_path / "bulk.json").write_text("183_计划.md" + " " * (300 * 1024), encoding="utf-8")
    result = inventory(tmp_path)
    assert not any(row["referrer"] == "bulk.json" for row in result["references"])
    assert any(row["path"] == "bulk.json" and row["reason"] == "text_size_budget" for row in result["uninspected"])
