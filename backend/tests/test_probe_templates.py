"""165 E2: 12 条探查模板逐条校验（schema/参数/聚合形态/无注释/无双源字面量）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

TPL_DIR = Path(__file__).resolve().parents[1] / "scripts" / "probe_templates"
TEMPLATES = sorted(TPL_DIR.glob("T*.json"))

REQUIRED_KEYS = {"code", "probe_type", "name", "severity_default", "window_kind", "sides",
                 "derive", "trigger", "object_desc_tpl", "large_table_guard"}
PROBE_TYPES = {"R-REF", "R-CNT", "R-KEY", "R-XSYS", "R-DOM"}


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_twelve_templates_present():
    assert len(TEMPLATES) == 12, [p.stem for p in TEMPLATES]


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
class TestEachTemplate:
    def test_schema(self, path):
        tpl = _load(path)
        missing = REQUIRED_KEYS - set(tpl)
        assert not missing, f"{path.stem} 缺 {missing}"
        assert tpl["probe_type"] in PROBE_TYPES
        assert tpl["severity_default"] in {"P1", "P2", "P3"}
        assert tpl["trigger"]["op"] in {"gt", "ge", "lt", "le"}
        assert isinstance(tpl["trigger"]["threshold"], (int, float))
        assert tpl["derive"]["metric"] and tpl["derive"]["unit"]

    def test_params_contract(self, path):
        tpl = _load(path)
        for s in tpl["sides"]:
            sql = s.get("sql") or ""
            if s.get("mode") in ("blocked", "key_lookup"):
                continue
            assert ":START_DATE" in sql and ":END_DATE" in sql, f"{path.stem} 参数缺失"

    def test_sql_aggregate_no_comment_no_literal(self, path):
        tpl = _load(path)
        for s in tpl["sides"]:
            sql = s.get("sql") or ""
            if not sql:
                continue
            assert "--" not in sql and "/*" not in sql, f"{path.stem} SQL 含注释"
            assert "SELECT" in sql.upper()
            # 聚合形态（单源）或键/分组形态（双源）
            if len(tpl["sides"]) == 1:
                assert any(k in sql.upper() for k in ("COUNT(", "SUM(")), f"{path.stem} 非聚合"
            # 零患者字面量：无引号包裹的长数字串/中文姓名模式（宽松断言：无 IN ('具体值') 列表）
            assert "__KEYS__" in sql or "IN (" not in sql.upper(), f"{path.stem} 疑似字面量 IN 列表"

    def test_dual_source_no_id_literal(self, path):
        tpl = _load(path)
        if len(tpl["sides"]) == 2:
            for s in tpl["sides"]:
                sql = s.get("sql") or ""
                assert "ROWNUM <= 1000" not in sql or s["side"] == "a", "抽样只允许在 a 侧"
                if s.get("mode") == "key_lookup":
                    assert "__KEYS__" in sql

    def test_blocked_only_with_reason(self, path):
        tpl = _load(path)
        if tpl.get("blocked"):
            assert tpl["sides"][1].get("reason"), "BLOCKED 必须带原因"


class TestTemplateSemantics:
    def test_t5_threshold_direction(self):
        t5 = _load(TPL_DIR / "T5.json")
        assert t5["trigger"]["op"] == "lt"  # 回写率低于阈值才越阈

    def test_t11_mapping_covers_five(self):
        t11 = _load(TPL_DIR / "T11.json")
        assert set(t11["derive"]["mapping"].values()) == {"1", "2", "3", "4", "9"}

    def test_t12_no_value_domain_write(self):
        t12 = _load(TPL_DIR / "T12.json")
        assert t12["derive"]["finding_per_value"] is True
        assert t12["derive"]["max_findings"] <= 50
        assert "149" in t12.get("note", "")

    def test_t6_large_table_guard(self):
        t6 = _load(TPL_DIR / "T6.json")
        assert t6["large_table_guard"] and "LAB_RESULT" in t6["large_table_guard"]

    def test_executor_pure_funcs(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("run_probe", Path(__file__).resolve().parents[1] / "scripts" / "run_probe.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from datetime import date
        s, e = mod.month_window(False)
        assert s.day == 1 and s < e
        assert mod.evaluate_trigger(83.2, {"op": "gt", "threshold": 1.0}) is True
        assert mod.evaluate_trigger(0.5, {"op": "gt", "threshold": 1.0}) is False
        assert mod.evaluate_trigger(35.5, {"op": "lt", "threshold": 90.0}) is True
        assert mod.evaluate_trigger(99.5, {"op": "lt", "threshold": 99.0}) is False
        sql = mod.render_params("X >= TO_DATE(:START_DATE,'YYYY-MM-DD')", date(2026, 7, 1), date(2026, 8, 1), "oracle")
        assert "'2026-07-01'" in sql and ":START_DATE" not in sql
