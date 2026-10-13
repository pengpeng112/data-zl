"""210 S3/S9：数据集安全策略纯逻辑测试（无数据库）。

覆盖 T04（非法枚举/结构拒绝）、T05（未分类默认拒绝）、T06（放宽需审批）、
T08（组合继承保守序）、T12（授权时间边界）、T13（多授权确定性解析+墓碑）、
T16（导出/训练标志全等级生效、P4 独立权限、行范围门、列投影）。

运行目录 plan193/（哨兵 URL，不连库）；与 193 既有 16 项互补，不重复覆盖。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.dataset import AssetDsClassification, AssetDsGrant
from app.services import dataset_security as sec

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeDb:
    """scalars 按 SQL 文本中的表名路由到内存行；永不执行 SQL。

    对授权行按查询契约排序（valid_from 最新、id 最大优先），与真实 ORDER BY 一致。
    """

    def __init__(self, classifications=None, grants=None):
        self._cls = classifications or []
        self._grants = grants or []

    def scalars(self, stmt):
        txt = str(stmt)
        if "asset_ds_classifications" in txt:
            return FakeScalars(self._cls)
        if "asset_ds_grants" in txt:
            floor = datetime.min.replace(tzinfo=timezone.utc)
            rows = sorted(self._grants,
                          key=lambda g: (g.valid_from or floor, g.id),
                          reverse=True)
            return FakeScalars(rows)
        return FakeScalars([])


def _cls(labels: dict, ref: str = "dataset:SYNTH:1", version: int = 1) -> AssetDsClassification:
    return AssetDsClassification(object_type="dataset_version", object_ref=ref,
                                 labels=labels, status="active", version=version)


def _grant(status: str = "active", ref: str = "dataset:SYNTH:1", ops=None,
           valid_from=None, valid_until=None, gid: int = 1,
           row_scope=None, column_scope=None) -> AssetDsGrant:
    return AssetDsGrant(
        id=gid, principal="u1", purpose_code="research", resource_ref=ref,
        resource_type="dataset_version" if ref != "*" else "global",
        operations=ops or ["read", "export", "train"], status=status,
        legal_basis_ref="basis", approved_by="reviewer",
        valid_from=valid_from if valid_from is not None else NOW - timedelta(days=1),
        valid_until=valid_until if valid_until is not None else NOW + timedelta(days=1),
        row_scope=row_scope if row_scope is not None else {"patients": ["P1"]},
        column_scope=column_scope if column_scope is not None else {})


P3_LABELS = {"protection_level": "P3", "personal_info": "personal",
             "usage_constraints": {"purposes": ["research"], "export_allowed": True,
                                   "training_allowed": True}}


# ---------- T04：非法枚举/类型/结构一律拒绝 ----------

@pytest.mark.parametrize("labels", [
    {"protection_level": "P0"},
    {"protection_level": 3},
    {"personal_info": "unknown_enum"},
    {"data_form": "paragraph"},
    {"processing_state": "encrypted"},
    {"legal_status": "top_secret"},
    {"business_categories": ["not_a_category"]},
    {"pi_markers": ["super_dent"]},
    {"unknown_dimension": {}},
    {"usage_constraints": {"purposes": "research"}},
    {"usage_constraints": {"purposes": [1, 2]}},
    {"usage_constraints": {"export_allowed": "yes"}},
    {"usage_constraints": {"valid_until": "not-a-date"}},
    {"usage_constraints": {"unknown_flag": True}},
])
def test_invalid_labels_rejected(labels):
    with pytest.raises(sec.PolicyValidationError):
        sec.validate_labels(labels)
    with pytest.raises(sec.PolicyValidationError):
        sec.resolve_policy(labels)


def test_valid_labels_accepted_and_level_column_consistency():
    labels = {"protection_level": "P2", "personal_info": "none",
              "business_categories": ["lab"],
              "usage_constraints": {"purposes": ["research"], "export_allowed": False}}
    policy = sec.resolve_policy(labels)
    assert policy.protection_level == "P2"
    assert policy.purposes == ["research"]


def test_canonical_object_ref_rejects_colon_key_and_requires_columns():
    good = sec.canonical_object_ref("table", {
        "source_code": "HIS", "schema_name": "HIS", "table_name": "WEIRD:NAME"})
    assert "WEIRD:NAME" in good and good.startswith("{")
    with pytest.raises(sec.PolicyValidationError):
        sec.canonical_object_ref("column", {"source_code": "HIS",
                                            "schema_name": "HIS", "table_name": "T"})
    with pytest.raises(sec.PolicyValidationError):
        sec.canonical_object_ref("database", {"source_code": "HIS"})


# ---------- T05/T08：未分类默认拒绝与组合保守序 ----------

def test_unclassified_pending_and_fail_closed_purposes():
    unclassified = sec.resolve_policy(None)
    assert unclassified.is_pending and unclassified.protection_level == "P4"
    # 已分类但未写用途 → purposes=[]（全部禁止，fail-closed）
    partial = sec.resolve_policy({"protection_level": "P2"})
    assert partial.purposes == []


def test_combine_conservative_order():
    p3 = sec.resolve_policy({"protection_level": "P3", "personal_info": "personal",
                             "usage_constraints": {"purposes": ["research", "stats"],
                                                   "export_allowed": True,
                                                   "valid_until": "2027-01-01T00:00:00+00:00"}})
    p2 = sec.resolve_policy({"protection_level": "P2", "personal_info": "none",
                             "usage_constraints": {"purposes": ["research"],
                                                   "export_allowed": True,
                                                   "valid_until": "2026-12-01T00:00:00+00:00"}})
    combined = sec.combine_policies([p3, p2], joined=False)
    assert combined.protection_level == "P3"          # max
    assert combined.purposes == ["research"]           # 交集
    assert combined.valid_until == "2026-12-01T00:00:00+00:00"  # 最早
    joined = sec.combine_policies([p2, p2], joined=True)
    assert joined.protection_level == "P3"             # JOIN 地板 P3
    assert joined.re_id_risk_review_required
    all_none = sec.combine_policies([
        sec.resolve_policy({"protection_level": "P1", "personal_info": "none"})] * 2)
    assert all_none.personal_info == "none"            # 全 none 仍为 none
    mixed = sec.combine_policies([
        sec.resolve_policy({"protection_level": "P1", "personal_info": "none"}),
        sec.resolve_policy({"protection_level": "P1", "personal_info": "pending"})])
    assert mixed.personal_info == "pending"            # none+pending → pending（保守）
    unconstrained = sec.combine_policies([
        sec.resolve_policy({"protection_level": "P2",
                            "usage_constraints": {"purposes": ["research"]}}),
        sec.resolve_policy(None)])
    assert unconstrained.purposes is None               # 未分类输入 → 组合未约束→禁止


# ---------- T06：放宽需审批 ----------

def test_widening_requires_approval():
    cur = sec.resolve_policy(P3_LABELS)
    wider_purpose = sec.resolve_policy({
        **P3_LABELS,
        "usage_constraints": {"purposes": ["research", "external"],
                              "export_allowed": True, "training_allowed": True}})
    needs, reasons = sec.change_requires_approval(cur, wider_purpose)
    assert needs and any("用途扩张" in r for r in reasons)
    open_export = sec.resolve_policy({
        **P3_LABELS,
        "usage_constraints": {"purposes": ["research"], "export_allowed": True,
                              "training_allowed": True}})
    # P3_LABELS export_allowed=True；构造禁止版本再放开对比
    no_export = sec.resolve_policy({
        "protection_level": "P3", "personal_info": "personal",
        "usage_constraints": {"purposes": ["research"], "export_allowed": False,
                              "training_allowed": True}})
    needs, _ = sec.change_requires_approval(no_export, open_export)
    assert needs
    longer = sec.resolve_policy({
        **P3_LABELS,
        "usage_constraints": {"purposes": ["research"], "export_allowed": True,
                              "training_allowed": True,
                              "valid_until": "2030-01-01T00:00:00+00:00"}})
    with_horizon = sec.resolve_policy({
        **P3_LABELS,
        "usage_constraints": {"purposes": ["research"], "export_allowed": True,
                              "training_allowed": True,
                              "valid_until": "2027-06-01T00:00:00+00:00"}})
    needs, reasons = sec.change_requires_approval(with_horizon, longer)
    assert needs and any("有效期延长" in r for r in reasons)
    # 收窄/升紧不需要审批
    tighter = sec.resolve_policy({
        **P3_LABELS, "protection_level": "P4",
        "usage_constraints": {"purposes": [], "export_allowed": False,
                              "training_allowed": False}})
    needs, _ = sec.change_requires_approval(cur, tighter)
    assert not needs
    # 同级降保护等级需要审批
    drop = sec.resolve_policy({**P3_LABELS, "protection_level": "P2"})
    assert sec.change_requires_approval(cur, drop)[0]


# ---------- T12：授权时间边界 ----------

def test_grant_time_boundaries():
    future = _grant(valid_from=NOW + timedelta(hours=1))
    ok, decision = sec.grant_active(future, now=NOW)
    assert not ok and decision == "deny_not_yet_valid"
    boundary = _grant(valid_until=NOW)
    ok, decision = sec.grant_active(boundary, now=NOW)
    assert not ok and decision == "deny_grant_expired"
    revoked = _grant(status="revoked")
    assert sec.grant_active(revoked, now=NOW) == (False, "deny_grant_revoked")
    pending = _grant(status="pending")
    assert sec.grant_active(pending, now=NOW) == (False, "deny_grant_pending")
    no_op = _grant(ops=["read"])
    ok, decision = sec.grant_active(no_op, now=NOW, operation="export")
    assert not ok and decision == "deny_operation"
    active = _grant()
    assert sec.grant_active(active, now=NOW) == (True, "allow")


# ---------- T13：多授权确定性与撤销墓碑 ----------

def test_resolve_grant_priority_and_tombstone():
    ref = "dataset:SYNTH:1"
    # 具体授权优先于全局
    db = FakeDb(grants=[_grant(ref="*", gid=10), _grant(ref=ref, gid=11)])
    g, decision, _ = sec.resolve_grant(db, "u1", "research", ref, now=NOW)
    assert g is not None and g.id == 11 and decision == "allow"
    # 具体档已撤销且无更新的可用行 → 墓碑，拒绝且不回退全局
    db = FakeDb(grants=[_grant(ref="*", gid=10), _grant(ref=ref, gid=5, status="revoked")])
    g, decision, reason = sec.resolve_grant(db, "u1", "research", ref, now=NOW)
    assert g is None and decision == "deny_grant_revoked" and "不回退" in reason
    # 撤销后新授的具体授权可用（后授覆盖旧撤销）
    db = FakeDb(grants=[_grant(ref=ref, gid=5, status="revoked"),
                        _grant(ref=ref, gid=9)])
    g, decision, _ = sec.resolve_grant(db, "u1", "research", ref, now=NOW)
    assert g is not None and g.id == 9
    # 仅 pending → 待审批拒绝
    db = FakeDb(grants=[_grant(ref=ref, status="pending")])
    g, decision, _ = sec.resolve_grant(db, "u1", "research", ref, now=NOW)
    assert g is None and decision == "deny_grant_pending"
    # 无授权
    db = FakeDb(grants=[])
    g, decision, _ = sec.resolve_grant(db, "u1", "research", ref, now=NOW)
    assert g is None and decision == "deny_no_grant"
    # 同档多条 active：valid_from 最新优先，再按 id 最大（确定性）
    db = FakeDb(grants=[_grant(ref=ref, gid=3, valid_from=NOW - timedelta(days=5)),
                        _grant(ref=ref, gid=7, valid_from=NOW - timedelta(days=1))])
    g, _, _ = sec.resolve_grant(db, "u1", "research", ref, now=NOW)
    assert g.id == 7


# ---------- T16：导出/训练标志、P4 权限、行范围、列投影 ----------

def _gateway(db, labels, operation="read", columns=None, p4=False, purpose="research"):
    return sec.enforce_read(db, "u1", purpose, "dataset:SYNTH:1",
                            operation=operation, requested_columns=columns,
                            now=NOW, p4_authorized=p4)


def test_export_forbidden_any_level():
    labels = {"protection_level": "P2", "personal_info": "none",
              "usage_constraints": {"purposes": ["research"], "export_allowed": False}}
    db = FakeDb(classifications=[_cls(labels)], grants=[_grant()])
    r = _gateway(db, labels, operation="export")
    assert not r.allowed and r.decision == "deny_export_forbidden"


def test_training_forbidden_any_level():
    labels = {"protection_level": "P2", "personal_info": "none",
              "usage_constraints": {"purposes": ["research"], "training_allowed": False}}
    db = FakeDb(classifications=[_cls(labels)], grants=[_grant()])
    r = _gateway(db, labels, operation="train")
    assert not r.allowed and r.decision == "deny_train_forbidden"


def test_p4_requires_independent_permission():
    labels = {"protection_level": "P4", "personal_info": "sensitive_personal",
              "usage_constraints": {"purposes": ["research"], "export_allowed": True}}
    db = FakeDb(classifications=[_cls(labels)], grants=[_grant()])
    assert _gateway(db, labels).decision == "deny_p4_permission"
    assert _gateway(db, labels, p4=True).allowed


def test_invalid_policy_denies_not_500():
    malformed = {"protection_level": "P0", "personal_info": "unknown_enum"}
    db = FakeDb(classifications=[_cls(malformed)], grants=[_grant()])
    r = _gateway(db, malformed)
    assert not r.allowed and r.decision == "deny_invalid_policy"


def test_unclassified_denies_but_metadata_visible_elsewhere():
    db = FakeDb(classifications=[], grants=[_grant()])
    r = _gateway(db, None)
    assert not r.allowed and r.decision == "deny_unclassified"


def test_row_scope_required_for_p3():
    db = FakeDb(classifications=[_cls(P3_LABELS)],
                grants=[_grant(row_scope={})])
    r = _gateway(db, P3_LABELS)
    assert not r.allowed and r.decision == "deny_row_scope"
    db2 = FakeDb(classifications=[_cls(P3_LABELS)],
                 grants=[_grant(row_scope={"all": True})])
    assert _gateway(db2, P3_LABELS).allowed  # 显式审批全范围


def test_column_projection_blocked_not_overridable():
    db = FakeDb(classifications=[_cls(P3_LABELS)],
                grants=[_grant(column_scope={"allow": ["a", "b"], "blocked": ["b"]})])
    r = _gateway(db, P3_LABELS, columns=["a"])
    assert r.allowed and r.allowed_columns == ["a"]  # blocked 从投影剔除
    r2 = _gateway(db, P3_LABELS, columns=["b"])
    assert not r2.allowed and r2.decision == "deny_column" and r2.columns_blocked == ["b"]
    r3 = _gateway(db, P3_LABELS, columns=["c"])
    assert not r3.allowed and r3.decision == "deny_column"


def test_purpose_outside_labels_denies():
    db = FakeDb(classifications=[_cls(P3_LABELS)], grants=[_grant()])
    r = _gateway(db, P3_LABELS, purpose="marketing")
    assert not r.allowed and r.decision == "deny_purpose"


def test_allow_path_full_chain():
    db = FakeDb(classifications=[_cls(P3_LABELS)], grants=[_grant()])
    r = _gateway(db, P3_LABELS, operation="export", columns=None)
    assert r.allowed and r.grant_id is not None and r.row_scope == {"patients": ["P1"]}
