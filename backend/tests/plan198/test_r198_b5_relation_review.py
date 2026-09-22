"""198 B5 / F05-T09-T10：关系审核严格身份匹配与 approve 语义（纯逻辑，无 DB）。

用 fake DB 复现 r197-audit-20260922/service_reproductions.json 的两类故障：
同端点不同字段误匹配（请求 PATIENT_ID→VISIT_ID 却返回 OPER_ID→OPER_ID 关系 41）、
approve 无条件 validation_status="sample_pass"。
"""
from __future__ import annotations

from app.models.asset import AssetRelation, AssetRelationReview
from app.services.relation_review_service import (
    approve_review,
    column_pair_key,
    detect_join_direction,
    direction_compatible,
    find_matching_relations,
    normalize_column_tokens,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDB:
    """只实现 find_matching_relations/populate_endpoint_fields 用到的接口。"""

    def __init__(self, relation_rows=(), endpoint_rows=()):
        self._relation_rows = list(relation_rows)
        self._endpoint_rows = list(endpoint_rows)
        self.added = []

    def scalars(self, stmt):
        return _FakeResult(self._relation_rows)

    def execute(self, stmt):
        return _FakeResult(self._endpoint_rows)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None


def _relation(**kwargs) -> AssetRelation:
    row = AssetRelation()
    for key, value in kwargs.items():
        setattr(row, key, value)
    return row


def _review(**kwargs) -> AssetRelationReview:
    row = AssetRelationReview()
    row.review_status = "draft"
    row.relation_desc_cn = "r198 纯逻辑测试"
    for key, value in kwargs.items():
        setattr(row, key, value)
    return row


# ── 列 token / 成对映射工具 ─────────────────────────────────────────


class TestColumnPairKey:
    def test_plus_pipe_semicolon_comma_unified(self):
        assert normalize_column_tokens("PATIENT_ID+VISIT_ID") == ["PATIENT_ID", "VISIT_ID"]
        assert normalize_column_tokens("patient_id | visit_id") == ["PATIENT_ID", "VISIT_ID"]
        assert column_pair_key("A+B", "X;Y") == frozenset({("A", "X"), ("B", "Y")})

    def test_empty_or_uneven_returns_none(self):
        assert column_pair_key(None, "X") is None
        assert column_pair_key("A", "") is None
        assert column_pair_key("A,B", "X") is None

    def test_subset_not_equal(self):
        assert column_pair_key("A,B", "X,Y") != column_pair_key("A", "X")


# ── T09：严格身份匹配 ───────────────────────────────────────────────


class TestFindMatchingStrictIdentity:
    def _oper_relation(self) -> AssetRelation:
        return _relation(
            id=41,
            from_table="HIS.OPERATION_MASTER",
            from_columns="OPER_ID",
            to_table="HIS.OPERATION_MASTER",
            to_columns="OPER_ID",
            join_condition="HIS.OPERATION_MASTER.OPER_ID=HIS.OPERATION_MASTER.OPER_ID",
            relation_layer="formal",
            validation_status="verified",
        )

    def test_same_tables_different_columns_no_match(self):
        # 复现 audit：请求 PATIENT_ID→VISIT_ID，库里只有 OPER_ID→OPER_ID 关系 41
        db = _FakeDB(relation_rows=[self._oper_relation()])
        matches = find_matching_relations(
            db,
            from_table="HIS.OPERATION_MASTER",
            to_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID",
            to_columns="VISIT_ID",
        )
        assert matches == []

    def test_no_fallback_to_all_same_table_relations(self):
        # 任一筛选字段为空 → 空列表（无证据即无匹配），不得回退同表全部关系
        db = _FakeDB(relation_rows=[self._oper_relation()])
        assert find_matching_relations(
            db, from_table="HIS.OPERATION_MASTER", to_table="HIS.OPERATION_MASTER",
            from_columns=None, to_columns=None,
        ) == []
        assert find_matching_relations(
            db, from_table="HIS.OPERATION_MASTER", to_table="HIS.OPERATION_MASTER",
            from_columns="OPER_ID", to_columns=None,
        ) == []

    def test_id_is_not_substring_of_patient_id(self):
        # 旧实现的子串包含比较会让 ID 匹配 PATIENT_ID；必须是整 token 等值
        row = _relation(
            id=7,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID,PATIENT_ID",
            join_condition="a.PATIENT_ID=b.PATIENT_ID AND a.VISIT_ID=b.PATIENT_ID",
        )
        db = _FakeDB(relation_rows=[row])
        assert find_matching_relations(
            db,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="ID,VISIT_ID",
            to_columns="ID,ID",
        ) == []

    def test_full_pair_match_succeeds(self):
        row = _relation(
            id=7,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID,PATIENT_ID",
            join_condition="a.PATIENT_ID=b.PATIENT_ID",
        )
        db = _FakeDB(relation_rows=[row])
        matches = find_matching_relations(
            db,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID,VISIT_ID",
            to_columns="PATIENT_ID,PATIENT_ID",
        )
        assert [r.id for r in matches] == [7]

    def test_subset_columns_do_not_match(self):
        composite_row = _relation(
            id=7,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID,VISIT_ID",
        )
        db = _FakeDB(relation_rows=[composite_row])
        # 查询单列，库中复合键 → 子集不算匹配
        assert find_matching_relations(
            db,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID",
            to_columns="PATIENT_ID",
        ) == []
        # 反向：查询复合键，库中只有单列 → 也不匹配
        single_row = _relation(
            id=8,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID",
        )
        db2 = _FakeDB(relation_rows=[single_row])
        assert find_matching_relations(
            db2,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID,VISIT_ID",
            to_columns="PATIENT_ID,VISIT_ID",
        ) == []

    def test_inner_reversed_is_equivalent(self):
        # 库中 B→A（INNER），查询 A→B（INNER）等价
        row = _relation(
            id=11,
            from_table="HIS.LAB_RESULT",
            from_columns="TEST_NO",
            to_table="HIS.LAB_TEST_MASTER",
            to_columns="TEST_NO",
            join_condition="HIS.LAB_RESULT INNER JOIN HIS.LAB_TEST_MASTER ON ...",
        )
        db = _FakeDB(relation_rows=[row])
        matches = find_matching_relations(
            db,
            from_table="HIS.LAB_TEST_MASTER",
            to_table="HIS.LAB_RESULT",
            from_columns="TEST_NO",
            to_columns="TEST_NO",
            join_type="INNER",
        )
        assert [r.id for r in matches] == [11]

    def test_left_reversed_requires_side_flip(self):
        # 查询 A LEFT JOIN B；库中存的是 B LEFT JOIN A（B 保留）→ 语义不同，不匹配
        left_from_b = _relation(
            id=21,
            from_table="HIS.EXAM_REPORT",
            from_columns="EXAM_NO",
            to_table="HIS.EXAM_MASTER",
            to_columns="EXAM_NO",
            join_condition="HIS.EXAM_REPORT LEFT JOIN HIS.EXAM_MASTER ON ...",
        )
        db = _FakeDB(relation_rows=[left_from_b])
        assert find_matching_relations(
            db,
            from_table="HIS.EXAM_MASTER",
            to_table="HIS.EXAM_REPORT",
            from_columns="EXAM_NO",
            to_columns="EXAM_NO",
            join_type="LEFT",
        ) == []
        # 库中 B RIGHT JOIN A（A 保留）与查询 A LEFT JOIN B 等价 → 匹配
        right_keep_a = _relation(
            id=22,
            from_table="HIS.EXAM_REPORT",
            from_columns="EXAM_NO",
            to_table="HIS.EXAM_MASTER",
            to_columns="EXAM_NO",
            join_condition="HIS.EXAM_REPORT RIGHT JOIN HIS.EXAM_MASTER ON ...",
        )
        db = _FakeDB(relation_rows=[right_keep_a])
        matches = find_matching_relations(
            db,
            from_table="HIS.EXAM_MASTER",
            to_table="HIS.EXAM_REPORT",
            from_columns="EXAM_NO",
            to_columns="EXAM_NO",
            join_type="LEFT",
        )
        assert [r.id for r in matches] == [22]

    def test_direction_missing_on_one_side_skips_check(self):
        # 存在时才比较：库中条件无可判定方向 → 不因方向阻断
        row = _relation(
            id=31,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID",
            join_condition="HIS.PAT_VISIT.PATIENT_ID=HIS.PAT_MASTER_INDEX.PATIENT_ID",
        )
        db = _FakeDB(relation_rows=[row])
        matches = find_matching_relations(
            db,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID",
            to_columns="PATIENT_ID",
            join_type="LEFT",
        )
        assert [r.id for r in matches] == [31]

    def test_system_source_compared_when_available_on_both_sides(self):
        row = _relation(
            id=41,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID",
            from_system_code="DATA_CENTER",
            from_source_code="ods_8_216",
        )
        db = _FakeDB(relation_rows=[row])
        # 查询声明 HIS 源身份（可得时比较）→ ODS 镜像行不匹配
        assert find_matching_relations(
            db,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID",
            to_columns="PATIENT_ID",
            from_system_code="HIS",
            from_source_code="his_source_10_10_10_15",
        ) == []
        # 查询未声明身份（不可得）→ 不外推阻断，仍按表+列匹配
        matches = find_matching_relations(
            db,
            from_table="HIS.PAT_VISIT",
            to_table="HIS.PAT_MASTER_INDEX",
            from_columns="PATIENT_ID",
            to_columns="PATIENT_ID",
        )
        assert [r.id for r in matches] == [41]

    def test_owner_alias_still_matches_mirror_query(self):
        # plan127 回归：ODS HIS.* 查询名匹配 owner 命名正式关系（证据支持的别名映射）
        row = _relation(
            id=51,
            from_table="INPBILL.INP_BILL_DETAIL",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="MEDREC.PAT_VISIT",
            to_columns="PATIENT_ID,VISIT_ID",
            join_condition="INPBILL.INP_BILL_DETAIL.PATIENT_ID=MEDREC.PAT_VISIT.PATIENT_ID AND INPBILL.INP_BILL_DETAIL.VISIT_ID=MEDREC.PAT_VISIT.VISIT_ID",
            relation_layer="formal",
            validation_status="verified",
        )
        db = _FakeDB(relation_rows=[row])
        matches = find_matching_relations(
            db,
            from_table="HIS.INP_BILL_DETAIL",
            to_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID+VISIT_ID",
            to_columns="PATIENT_ID,VISIT_ID",
        )
        assert [r.id for r in matches] == [51]


class TestJoinDirectionDetection:
    def test_keyword_detection(self):
        assert detect_join_direction("A LEFT JOIN B ON a.x=b.x") == "LEFT"
        assert detect_join_direction("a inner join b") == "INNER"
        assert detect_join_direction("A FULL JOIN B") == "FULL"

    def test_oracle_plus_marker(self):
        assert detect_join_direction("a.x = b.x(+)") == "LEFT"
        assert detect_join_direction("a.x(+) = b.x") == "RIGHT"

    def test_undetectable_returns_none(self):
        assert detect_join_direction("a.x=b.x") is None
        assert detect_join_direction(None) is None

    def test_direction_compatible_rules(self):
        assert direction_compatible("LEFT", "LEFT", reversed_=False)
        assert direction_compatible("LEFT", "RIGHT", reversed_=True)
        assert direction_compatible("INNER", "INNER", reversed_=True)
        assert not direction_compatible("LEFT", "LEFT", reversed_=True)
        assert not direction_compatible("INNER", "LEFT", reversed_=False)
        assert direction_compatible("LEFT", None, reversed_=False)


# ── T10：approve 语义 ───────────────────────────────────────────────


class TestApproveReviewSemantics:
    def test_created_candidate_not_sample_pass(self):
        # 未实测草稿人工 approve 不得制造 sample_pass 验证事实
        review = _review(
            id=901,
            from_table="HIS.ORDERS",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_VISIT",
            to_columns="PATIENT_ID,VISIT_ID",
            join_condition="HIS.ORDERS.PATIENT_ID=HIS.PAT_VISIT.PATIENT_ID AND HIS.ORDERS.VISIT_ID=HIS.PAT_VISIT.VISIT_ID",
            confidence="B",
        )
        db = _FakeDB(endpoint_rows=[("HIS", "his_source_10_10_10_15")])
        result = approve_review(db, review, reviewer="r198-test")
        assert result["ok"] is True
        assert result["action"] == "created_candidate"
        assert result["validation_status"] == "not_run"
        assert result["validation_status"] != "sample_pass"
        created = db.added[0]
        assert created.validation_status == "not_run"
        assert created.join_condition == review.join_condition

    def test_created_candidate_carries_endpoint_identity(self):
        review = _review(
            id=902,
            from_table="MEDREC.PAT_VISIT",
            from_columns="PATIENT_ID",
            to_table="MEDREC.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID",
            join_condition="MEDREC.PAT_VISIT.PATIENT_ID=MEDREC.PAT_MASTER_INDEX.PATIENT_ID",
            from_system_code="HIS",
            from_source_code="his_source_10_10_10_15",
            to_system_code="HIS",
            to_source_code="his_source_10_10_10_15",
        )
        db = _FakeDB()  # 注册表无该表 → 解析未命中，草稿声明身份优先
        result = approve_review(db, review, reviewer="r198-test")
        assert result["ok"] is True
        created = db.added[0]
        assert created.from_system_code == "HIS"
        assert created.from_source_code == "his_source_10_10_10_15"
        assert created.to_system_code == "HIS"
        assert created.to_source_code == "his_source_10_10_10_15"
        assert created.from_schema_name == "MEDREC"
        assert created.from_table_name == "PAT_VISIT"

    def test_missing_fields_block_candidate_creation(self):
        review = _review(
            id=903,
            from_table="HIS.ORDERS",
            from_columns="PATIENT_ID",
            to_table="HIS.PAT_VISIT",
            to_columns=None,  # 缺失字段
            join_condition=None,  # 缺失条件
        )
        db = _FakeDB()
        result = approve_review(db, review, reviewer="r198-test")
        assert result["ok"] is False
        assert result["error_code"] == "incomplete_candidate_identity"
        missing = set(result["missing_fields"])
        assert "to_columns" in missing
        assert "join_condition" in missing
        assert db.added == []  # 不静默丢字段新建
        assert review.review_status == "draft"  # 阻断不改变治理状态

    def test_uneven_columns_block_candidate_creation(self):
        review = _review(
            id=904,
            from_table="HIS.ORDERS",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_VISIT",
            to_columns="PATIENT_ID",
            join_condition="HIS.ORDERS.PATIENT_ID=HIS.PAT_VISIT.PATIENT_ID",
        )
        db = _FakeDB()
        result = approve_review(db, review, reviewer="r198-test")
        assert result["ok"] is False
        assert result["error_code"] == "incomplete_candidate_identity"
        assert any("数量不一致" in m for m in result["missing_fields"])

    def test_same_table_different_columns_not_linked(self):
        # 与严格匹配共用：正式关系字段不同 → 不因"同表"误链，走新建（且未验证不造 sample_pass）
        formal = _relation(
            id=41,
            from_table="HIS.OPERATION_MASTER",
            from_columns="OPER_ID",
            to_table="HIS.OPERATION_MASTER",
            to_columns="OPER_ID",
            relation_layer="formal",
            validation_status="verified",
        )
        review = _review(
            id=905,
            from_table="HIS.OPERATION_MASTER",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_VISIT",
            to_columns="PATIENT_ID,VISIT_ID",
            join_condition="HIS.OPERATION_MASTER.PATIENT_ID=HIS.PAT_VISIT.PATIENT_ID",
        )
        db = _FakeDB(relation_rows=[formal], endpoint_rows=[("HIS", "his_source_10_10_10_15")])
        result = approve_review(db, review, reviewer="r198-test")
        assert result["ok"] is True
        assert result["action"] == "created_candidate"
        assert result["source_relation_id"] != 41
        assert result["validation_status"] == "not_run"

    def test_matching_formal_relation_linked(self):
        formal = _relation(
            id=41,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID,PATIENT_ID",
            join_condition="a.PATIENT_ID=b.PATIENT_ID",
            relation_layer="formal",
            validation_status="verified",
        )
        review = _review(
            id=906,
            from_table="HIS.PAT_VISIT",
            from_columns="PATIENT_ID,VISIT_ID",
            to_table="HIS.PAT_MASTER_INDEX",
            to_columns="PATIENT_ID,PATIENT_ID",
            join_condition="HIS.PAT_VISIT.PATIENT_ID=HIS.PAT_MASTER_INDEX.PATIENT_ID",
        )
        db = _FakeDB(relation_rows=[formal])
        result = approve_review(db, review, reviewer="r198-test")
        assert result["ok"] is True
        assert result["action"] == "linked_formal"
        assert result["source_relation_id"] == 41
        assert review.review_status == "approved"

    def test_non_draft_review_rejected(self):
        review = _review(id=907, from_table="A", to_table="B")
        review.review_status = "approved"
        db = _FakeDB()
        result = approve_review(db, review)
        assert result["ok"] is False
        assert "cannot approve" in result["error"]
