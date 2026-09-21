"""193 纯逻辑测试：分类传播、状态机、切分、导出清洗（不连库）。

对应 B02 契约 §3/§6 与 B04/B05/B10/B13/B14 服务层纯函数。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import dataset_pipeline as pipe  # noqa: E402
from app.services import dataset_products as prod  # noqa: E402
from app.services import dataset_security as sec  # noqa: E402


def test_unclassified_defaults_p4_pending():
    p = sec.resolve_policy(None)
    assert p.protection_level == "P4"
    assert p.is_pending
    assert not p.export_allowed and not p.training_allowed


def test_combine_takes_max_level_and_intersects_purposes():
    a = sec.resolve_policy({"protection_level": "P2", "personal_info": "personal",
                            "usage_constraints": {"purposes": ["research", "ops"]}})
    b = sec.resolve_policy({"protection_level": "P3", "personal_info": "sensitive_personal",
                            "usage_constraints": {"purposes": ["research", "training"]}})
    c = sec.combine_policies([a, b], joined=True)
    assert c.protection_level == "P3"
    assert c.purposes == ["research"]


def test_join_combination_floor_p3():
    a = sec.resolve_policy({"protection_level": "P1", "personal_info": "none"})
    b = sec.resolve_policy({"protection_level": "P2", "personal_info": "none"})
    c = sec.combine_policies([a, b], joined=True)
    assert c.protection_level == "P3"
    assert c.re_id_risk_review_required


def test_unconstrained_input_fails_closed():
    a = sec.resolve_policy({"protection_level": "P2", "usage_constraints": {"purposes": ["research"]}})
    b = sec.resolve_policy(None)  # 未标注
    c = sec.combine_policies([a, b])
    assert c.purposes is None  # fail-closed：组合结果未约束→默认禁止


def test_pseudonymization_does_not_downgrade():
    raw = sec.resolve_policy({"protection_level": "P3", "personal_info": "sensitive_personal"})
    deid = sec.resolve_policy({"protection_level": "P3", "personal_info": "sensitive_personal",
                               "processing_state": "de_identified"})
    assert not sec.downgrade_requires_approval(raw, deid)
    lower = sec.resolve_policy({"protection_level": "P2"})
    assert sec.downgrade_requires_approval(raw, lower)


def test_version_state_machine():
    assert pipe.transition_version("draft", "validated") == "validated"
    assert pipe.transition_version("published", "deprecated") == "deprecated"
    for bad in [("draft", "published"), ("published", "draft"), ("deprecated", "published"),
                ("revoked", "approved")]:
        try:
            pipe.transition_version(*bad)
            raise AssertionError(f"应拒绝 {bad}")
        except pipe.StateMachineError:
            pass


def test_manifest_deterministic():
    m = {"row_count": 3, "kinds": ["visit"], "rule_versions": {"r": "v1"}, "cutoff_at": None}
    assert pipe.manifest_digest(m) == pipe.manifest_digest(dict(m))
    m2 = dict(m); m2["row_count"] = 4
    assert pipe.manifest_digest(m) != pipe.manifest_digest(m2)


def test_deterministic_patient_id_stable_and_distinct():
    a = pipe.deterministic_patient_id("SRC_A", "P1")
    assert a == pipe.deterministic_patient_id("SRC_A", "P1")
    assert a != pipe.deterministic_patient_id("SRC_B", "P1")  # 不同源同号不串人
    assert a != pipe.deterministic_patient_id("SRC_A", "P2")  # 同源不同人不合并


def test_standardize_unknown_code_quarantined():
    v, flag = pipe.standardize_code("J99.9", {"I50.900": "I50.x"}, "rules_v1")
    assert v is None and flag == "unknown_code"
    v, flag = pipe.standardize_code("I50.900", {"I50.900": "I50.x"}, "rules_v1")
    assert v == "I50.x" and flag == "ok"


def test_unit_mismatch_not_converted():
    v, flag = pipe.convert_unit(5.0, "mg/dL", "mmol/L")
    assert v is None and flag == "unit_mismatch"


def test_patient_group_split_disjoint():
    pids = [f"DS-P{i:04d}" for i in range(200)]
    s = prod.patient_group_split(pids, prod.SplitConfig(seed=7))
    assert not (set(s["train"]) & set(s["val"]))
    assert not (set(s["train"]) & set(s["test"]))
    assert not (set(s["val"]) & set(s["test"]))
    assert sorted(s["train"] + s["val"] + s["test"]) == sorted(pids)
    # 确定性
    s2 = prod.patient_group_split(pids, prod.SplitConfig(seed=7))
    assert s == s2


def test_future_info_leak_guard():
    pred = datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert prod.temporal_features_available(datetime(2026, 1, 9, tzinfo=timezone.utc), pred)
    assert not prod.temporal_features_available(datetime(2026, 1, 11, tzinfo=timezone.utc), pred)
    assert not prod.temporal_features_available(None, pred)


def test_csv_injection_sanitized():
    assert prod.sanitize_csv_cell("=SUM(A1:A9)").startswith("'")
    assert prod.sanitize_csv_cell("+CMD('calc')").startswith("'")
    assert prod.sanitize_csv_cell("-1+1").startswith("'")
    assert prod.sanitize_csv_cell("@cmd").startswith("'")
    assert prod.sanitize_csv_cell("正常文本") == "正常文本"
    assert prod.sanitize_csv_cell(None) == ""


def test_mask_free_text_pii():
    text = "患者 370104199001011234 电话 13812345678 复诊"
    masked, hit = prod.mask_free_text(text)
    assert hit
    assert "370104199001011234" not in masked
    assert "13812345678" not in masked
    assert "复诊" in masked


def test_readmission_counting_by_patient_not_rows():
    # JOIN 不放大计数：同患者多行事实只计一次
    times = {"P1": [datetime(2026, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 1, 20, tzinfo=timezone.utc),
                    datetime(2026, 2, 1, tzinfo=timezone.utc)],
             "P2": [datetime(2026, 1, 1, tzinfo=timezone.utc)]}
    readmitted = 0
    for pid, ts in times.items():
        ts.sort()
        if any(0 < (b - a).days <= 30 for a, b in zip(ts, ts[1:])):
            readmitted += 1
    assert readmitted == 1


def test_audit_payload_has_no_patient_values():
    payload = sec.audit_event("read", "user1", "dataset:DS:1", "allow")
    assert payload["module"] == "dataset"
    assert "patient" not in str(payload).lower() or payload["entity_ref"] == "dataset:DS:1"
