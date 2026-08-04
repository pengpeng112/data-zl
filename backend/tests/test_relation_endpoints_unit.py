"""关系端点身份、分层、业务键的纯逻辑单元测试（98号 S0 / 100号修复）。

不依赖数据库，验证 relation_identity 工具的拆分、业务键计算、分层推导。
100号新增：三段式拆分、物理键跨系统不碰撞、多关系不被错误去重。
"""
from __future__ import annotations

from app.services.relation_identity import (
    split_qualified_name,
    split_schema_table,
    compute_business_key,
    derive_layer,
    physical_node_key,
)


class TestSplitQualifiedName:
    def test_bare_table_name(self):
        assert split_qualified_name("PAT_VISIT") == (None, None, "PAT_VISIT")

    def test_two_part(self):
        assert split_qualified_name("MEDREC.PAT_VISIT") == (None, "MEDREC", "PAT_VISIT")

    def test_three_part(self):
        assert split_qualified_name("rmcloudlis7.dbo.V_EMR_INSPECTION") == ("rmcloudlis7", "dbo", "V_EMR_INSPECTION")

    def test_empty(self):
        assert split_qualified_name("") == (None, None, None)
        assert split_qualified_name(None) == (None, None, None)

    def test_whitespace(self):
        assert split_qualified_name("  ") == (None, None, None)

    def test_backward_compat_split_schema_table(self):
        assert split_schema_table("MEDREC.PAT_VISIT") == ("MEDREC", "PAT_VISIT")
        assert split_schema_table("PAT_VISIT") == (None, "PAT_VISIT")
        assert split_schema_table("rmcloudlis7.dbo.V_X") == ("dbo", "V_X")


class TestPhysicalNodeKey:
    def test_full_key(self):
        key = physical_node_key("HIS", "his_src", None, "MEDREC", "PAT_VISIT")
        assert key == "HIS|his_src||MEDREC|PAT_VISIT"

    def test_with_namespace(self):
        key = physical_node_key("LIS", "lis_src", "rmcloudlis7", "dbo", "V_X")
        assert key == "LIS|lis_src|rmcloudlis7|dbo|V_X"

    def test_missing_system_returns_none(self):
        assert physical_node_key(None, "src", None, "MEDREC", "PAT_VISIT") is None

    def test_missing_source_returns_none(self):
        assert physical_node_key("HIS", None, None, "MEDREC", "PAT_VISIT") is None

    def test_missing_table_returns_none(self):
        assert physical_node_key("HIS", "src", None, "MEDREC", None) is None

    def test_cross_system_no_collision(self):
        key1 = physical_node_key("HIS_SOURCE", "his_src", None, "HIS", "PAT_VISIT")
        key2 = physical_node_key("DATA_CENTER", "ods_src", None, "HIS", "PAT_VISIT")
        assert key1 != key2


class TestComputeBusinessKey:
    def test_stable_md5(self):
        key = compute_business_key("MEDREC.PAT_VISIT", "MEDREC.PAT_MASTER_INDEX", "PATIENT_ID", "PATIENT_ID", "a=b")
        assert key is not None
        assert len(key) == 32

    def test_idempotent(self):
        k1 = compute_business_key("A.B", "C.D", "X", "Y", "x=y")
        k2 = compute_business_key("A.B", "C.D", "X", "Y", "x=y")
        assert k1 == k2

    def test_different_join_different_key(self):
        k1 = compute_business_key("A.B", "C.D", "X", "Y", "x=y")
        k2 = compute_business_key("A.B", "C.D", "X", "Y", "x=z")
        assert k1 != k2

    def test_case_insensitive(self):
        k1 = compute_business_key("MEDREC.PAT_VISIT", "MEDREC.DIAGNOSIS", "PATIENT_ID", "PATIENT_ID", None)
        k2 = compute_business_key("medrec.pat_visit", "medrec.diagnosis", "patient_id", "patient_id", None)
        assert k1 == k2

    def test_missing_table_returns_none(self):
        assert compute_business_key(None, "C.D", "X", "Y", None) is None
        assert compute_business_key("A.B", None, "X", "Y", None) is None

    def test_cross_system_different_key(self):
        k1 = compute_business_key("HIS.PAT_VISIT", "HIS.DIAG", "PID", "PID", None,
                                  from_system_code="HIS_SOURCE", from_source_code="src1",
                                  to_system_code="HIS_SOURCE", to_source_code="src1")
        k2 = compute_business_key("HIS.PAT_VISIT", "HIS.DIAG", "PID", "PID", None,
                                  from_system_code="DATA_CENTER", from_source_code="src2",
                                  to_system_code="DATA_CENTER", to_source_code="src2")
        assert k1 != k2

    def test_multi_relation_same_tables_not_deduped(self):
        k1 = compute_business_key("A.B", "C.D", "X", "Y", "cond1")
        k2 = compute_business_key("A.B", "C.D", "X", "Y", "cond2")
        k3 = compute_business_key("A.B", "C.D", "Z", "W", "cond1")
        assert len({k1, k2, k3}) == 3


class TestDeriveLayer:
    def test_deferred_confidence_d(self):
        assert derive_layer("D", "verified") == "deferred"

    def test_sync_mapping(self):
        assert derive_layer("A", "user_confirmed_sync") == "sync_mapping"
        assert derive_layer("A", "user_confirmed_sync_parallel") == "sync_mapping"

    def test_candidate_status(self):
        assert derive_layer("B", "candidate") == "candidate"

    def test_formal_verified_a(self):
        assert derive_layer("A", "verified") == "formal"

    def test_formal_partial(self):
        assert derive_layer("B", "partial") == "formal"

    def test_formal_legacy_a_rechecked(self):
        assert derive_layer("A", "A_rechecked") == "formal"

    def test_empty_status_defaults_candidate(self):
        assert derive_layer(None, None) == "candidate"
        assert derive_layer("A", "") == "candidate"