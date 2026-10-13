"""208 A3（207 T08 补全）：confirmed 值域通用执行器合成真值验收。

对应 207 验收矩阵 T08 + 208 A包第3条：
- confirmed 才能权威判错；pending/deprecated/conflicted/未登记 → blocked（待确认/受阻）；
- 绑定 confirmed 版本（指纹）+ 生效时间 + 物理源；观测冻结 value_domain 快照；
- 值域版本切换 → 旧 PASS 复测证据失效（evaluate_trusted_recheck 指纹比对）；
- 空集语义：数据侧零行 NO_DATA；码值映射（known 分布 + 未知码单列）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.asset_system import AssetDataSource
from app.models.quality_governance import (
    QualityControl,
    QualityControlDetector,
    QualityObservation,
    QualityRun,
)
from app.models.value_domain import AssetColumnValueDomain
from app.services import quality_execution_service as qes
from app.services.quality_value_domain import (
    build_distribution_sql,
    compare_distribution,
    parse_binding,
)

NOW = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)

BINDING = {
    "system_code": "HIS", "source_code": "his_src",
    "schema_name": "ODS", "table_name": "PAT_VISIT", "column_name": "DISCHARGE_DISPOSITION",
}


def seed_source(db):
    db.add(AssetDataSource(system_code="HIS", source_code="his_src",
                           source_name_cn="HIS源", db_type="oracle"))
    db.flush()


def seed_domain_row(db, code, *, status="confirmed", conflict="none", kind="enum",
                    meaning=None, confirmed=True):
    db.add(AssetColumnValueDomain(
        system_code=BINDING["system_code"], source_code=BINDING["source_code"],
        schema_name=BINDING["schema_name"], table_name=BINDING["table_name"],
        column_name=BINDING["column_name"], code=code,
        meaning=meaning or f"码值{code}", domain_kind=kind,
        status=status, conflict_status=conflict,
        confirmed_by="t" if confirmed and status == "confirmed" else None,
        confirmed_at=NOW if confirmed and status == "confirmed" else None,
    ))
    db.flush()


def make_vd_control(db, *, code="QC-VD-001", mapping_extra=None):
    control = QualityControl(
        control_code=code, version=1, title=f"值域清单 {code}",
        lifecycle_status="active", dimension="validity", category="R-VAL",
        primary_system_code="HIS", source_code="his_src",
        object_key="HIS|ods|PAT_VISIT|DISCHARGE_DISPOSITION",
        metric_name="unknown_code_rate", metric_unit="%",
        comparator="gt", threshold_value=0, no_data_policy="blocked",
        verification_policy="auto_recheck_manual_close", required_pass_count=1,
        schedule_enabled="false", created_by="t", updated_by="t",
    )
    db.add(control)
    db.flush()
    mapping = dict(BINDING)
    mapping.update(mapping_extra or {})
    det = QualityControlDetector(
        control_id=control.id, detector_kind="value_domain", detector_ref=f"VD-{code}",
        detector_version="1", status="active", result_mapping=mapping,
        created_by="t", updated_by="t",
    )
    db.add(det)
    db.commit()
    return control, det


def fake_fetch(monkeypatch, rows, *, status="success", truncated=False):
    from app.services import quality_sql_runner as runner

    def _fetch(sql, source_code, *, max_rows=1000, db=None):
        return {"status": status, "rows": rows, "truncated": truncated,
                "errors": ["bad sql"], "note": "connection timeout"}

    monkeypatch.setattr(runner, "fetch_readonly_rows", _fetch)


def run_vd_once(db, monkeypatch, rows, *, purpose="check", issue_id=None, truncated=False):
    control, det = make_vd_control(db)
    fake_fetch(monkeypatch, rows, truncated=truncated)
    result = qes.create_run(db, control, purpose=purpose,
                            trigger_kind="recheck" if purpose == "recheck" else "manual",
                            requested_by="u-admin", issue_id=issue_id, now=NOW, actor="u-admin")
    db.commit()
    parent = result["run"]
    child = db.scalar(select(QualityRun).where(
        QualityRun.parent_run_id == parent.id, QualityRun.detector_id.isnot(None)))
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    assert claimed is not None and claimed.id == child.id
    exec_result = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    return control, det, parent, child, exec_result


# ── 纯逻辑：绑定与 SQL 构造 ─────────────────────────────────────────────

def test_binding_requires_identity_and_safe_identifiers():
    full = parse_binding(BINDING)
    assert full["column_name"] == "DISCHARGE_DISPOSITION"
    with pytest.raises(ValueError):
        parse_binding({"source_code": "his_src"})  # 缺字段
    with pytest.raises(ValueError):
        parse_binding({**BINDING, "table_name": "PAT_VISIT; DROP TABLE x"})
    sql = build_distribution_sql(BINDING)
    assert sql == ("SELECT DISCHARGE_DISPOSITION AS CODE, COUNT(*) AS CNT "
                   "FROM ODS.PAT_VISIT GROUP BY DISCHARGE_DISPOSITION")


# ── 纯逻辑：分布比对（码值映射 + 空集语义） ────────────────────────────

CODES = [
    {"code": "1", "meaning": "医嘱离院", "current_version_id": 3, "confirmed_at": "2026-09-01T00:00:00+08:00"},
    {"code": "4", "meaning": "非医嘱离院", "current_version_id": 3, "confirmed_at": "2026-09-01T00:00:00+08:00"},
    {"code": "5", "meaning": "死亡", "current_version_id": 3, "confirmed_at": "2026-09-01T00:00:00+08:00"},
]


def test_distribution_known_codes_pass_with_mapping_evidence():
    rows = [{"CODE": "1", "CNT": 60}, {"CODE": "4", "CNT": 30}, {"CODE": "5", "CNT": 10}]
    out = compare_distribution(rows, CODES)
    assert out.status == "pass" and out.total == 100 and out.illegal == 0
    assert {d["code"] for d in out.known_distribution} == {"1", "4", "5"}
    assert all(d["meaning"] for d in out.known_distribution)  # 码值映射带含义


def test_distribution_unknown_code_fails_and_single_lists():
    rows = [{"CODE": "1", "CNT": 90}, {"CODE": "9", "CNT": 8}, {"CODE": None, "CNT": 2}]
    out = compare_distribution(rows, CODES)
    assert out.status == "fail" and out.total == 100
    assert out.illegal == 8 and out.null_count == 2  # NULL 默认不计非法
    assert out.unknown_codes == [{"code": "9", "count": 8}]


def test_distribution_null_is_error_option():
    rows = [{"CODE": "1", "CNT": 8}, {"CODE": None, "CNT": 2}]
    out = compare_distribution(rows, CODES, null_is_error=True)
    assert out.status == "fail" and out.illegal == 2 and out.null_count == 2


def test_distribution_numeric_code_normalization():
    rows = [{"CODE": 1, "CNT": 50}, {"CODE": 4.0, "CNT": 50}]  # 数值型列码值
    out = compare_distribution(rows, CODES)
    assert out.status == "pass" and out.total == 100


def test_distribution_empty_rows_is_no_data_not_all_illegal():
    out = compare_distribution([], CODES)
    assert out.status == "no_data" and out.error_code == "EMPTY_SCOPE"


def test_fingerprint_changes_only_when_codes_change():
    from app.services.quality_value_domain import DomainVerdict, load_domain_verdict  # noqa: F401

    v1 = DomainVerdict("ok", codes=CODES)
    v2 = DomainVerdict("ok", codes=list(CODES))
    v3 = DomainVerdict("ok", codes=CODES + [
        {"code": "9", "meaning": "新码", "current_version_id": 4, "confirmed_at": "2026-09-20T00:00:00+08:00"}])
    assert v1.fingerprint() == v2.fingerprint()
    assert v1.fingerprint() != v3.fingerprint()
    assert v1.effective_window()["confirmed_at_max"].startswith("2026-09-01")


# ── 登记状态分层（平台库，sqlite 内存） ─────────────────────────────────

def test_load_verdict_layering(db):
    from app.services.quality_value_domain import load_domain_verdict

    seed_source(db)
    v = load_domain_verdict(db, BINDING)
    assert v.status == "not_registered" and not v.authoritative
    seed_domain_row(db, "9", status="pending", confirmed=False)
    v = load_domain_verdict(db, BINDING)
    assert v.status == "pending_only" and "pending" in v.message
    seed_domain_row(db, "1")
    v = load_domain_verdict(db, BINDING)
    assert v.authoritative and v.pending_count == 1
    seed_domain_row(db, "4", conflict="conflicted")
    v = load_domain_verdict(db, BINDING)
    assert v.authoritative and "4" not in {c["code"] for c in v.codes}


def test_load_verdict_deprecated_only_and_no_enum(db):
    from app.services.quality_value_domain import load_domain_verdict

    seed_source(db)
    seed_domain_row(db, "1", status="deprecated", confirmed=False)
    v = load_domain_verdict(db, BINDING)
    assert v.status == "deprecated_only" and "失效" in v.message
    db.query(AssetColumnValueDomain).delete()
    seed_domain_row(db, "0-100", kind="threshold")
    v = load_domain_verdict(db, BINDING)
    assert v.status == "no_enum_codes" and "enum" in v.message


# ── 执行链（pending 不判非法 / confirmed 判错 / 空集 / 截断） ───────────

def test_t08_pending_domain_blocks_never_fails(db, monkeypatch):
    seed_source(db)
    seed_domain_row(db, "9", status="pending", confirmed=False)
    control, det = make_vd_control(db)
    fake_fetch(monkeypatch, [{"CODE": "9", "CNT": 5}])
    result = qes.create_run(db, control, purpose="check", trigger_kind="manual",
                            requested_by="u-admin", now=NOW, actor="u-admin")
    db.commit()
    # 预检即受阻：落 blocked 父运行单留证（不虚报排队，不产生 FAIL；无子单）
    assert result["status"] == "blocked"
    parent = result["run"]
    assert parent.error_code == "PREFLIGHT_BLOCKED"
    assert "不权威判非法" in (parent.error_message_sanitized or "")
    child = db.scalar(select(QualityRun).where(QualityRun.parent_run_id == parent.id))
    assert child is None
    # 无 FAIL 观测 → 不建问题单
    from app.models.quality_governance import QualityIssue
    assert db.scalar(select(QualityIssue).where(QualityIssue.control_id == control.id)) is None


def test_t08_confirmed_unknown_code_fails_with_frozen_snapshot(db, monkeypatch):
    seed_source(db)
    for c in ("1", "4", "5"):
        seed_domain_row(db, c)
    rows = [{"CODE": "1", "CNT": 90}, {"CODE": "9", "CNT": 8}, {"CODE": None, "CNT": 2}]
    control, det, parent, child, exec_result = run_vd_once(db, monkeypatch, rows)
    assert exec_result["status"] == "fail"  # 数据态；运行单本身 succeeded
    assert child.status == "succeeded"
    obs = db.scalar(select(QualityObservation).where(QualityObservation.run_key == f"qr:{child.id}:1"))
    assert obs.result_status == "fail"
    assert float(obs.numerator) == 8 and float(obs.denominator) == 100
    snap = obs.threshold_snapshot["value_domain"]
    assert snap["code_count"] == 3 and snap["fingerprint"]
    assert snap["unknown_codes"] == [{"code": "9", "count": 8}]
    assert snap["binding"]["column_name"] == "DISCHARGE_DISPOSITION"
    assert snap["effective"]["confirmed_at_max"]


def test_t08_confirmed_all_known_passes_and_empty_is_no_data(db, monkeypatch):
    seed_source(db)
    for c in ("1", "4", "5"):
        seed_domain_row(db, c)
    control, det, parent, child, exec_result = run_vd_once(
        db, monkeypatch, [{"CODE": "1", "CNT": 100}])
    assert exec_result["status"] == "pass"
    obs = db.scalar(select(QualityObservation).where(QualityObservation.run_key == f"qr:{child.id}:1"))
    assert obs.result_status == "pass"
    # 空集语义：同一 control 再跑一轮空分布 → NO_DATA（不得全非法/关单）
    fake_fetch(monkeypatch, [])  # 第二轮分布为空
    result = qes.create_run(db, control, purpose="check", trigger_kind="manual",
                            requested_by="u-admin", now=NOW, actor="u-admin")
    db.commit()
    child3 = db.scalar(select(QualityRun).where(
        QualityRun.parent_run_id == result["run"].id, QualityRun.detector_id.isnot(None)))
    claimed = qes.claim_next_run(db, "w1", now=NOW + timedelta(minutes=5))
    assert claimed is not None and claimed.id == child3.id
    exec3 = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    assert exec3["status"] == "no_data"
    obs3 = db.scalar(select(QualityObservation).where(
        QualityObservation.run_key == f"qr:{child3.id}:1"))
    assert obs3.result_status == "no_data" and obs3.error_code == "EMPTY_SCOPE"


def test_t08_cardinality_overflow_blocks_instead_of_wrong_stats(db, monkeypatch):
    seed_source(db)
    for c in ("1", "4", "5"):
        seed_domain_row(db, c)
    rows = [{"CODE": str(i), "CNT": 1} for i in range(600)]
    control, det, parent, child, exec_result = run_vd_once(db, monkeypatch, rows, truncated=True)
    assert exec_result["status"] == "blocked"
    obs = db.scalar(select(QualityObservation).where(QualityObservation.run_key == f"qr:{child.id}:1"))
    assert obs.error_code == "VD_CARDINALITY"


def test_t08_preflight_reports_pending_warning_and_source_binding(db):
    seed_source(db)
    for c in ("1", "4", "5"):
        seed_domain_row(db, c)
    seed_domain_row(db, "9", status="pending", confirmed=False)
    control, det = make_vd_control(db)
    report = qes.preflight_control(db, control, now=NOW)
    assert report.executable
    info = next(d for d in report.detectors if d["detector_kind"] == "value_domain")
    assert info["executable"] and info["source_code"] == "his_src"
    assert info["value_domain"]["code_count"] == 3
    assert any("pending" in w for w in info.get("warnings", []))


def test_t08_preflight_blocks_when_source_unregistered(db):
    for c in ("1", "4", "5"):
        seed_domain_row(db, c)  # 不 seed_source
    control, det = make_vd_control(db)
    report = qes.preflight_control(db, control, now=NOW)
    info = next(d for d in report.detectors if d["detector_kind"] == "value_domain")
    assert not info["executable"] and "数据源未登记" in info["blocked_reason"]


def test_t08_version_switch_invalidates_old_pass_recheck(db, monkeypatch):
    """PASS 复测后值域版本变化（新增 confirmed 码）→ 旧 PASS 不能关闭问题。"""
    from app.models.quality_governance import QualityIssue
    from app.services.quality_governance_service import apply_observation

    seed_source(db)
    for c in ("1", "4", "5"):
        seed_domain_row(db, c)
    control, det = make_vd_control(db)
    # 造一个待关闭问题（整改已提交，复测 PASS 在其后）
    fake_fetch(monkeypatch, [{"CODE": "1", "CNT": 100}])
    issue = QualityIssue(
        issue_code="QI-VD-001", control_id=control.id, opened_control_version=1,
        scope_key=control.object_key, issue_type="data_defect", severity="medium",
        title="未知码值", status="in_progress", recheck_substatus="passed",
        recheck_pass_streak=1, remediation_submitted_at=NOW, created_by="t", updated_by="t",
    )
    db.add(issue)
    db.flush()
    result = qes.create_run(db, control, purpose="recheck", trigger_kind="recheck",
                            requested_by="u-admin", issue_id=issue.id, now=NOW, actor="u-admin")
    db.commit()
    child = db.scalar(select(QualityRun).where(
        QualityRun.parent_run_id == result["run"].id, QualityRun.detector_id.isnot(None)))
    claimed = qes.claim_next_run(db, "w1", now=NOW)
    assert claimed is not None and claimed.id == child.id
    exec_result = qes.execute_claimed_run(db, claimed, worker_id="w1", now=NOW)
    db.commit()
    assert exec_result["status"] == "pass"
    issue.scope_key = child.scope_key  # 与复测运行同口径
    issue.last_verification_run_id = result["run"].id
    db.commit()
    ok, errors, _ = qes.evaluate_trusted_recheck(db, issue, now=NOW)
    assert ok, errors  # 指纹一致 → 可信
    # 值域版本切换：新增 confirmed 码（指纹变化）
    seed_domain_row(db, "9", meaning="新增码")
    db.commit()
    ok2, errors2, _ = qes.evaluate_trusted_recheck(db, issue, now=NOW)
    assert not ok2 and any("值域版本已变化" in e for e in errors2)
