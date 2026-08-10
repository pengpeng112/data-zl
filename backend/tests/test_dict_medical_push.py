"""推送计划服务纯逻辑测试（101号 §5.1）。

不依赖数据库，验证计划哈希、完整性校验、审批规则。
"""
from __future__ import annotations

import pytest

from app.services.dict_medical_push import (
    _compute_plan_hash,
    PLAN_TTL_HOURS,
    VALID_TARGET_SYSTEMS,
)


class TestPlanHash:
    def test_deterministic(self):
        items = [
            {"item_code": "Y001", "item_name_cn": "脑梗死", "national_clinical_code": "I63.900", "insurance_code": "I63.900"},
            {"item_code": "Y002", "item_name_cn": "脑出血", "national_clinical_code": "I61.000", "insurance_code": "I61.000"},
        ]
        h1 = _compute_plan_hash(items)
        h2 = _compute_plan_hash(list(items))
        assert h1 == h2
        assert len(h1) == 32

    def test_order_independent(self):
        items = [
            {"item_code": "Y001", "item_name_cn": "A", "national_clinical_code": "X", "insurance_code": "Z"},
            {"item_code": "Y002", "item_name_cn": "B", "national_clinical_code": "Y", "insurance_code": "W"},
        ]
        h1 = _compute_plan_hash(items)
        h2 = _compute_plan_hash(list(reversed(items)))
        assert h1 == h2

    def test_content_change_detected(self):
        items1 = [{"item_code": "Y001", "item_name_cn": "A", "national_clinical_code": "X", "insurance_code": "Z"}]
        items2 = [{"item_code": "Y001", "item_name_cn": "B", "national_clinical_code": "X", "insurance_code": "Z"}]
        assert _compute_plan_hash(items1) != _compute_plan_hash(items2)

    def test_empty_items(self):
        h = _compute_plan_hash([])
        assert len(h) == 32


class TestConstants:
    def test_valid_targets(self):
        # 正式目标系统编码为 HIS_SOURCE / JHEMR_VASTBASE；HIS/JHEMR 仅别名。
        from app.services.dict_medical_push import TARGET_ALIASES

        assert "HIS_SOURCE" in VALID_TARGET_SYSTEMS
        assert "JHEMR_VASTBASE" in VALID_TARGET_SYSTEMS
        assert len(VALID_TARGET_SYSTEMS) == 2
        assert TARGET_ALIASES.get("HIS") == "HIS_SOURCE"
        assert TARGET_ALIASES.get("JHEMR") == "JHEMR_VASTBASE"

    def test_plan_ttl(self):
        assert PLAN_TTL_HOURS == 24