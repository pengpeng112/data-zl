"""207 跨源一致性比对测试（sqlite 纯逻辑）：T09/T10/T11 + 执行器集成。

合成真值验收：同数量不同键、同分布个体错配、复合键/前导零/一对多/双向缺失、
零样本 NO_DATA。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityObservation,
    QualityRun,
)
from app.services import quality_cross_source as xsrc
from app.services import quality_execution_service as qes
from tests.plan207.test_execution_chain import NOW, make_control

NOW_REAL = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


# ── T09：数量对账 ≠ 逐键一致 ─────────────────────────────────────────────

def test_t09_same_counts_disjoint_keys_exposed():
    a = [{"K": f"A{i:03d}", "V": "1"} for i in range(50)]
    b = [{"K": f"B{i:03d}", "V": "1"} for i in range(50)]
    cmp = xsrc.compare_keyed_datasets(a, b, key_fields=["K"], compare_fields=["V"])
    verdict = xsrc.cross_source_verdict(cmp)
    assert verdict["status"] == "fail"
    m = verdict["metrics"]
    assert m["counts_equal"] is True  # 数量相同……
    assert m["bidirectional_missing"] == 100  # ……但键完全不同：逐键指标暴露
    assert cmp.matched_keys == 0


def test_t09_same_distribution_individual_mismatch():
    """分布相同（每码各 N 条）但个体错配：键级比对必须发现。"""
    a = [{"K": f"P{i:03d}", "CODE": "01" if i % 2 == 0 else "02"} for i in range(10)]
    # B 侧同样 5×01 + 5×02，但其中两个键的码互换
    b = [{"K": f"P{i:03d}", "CODE": ("02" if i in (0, 2) else ("01" if i % 2 == 0 else "02"))}
         for i in range(10)]
    cmp = xsrc.compare_keyed_datasets(a, b, key_fields=["K"], compare_fields=["CODE"])
    verdict = xsrc.cross_source_verdict(cmp)
    assert verdict["status"] == "fail"
    assert cmp.mismatched_keys == 2
    assert verdict["metrics"]["counts_equal"] is True  # 数量与分布都对——但个体错配


# ── T10：复合键 / 前导零 / 一对多 / 双向缺失 ────────────────────────────

def test_t10_composite_key_and_leading_zeros():
    a = [{"PID": "0123456", "VIS": "1", "V": "x"}, {"PID": "123456", "VIS": "1", "V": "x"}]
    b = [{"PID": "123456 ", "VIS": "1", "V": "x"}, {"PID": "0123456", "VIS": "1", "V": "x"}]
    cmp = xsrc.compare_keyed_datasets(a, b, key_fields=["PID", "VIS"], compare_fields=["V"])
    assert cmp.matched_keys == 2          # '0123456' ≠ '123456'：前导零保留不误匹配
    assert cmp.a_only == [] and cmp.b_only == []
    # 尾部空白被规范化（'123456 ' == '123456'）
    assert cmp.mismatched_keys == 0


def test_t10_one_to_many_duplicate_keys_not_hidden():
    a = [{"K": "X", "V": "1"}, {"K": "X", "V": "1"}]   # A 侧一对多
    b = [{"K": "X", "V": "1"}]
    cmp = xsrc.compare_keyed_datasets(a, b, key_fields=["K"], compare_fields=["V"])
    verdict = xsrc.cross_source_verdict(cmp)
    assert verdict["status"] == "fail"                 # 重复键本身即失败，不默默去重
    assert verdict["metrics"]["duplicate_keys"] == 1


def test_t10_bidirectional_missing_independent():
    a = [{"K": "1"}, {"K": "2"}, {"K": "3"}]
    b = [{"K": "2"}, {"K": "3"}, {"K": "4"}, {"K": "5"}]
    cmp = xsrc.compare_keyed_datasets(a, b, key_fields=["K"])
    assert cmp.a_only == [("1",)]        # A 缺 B（A 有 B 无）
    assert sorted(cmp.b_only) == [("4",), ("5",)]  # B 缺 A
    assert cmp.matched_keys == 2


def test_t10_code_mapping_semantics():
    """B 侧院内码映射后与 A 侧国标码一致 → 通过；未知映射单列不猜。"""
    a = [{"K": "1", "CODE": "1"}, {"K": "2", "CODE": "0"}]
    b = [{"K": "1", "CODE": "M"}, {"K": "2", "CODE": "F"}]
    mapping = {"M": "1"}  # F 无映射定义
    cmp = xsrc.compare_keyed_datasets(a, b, key_fields=["K"], compare_fields=["CODE"],
                                      code_mapping=mapping)
    assert cmp.mismatched_keys == 1        # K=2：F 无映射 → 错配
    assert cmp.unmapped_codes == ["F"]     # 未知映射单列，不猜语义


# ── T11：零样本 / 单侧空 ────────────────────────────────────────────────

def test_t11_both_empty_is_no_data():
    verdict = xsrc.cross_source_verdict(
        xsrc.compare_keyed_datasets([], [], key_fields=["K"]))
    assert verdict["status"] == "no_data"


def test_t11_single_side_empty_is_fail_with_detail():
    a = [{"K": "1"}]
    verdict = xsrc.cross_source_verdict(
        xsrc.compare_keyed_datasets(a, [], key_fields=["K"]))
    assert verdict["status"] == "fail"
    assert verdict["metrics"]["bidirectional_missing"] == 1


# ── 执行器集成：双源探查映射 → 六态观测 ─────────────────────────────────

def _make_probe_control(db, *, sides, compare, code="QC-207-XSRC"):
    control = QualityControl(
        control_code=code, version=1, title="跨源测试", lifecycle_status="active",
        category="R-XSYS", primary_system_code="HIS", source_code="his_src",
        metric_name="cross_missing_rate", metric_unit="%",
        verification_policy="manual", created_by="t", updated_by="t",
    )
    db.add(control)
    db.flush()
    det = QualityControlDetector(
        control_id=control.id, detector_kind="probe_template", detector_ref=f"PROBE-{code}",
        detector_version="1", status="active",
        result_mapping={"sides": sides, "compare": compare},
        created_by="t", updated_by="t",
    )
    db.add(det)
    db.commit()
    return control, det


def _patch_fetch(monkeypatch, side_a: dict, side_b: dict, status_a="success", status_b="success"):
    from app.services import quality_sql_runner

    def fake_fetch(sql, source_code, *, max_rows=1000, db=None):
        if source_code == "src-a":
            return {"status": status_a, "rows": side_a if status_a == "success" else [],
                    "note": "boom" if status_a != "success" else None}
        return {"status": status_b, "rows": side_b if status_b == "success" else [],
                "note": "boom" if status_b != "success" else None}

    monkeypatch.setattr(quality_sql_runner, "fetch_readonly_rows", fake_fetch)


def test_executor_cross_source_fail_builds_observation(db, monkeypatch):
    sides = [
        {"source_code": "src-a", "sql": "SELECT K, CODE FROM A"},
        {"source_code": "src-b", "sql": "SELECT K, CODE FROM B"},
    ]
    compare = {"key_fields": ["K"], "compare_fields": ["CODE"],
               "missing_threshold_pct": 0, "mismatch_threshold_pct": 0}
    control, det = _make_probe_control(db, sides=sides, compare=compare)
    _patch_fetch(monkeypatch,
                 [{"K": "1", "CODE": "1"}, {"K": "2", "CODE": "1"}],
                 [{"K": "1", "CODE": "1"}, {"K": "3", "CODE": "1"}])
    result = qes.create_run(db, control, requested_by="u", now=NOW_REAL)
    db.commit()
    claimed = qes.claim_next_run(db, "w1", now=NOW_REAL)
    assert claimed is not None
    out = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW_REAL)
    db.commit()
    assert out["status"] == "fail"
    obs = db.scalar(select(QualityObservation).where(QualityObservation.control_id == control.id))
    assert obs.result_status == "fail"
    assert obs.numerator == 2 and obs.denominator == 2  # 双向缺失 2 / 键并集最大 2
    # 观测不携带患者明细：evidence 只有摘要
    assert obs.evidence_digest


def test_executor_cross_source_pass_and_no_data(db, monkeypatch):
    sides = [
        {"source_code": "src-a", "sql": "SELECT K FROM A"},
        {"source_code": "src-b", "sql": "SELECT K FROM B"},
    ]
    compare = {"key_fields": ["K"]}
    control, det = _make_probe_control(db, sides=sides, compare=compare, code="QC-207-XSRC2")
    _patch_fetch(monkeypatch, [{"K": "1"}, {"K": "2"}], [{"K": "1"}, {"K": "2"}])
    result = qes.create_run(db, control, requested_by="u", now=NOW_REAL)
    db.commit()
    claimed = qes.claim_next_run(db, "w1", now=NOW_REAL)
    out = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW_REAL)
    db.commit()
    assert out["status"] == "pass"

    # 零样本 → NO_DATA（不作通过证据）
    control2, det2 = _make_probe_control(db, sides=sides, compare=compare, code="QC-207-XSRC3")
    _patch_fetch(monkeypatch, [], [])
    result2 = qes.create_run(db, control2, requested_by="u", now=NOW_REAL)
    db.commit()
    claimed2 = qes.claim_next_run(db, "w1", now=NOW_REAL)
    out2 = qes.execute_claimed_run(db, claimed2, worker_id="w1", now=NOW_REAL)
    db.commit()
    assert out2["status"] == "no_data"


def test_executor_cross_source_connection_error_is_error_not_pass(db, monkeypatch):
    """单侧不可达：ERROR（不是 PASS/BLOCKED 混淆），连接类有限退避后失败。"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "quality_execution_max_attempts", 1, raising=False)
    sides = [
        {"source_code": "src-a", "sql": "SELECT K FROM A"},
        {"source_code": "src-b", "sql": "SELECT K FROM B"},
    ]
    control, det = _make_probe_control(
        db, sides=sides, compare={"key_fields": ["K"]}, code="QC-207-XSRC4")
    _patch_fetch(monkeypatch, [{"K": "1"}], [], status_b="failed")
    result = qes.create_run(db, control, requested_by="u", now=NOW_REAL)
    db.commit()
    claimed = qes.claim_next_run(db, "w1", now=NOW_REAL)
    out = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW_REAL)
    db.commit()
    assert out["status"] == "error"  # CONNECTION 类错误：运行 error，绝不 PASS
    child = db.get(QualityRun, claimed.id)
    assert child.error_code == "CONNECTION"
