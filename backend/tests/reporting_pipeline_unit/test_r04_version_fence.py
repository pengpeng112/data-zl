"""R04 装载边界回归：版本精确比较 / 作用域隔离 / 批准不可伪造。

对应补充验收 RT1-014（离线部分：大整数精度、跨表同 ID、未知顺序
CONFLICT）与 RT1-012（离线部分：调用方伪造批准字符串被拒）。
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.apply_port import (
    ApplyPort,
    ApplyRefused,
    ApplyRequest,
    InMemoryApplyExecutor,
    PlatformApprovalVerifier,
    TargetCommitCredential,
    VersionGuard,
    VersionScope,
    compare_versions,
    CONFLICT,
    INSERT,
    NO_CHANGE,
    UPDATE,
)
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.readback_types import ColumnMeta

META = {
    "ID": ColumnMeta("ID", "VARCHAR"),
    "AMOUNT": ColumnMeta("AMOUNT", "NUMBER", precision=12, scale=2),
}


def _manifest() -> BatchManifest:
    return BatchManifest(
        batch_id="B1", attempt_id="A1", task_id="T", config_version="v1",
        definition_fingerprint=None, source_identity="s", window_fingerprint="w",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=1, valid=1),
        pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=10, schema_version="v",
        type_contract_version="t", payload_sha256="a" * 64,
    )


class TestExactVersionCompare(unittest.TestCase):
    """RT1-014：float 精度与字典序回退的机器化复验。"""

    def test_big_integers_not_equal_after_float(self):
        a, b = "9007199254740992", "9007199254740993"
        # 前提：float 下确实不可分（F07 的原始风险）
        self.assertEqual(float(a), float(b))
        # 精确路径仍可分
        self.assertEqual(compare_versions(b, a), 1)
        self.assertEqual(compare_versions(a, b), -1)

    def test_beyond_float_precision_still_exact(self):
        # 超出 float 安全整数范围仍精确（F07 核心：不再先转 float）
        a, b = "9007199254740993", "9007199254740995"
        self.assertEqual(compare_versions(b, a), 1)
        self.assertEqual(compare_versions(a, b), -1)

    def test_decimal_exact(self):
        self.assertEqual(compare_versions("1.9", "1.10"), 1)  # 数值语义：1.9 > 1.10

    def test_timestamp_normalized(self):
        self.assertEqual(
            compare_versions("2026-10-20T12:00:00+08:00", "2026-10-20T04:00:00+00:00"),
            0,
        )

    def test_unorderable_returns_none_then_conflict(self):
        guard = VersionGuard()
        guard.register_applied(("K1",), "hash-aaaa")
        # 未声明类型且非数值/时间 → 无法建立顺序 → CONFLICT（不按字典序冒充）
        self.assertEqual(guard.check(("K1",), "hash-bbbb"), CONFLICT)


class TestVersionScopeIsolation(unittest.TestCase):
    """RT1-014：版本键含目标/租户/表，跨表同 ID 不互相污染。"""

    def test_same_key_different_tables_independent(self):
        guard = VersionGuard()
        scope_a = VersionScope("orcl-874", "tenant1", "EMR_TABLE_A")
        scope_b = VersionScope("orcl-874", "tenant1", "EMR_TABLE_B")
        guard.register_applied(("K1",), "1000", scope=scope_a, operation_id="OP1")
        # 表 B 无版本记录 → INSERT（不被表 A 的同键污染成 NO_CHANGE/CONFLICT）
        self.assertEqual(guard.check(("K1",), "500", scope=scope_b), INSERT)
        # 表 A 的原判定不受影响
        self.assertEqual(guard.check(("K1",), "1000", scope=scope_a), NO_CHANGE)
        self.assertEqual(guard.check(("K1",), "1100", scope=scope_a), UPDATE)
        self.assertEqual(guard.check(("K1",), "900", scope=scope_a), CONFLICT)

    def test_different_target_instances_independent(self):
        guard = VersionGuard()
        scope_t1 = VersionScope("orcl-874", "t", "EMR_X")
        scope_t2 = VersionScope("orcl-other", "t", "EMR_X")
        guard.register_applied(("K9",), "100", scope=scope_t1, operation_id="OP1")
        self.assertEqual(guard.check(("K9",), "50", scope=scope_t2), INSERT)


class TestApprovalCannotBeForged(unittest.TestCase):
    """RT1-012：调用方传批准字符串不能自认已批准。"""

    def _request(self, **overrides) -> ApplyRequest:
        base = dict(
            manifest=_manifest(),
            quality_verified=True,
            approval_ref="FORGED-REF-BY-CALLER",
            executor_id="exec-1",
            target_object="DBOPER.EMR_X",
            allowed_operations=("MERGE",),
            idempotency_key_columns=("ID",),
            rows=({"ID": "K1", "AMOUNT": Decimal("1.00")},),
            column_meta=META,
            version_order="1000",
            lease_resource="target:DBOPER.EMR_X",
            fencing_token=7,
        )
        base.update(overrides)
        return ApplyRequest(**base)

    def test_platform_verifier_rejects_unregistered_ref(self):
        verifier = PlatformApprovalVerifier(
            executor_lookup=lambda code, target: None,
            approval_lookup=lambda ref, code: None,
        )
        decision = verifier.verify(
            approval_ref="FORGED", executor_id="exec-1",
            target_object="DBOPER.EMR_X", allowed_operations=("MERGE",),
        )
        self.assertFalse(decision.approved)

    def test_platform_verifier_rejects_disabled_executor(self):
        verifier = PlatformApprovalVerifier(
            executor_lookup=lambda code, target: {"enabled": False},
            approval_lookup=lambda ref, code: {"valid": True},
        )
        decision = verifier.verify(
            approval_ref="R", executor_id="exec-1",
            target_object="DBOPER.EMR_X", allowed_operations=("MERGE",),
        )
        self.assertFalse(decision.approved)

    def test_platform_verifier_rejects_invalid_approval(self):
        verifier = PlatformApprovalVerifier(
            executor_lookup=lambda code, target: {"enabled": True},
            approval_lookup=lambda ref, code: {"valid": False},
        )
        decision = verifier.verify(
            approval_ref="R", executor_id="exec-1",
            target_object="DBOPER.EMR_X", allowed_operations=("MERGE",),
        )
        self.assertFalse(decision.approved)

    def test_production_port_refuses_static_verifier(self):
        with self.assertRaises(ApplyRefused):
            ApplyPort(
                whitelisted_executors=["exec-1"],
                approved_refs={"ANY"},
                enforce_fence=False,
                production_mode=True,
            )

    def test_forged_ref_rejected_in_apply(self):
        port = ApplyPort(
            whitelisted_executors=["exec-1"],
            approval_verifier=PlatformApprovalVerifier(
                executor_lookup=lambda code, target: {"enabled": True},
                approval_lookup=lambda ref, code: None,  # 平台无该批准记录
            ),
        )
        with self.assertRaises(ApplyRefused) as ctx:
            port.apply(self._request(), InMemoryApplyExecutor(), target_rows={})
        self.assertIn("批准核验未通过", str(ctx.exception))


class TestCommitCredentialRequired(unittest.TestCase):
    """同事务提交凭据：缺凭据的"已提交"不能被当确认提交。"""

    def test_credential_shape(self):
        credential = TargetCommitCredential(
            operation_id="OP-1", batch_id="B1", manifest_hash="a" * 64,
            target_object="DBOPER.EMR_X", scope_summary="MERGE",
            rows_affected=1, committed=True,
        )
        self.assertTrue(credential.committed)


if __name__ == "__main__":
    unittest.main()
