"""198 B5 / F06-T11-T12：配方消费路径（纯逻辑，无 DB）。

覆盖：知识型 dict 形态显式标记与生成拒绝、标准数组生成含 ON/join_type 的 SQL、
非法表名/空 ON/不存在族 ID 在治理前被机器可读拒绝。
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.recipe_service import (
    canonical_recipe_payload,
    classify_recipe_joins,
    generate_select_sql,
    normalize_recipe_joins,
    recipe_readiness,
    unresolvable_family_refs,
    validate_recipe_structure,
    validate_recipe_tables,
)

# r197 草稿 R197_rcp-s3-01 的真实 dict 形态（platform_readback.json）
R197_DICT_JOINS = {
    "time_fields": ["VISIT_DATE", "CHARGE_DATE_TIME（以元数据为准）"],
    "dedup_strategy": "明细↔开单必须三列复合键（RCPT_NO+VISIT_NO+VISIT_DATE）",
    "join_family_ids": [
        "S2F-B460DFC719",
        "S2F-0BF98D1B1C",
        "S3F:OUTP_ORDER_DESC.RCPT_NO=OUTP_RCPT_MASTER.RCPT_NO",
    ],
}

R197_PAYLOAD = {
    "name": "门诊费用三表链（收据-明细-开单）",
    "primary_tables": ["OUTP_RCPT_MASTER", "OUTP_BILL_ITEMS", "OUTP_ORDER_DESC"],
    "joins": R197_DICT_JOINS,
    "dedup_strategy": R197_DICT_JOINS["dedup_strategy"],
    "time_fields": R197_DICT_JOINS["time_fields"],
}

STANDARD_JOINS = [
    {
        "join_type": "inner",
        "from": "OUTP_RCPT_MASTER",
        "to": "OUTP_BILL_ITEMS",
        "on": "OUTP_RCPT_MASTER.RCPT_NO = OUTP_BILL_ITEMS.RCPT_NO",
    },
    {
        "join_type": "LEFT",
        "from": "OUTP_BILL_ITEMS",
        "to": "OUTP_ORDER_DESC",
        "on": "OUTP_BILL_ITEMS.NO = OUTP_ORDER_DESC.NO",
    },
]


def _detail(exc: HTTPException) -> dict:
    return exc.value.detail if isinstance(exc.value.detail, dict) else {"detail": exc.value.detail}


# ── T11：知识型形态识别与生成拒绝 ──────────────────────────────────


class TestKnowledgeFormJoins:
    def test_dict_joins_not_silently_empty(self):
        normalized, reasons = classify_recipe_joins(R197_DICT_JOINS)
        assert normalized == []
        assert reasons, "dict 形态必须给出显式原因，不得静默当空关联"
        assert "知识型" in reasons[0]

    def test_empty_and_none_are_valid_shapes(self):
        assert classify_recipe_joins(None) == ([], [])
        assert classify_recipe_joins([]) == ([], [])
        assert normalize_recipe_joins(None) == []
        assert normalize_recipe_joins("bad") == []

    def test_non_dict_items_in_list_flagged(self):
        normalized, reasons = classify_recipe_joins([{"on": "a=b"}, "oops"])
        assert reasons and "非对象项" in reasons[0]

    def test_readiness_marker_in_canonical_payload(self):
        payload = canonical_recipe_payload(R197_PAYLOAD)
        assert payload["readiness"] == "not_executable"
        assert payload["not_ready_reasons"], "机器可读 not_ready_reasons 必须存在"
        assert any("知识型" in r for r in payload["not_ready_reasons"])
        assert payload["joins"] == R197_DICT_JOINS  # 知识载体原样保留，不改写为空数组

    def test_ready_payload_for_standard_shape(self):
        payload = canonical_recipe_payload({"primary_tables": ["A", "B"], "joins": STANDARD_JOINS})
        assert payload["readiness"] == "ready"
        assert payload["not_ready_reasons"] == []

    def test_hash_stable_for_equivalent_empty_joins(self):
        # 既有兼容：joins None 与 [] 的 canonical/hash 必须一致（不因 readiness 字段回归）
        first = canonical_recipe_payload({"joins": None, "primary_tables": [{"table": "HIS.PATIENT"}]})
        second = canonical_recipe_payload({"joins": [], "primary_tables": [{"table": "HIS.PATIENT"}]})
        assert first == second

    def test_generate_refuses_dict_joins_with_reason(self):
        with pytest.raises(HTTPException) as exc:
            generate_select_sql(R197_PAYLOAD["primary_tables"], R197_DICT_JOINS)
        detail = _detail(exc)
        assert exc.value.status_code == 422
        assert detail["code"] == "recipe_not_executable"
        assert detail["reasons"]

    def test_generate_refuses_complex_payload_knowledge_only(self):
        # 复杂配方（聚合/时间选价/复合去重）归知识型：结构化 joins 也不降格平铺
        payload = {
            "primary_tables": ["A", "B"],
            "joins": STANDARD_JOINS,
            "dedup_strategy": "必须三列复合键，DISTINCT/MAX 不能替代键补全",
            "time_fields": ["CHARGE_DATE_TIME"],
        }
        assert recipe_readiness(payload)["readiness"] == "not_executable"
        with pytest.raises(HTTPException) as exc:
            generate_select_sql(payload["primary_tables"], STANDARD_JOINS, payload=payload)
        detail = _detail(exc)
        assert detail["code"] == "recipe_knowledge_only"
        assert any("dedup_strategy" in r for r in detail["reasons"])

    def test_standard_array_generates_sql_with_on_and_join_type(self):
        sql = generate_select_sql(["OUTP_RCPT_MASTER", "OUTP_BILL_ITEMS"], STANDARD_JOINS[:1])
        assert "INNER JOIN OUTP_BILL_ITEMS ON OUTP_RCPT_MASTER.RCPT_NO = OUTP_BILL_ITEMS.RCPT_NO" in sql
        sql2 = generate_select_sql(["A", "B", "C"], STANDARD_JOINS)
        assert "LEFT JOIN C ON" in sql2


# ── T12：治理前结构校验（非法表名 / 空 ON / 族引用） ────────────────


class TestStructureValidation:
    def test_illegal_table_identifier_rejected_before_generation(self):
        tables = ["DRUG_IMPORT_MASTER/DETAIL", "DRUG_STOCK"]  # r197 R197_rcp-s5-03 真实形态
        reasons = validate_recipe_structure(tables, [])
        assert any("非法表标识" in r for r in reasons)
        with pytest.raises(HTTPException) as exc:
            generate_select_sql(tables, [])
        assert _detail(exc)["code"] == "invalid_table_identifier"
        with pytest.raises(HTTPException) as exc2:
            validate_recipe_tables(tables)
        assert exc2.value.status_code == 422

    def test_empty_on_rejected(self):
        joins = [{"join_type": "LEFT", "from": "A", "to": "B", "on": ""}]
        reasons = validate_recipe_structure(["A", "B"], joins)
        assert any("空 ON" in r for r in reasons)
        with pytest.raises(HTTPException) as exc:
            generate_select_sql(["A", "B"], joins)
        assert _detail(exc)["code"] == "missing_join_condition"

    def test_missing_join_rejected(self):
        reasons = validate_recipe_structure(["A", "B", "C"], [{"join_type": "INNER", "on": "A.X=B.X"}])
        assert any("数量不足" in r for r in reasons)

    def test_unknown_family_id_rejected(self):
        joins = [
            {
                "join_type": "INNER",
                "from": "OUTP_RCPT_MASTER",
                "to": "OUTP_BILL_ITEMS",
                "on": "OUTP_RCPT_MASTER.RCPT_NO = OUTP_BILL_ITEMS.RCPT_NO",
                "join_family_ids": ["S2F-B460DFC719"],  # r197 本地族 ID，平台无对应实体
            }
        ]
        reasons = validate_recipe_structure(["OUTP_RCPT_MASTER", "OUTP_BILL_ITEMS"], joins)
        assert any("未解析的关系族引用" in r for r in reasons)
        assert unresolvable_family_refs(joins) == ["S2F-B460DFC719"]

    def test_self_describing_family_pair_resolves(self):
        joins = [
            {
                "join_type": "INNER",
                "on": "A.X = B.X",
                "join_family_ids": ["OUTP_ORDER_DESC.RCPT_NO=OUTP_RCPT_MASTER.RCPT_NO"],
            }
        ]
        assert unresolvable_family_refs(joins) == []
        assert validate_recipe_structure(["A", "B"], joins) == []

    def test_whitelisted_family_id_resolves(self):
        joins = [{"join_type": "INNER", "on": "A.X = B.X", "family_id": "FAM-1"}]
        assert unresolvable_family_refs(joins, known_family_ids={"FAM-1"}) == []
        assert unresolvable_family_refs(joins) == ["FAM-1"]

    def test_dict_joins_blocked_at_submit_gate(self):
        reasons = validate_recipe_structure(R197_PAYLOAD["primary_tables"], R197_DICT_JOINS)
        assert any("知识型" in r for r in reasons)

    def test_dict_joins_blocked_at_submit_gate_with_payload(self):
        # submit 入口带 recipe_json：payload 复杂口径同样进入校验原因
        reasons = validate_recipe_structure(
            R197_PAYLOAD["primary_tables"], R197_DICT_JOINS, payload=canonical_recipe_payload(R197_PAYLOAD)
        )
        assert any("知识型" in r for r in reasons)
        assert any("dedup_strategy" in r for r in reasons)

    def test_single_table_recipe_is_valid(self):
        # 兼容：单表配方（无 joins）不得被过度校验误伤
        assert validate_recipe_structure([{"table": "HIS.PAT_VISIT"}], []) == []

    def test_unsafe_condition_rejected(self):
        joins = [{"join_type": "LEFT", "on": "A.X = B.X; DROP TABLE t"}]
        reasons = validate_recipe_structure(["A", "B"], joins)
        assert any("不安全" in r for r in reasons)
        with pytest.raises(HTTPException) as exc:
            generate_select_sql(["A", "B"], joins)
        assert _detail(exc)["code"] == "unsafe_join_condition"

    def test_unsupported_join_type_rejected(self):
        joins = [{"join_type": "LEFT_JOIN", "on": "A.X = B.X"}]
        reasons = validate_recipe_structure(["A", "B"], joins)
        assert any("不支持的 join_type" in r for r in reasons)
        with pytest.raises(HTTPException) as exc:
            generate_select_sql(["A", "B"], joins)
        assert _detail(exc)["code"] == "unsupported_join_type"
