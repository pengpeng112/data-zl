"""Tests for identity classification, sync orchestrator, and adapters.

Pure-logic tests run without DB. DB-dependent tests require APP_TEST_DB_URL.
Classifier test data uses LIVE HIS value domains (verified 2026-08-03).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.identity_classification import (
    ClassificationResult,
    classify_person,
    classify_batch,
    is_valid_group_class,
    allowed_additional_group_classes,
)

CUTOFF_AFTER = datetime(2026, 7, 25, tzinfo=timezone.utc)
CUTOFF_BEFORE = datetime(2026, 7, 19, tzinfo=timezone.utc)


# ===========================================================================
# Classifier pure-logic tests (live HIS JOB/TITLE value domains)
# ===========================================================================

class TestClassifyPerson:
    def test_doctor_by_job(self):
        result = classify_person(job="医生", title="主治医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"
        assert result.rule_version == "v2"

    def test_doctor_by_clinical_job(self):
        result = classify_person(job="临床", title="医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_doctor_chief_title_not_management(self):
        result = classify_person(job="医生", title="主任医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_doctor_deputy_chief(self):
        result = classify_person(job="临床", title="副主任医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_doctor_resident_title(self):
        result = classify_person(job="医生", title="住院医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_nurse_by_job(self):
        result = classify_person(job="护理", title="护师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "nurse"

    def test_nurse_by_title(self):
        result = classify_person(job="护士", title="主管护师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "nurse"

    def test_pharmacist_by_job(self):
        result = classify_person(job="药剂", title="药师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "pharmacist"

    def test_chief_pharmacist_not_management(self):
        result = classify_person(job="药剂", title="主任药师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "pharmacist"

    def test_outsource_runhua_pharmacy(self):
        result = classify_person(job="润华药学", title="药士", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "excluded_outsource"

    def test_outsource_vendor(self):
        result = classify_person(job="厂商驻场", title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "excluded_outsource"

    def test_outsource_yibang_aftersale(self):
        result = classify_person(job="颐邦售后", title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "excluded_outsource"

    def test_management_job_excluded(self):
        result = classify_person(job="行政管理", title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "excluded_management"

    def test_management_title_excluded(self):
        result = classify_person(job="医生", title="科主任", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "excluded_management"

    def test_head_nurse_title_excluded(self):
        result = classify_person(job="护理", title="护士长", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "excluded_management"

    def test_management_job_with_clinical_title_is_doctor(self):
        result = classify_person(job="行政管理", title="主任医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_classification_conflict_nurse_pharmacist(self):
        result = classify_person(job="护理", title="药师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "classification_conflict"
        assert result.conflict_detail is not None

    def test_classification_conflict_doctor_pharmacist(self):
        result = classify_person(job="医生", title="药士", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "classification_conflict"

    def test_status_conflict(self):
        result = classify_person(job="医生", title="主治医师", status="1", validstate="0", create_date=CUTOFF_AFTER)
        assert result.classification == "status_conflict"

    def test_status_conflict_reverse(self):
        result = classify_person(job="护理", title="护师", status="0", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "status_conflict"

    def test_legacy_unmanaged(self):
        result = classify_person(job="医生", title="主治医师", status="1", validstate="1", create_date=CUTOFF_BEFORE)
        assert result.classification == "legacy_unmanaged"

    def test_legacy_unmanaged_old_date(self):
        result = classify_person(job="护理", title="护师", status="1", validstate="1", create_date=datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert result.classification == "legacy_unmanaged"

    def test_null_create_date_isolated(self):
        """107 §15.5: 创建日期缺失必须隔离，不得纳入纳管。"""
        result = classify_person(job="医生", title="主治医师", status="1", validstate="1", create_date=None)
        assert result.classification == "master_data_missing"

    def test_unsupported_null_job_title(self):
        result = classify_person(job=None, title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "unsupported"

    def test_unsupported_empty_strings(self):
        result = classify_person(job="", title="", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "unsupported"

    def test_unsupported_unknown_job(self):
        result = classify_person(job="收费员", title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "unsupported"

    # --- 104 复核发现的核心缺陷回归：医技/技师不得判为医师 ---

    def test_yiji_job_not_doctor(self):
        """JOB=医技（活库 238 名技师）绝不能分类为 doctor。"""
        result = classify_person(job="医技", title="技师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification != "doctor"

    def test_technician_title_blocks_clinical_job(self):
        """JOB=影像诊断 + TITLE=技师 是技师，不是医师（活库 14 人）。"""
        result = classify_person(job="影像诊断", title="技师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "unsupported"
        assert result.matched_rule == "non_clinical_title"

    def test_imaging_doctor_with_clinical_title(self):
        result = classify_person(job="影像诊断", title="医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_ambiguous_job_without_title_not_synced(self):
        """JOB=影像诊断/急救 但无临床职称：不同步（保守）。"""
        result = classify_person(job="影像诊断", title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "unsupported"
        result2 = classify_person(job="急救", title=None, status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result2.classification == "unsupported"

    def test_emergency_doctor_with_title(self):
        result = classify_person(job="急救", title="主治医师", status="1", validstate="1", create_date=CUTOFF_AFTER)
        assert result.classification == "doctor"

    def test_single_char_keyword_never_used(self):
        """回归：禁止单字“医/护/药”关键词（103 硬性约束）。"""
        import app.services.identity_classification as mod
        for name in dir(mod):
            value = getattr(mod, name)
            if isinstance(value, (frozenset, set, tuple, list)):
                assert "医" not in value or "医" in ("医士",)
                assert "护" not in value
                assert "药" not in value


class TestClassifyBatch:
    def test_batch_multiple(self):
        rows = [
            {"job": "医生", "title": "主治医师", "status": "1", "validstate": "1", "create_date": CUTOFF_AFTER},
            {"job": "护理", "title": "护师", "status": "1", "validstate": "1", "create_date": CUTOFF_AFTER},
            {"job": "润华药学", "title": "药士", "status": "1", "validstate": "1", "create_date": CUTOFF_AFTER},
        ]
        results = classify_batch(rows)
        assert len(results) == 3
        assert results[0].classification == "doctor"
        assert results[1].classification == "nurse"
        assert results[2].classification == "excluded_outsource"


class TestGroupClassWhitelist:
    """Live GROUP_CLASS values (verified 2026-08-03): 病区医生/门诊医生/
    病区护士/检查医生/手术医生/麻醉医生/药品组/收款员/物资管理/行政管理。
    Plan 107's literal "住院医师"/"病房护士" do NOT exist in the live DB."""

    def test_doctor_ward_group_accepted(self):
        assert is_valid_group_class("病区医生", "doctor") is True

    def test_nurse_ward_group_accepted(self):
        assert is_valid_group_class("病区护士", "nurse") is True

    def test_outpatient_group_rejected_for_doctor(self):
        assert is_valid_group_class("门诊医生", "doctor") is False

    def test_nurse_group_rejected_for_doctor(self):
        assert is_valid_group_class("病区护士", "doctor") is False

    def test_pharmacist_no_additional_depts(self):
        assert is_valid_group_class("药品组", "pharmacist") is False
        assert is_valid_group_class("病区医生", "pharmacist") is False
        assert allowed_additional_group_classes("pharmacist") == frozenset()

    def test_nonclinical_groups_rejected(self):
        assert is_valid_group_class("收款员", "doctor") is False
        assert is_valid_group_class("物资管理", "nurse") is False
        assert is_valid_group_class("行政管理", "doctor") is False

    def test_none_and_empty_rejected(self):
        assert is_valid_group_class(None, "doctor") is False
        assert is_valid_group_class("", "doctor") is False

    def test_legacy_plan_values_do_not_exist(self):
        """107 字面值在活库不存在；必须使用活库映射值。"""
        assert is_valid_group_class("住院医师", "doctor") is False
        assert is_valid_group_class("病房护士", "nurse") is False


# ===========================================================================
# Orchestrator unit tests (mocked DB)
# ===========================================================================

class TestOrchestratorHelpers:
    def test_mask_emp_no_short(self):
        from app.services.identity_sync_orchestrator import _mask_emp_no
        assert _mask_emp_no("AB") == "**"
        assert _mask_emp_no("ABCD") == "****"

    def test_mask_emp_no_normal(self):
        from app.services.identity_sync_orchestrator import _mask_emp_no
        masked = _mask_emp_no("123456")
        assert masked.startswith("12")
        assert masked.endswith("56")
        assert "*" in masked

    def test_action_hash_deterministic(self):
        from app.services.identity_sync_orchestrator import _action_hash
        actions = [
            {"target_system": "CDMS", "action_type": "insert_user", "target_table": "T_MSS_EMP_DICT"},
            {"target_system": "JHEMR", "action_type": "ensure_role_group", "target_table": "jhauth_user_vs_role_group"},
        ]
        h1 = _action_hash(actions)
        h2 = _action_hash(actions)
        assert h1 == h2
        assert len(h1) == 32

    def test_strip_sensitive(self):
        from app.services.identity_sync_orchestrator import _strip_sensitive
        data = {"FPWD": "secret", "FLOGINNAME": "user1", "NAME": "张三", "FDEPTID": "001"}
        stripped = _strip_sensitive(data)
        assert "FPWD" not in stripped
        assert "NAME" not in stripped
        assert stripped["FLOGINNAME"] == "user1"
        assert stripped["FDEPTID"] == "001"


# ===========================================================================
# CDMS adapter unit tests (no real connection; live schema verified 2026-08-03)
# ===========================================================================

class TestCdmsAdapterConstants:
    def test_base_template(self):
        from app.services.cdms_identity_adapter import CDMS_BASE_TEMPLATE
        assert CDMS_BASE_TEMPLATE["FSYSID"] == "2"  # 活库众数（医疗904/护理1036 全量一致）
        assert CDMS_BASE_TEMPLATE["FUSERTYPE"] == "0"
        assert CDMS_BASE_TEMPLATE["FUSERSTATE"] == "0"
        assert CDMS_BASE_TEMPLATE["HOSPITALAREACODE"] == "A00001"

    def test_base_auth(self):
        from app.services.cdms_identity_adapter import CDMS_BASE_AUTH
        ftypes = {a["ftype"] for a in CDMS_BASE_AUTH}
        assert ftypes == {"3", "5", "10"}
        values = {a["fvalue"] for a in CDMS_BASE_AUTH}
        assert "100005" in values  # FTYPE=3 众数
        assert "A00001" in values  # FTYPE=5 众数
        assert "1" in values       # FTYPE=10：允许查询出院患者

    def test_no_ftype_8_32(self):
        from app.services.cdms_identity_adapter import CDMS_BASE_AUTH
        ftypes = {a["ftype"] for a in CDMS_BASE_AUTH}
        assert "8" not in ftypes
        assert "32" not in ftypes

    def test_strip_sensitive(self):
        from app.services.cdms_identity_adapter import _strip_sensitive
        data = {"FPWD": "abc123", "FLOGINNAME": "user1", "PASSWORD": "xyz"}
        result = _strip_sensitive(data)
        assert "FPWD" not in result
        assert "PASSWORD" not in result
        assert result["FLOGINNAME"] == "user1"

    def test_auth_sql_uses_live_columns(self):
        """回归：AUTHMAPPING 无 FLOGINNAME/FVALUE 列（ORA-00904）。"""
        import app.services.cdms_identity_adapter as mod
        assert "FLOGINNAME" not in mod._SQL_SELECT_AUTH
        assert "FVALUE" not in mod._SQL_SELECT_AUTH
        assert "WHERE FID = :emp_no" in mod._SQL_SELECT_AUTH
        assert "FUSER" in mod._SQL_SELECT_AUTH
        assert "FUPDATEUSER" in mod._SQL_SELECT_AUTH
        assert "FAUTHORITYID" in mod._SQL_SELECT_AUTH
        assert "FLOGINNAME" not in mod._SQL_INSERT_AUTH
        assert "FAUTHMAPPINGID" in mod._SQL_INSERT_AUTH
        assert "FPRIVIEGETYPE" in mod._SQL_INSERT_AUTH
        assert "FUPDATEUSER" in mod._SQL_INSERT_AUTH
        assert "NULL" in mod._SQL_INSERT_AUTH
        assert mod.CDMS_OPERATOR == "admin"

    def test_emp_sql_uses_fdept_not_fdeptid(self):
        """回归：EMP_DICT 无 FDEPTID 列，真实科室列为 FDEPT。"""
        import app.services.cdms_identity_adapter as mod
        assert "FDEPTID" not in mod._SQL_INSERT_EMP
        assert "FDEPT" in mod._SQL_INSERT_EMP
        assert "FDEPTID" not in mod._SQL_SELECT_EMP


# ===========================================================================
# JHEMR adapter unit tests (no real connection)
# ===========================================================================

class TestJhemrAdapterConstants:
    def test_hospital_no(self):
        from app.services.jhemr_identity_adapter import JHEMR_HOSPITAL_NO
        assert JHEMR_HOSPITAL_NO == "49557032X"

    def test_role_group_map(self):
        from app.services.jhemr_identity_adapter import ROLE_GROUP_MAP
        assert ROLE_GROUP_MAP["doctor"] == "001"
        assert ROLE_GROUP_MAP["pharmacist"] == "001"
        assert ROLE_GROUP_MAP["nurse"] == "002"

    def test_role_chain_001(self):
        from app.services.jhemr_identity_adapter import ROLE_CHAIN
        chain = ROLE_CHAIN["001"]
        assert chain["role_id"] == "25"
        assert chain["default_role"] == "DOCTOR/0"

    def test_role_chain_002(self):
        from app.services.jhemr_identity_adapter import ROLE_CHAIN
        chain = ROLE_CHAIN["002"]
        assert chain["role_id"] == "101"
        assert chain["default_role"] == "NURSE/1"

    def test_sensitive_fields_defined(self):
        from app.services.jhemr_identity_adapter import SENSITIVE_USER_FIELDS
        assert "user_pwd" in SENSITIVE_USER_FIELDS or "USER_PWD" in {f.upper() for f in SENSITIVE_USER_FIELDS}
        assert "user_pwd_sm" in SENSITIVE_USER_FIELDS or "USER_PWD_SM" in {f.upper() for f in SENSITIVE_USER_FIELDS}

    def test_no_duplicate_forbidden_tables(self):
        """回归：FORBIDDEN_WRITE_TABLES 只定义一次。"""
        import inspect
        import app.services.jhemr_identity_adapter as mod
        source = inspect.getsource(mod)
        assert source.count("FORBIDDEN_WRITE_TABLES = (") == 1
        assert "user_pwd" in mod.FORBIDDEN_WRITE_TABLES
        assert "user_pwd_sm" in mod.FORBIDDEN_WRITE_TABLES

    def test_users_insert_includes_user_dept(self):
        """回归：107 §5.4 要求 users.user_dept = HIS 主科室。"""
        import inspect
        from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
        source = inspect.getsource(JhemrIdentityAdapter.create_user_full)
        assert "user_dept" in source.split("INSERT INTO jhemr.users")[1].split("VALUES")[0]

    def test_sublogin_subsign_only_last_modify_time(self):
        """回归：活库 users_sublogin/users_subsign 无 last_modify_date 列。"""
        import inspect
        import re
        from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
        for fn in (JhemrIdentityAdapter.create_user_full, JhemrIdentityAdapter.align_existing_user):
            source = inspect.getsource(fn).replace('"', " ").replace("\n", " ")
            statements = re.findall(
                r'INSERT INTO jhemr\.users_sub(?:login|sign)\s*\(([^)]*)\)', source
            )
            assert statements, "expected sublogin/subsign INSERT statements"
            for cols in statements:
                assert "last_modify_date" not in cols
                assert "last_modify_user_id" not in cols
                assert "last_modify_time" in cols


class TestJhemrPasswordGate:
    def _adapter(self, **kwargs):
        from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
        adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
        adapter.hospital_no = "49557032X"
        adapter.password_secret_ref = kwargs.get("secret_ref", "")
        adapter.password_write_enabled = kwargs.get("write_enabled", False)
        adapter.sync_operator_id = "TEST"
        adapter._conn = None
        adapter._driver = None
        adapter._tunnel = None
        adapter._local_port = None
        import threading
        adapter._lock = threading.Lock()
        adapter.user_exists = lambda e: False
        adapter._ensure_conn = lambda: MagicMock()
        return adapter

    def test_create_refused_when_password_write_disabled(self):
        """107 §5.2：密码写入未启用时禁止建号（失败关闭，不产生半账号）。"""
        from app.services.jhemr_identity_adapter import JhemrIdentityError
        adapter = self._adapter(write_enabled=False, secret_ref="env:WHATEVER")
        with pytest.raises(JhemrIdentityError):
            adapter.create_user_full("EMP90", "Test", "doctor", "D01", [])

    def test_create_refused_without_secret_ref(self):
        from app.services.jhemr_identity_adapter import JhemrIdentityError
        adapter = self._adapter(write_enabled=True, secret_ref="")
        with pytest.raises(JhemrIdentityError):
            adapter.create_user_full("EMP90", "Test", "doctor", "D01", [])

    def test_create_refused_without_primary_dept(self):
        from app.services.jhemr_identity_adapter import JhemrIdentityError
        adapter = self._adapter(write_enabled=True, secret_ref="env:X")
        with pytest.raises(JhemrIdentityError):
            adapter.create_user_full("EMP90", "Test", "doctor", "", [])


# ===========================================================================
# Migration structure test
# ===========================================================================

class TestMigrationStructure:
    def test_migration_file_exists(self):
        from pathlib import Path
        migration = Path("alembic/versions/a3b4c5d6e7f8_identity_sync_tables.py")
        assert migration.exists()

    def test_migration_revision_chain(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "migration", "alembic/versions/a3b4c5d6e7f8_identity_sync_tables.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "e7f8a9b0c1d2"
        assert mod.down_revision == "d6e7f8a9b0c1"
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")

    def test_group_class_migration_chain(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "migration_gc", "alembic/versions/f8a9b0c1d2e3_add_identity_person_department_group_class.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "f8a9b0c1d2e3"
        assert mod.down_revision == "f1a2b3c4d5e6"


# ===========================================================================
# Config tests
# ===========================================================================

class TestConfig:
    def test_identity_sync_defaults(self):
        from app.core.config import Settings
        s = Settings(db_url="postgresql://test:test@localhost/test")
        assert s.identity_sync_enabled is False
        assert s.identity_sync_jhemr_hospital_no == "49557032X"
        assert s.identity_sync_managed_since == "2026-07-20"
        assert s.identity_sync_lock_timeout_seconds == 300
        assert s.identity_sync_lookback_hours == 24
        assert s.identity_jhemr_password_write_enabled is False

    def test_identity_sync_disabled_by_default(self):
        from app.core.config import settings
        assert settings.identity_sync_enabled is False


# ===========================================================================
# API safety tests
# ===========================================================================

class TestApiSafety:
    def test_wildcard_rejected(self):
        # Plan 107 section 6: API no longer accepts client-specified emp_no.
        # The old DryRunRequest model has been removed entirely.
        import app.api.v1.identity_sync as api_mod
        assert not hasattr(api_mod, "DryRunRequest")
        assert not hasattr(api_mod, "ApplyRequest")

    def test_mask_function(self):
        from app.services.identity_sync_orchestrator import _mask_emp_no
        assert _mask_emp_no("123456") == "12**56"
        assert _mask_emp_no("AB") == "**"
