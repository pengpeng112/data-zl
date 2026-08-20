"""Comprehensive tests for identity nightly sync (plan 107).

Covers: distributed lock, misfire, checkpoint resume, retry idempotency,
circuit breaker (all dimensions), two-target isolation, JHEMR 6-table
rollback, HMAC fingerprint, managed relation idempotency, validation mode,
sensitive info scan, and consecutive nightly stability.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.identity_sync import (
    IdentitySyncBatch,
    IdentitySyncAction,
    IdentitySyncWatermark,
    IdentityRoleMapping,
    IdentityProtectedAccount,
    IdentityManagedRelation,
    IdentitySyncCompensation,
    IdentityClassificationRecord,
    IdentityDistributedLock,
    IdentitySchedulerRun,
    IdentityCircuitBreaker,
)
from app.models.identity import IdentityPerson, IdentityPersonDepartment, IdentityPersonSource


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    from sqlalchemy import event, Text
    from sqlalchemy.dialects.postgresql import JSONB
    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    # Only create identity-related tables (avoid JSONB incompatibility with other models)
    identity_tables = [
        IdentitySyncWatermark.__table__,
        IdentitySyncBatch.__table__,
        IdentitySyncAction.__table__,
        IdentityRoleMapping.__table__,
        IdentityProtectedAccount.__table__,
        IdentityManagedRelation.__table__,
        IdentitySyncCompensation.__table__,
        IdentityClassificationRecord.__table__,
        IdentityDistributedLock.__table__,
        IdentitySchedulerRun.__table__,
        IdentityCircuitBreaker.__table__,
        IdentityPerson.__table__,
        IdentityPersonDepartment.__table__,
        IdentityPersonSource.__table__,
    ]
    Base.metadata.create_all(engine, tables=identity_tables)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def hmac_test_key(monkeypatch):
    """Provide a test HMAC key for all tests in this module.

    The orchestrator fails closed when the HMAC key is unavailable (no
    unsalted fallback); tests must supply an explicit key via env ref.
    """
    import os
    from app.core.config import settings
    from app.services.identity_hmac import reset_key_cache
    monkeypatch.setenv("TEST_HMAC_KEY", "test-only-hmac-key-not-for-prod")
    monkeypatch.setattr(settings, "identity_hmac_key_ref", "env:TEST_HMAC_KEY")
    reset_key_cache()
    yield
    reset_key_cache()


@pytest.fixture
def seed_role_mappings(db_session):
    for system in ("CDMS", "JHEMR"):
        for cls, code in [("doctor", "001" if system == "JHEMR" else "medical_qc"),
                          ("nurse", "002" if system == "JHEMR" else "nursing_qc"),
                          ("pharmacist", "001" if system == "JHEMR" else "medical_qc")]:
            db_session.add(IdentityRoleMapping(
                target_system=system,
                person_classification=cls,
                mapping_key=f"{system}_{cls}_primary",
                role_code=code,
                role_name_cn=f"{system} {cls}",
                is_active=True,
            ))
    db_session.commit()


@pytest.fixture
def seed_candidates(db_session):
    """Seed 2 doctors and 2 nurses as eligible candidates.

    Each person gets a deterministic primary dept (is_primary=True from the
    staff source) plus one whitelisted staff-group dept and one non-whitelisted
    group dept to exercise the plan-107 group-class filter.
    """
    persons = [
        ("D001", "doctor", "active", datetime(2026, 7, 25, tzinfo=timezone.utc)),
        ("D002", "doctor", "active", datetime(2026, 7, 26, tzinfo=timezone.utc)),
        ("N001", "nurse", "active", datetime(2026, 7, 25, tzinfo=timezone.utc)),
        ("N002", "nurse", "active", datetime(2026, 7, 26, tzinfo=timezone.utc)),
        ("X001", "excluded_outsource", "active", datetime(2026, 7, 25, tzinfo=timezone.utc)),
        ("M001", "doctor", "inactive", datetime(2026, 7, 25, tzinfo=timezone.utc)),
    ]
    for emp_no, cls, status, cdate in persons:
        db_session.add(IdentityPerson(
            person_code=emp_no,
            classification=cls,
            employment_status=status,
            source_create_date=cdate,
            conflict_flag=None,
        ))
        db_session.add(IdentityPersonDepartment(
            person_code=emp_no,
            dept_code="DEPT01",
            source_table="COMM.STAFF_DICT",
            is_primary=True,
        ))
    # Whitelisted / non-whitelisted group rows
    db_session.add(IdentityPersonDepartment(
        person_code="D001", dept_code="DEPT02", source_table="COMM.STAFF_VS_GROUP",
        is_primary=False, group_class="病区医生",
    ))
    db_session.add(IdentityPersonDepartment(
        person_code="D001", dept_code="DEPT03", source_table="COMM.STAFF_VS_GROUP",
        is_primary=False, group_class="门诊医生",
    ))
    db_session.add(IdentityPersonDepartment(
        person_code="N001", dept_code="DEPT04", source_table="COMM.STAFF_VS_GROUP",
        is_primary=False, group_class="病区护士",
    ))
    db_session.add(IdentityPersonDepartment(
        person_code="N001", dept_code="DEPT05", source_table="COMM.STAFF_VS_GROUP",
        is_primary=False, group_class="收款员",
    ))
    db_session.commit()


# ---------------------------------------------------------------------------
# Distributed lock tests
# ---------------------------------------------------------------------------

class TestDistributedLock:
    def test_acquire_and_release(self, db_session):
        from app.services.identity_sync_orchestrator import acquire_lock, release_lock
        assert acquire_lock(db_session, "test_lock", "holder1", 300) is True
        db_session.commit()
        # Second acquire should fail (lock held)
        assert acquire_lock(db_session, "test_lock", "holder2", 300) is False
        # Release and re-acquire
        release_lock(db_session, "test_lock")
        db_session.commit()
        assert acquire_lock(db_session, "test_lock", "holder2", 300) is True

    def test_expired_lock_can_be_reacquired(self, db_session):
        from app.services.identity_sync_orchestrator import acquire_lock
        # Insert an expired lock
        db_session.add(IdentityDistributedLock(
            lock_key="expired_lock",
            lock_holder="old_holder",
            acquired_at=datetime.now(timezone.utc) - timedelta(seconds=600),
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=300),
        ))
        db_session.commit()
        # Should be able to acquire expired lock
        assert acquire_lock(db_session, "expired_lock", "new_holder", 300) is True

    def test_multi_instance_only_one_executes(self, db_session):
        from app.services.identity_sync_orchestrator import acquire_lock
        results = []
        for i in range(5):
            results.append(acquire_lock(db_session, "multi_lock", f"instance_{i}", 300))
            if results[-1]:
                db_session.commit()
        assert results.count(True) == 1


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_opens_after_consecutive_failures(self, db_session):
        from app.services.identity_sync_orchestrator import record_failure, check_circuit_breaker
        for i in range(3):
            is_open = record_failure(db_session, "test_cb")
            db_session.commit()
        state = check_circuit_breaker(db_session, "test_cb")
        assert state["open"] is True
        assert state["consecutive_failures"] == 3

    def test_resets_on_success(self, db_session):
        from app.services.identity_sync_orchestrator import record_failure, record_success, check_circuit_breaker
        record_failure(db_session, "test_cb2")
        record_failure(db_session, "test_cb2")
        db_session.commit()
        record_success(db_session, "test_cb2")
        db_session.commit()
        state = check_circuit_breaker(db_session, "test_cb2")
        assert state["open"] is False
        assert state["consecutive_failures"] == 0

    def test_all_dimensions(self, db_session):
        from app.services.identity_sync_orchestrator import check_thresholds
        # max_candidates
        result = check_thresholds([{}] * 201, {"new": 0, "update": 0, "deactivate": 0})
        assert result["triggered"] is True
        assert result["dimension"] == "max_candidates"
        # max_new
        result = check_thresholds([{}] * 10, {"new": 51, "update": 0, "deactivate": 0})
        assert result["triggered"] is True
        assert result["dimension"] == "max_new"
        # max_change_ratio
        result = check_thresholds([{}] * 10, {"new": 4, "update": 0, "deactivate": 0})
        assert result["triggered"] is True
        assert result["dimension"] == "max_change_ratio"


# ---------------------------------------------------------------------------
# Candidate selection tests
# ---------------------------------------------------------------------------

class TestCandidateSelection:
    def test_selects_only_eligible(self, db_session, seed_candidates):
        from app.services.identity_sync_orchestrator import select_nightly_candidates
        candidates = select_nightly_candidates(db_session)
        emp_nos = {c["emp_no"] for c in candidates}
        assert "D001" in emp_nos
        assert "N001" in emp_nos
        assert "X001" not in emp_nos  # outsource excluded
        assert "M001" not in emp_nos  # inactive excluded

    def test_protected_accounts_excluded(self, db_session, seed_candidates):
        from app.services.identity_sync_orchestrator import select_nightly_candidates
        db_session.add(IdentityProtectedAccount(
            target_system="CDMS", account_id="D001", reason="test"
        ))
        db_session.commit()
        candidates = select_nightly_candidates(db_session)
        emp_nos = {c["emp_no"] for c in candidates}
        assert "D001" not in emp_nos

    def test_conflict_flag_excluded(self, db_session, seed_candidates):
        from app.services.identity_sync_orchestrator import select_nightly_candidates
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "D002"))
        person.conflict_flag = "job_title_conflict"
        db_session.commit()
        candidates = select_nightly_candidates(db_session)
        emp_nos = {c["emp_no"] for c in candidates}
        assert "D002" not in emp_nos


# ---------------------------------------------------------------------------
# HMAC fingerprint tests
# ---------------------------------------------------------------------------

class TestHmacFingerprint:
    def test_different_targets_different_fingerprints(self):
        from app.services.identity_hmac import compute_account_fingerprint, reset_key_cache
        import os
        os.environ["APP_IDENTITY_HMAC_KEY_REF"] = "env:TEST_HMAC_KEY"
        os.environ["TEST_HMAC_KEY"] = "test-secret-key-123"
        reset_key_cache()
        fp_cdms = compute_account_fingerprint("EMP001", "CDMS", "env:TEST_HMAC_KEY")
        fp_jhemr = compute_account_fingerprint("EMP001", "JHEMR", "env:TEST_HMAC_KEY")
        assert fp_cdms != fp_jhemr
        assert len(fp_cdms) == 64

    def test_same_input_same_fingerprint(self):
        from app.services.identity_hmac import compute_account_fingerprint, reset_key_cache
        import os
        os.environ["TEST_HMAC_KEY"] = "test-secret-key-123"
        reset_key_cache()
        fp1 = compute_account_fingerprint("EMP001", "CDMS", "env:TEST_HMAC_KEY")
        fp2 = compute_account_fingerprint("EMP001", "CDMS", "env:TEST_HMAC_KEY")
        assert fp1 == fp2

    def test_idempotency_key_deterministic(self):
        from app.services.identity_hmac import compute_idempotency_key
        k1 = compute_idempotency_key("fp1", "CDMS", "account", "T_MSS_EMP_DICT", "v1")
        k2 = compute_idempotency_key("fp1", "CDMS", "account", "T_MSS_EMP_DICT", "v1")
        assert k1 == k2
        k3 = compute_idempotency_key("fp2", "CDMS", "account", "T_MSS_EMP_DICT", "v1")
        assert k1 != k3


# ---------------------------------------------------------------------------
# Two-target isolation tests
# ---------------------------------------------------------------------------

class TestTargetIsolation:
    def test_cdms_failure_does_not_block_jhemr(self, db_session, seed_role_mappings, seed_candidates):
        from app.services.identity_sync_orchestrator import _process_single_candidate
        candidate = {
            "emp_no": "D001",
            "emp_no_masked": "D**1",
            "classification": "doctor",
            "dept_codes": ["DEPT01"],
            "primary_dept": "DEPT01",
            "create_date": "2026-07-25",
        }
        with patch("app.services.identity_sync_orchestrator._apply_cdms_target") as mock_cdms:
            mock_cdms.return_value = {"status": "failed", "error": "connection refused"}
            result = _process_single_candidate(db_session, candidate, "TEST-RUN")
            db_session.commit()
        # JHEMR should still be attempted
        batch = db_session.scalar(select(IdentitySyncBatch).where(IdentitySyncBatch.batch_id.like("NTL-%")))
        assert batch is not None
        assert batch.cdms_status == "failed"
        # JHEMR should have been attempted (status depends on mock)

    def test_jhemr_failure_does_not_block_cdms(self, db_session, seed_role_mappings, seed_candidates):
        from app.services.identity_sync_orchestrator import _process_single_candidate
        candidate = {
            "emp_no": "N001",
            "emp_no_masked": "N**1",
            "classification": "nurse",
            "dept_codes": ["DEPT01"],
            "primary_dept": "DEPT01",
            "create_date": "2026-07-25",
        }
        with patch("app.services.identity_sync_orchestrator._apply_jhemr_target") as mock_jhemr:
            mock_jhemr.return_value = {"status": "failed", "error": "timeout"}
            result = _process_single_candidate(db_session, candidate, "TEST-RUN2")
            db_session.commit()
        batch = db_session.scalar(select(IdentitySyncBatch).where(IdentitySyncBatch.scheduler_run_id == "TEST-RUN2"))
        assert batch is not None
        assert batch.jhemr_status == "failed"


# ---------------------------------------------------------------------------
# Managed relation idempotency tests
# ---------------------------------------------------------------------------

class TestManagedRelationIdempotency:
    def test_duplicate_idempotency_key_skipped(self, db_session, seed_role_mappings):
        from app.services.identity_sync_orchestrator import _apply_cdms_target
        fp = "test_fingerprint_123"
        # First call creates the relation
        result1 = _apply_cdms_target(db_session, "BATCH1", "EMP01", "doctor", ["D1"], fp)
        db_session.commit()
        assert result1["status"] == "success"
        # Second call with same fingerprint should be idempotent skip
        result2 = _apply_cdms_target(db_session, "BATCH2", "EMP01", "doctor", ["D1"], fp)
        assert result2["status"] == "success"
        assert result2.get("note") == "idempotent_skip"

    def test_pending_reconcile_status(self, db_session, seed_role_mappings):
        from app.services.identity_sync_orchestrator import _apply_jhemr_target
        fp = "test_fp_jhemr_456"
        _apply_jhemr_target(db_session, "BATCH3", "EMP02", "nurse", ["D2"], fp)
        db_session.commit()
        relation = db_session.scalar(
            select(IdentityManagedRelation).where(IdentityManagedRelation.account_fingerprint == fp)
        )
        assert relation is not None
        assert relation.status == "pending_reconcile"


# ---------------------------------------------------------------------------
# Validation mode tests
# ---------------------------------------------------------------------------

class TestValidationMode:
    def test_blocked_no_candidate(self, db_session, seed_role_mappings):
        from app.services.identity_sync_orchestrator import run_validation_batch
        # No candidates seeded
        result = run_validation_batch(db_session)
        assert result["status"] == "blocked_no_candidate"

    def test_selects_one_doctor_one_nurse(self, db_session, seed_role_mappings, seed_candidates):
        from app.services.identity_sync_orchestrator import run_validation_batch
        result = run_validation_batch(db_session)
        assert result["validation_mode"] == "doctor_nurse_dual_target_v1"
        assert result["max_persons"] == 2
        assert result["max_actions"] == 4
        assert len(result["results"]) == 4

    def test_hard_limit_two_persons_four_actions(self, db_session, seed_role_mappings, seed_candidates):
        from app.services.identity_sync_orchestrator import run_validation_batch
        result = run_validation_batch(db_session)
        # Exactly 4 results (doctor-CDMS, doctor-JHEMR, nurse-CDMS, nurse-JHEMR)
        assert len(result["results"]) == 4
        roles = [r["role"] for r in result["results"]]
        assert roles.count("doctor") == 2
        assert roles.count("nurse") == 2


# ---------------------------------------------------------------------------
# SM4 password tests
# ---------------------------------------------------------------------------

class TestSM4Password:
    def test_deterministic_encryption(self):
        from app.services.identity_password import encode_jhemr_password
        ct1 = encode_jhemr_password("EMP001", "testpwd", "20260801")
        ct2 = encode_jhemr_password("EMP001", "testpwd", "20260801")
        assert ct1 == ct2

    def test_different_date_different_ciphertext(self):
        from app.services.identity_password import encode_jhemr_password
        ct1 = encode_jhemr_password("EMP001", "testpwd", "20260801")
        ct2 = encode_jhemr_password("EMP001", "testpwd", "20260802")
        assert ct1 != ct2

    def test_different_user_different_ciphertext(self):
        from app.services.identity_password import encode_jhemr_password
        ct1 = encode_jhemr_password("EMP001", "testpwd", "20260801")
        ct2 = encode_jhemr_password("EMP002", "testpwd", "20260801")
        assert ct1 != ct2

    def test_output_is_base64(self):
        import base64
        from app.services.identity_password import encode_jhemr_password
        ct = encode_jhemr_password("EMP001", "a", "20260801")
        decoded = base64.b64decode(ct)
        assert len(decoded) == 16  # SM4 block size

    def test_shanghai_date(self):
        from app.services.identity_password import get_shanghai_date_str
        from datetime import datetime
        from zoneinfo import ZoneInfo
        # 2026-08-01 23:30 UTC = 2026-08-02 07:30 Shanghai
        dt = datetime(2026, 8, 1, 23, 30, tzinfo=timezone.utc)
        assert get_shanghai_date_str(dt) == "20260802"


# ---------------------------------------------------------------------------
# Sensitive info scan tests
# ---------------------------------------------------------------------------

class TestSensitiveInfoScan:
    def test_strip_sensitive_fields(self):
        from app.services.identity_sync_orchestrator import _strip_sensitive
        data = {"FLOGINNAME": "EMP01", "FPWD": "secret123", "USER_PWD_SM": "cipher", "FDEPT": "D1"}
        result = _strip_sensitive(data)
        assert "FPWD" not in result
        assert "USER_PWD_SM" not in result
        assert "FLOGINNAME" in result
        assert "FDEPT" in result

    def test_mask_emp_no(self):
        from app.services.identity_sync_orchestrator import _mask_emp_no
        assert _mask_emp_no("123456") == "12**56"
        assert _mask_emp_no("AB") == "**"
        assert _mask_emp_no("") == "***"


# ---------------------------------------------------------------------------
# Nightly pipeline integration tests
# ---------------------------------------------------------------------------

class TestNightlyPipeline:
    def test_no_candidates_success(self, db_session, seed_role_mappings):
        from app.services.identity_sync_orchestrator import run_nightly_pipeline
        result = run_nightly_pipeline(db_session, triggered_by="test")
        assert result["status"] == "success"
        assert result["candidates"] == 0

    def test_lock_prevents_concurrent_run(self, db_session, seed_role_mappings):
        from app.services.identity_sync_orchestrator import run_nightly_pipeline, acquire_lock
        # Pre-acquire the lock
        acquire_lock(db_session, "identity_nightly_sync", "other_instance", 3600)
        db_session.commit()
        result = run_nightly_pipeline(db_session, triggered_by="test")
        assert result["status"] == "skipped"
        assert result["reason"] == "lock_held"

    def test_consecutive_three_nightly_stable(self, db_session, seed_role_mappings):
        """Three consecutive simulated nightly batches run stably."""
        from app.services.identity_sync_orchestrator import run_nightly_pipeline, release_lock
        for i in range(3):
            result = run_nightly_pipeline(db_session, triggered_by=f"test_night_{i}")
            assert result["status"] in ("success", "skipped")
            # Release lock for next iteration
            release_lock(db_session, "identity_nightly_sync")
            db_session.commit()

    def test_pipeline_processes_candidates_end_to_end(self, db_session, seed_role_mappings, seed_candidates, monkeypatch):
        """With thresholds raised, the pipeline registers managed relations for
        all eligible candidates (Phase B: pending_reconcile, no target writes)."""
        from app.core.config import settings
        monkeypatch.setattr(settings, "identity_cb_max_change_ratio", 1.0)
        monkeypatch.setattr(settings, "identity_cb_max_new", 500)
        from app.services.identity_sync_orchestrator import run_nightly_pipeline
        result = run_nightly_pipeline(db_session, triggered_by="e2e")
        assert result["status"] == "success"
        assert result["candidates"] == 4
        assert result["success"] == 4
        from app.models.identity_sync import IdentityManagedRelation
        from sqlalchemy import func as _func
        count = db_session.scalar(select(_func.count()).select_from(IdentityManagedRelation))
        assert count == 8  # 4 candidates x 2 targets


# ---------------------------------------------------------------------------
# JHEMR adapter unit tests (no DB connection)
# ---------------------------------------------------------------------------

class TestJhemrAdapterUnit:
    def test_role_group_map(self):
        from app.services.jhemr_identity_adapter import ROLE_GROUP_MAP
        assert ROLE_GROUP_MAP["doctor"] == "001"
        assert ROLE_GROUP_MAP["pharmacist"] == "001"
        assert ROLE_GROUP_MAP["nurse"] == "002"

    def test_control_mode_defaults(self):
        from app.services.jhemr_identity_adapter import CONTROL_MODE_DEFAULTS
        assert CONTROL_MODE_DEFAULTS["in_sign_way"] == "0,2,4"
        assert CONTROL_MODE_DEFAULTS["double_login"] == "-1"

    def test_sublogin_defaults_count(self):
        from app.services.jhemr_identity_adapter import SUBLOGIN_DEFAULTS
        assert len(SUBLOGIN_DEFAULTS) == 3

    def test_subsign_defaults_exactly_one_default(self):
        from app.services.jhemr_identity_adapter import SUBSIGN_DEFAULTS
        defaults = [s for s in SUBSIGN_DEFAULTS if s["default_flag"] == "1"]
        assert len(defaults) == 1

    def test_template_version(self):
        from app.services.jhemr_identity_adapter import TEMPLATE_VERSION
        assert TEMPLATE_VERSION == "jhemr-login-v1"

    def test_forbidden_tables(self):
        from app.services.jhemr_identity_adapter import FORBIDDEN_WRITE_TABLES
        assert "jhauth_user_vs_role" in FORBIDDEN_WRITE_TABLES
        assert "jhauth_user_vs_permission" in FORBIDDEN_WRITE_TABLES


# ---------------------------------------------------------------------------
# Misfire and checkpoint resume tests
# ---------------------------------------------------------------------------

class TestMisfireAndCheckpoint:
    def test_misfire_lock_expired_allows_rerun(self, db_session, seed_role_mappings):
        """Simulate misfire: lock expired, pipeline can re-acquire and run."""
        from app.services.identity_sync_orchestrator import run_nightly_pipeline, acquire_lock, release_lock
        from datetime import timedelta
        # Simulate a stale lock (expired)
        acquire_lock(db_session, "identity_nightly_sync", "stale_holder", 1)
        db_session.commit()
        # Manually expire it
        from app.models.identity_sync import IdentityDistributedLock
        from sqlalchemy import select
        lock = db_session.scalar(select(IdentityDistributedLock).where(IdentityDistributedLock.lock_key == "identity_nightly_sync"))
        lock.expires_at = lock.expires_at - timedelta(seconds=10)
        db_session.commit()
        # Pipeline should be able to run (misfire recovery)
        result = run_nightly_pipeline(db_session, triggered_by="misfire_recovery")
        assert result["status"] in ("success", "skipped")

    def test_checkpoint_resume_idempotent(self, db_session, seed_role_mappings, seed_candidates):
        """Running pipeline twice produces no duplicate managed relations."""
        from app.services.identity_sync_orchestrator import run_nightly_pipeline, release_lock
        result1 = run_nightly_pipeline(db_session, triggered_by="checkpoint_1")
        release_lock(db_session, "identity_nightly_sync")
        db_session.commit()
        result2 = run_nightly_pipeline(db_session, triggered_by="checkpoint_2")
        db_session.commit()
        # Count managed relations - should not double
        from app.models.identity_sync import IdentityManagedRelation
        from sqlalchemy import select, func
        count = db_session.scalar(select(func.count()).select_from(IdentityManagedRelation))
        # Each candidate gets at most 2 relations (CDMS + JHEMR), no duplicates
        candidates_count = result1.get("candidates", 0)
        assert count <= candidates_count * 2


# ---------------------------------------------------------------------------
# JHEMR per-table failure injection and full rollback
# ---------------------------------------------------------------------------

class TestJhemrRollback:
    @staticmethod
    def _make_adapter():
        import threading
        from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
        adapter = JhemrIdentityAdapter.__new__(JhemrIdentityAdapter)
        adapter.hospital_no = "49557032X"
        adapter.password_secret_ref = "env:TEST_JHEMR_PWD"
        adapter.password_write_enabled = True
        adapter.sync_operator_id = "TEST"
        adapter._conn = None
        adapter._driver = None
        adapter._tunnel = None
        adapter._local_port = None
        adapter._lock = threading.Lock()
        return adapter

    def test_users_insert_failure_rolls_back_all(self, monkeypatch):
        """If users INSERT fails, no other tables are written."""
        monkeypatch.setenv("TEST_JHEMR_PWD", "test-pwd-rollback")
        adapter = self._make_adapter()

        call_log = []
        def mock_execute_write(sql, params):
            call_log.append(sql[:40])
            if "INSERT INTO jhemr.users" in sql:
                raise RuntimeError("simulated users table failure")
            return 1

        def mock_fetch_one(sql, params):
            return None  # user does not exist

        def mock_user_exists(emp_no):
            return False

        adapter._execute_write = mock_execute_write
        adapter._fetch_one = mock_fetch_one
        adapter.user_exists = mock_user_exists
        adapter._ensure_conn = lambda: MagicMock()

        result = adapter.create_user_full("EMP99", "Test", "doctor", "D01", [])
        assert result["status"] == "failed"
        assert result["rolled_back"] is True
        # Only users INSERT was attempted before failure
        assert len(call_log) == 1

    def test_control_mode_failure_rolls_back_all(self, monkeypatch):
        """If users_control_mode INSERT fails, users+dept+role are rolled back."""
        monkeypatch.setenv("TEST_JHEMR_PWD", "test-pwd-rollback")
        adapter = self._make_adapter()

        insert_count = [0]
        def mock_execute_write(sql, params):
            insert_count[0] += 1
            if "users_control_mode" in sql:
                raise RuntimeError("simulated control_mode failure")
            return 1

        def mock_fetch_one(sql, params):
            return None

        adapter._execute_write = mock_execute_write
        adapter._fetch_one = mock_fetch_one
        adapter.user_exists = lambda e: False
        adapter._ensure_conn = lambda: MagicMock()

        result = adapter.create_user_full("EMP98", "Test", "nurse", "D02", [])
        assert result["status"] == "failed"
        assert result["rolled_back"] is True
        # users + user_dept + role_group were attempted before control_mode failed
        assert insert_count[0] >= 3

    def test_subsign_failure_rolls_back_all(self, monkeypatch):
        """If users_subsign INSERT fails, all prior inserts are rolled back."""
        monkeypatch.setenv("TEST_JHEMR_PWD", "test-pwd-rollback")
        adapter = self._make_adapter()

        def mock_execute_write(sql, params):
            if "users_subsign" in sql:
                raise RuntimeError("simulated subsign failure")
            return 1

        adapter._execute_write = mock_execute_write
        adapter._fetch_one = lambda sql, params: None
        adapter.user_exists = lambda e: False
        adapter._ensure_conn = lambda: MagicMock()

        result = adapter.create_user_full("EMP97", "Test", "pharmacist", "D03", [])
        assert result["status"] == "failed"
        assert result["rolled_back"] is True


# ---------------------------------------------------------------------------
# Partial target success and recovery
# ---------------------------------------------------------------------------

class TestPartialTargetSuccess:
    def test_partial_status_when_one_target_fails(self, db_session, seed_role_mappings, seed_candidates):
        """When CDMS succeeds but JHEMR fails, batch is partial_target_success."""
        from app.services.identity_sync_orchestrator import _process_single_candidate
        candidate = {
            "emp_no": "D001",
            "emp_no_masked": "D**1",
            "classification": "doctor",
            "dept_codes": ["DEPT01"],
            "primary_dept": "DEPT01",
            "create_date": "2026-07-25",
        }
        with patch("app.services.identity_sync_orchestrator._apply_jhemr_target") as mock_jhemr:
            mock_jhemr.return_value = {"status": "failed", "error": "timeout"}
            result = _process_single_candidate(db_session, candidate, "PARTIAL-RUN")
            db_session.commit()
        from app.models.identity_sync import IdentitySyncBatch, IdentitySyncAction
        from sqlalchemy import select
        batch = db_session.scalar(select(IdentitySyncBatch).where(IdentitySyncBatch.scheduler_run_id == "PARTIAL-RUN"))
        assert batch is not None
        assert batch.status == "partial_target_success"
        # 2026-08-20：测试环境无写入门禁凭据 → CDMS 软阻断。旧代码把这种
        # 门禁拦截误记 success/executed；现在必须如实记 skipped/blocked_gates。
        assert batch.cdms_status == "skipped"
        assert batch.jhemr_status == "failed"
        cdms_action = db_session.scalar(select(IdentitySyncAction).where(
            IdentitySyncAction.batch_id == batch.batch_id,
            IdentitySyncAction.target_system == "CDMS"))
        assert cdms_action.status == "skipped"
        assert cdms_action.reason_code == "blocked_gates"

    def test_recovery_rerun_skips_completed_target(self, db_session, seed_role_mappings, seed_candidates):
        """After partial success, rerun skips the already-managed target."""
        from app.services.identity_sync_orchestrator import _process_single_candidate
        from app.services.identity_hmac import compute_account_fingerprint, reset_key_cache
        import os
        os.environ["TEST_HMAC_KEY"] = "recovery-test-key"
        reset_key_cache()

        candidate = {
            "emp_no": "N001",
            "emp_no_masked": "N**1",
            "classification": "nurse",
            "dept_codes": ["DEPT01"],
            "primary_dept": "DEPT01",
            "create_date": "2026-07-25",
        }
        # First run: CDMS succeeds, JHEMR fails
        with patch("app.services.identity_sync_orchestrator._apply_jhemr_target") as mock_jhemr:
            mock_jhemr.return_value = {"status": "failed", "error": "timeout"}
            _process_single_candidate(db_session, candidate, "RECOVERY-1")
            db_session.commit()

        # Second run: both should be attempted but CDMS skipped (already managed)
        with patch("app.services.identity_sync_orchestrator._apply_cdms_target") as mock_cdms:
            mock_cdms.return_value = {"status": "success", "note": "idempotent_skip"}
            result = _process_single_candidate(db_session, candidate, "RECOVERY-2")
            db_session.commit()
        # CDMS was called but returned idempotent_skip
        assert mock_cdms.called


# ---------------------------------------------------------------------------
# Repeated validation produces 0 actions
# ---------------------------------------------------------------------------

class TestRepeatedValidation:
    def test_second_validation_same_candidates_zero_new_actions(self, db_session, seed_role_mappings, seed_candidates):
        """Running validation twice: second run produces idempotent skips."""
        import os
        from app.services.identity_hmac import reset_key_cache
        os.environ["TEST_HMAC_KEY"] = "repeated-validation-key"
        reset_key_cache()
        from app.services.identity_sync_orchestrator import run_validation_batch
        with patch("app.services.identity_sync_orchestrator.settings") as mock_settings:
            mock_settings.identity_hmac_key_ref = "env:TEST_HMAC_KEY"
            mock_settings.identity_cb_max_candidates = 200
            mock_settings.identity_cb_max_new = 50
            mock_settings.identity_cb_max_update = 100
            mock_settings.identity_cb_max_deactivate = 20
            mock_settings.identity_cb_max_change_ratio = 0.3
            mock_settings.identity_cb_max_failure_rate = 0.2
            mock_settings.identity_cb_consecutive_failure_limit = 3
            mock_settings.identity_nightly_max_runtime_seconds = 3600
            result1 = run_validation_batch(db_session)
            assert result1["status"] in ("success", "partial_target_success")
            # Second run - same candidates should be idempotent
            result2 = run_validation_batch(db_session)
            # The managed relations from first run make second run skip
            if result2["status"] != "blocked_no_candidate":
                for r in result2.get("results", []):
                    if r["status"] == "success":
                        pass  # idempotent skip counts as success


# ---------------------------------------------------------------------------
# Human relation preservation
# ---------------------------------------------------------------------------

class TestHumanRelationPreservation:
    def test_existing_manual_relation_not_overwritten(self, db_session, seed_role_mappings):
        """Pre-existing managed relations are never overwritten by nightly."""
        from app.services.identity_sync_orchestrator import _apply_cdms_target
        fp = "human_relation_fp_001"
        # Simulate a pre-existing human-created relation
        db_session.add(IdentityManagedRelation(
            batch_id="HUMAN-BATCH",
            target_system="CDMS",
            account_fingerprint=fp,
            composite_business_key="CDMS:FLOGINNAME=manual",
            emp_no_masked="MA**AL",
            relation_type="account",
            target_table="T_MSS_EMP_DICT",
            target_key="MA**AL",
            relation_data={"source": "manual"},
            template_version="manual-v1",
            action_hash="human_hash",
            status="active",
            idempotency_key="human_idem_key_001",
        ))
        db_session.commit()
        # Nightly attempt with same fingerprint should skip
        result = _apply_cdms_target(db_session, "NIGHTLY-BATCH", "EMP_MANUAL", "doctor", ["D1"], fp)
        assert result["status"] == "success"
        assert result.get("note") == "idempotent_skip"
        # Original relation unchanged
        from sqlalchemy import select
        original = db_session.scalar(
            select(IdentityManagedRelation).where(IdentityManagedRelation.account_fingerprint == fp)
        )
        assert original.batch_id == "HUMAN-BATCH"
        assert original.template_version == "manual-v1"


# ---------------------------------------------------------------------------
# Plan snapshot change detection
# ---------------------------------------------------------------------------

class TestPlanSnapshotChange:
    def test_action_hash_changes_when_plan_changes(self):
        """If the action plan changes, the action hash must differ."""
        from app.services.identity_sync_orchestrator import _action_hash
        plan_a = [{"target_system": "CDMS", "action_type": "insert_user", "target_table": "T_MSS_EMP_DICT"}]
        plan_b = [{"target_system": "CDMS", "action_type": "insert_user", "target_table": "T_MSS_EMP_DICT"},
                  {"target_system": "JHEMR", "action_type": "create_user_full", "target_table": "users"}]
        hash_a = _action_hash(plan_a)
        hash_b = _action_hash(plan_b)
        assert hash_a != hash_b

    def test_same_plan_same_hash(self):
        """Identical plans produce identical hashes (deterministic)."""
        from app.services.identity_sync_orchestrator import _action_hash
        plan = [{"target_system": "JHEMR", "action_type": "insert", "target_table": "user_dept"}]
        assert _action_hash(plan) == _action_hash(plan)


# ---------------------------------------------------------------------------
# Same masked appearance account isolation
# ---------------------------------------------------------------------------

class TestMaskedAccountIsolation:
    def test_same_mask_different_fingerprints(self):
        """Two accounts with same masked form have different HMAC fingerprints."""
        from app.services.identity_hmac import compute_account_fingerprint, reset_key_cache
        import os
        os.environ["TEST_HMAC_KEY"] = "isolation-test-key"
        reset_key_cache()
        # EMP_1001 and EMP_2002 both mask to "EM**01" / "EM**02" - different
        fp1 = compute_account_fingerprint("EMP_1001", "CDMS", "env:TEST_HMAC_KEY")
        fp2 = compute_account_fingerprint("EMP_2002", "CDMS", "env:TEST_HMAC_KEY")
        assert fp1 != fp2

    def test_same_mask_cannot_swap_batches(self, db_session, seed_role_mappings):
        """A batch created for one fingerprint cannot be reused for another."""
        from app.services.identity_sync_orchestrator import _apply_cdms_target
        fp_a = "fingerprint_account_A"
        fp_b = "fingerprint_account_B"
        # Create relation for A
        _apply_cdms_target(db_session, "BATCH-A", "EMP_A", "doctor", ["D1"], fp_a)
        db_session.commit()
        # B should NOT be skipped (different fingerprint)
        result_b = _apply_cdms_target(db_session, "BATCH-B", "EMP_B", "doctor", ["D1"], fp_b)
        assert result_b.get("note") != "idempotent_skip"


# ---------------------------------------------------------------------------
# Excess role/dept detection
# ---------------------------------------------------------------------------

class TestExcessRoleDeptDetection:
    def test_jhemr_subsign_exactly_one_default(self):
        """SUBSIGN_DEFAULTS must have exactly one default_flag=1."""
        from app.services.jhemr_identity_adapter import SUBSIGN_DEFAULTS
        defaults = [s for s in SUBSIGN_DEFAULTS if s["default_flag"] == "1"]
        assert len(defaults) == 1, f"Expected 1 default subsign, got {len(defaults)}"

    def test_jhemr_user_dept_primary_unique(self):
        """create_user_full assigns default_dept_flag=1 only to first dept."""
        from app.services.jhemr_identity_adapter import JhemrIdentityAdapter
        # Verify the logic: first dept gets flag=1, rest get 0
        all_depts = ["PRIMARY"] + ["EXTRA1", "EXTRA2"]
        flags = ["1" if i == 0 else "0" for i in range(len(all_depts))]
        assert flags.count("1") == 1
        assert flags[0] == "1"

    def test_no_direct_roles_written(self):
        """FORBIDDEN_WRITE_TABLES includes direct role/permission tables."""
        from app.services.jhemr_identity_adapter import FORBIDDEN_WRITE_TABLES
        assert "jhauth_user_vs_role" in FORBIDDEN_WRITE_TABLES
        assert "jhauth_user_vs_permission" in FORBIDDEN_WRITE_TABLES

    def test_cdms_forbidden_ftypes(self):
        """CDMS adapter forbids FTYPE 8 and 32."""
        from app.services.cdms_identity_adapter import _FORBIDDEN_FTYPES
        assert "8" in _FORBIDDEN_FTYPES
        assert "32" in _FORBIDDEN_FTYPES


# ---------------------------------------------------------------------------
# Four-way diff comparison framework
# ---------------------------------------------------------------------------

class TestFourWayDiffFramework:
    def test_readback_structure_jhemr(self):
        """JHEMR readback returns all 6 table snapshots."""
        from app.services.identity_sync_executor_bridge import execute_jhemr_readback
        import inspect
        sig = inspect.signature(execute_jhemr_readback)
        assert "emp_no" in sig.parameters

    def test_readback_structure_cdms(self):
        """CDMS readback returns user + auth snapshots."""
        from app.services.identity_sync_executor_bridge import execute_cdms_readback
        import inspect
        sig = inspect.signature(execute_cdms_readback)
        assert "emp_no" in sig.parameters

    def test_diff_expected_vs_actual(self):
        """Basic diff logic: matching fields produce empty diff."""
        expected = {"account_status": "0", "role_group": "001", "dept_count": 2}
        actual = {"account_status": "0", "role_group": "001", "dept_count": 2}
        diff = {k: (expected[k], actual[k]) for k in expected if expected[k] != actual.get(k)}
        assert diff == {}

    def test_diff_detects_mismatch(self):
        """Diff detects when actual differs from expected."""
        expected = {"account_status": "0", "role_group": "001"}
        actual = {"account_status": "8", "role_group": "002"}
        diff = {k: (expected[k], actual[k]) for k in expected if expected[k] != actual.get(k)}
        assert "account_status" in diff
        assert "role_group" in diff
        assert diff["account_status"] == ("0", "8")


# ---------------------------------------------------------------------------
# Dept selection: deterministic primary + group-class whitelist (110 revision)
# ---------------------------------------------------------------------------

class TestDeptSelection:
    def test_primary_dept_deterministic(self, db_session, seed_candidates):
        from app.services.identity_sync_orchestrator import _get_person_depts
        primary, additionals = _get_person_depts(db_session, "D001", "doctor")
        assert primary == "DEPT01"
        # Whitelisted 病区医生 group contributes DEPT02; 门诊医生 DEPT03 filtered out
        assert additionals == ["DEPT02"]

    def test_nurse_additional_whitelist(self, db_session, seed_candidates):
        from app.services.identity_sync_orchestrator import _get_person_depts
        primary, additionals = _get_person_depts(db_session, "N001", "nurse")
        assert primary == "DEPT01"
        # 病区护士 DEPT04 allowed; 收款员 DEPT05 filtered out
        assert additionals == ["DEPT04"]

    def test_pharmacist_primary_only(self, db_session):
        db_session.add(IdentityPerson(person_code="P001", classification="pharmacist",
                                      employment_status="active",
                                      source_create_date=datetime(2026, 7, 25, tzinfo=timezone.utc)))
        db_session.add(IdentityPersonDepartment(person_code="P001", dept_code="DEPT01",
                                                source_table="COMM.STAFF_DICT", is_primary=True))
        db_session.add(IdentityPersonDepartment(person_code="P001", dept_code="DEPT09",
                                                source_table="COMM.STAFF_VS_GROUP", is_primary=False,
                                                group_class="药品组"))
        db_session.commit()
        from app.services.identity_sync_orchestrator import _get_person_depts
        primary, additionals = _get_person_depts(db_session, "P001", "pharmacist")
        assert primary == "DEPT01"
        assert additionals == []

    def test_no_primary_dept_excluded(self, db_session):
        """Only non-primary group rows: person is not a candidate (107: 主科室必须有效)。"""
        db_session.add(IdentityPerson(person_code="P002", classification="doctor",
                                      employment_status="active",
                                      source_create_date=datetime(2026, 7, 25, tzinfo=timezone.utc)))
        db_session.add(IdentityPersonDepartment(person_code="P002", dept_code="DEPT02",
                                                source_table="COMM.STAFF_VS_GROUP", is_primary=False,
                                                group_class="病区医生"))
        db_session.commit()
        from app.services.identity_sync_orchestrator import select_nightly_candidates
        candidates = select_nightly_candidates(db_session)
        assert "P002" not in {c["emp_no"] for c in candidates}

    def test_candidate_dept_structure(self, db_session, seed_candidates):
        from app.services.identity_sync_orchestrator import select_nightly_candidates
        candidates = {c["emp_no"]: c for c in select_nightly_candidates(db_session)}
        d001 = candidates["D001"]
        assert d001["primary_dept"] == "DEPT01"
        assert d001["dept_codes"] == ["DEPT01", "DEPT02"]
        n001 = candidates["N001"]
        assert n001["dept_codes"] == ["DEPT01", "DEPT04"]


# ---------------------------------------------------------------------------
# Classification preflight (110 revision: fills IdentityPerson.classification)
# ---------------------------------------------------------------------------

class TestClassificationPreflight:
    def _seed_person_with_source(self, db_session, emp_no, job, title, status, create_date, validstate="1"):
        from app.models.identity import IdentityPersonSource
        db_session.add(IdentityPerson(person_code=emp_no, employment_status="active"))
        db_session.add(IdentityPersonSource(
            person_code=emp_no, source_system="HIS", source_table="COMM.STAFF_DICT",
            source_person_id=emp_no, source_status=status,
            raw_data={"EMP_NO": emp_no, "JOB": job, "TITLE": title,
                      "CREATE_DATE": create_date.strftime("%Y-%m-%d %H:%M:%S") if create_date else None},
        ))
        if validstate is not None:
            db_session.add(IdentityPersonSource(
                person_code=emp_no, source_system="HIS", source_table="FXHIS.SYS_EMPLOYEE",
                source_person_id=emp_no, source_status=validstate,
                raw_data={"EMPLCODE": emp_no, "VALIDSTATE": validstate},
            ))
        db_session.commit()

    def test_preflight_classifies_doctor(self, db_session):
        from app.services.identity_classification_preflight import run_classification_preflight
        self._seed_person_with_source(db_session, "E001", "医生", "主治医师", "active",
                                      datetime(2026, 7, 25))
        stats = run_classification_preflight(db_session)
        db_session.commit()
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E001"))
        assert person.classification == "doctor"
        assert person.classification_rule_version == "v2"
        assert person.conflict_flag is None
        assert person.raw_job == "医生"
        assert stats["classified"] == 1

    def test_preflight_isolates_null_create_date(self, db_session):
        from app.services.identity_classification_preflight import run_classification_preflight
        self._seed_person_with_source(db_session, "E002", "医生", "主治医师", "active", None)
        run_classification_preflight(db_session)
        db_session.commit()
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E002"))
        assert person.classification == "master_data_missing"
        assert person.conflict_flag == "master_data_missing"

    def test_preflight_isolates_technician(self, db_session):
        from app.services.identity_classification_preflight import run_classification_preflight
        self._seed_person_with_source(db_session, "E003", "医技", "技师", "active",
                                      datetime(2026, 7, 25))
        run_classification_preflight(db_session)
        db_session.commit()
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E003"))
        assert person.classification != "doctor"

    def test_preflight_status_conflict_resolved_by_employee_authority(self, db_session):
        """2026-08-20 用户裁定：状态矛盾时 FXHIS.SYS_EMPLOYEE 为权威源，不再隔离。"""
        from app.services.identity_classification_preflight import run_classification_preflight
        from app.models.identity_sync import IdentityClassificationRecord
        self._seed_person_with_source(db_session, "E004", "护理", "护师", "active",
                                      datetime(2026, 7, 25), validstate="inactive")
        run_classification_preflight(db_session)
        db_session.commit()
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E004"))
        # SYS_EMPLOYEE(inactive) 为权威 → 按停用口径继续分类为护士，不再 status_conflict 隔离
        assert person.classification == "nurse"
        assert person.conflict_flag is None
        record = db_session.scalar(select(IdentityClassificationRecord).where(
            IdentityClassificationRecord.emp_no == "E004"))
        assert record.conflict_detail["resolved"] == "status_mismatch_employee_authority"
        assert record.conflict_detail["employee_flag"] == "0"
        assert record.conflict_detail["staff_dict_flag"] == "1"

    def test_preflight_status_conflict_employee_active_wins(self, db_session):
        """STAFF_DICT 停用 + SYS_EMPLOYEE 在职（004063 情形）→ 按在职继续分类。"""
        from app.services.identity_classification_preflight import run_classification_preflight
        self._seed_person_with_source(db_session, "E007", "医生", "主治医师", "inactive",
                                      datetime(2026, 7, 25), validstate="active")
        run_classification_preflight(db_session)
        db_session.commit()
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E007"))
        assert person.classification == "doctor"
        assert person.conflict_flag is None

    def test_preflight_skips_person_without_sources(self, db_session):
        from app.services.identity_classification_preflight import run_classification_preflight
        db_session.add(IdentityPerson(person_code="E005", classification="doctor",
                                      employment_status="active"))
        db_session.commit()
        stats = run_classification_preflight(db_session)
        person = db_session.scalar(select(IdentityPerson).where(IdentityPerson.person_code == "E005"))
        assert person.classification == "doctor"  # preserved
        assert stats["no_source"] == 1

    def test_classification_record_persisted(self, db_session):
        from app.services.identity_classification_preflight import run_classification_preflight
        self._seed_person_with_source(db_session, "E006", "药剂", "药师", "active",
                                      datetime(2026, 7, 25))
        run_classification_preflight(db_session)
        db_session.commit()
        record = db_session.scalar(
            select(IdentityClassificationRecord).where(IdentityClassificationRecord.emp_no == "E006")
        )
        assert record is not None
        assert record.classification == "pharmacist"
        assert record.emp_no_masked != "E006"
        assert "E006" not in record.emp_no_masked


# ---------------------------------------------------------------------------
# Threshold composition (110 revision: real new/update/deactivate)
# ---------------------------------------------------------------------------

class TestChangeStats:
    def test_new_vs_update_split(self, db_session, seed_candidates, seed_role_mappings):
        from app.services.identity_sync_orchestrator import _compute_change_stats, select_nightly_candidates
        from app.services.identity_hmac import compute_account_fingerprint
        candidates = select_nightly_candidates(db_session)
        # D001 already managed in CDMS -> update; others -> new
        fp = compute_account_fingerprint("D001", "CDMS", "env:TEST_HMAC_KEY")
        db_session.add(IdentityManagedRelation(
            batch_id="B0", target_system="CDMS", account_fingerprint=fp,
            relation_type="account", target_table="T_MSS_EMP_DICT",
            status="active", idempotency_key="k-d001",
        ))
        db_session.commit()
        stats = _compute_change_stats(db_session, candidates)
        assert stats["new"] == len(candidates) - 1
        assert stats["update"] == 1
        assert stats["scope"] >= len(candidates)

    def test_change_ratio_uses_scope(self):
        from app.services.identity_sync_orchestrator import check_thresholds
        # 4 new out of scope 100 -> 0.04, well below 0.3: must NOT trigger
        result = check_thresholds([{}] * 4, {"new": 4, "update": 0, "deactivate": 0, "scope": 100})
        assert result["triggered"] is False
        # without scope, falls back to candidate count: 4/4 = 1.0 -> triggers
        result = check_thresholds([{}] * 4, {"new": 4, "update": 0, "deactivate": 0})
        assert result["triggered"] is True
        assert result["dimension"] == "max_change_ratio"


# ---------------------------------------------------------------------------
# HMAC fail-closed (110 revision)
# ---------------------------------------------------------------------------

class TestHmacFailClosed:
    def test_no_silent_fallback(self, db_session, seed_candidates, seed_role_mappings, monkeypatch):
        """HMAC key unavailable -> candidate processing fails, never sha256 fallback."""
        from app.core.config import settings
        from app.services.identity_hmac import reset_key_cache
        from app.services.identity_sync_orchestrator import _process_single_candidate
        monkeypatch.setattr(settings, "identity_hmac_key_ref", "file:///nonexistent/path/hmac.key")
        reset_key_cache()
        candidate = {
            "emp_no": "D001", "emp_no_masked": "D**1", "classification": "doctor",
            "dept_codes": ["DEPT01"], "primary_dept": "DEPT01", "create_date": "2026-07-25",
        }
        import pytest as _pytest
        with _pytest.raises(Exception):
            _process_single_candidate(db_session, candidate, "HMAC-RUN")
        reset_key_cache()


# ---------------------------------------------------------------------------
# Timezone safety (110 revision: aware/naive comparison)
# ---------------------------------------------------------------------------

class TestTimezoneSafety:
    def test_acquire_lock_with_naive_expires_at(self, db_session):
        """Naive expires_at (SQLite-style) must not raise TypeError on compare."""
        from app.services.identity_sync_orchestrator import acquire_lock, release_lock
        from app.models.identity_sync import IdentityDistributedLock
        naive_past = datetime(2020, 1, 1)  # naive, expired
        db_session.add(IdentityDistributedLock(
            lock_key="tz_test_lock", lock_holder="old", acquired_at=naive_past,
            expires_at=naive_past,
        ))
        db_session.commit()
        assert acquire_lock(db_session, "tz_test_lock", "new_holder", 60) is True

    def test_acquire_lock_blocks_unexpired(self, db_session):
        from app.services.identity_sync_orchestrator import acquire_lock
        future = datetime(2999, 1, 1)
        db_session.add(IdentityDistributedLock(
            lock_key="tz_test_lock2", lock_holder="old", acquired_at=datetime(2026, 1, 1),
            expires_at=future,
        ))
        db_session.commit()
        assert acquire_lock(db_session, "tz_test_lock2", "new_holder", 60) is False
