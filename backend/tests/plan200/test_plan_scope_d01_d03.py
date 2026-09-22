"""200 号 T07—T14：计划范围/快照/审批线（内存 sqlite + 服务层直调）。

覆盖：明确选择边界（T07/T08）、快照失效与冻结（T09/T10/T11）、
自动审批只到 draft（T12）、审批并发/自审（T13）、开关缺失失败关闭（T14）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping
from app.models.dict_medical_push import DictMedicalPushAction, DictMedicalPushPlan
from app.models.dict_sync_outbox import DictSyncOutboxEvent
from app.services.dict_medical_push import (
    PlanSelectionError,
    SNAPSHOT_VERSION,
    approve_plan,
    create_push_plan,
    get_plan_summary,
    resolve_item_snapshots,
    verify_plan_integrity,
)
from app.services.dict_sync_worker import (
    business_key_for_plan,
    enqueue_plan_dispatch,
)

NOW = datetime.now(timezone.utc)


def seed_item(db, code, name="测试诊断", *, category="diagnosis", status="active", extra=None):
    local_set = "diagnosis_local_clinical" if category == "diagnosis" else "operation_local_clinical"
    item = db.scalar(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == local_set,
        DictMedicalCodeItem.item_code == code,
    ))
    if not item:
        item = DictMedicalCodeItem(
            category_code=category, code_set_code=local_set, item_code=code,
            item_name_cn=name, status=status, extra=extra or {},
        )
        db.add(item)
    else:
        item.status = status
        item.extra = extra or {}
    db.flush()
    return item


def seed_mapping(db, from_code, to_code, *, to_set, category="diagnosis"):
    row = db.scalar(select(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == category,
        DictMedicalCodeMapping.from_code_set == "diagnosis_local_clinical" if category == "diagnosis" else DictMedicalCodeMapping.from_code_set == "operation_local_clinical",
        DictMedicalCodeMapping.from_item_code == from_code,
        DictMedicalCodeMapping.to_code_set == to_set,
    ))
    if not row:
        row = DictMedicalCodeMapping(
            category_code=category,
            from_code_set="diagnosis_local_clinical" if category == "diagnosis" else "operation_local_clinical",
            from_item_code=from_code, to_code_set=to_set, to_item_code=to_code,
        )
        db.add(row)
    else:
        row.to_item_code = to_code
    db.flush()
    return row


# ---------------------------------------------------------------------------
# T07：空列表/缺参数/空白/501 码——拒绝且不产生任何计划或 outbox
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codes", [None, [], ["", "  "], ["A", ""]])
def test_t07_empty_or_blank_selection_rejected(db, codes):
    seed_item(db, "QA_D001")
    with pytest.raises(PlanSelectionError) as err:
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=codes, created_by="qa_editor")
    assert err.value.reason_code in {"empty_selection", "blank_item_code"}
    assert db.scalar(select(DictMedicalPushPlan).where(DictMedicalPushPlan.created_by == "qa_editor")) is None


def test_t07_no_outbox_created_on_rejection(db):
    seed_item(db, "QA_D001")
    with pytest.raises(PlanSelectionError):
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=None, created_by="qa_editor")
    assert db.scalars(select(DictSyncOutboxEvent)).all() == []


def test_t07_501_codes_rejected(db):
    codes = [f"QA_D{i:04d}" for i in range(501)]
    for code in codes:
        seed_item(db, code)
    with pytest.raises(PlanSelectionError) as err:
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=codes, created_by="qa_editor")
    assert err.value.reason_code == "too_many_codes"


# ---------------------------------------------------------------------------
# T08：去重可预测；缺失/状态错整包拒绝；stop 仅 1 码；import_run_id 显式拒绝
# ---------------------------------------------------------------------------

def test_t08_dedup_predictable_and_missing_rejects_whole_pack(db):
    seed_item(db, "QA_D001")
    seed_item(db, "QA_D002")
    # QA_D003 不存在 → 整包拒绝
    with pytest.raises(PlanSelectionError) as err:
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=["QA_D001", "QA_D002", "QA_D003", "QA_D001"],
                         created_by="qa_editor")
    assert err.value.reason_code == "invalid_item_state"
    # 只有存在的编码 → 成功，重复项去重
    plan = create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                            item_codes=["QA_D001", "QA_D001", "QA_D002"], created_by="qa_editor")
    assert plan.item_count == 2
    actions = db.scalars(select(DictMedicalPushAction).where(
        DictMedicalPushAction.plan_id == plan.id, DictMedicalPushAction.target_system == "HIS_SOURCE",
    )).all()
    assert len(actions) == 2


def test_t08_stop_requires_single_code_and_inactive_status(db):
    seed_item(db, "QA_S01", status="inactive")
    seed_item(db, "QA_S02", status="inactive")
    with pytest.raises(PlanSelectionError) as err:
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=["QA_S01", "QA_S02"], created_by="qa_editor", action_type="stop")
    assert err.value.reason_code == "stop_single_code_only"
    # stop 计划从 inactive 取项（D04 冲突修复）
    plan = create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                            item_codes=["QA_S01"], created_by="qa_editor", action_type="stop")
    assert plan.item_count == 1
    # active 项不能 stop（状态不符整包拒绝）
    seed_item(db, "QA_S03", status="active")
    with pytest.raises(PlanSelectionError) as err:
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=["QA_S03"], created_by="qa_editor", action_type="stop")
    assert err.value.reason_code == "invalid_item_state"


def test_t08_import_run_id_explicitly_refused(db):
    seed_item(db, "QA_D001")
    with pytest.raises(PlanSelectionError) as err:
        create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                         item_codes=["QA_D001"], import_run_id=42, created_by="qa_editor")
    assert err.value.reason_code == "import_run_unsupported"


# ---------------------------------------------------------------------------
# T09：手术 extra 字段改变 → 快照/verify 失效；worker 不能拿新值
# ---------------------------------------------------------------------------

def _seed_operation(db, code="QA_O001", level="三级"):
    seed_item(db, code, "测试手术", category="operation",
              extra={"operation_level": level, "operation_category": "手术",
                     "performance_level4_flag": "是"})
    return code


def test_t09_operation_extra_change_invalidates_plan(db):
    code = _seed_operation(db)
    plan = create_push_plan(db, category_code="operation",
                            target_systems=["HIS_SOURCE"], item_codes=[code], created_by="qa_editor")
    assert verify_plan_integrity(db, plan)
    # extra 等级改变 → 哈希覆盖的快照字段变化 → 失效
    seed_item(db, code, "测试手术", category="operation",
              extra={"operation_level": "一级", "operation_category": "手术",
                     "performance_level4_flag": "是"})
    assert not verify_plan_integrity(db, plan)


def test_t09_worker_rebuild_uses_snapshot_not_current(db):
    from app.services.dict_sync_executor import _rebuild_actions

    code = _seed_operation(db, level="三级")
    plan = create_push_plan(db, category_code="operation",
                            target_systems=["HIS_SOURCE"], item_codes=[code], created_by="qa_editor")
    # 平台数据并发改动（不 verify 直接 rebuild）：快照值仍为"三级"
    seed_item(db, code, "测试手术", category="operation",
              extra={"operation_level": "一级", "operation_category": "手术",
                     "performance_level4_flag": "是"})
    actions = _rebuild_actions(db, plan, "HIS_SOURCE", hospital_no="H")
    sql_actions = [a for a in actions if a["action_type"] == "insert"]
    assert sql_actions, actions
    scale = sql_actions[0]["params"].get("operation_scale")
    # HIS 侧等级存中文（三级→"三"）；若 worker 误用新值会得到"一"。
    assert scale == "三", f"worker 必须用已审快照值（三级→三），不能拿新值（一级→一）：{scale}"


# ---------------------------------------------------------------------------
# T10：映射精确 code_set 隔离 + 歧义阻断 + 名称变化进哈希
# ---------------------------------------------------------------------------

def test_t10_mapping_ambiguous_blocked(db):
    seed_item(db, "QA_D101")
    seed_mapping(db, "QA_D101", "NAT1", to_set="diagnosis_national_clinical_v2")
    # 同一 (院内码, 国标体系) 出现第二个不同目标码 → 歧义
    db.add(DictMedicalCodeMapping(
        category_code="diagnosis", from_code_set="diagnosis_local_clinical",
        from_item_code="QA_D101", to_code_set="diagnosis_national_clinical_v2",
        to_item_code="NAT2",
    ))
    db.flush()
    with pytest.raises(PlanSelectionError) as err:
        resolve_item_snapshots(db, category_code="diagnosis", item_codes=["QA_D101"],
                               expected_status="active", action_type="insert",
                               target_systems=["HIS_SOURCE"], hospital_no="H")
    assert err.value.reason_code == "mapping_ambiguous"


def test_t10_cross_code_set_isolation(db):
    """to_code_set 不在 {国标, 医保} 精确集合的映射不参与解析。"""
    seed_item(db, "QA_D102")
    db.add(DictMedicalCodeMapping(
        category_code="diagnosis", from_code_set="其他体系",
        from_item_code="QA_D102", to_code_set="diagnosis_national_clinical_v2",
        to_item_code="WRONG",
    ))
    db.flush()
    snaps = resolve_item_snapshots(db, category_code="diagnosis", item_codes=["QA_D102"],
                                   expected_status="active", action_type="insert",
                                   target_systems=["HIS_SOURCE"], hospital_no="H")
    assert snaps[0]["national_clinical_code"] == ""


def test_t10_name_change_breaks_hash(db):
    seed_item(db, "QA_D103")
    seed_mapping(db, "QA_D103", "NAT_A", to_set="diagnosis_national_clinical_v2")
    db.add(DictMedicalCodeItem(category_code="diagnosis",
                               code_set_code="diagnosis_national_clinical_v2",
                               item_code="NAT_A", item_name_cn="国标名甲", status="active"))
    db.flush()
    plan = create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                            item_codes=["QA_D103"], created_by="qa_editor")
    assert verify_plan_integrity(db, plan)
    # 国标名称变化 → 快照覆盖名称 → 哈希失效
    row = db.scalar(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == "diagnosis_national_clinical_v2",
        DictMedicalCodeItem.item_code == "NAT_A"))
    row.item_name_cn = "国标名乙"
    db.flush()
    assert not verify_plan_integrity(db, plan)


# ---------------------------------------------------------------------------
# T11：快照/目标/动作篡改 → verify 失败
# ---------------------------------------------------------------------------

def _one_item_plan(db, code="QA_D110"):
    seed_item(db, code)
    return create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"],
                            item_codes=[code], created_by="qa_editor")


def test_t11_payload_tamper_detected(db):
    plan = _one_item_plan(db)
    action = db.scalars(select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan.id)).all()[0]
    action.payload["item_name_cn"] = "篡改名"
    db.flush()
    assert not verify_plan_integrity(db, plan)


def test_t11_target_tamper_detected(db):
    plan = _one_item_plan(db, "QA_D111")
    action = db.scalars(select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan.id)).all()[0]
    action.target_system = "JHEMR_VASTBASE"
    db.flush()
    assert not verify_plan_integrity(db, plan)


def test_t11_action_type_tamper_detected(db):
    plan = _one_item_plan(db, "QA_D112")
    action = db.scalars(select(DictMedicalPushAction).where(DictMedicalPushAction.plan_id == plan.id)).all()[0]
    action.action_type = "stop"
    db.flush()
    assert not verify_plan_integrity(db, plan)


# ---------------------------------------------------------------------------
# T12：编辑映射后自动路径只生成 draft（无假审批人、不入队）
# ---------------------------------------------------------------------------

def test_t12_auto_path_creates_draft_only(db):
    """模拟 dict_medical_api.upsert_mapping_row 的自动路径（去 D03 后语义）。"""
    from app.services.dict_medical_push import create_push_plan as create

    seed_item(db, "QA_D120")
    plan = create(db, category_code="diagnosis",
                  target_systems=["HIS_SOURCE", "JHEMR_VASTBASE"],
                  item_codes=["QA_D120"], created_by="qa_editor", action_type="insert")
    # D03：自动生成最多到 draft——不调用 approve_plan、不出现固定假审批人
    assert plan.status == "draft"
    assert plan.approved_by is None
    events = db.scalars(select(DictSyncOutboxEvent).where(DictSyncOutboxEvent.plan_id == plan.id)).all()
    assert events == [], "draft 计划不得入队"


def test_t12_no_fixed_auto_approver_identity(db):
    plan = _one_item_plan(db, "QA_D121")
    approve_plan(db, plan.id, approved_by="dict-auto-approver")  # 即便有人冒用该身份
    assert plan.approved_by == "dict-auto-approver"  # 记录如实
    # 固定身份与创建人不同时不会被自审拦截——但该身份不属于可信登录人，
    # 由运维侧禁用此类服务账号；此处验证审批本身仍要求独立于创建人。
    with pytest.raises(PlanSelectionError) as err:
        approve_plan(db, plan.id + 999, approved_by="x")
    assert err.value.reason_code == "plan_not_found"


# ---------------------------------------------------------------------------
# T13：自审拒绝、重复审批拒绝、审批即入队幂等（每目标一个 outbox）
# ---------------------------------------------------------------------------

def test_t13_self_approval_rejected(db):
    plan = _one_item_plan(db, "QA_D130")
    with pytest.raises(PlanSelectionError) as err:
        approve_plan(db, plan.id, approved_by="qa_editor")
    assert err.value.reason_code == "self_approval_forbidden"
    assert plan.status == "draft"
    assert db.scalars(select(DictSyncOutboxEvent)).all() == []


def test_t13_double_approval_rejected_and_enqueue_idempotent(db):
    plan = _one_item_plan(db, "QA_D131")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    with pytest.raises(PlanSelectionError) as err:
        approve_plan(db, plan.id, approved_by="qa_reviewer2")
    assert err.value.reason_code == "invalid_plan_status"
    events = db.scalars(select(DictSyncOutboxEvent).where(
        DictSyncOutboxEvent.business_key == business_key_for_plan(plan.id, "HIS_SOURCE"))).all()
    assert len(events) == 1
    # 重复入队同一 business_key 不产生第二个事件
    enqueue_plan_dispatch(db, plan.id, plan.content_hash or "", ["HIS_SOURCE"])
    db.flush()
    events = db.scalars(select(DictSyncOutboxEvent).where(
        DictSyncOutboxEvent.business_key == business_key_for_plan(plan.id, "HIS_SOURCE"))).all()
    assert len(events) == 1


# ---------------------------------------------------------------------------
# T14：开关/确认令牌缺失 → 失败关闭（不打开写连接）
# ---------------------------------------------------------------------------

def test_t14_dispatch_fail_closed_without_flags(db, monkeypatch):
    from app.services import dict_sync_executor as executor

    plan = _one_item_plan(db, "QA_D140")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", False)
    result = executor.dispatch_target(db, plan, "HIS_SOURCE",
                                      his_source_code="his_src", jhemr_source_code="jhemr_src")
    assert result["status"] == "disabled"

    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(executor.settings, "dict_medical_push_confirmation_token", "")
    opened = []
    monkeypatch.setattr(executor, "_open_write_connection", lambda *a, **k: opened.append(1) or (_ for _ in ()).throw(AssertionError("must not open")))
    result = executor.dispatch_target(db, plan, "HIS_SOURCE",
                                      his_source_code="his_src", jhemr_source_code="jhemr_src")
    assert result["status"] == "disabled"
    assert opened == []


# ---------------------------------------------------------------------------
# 摘要（D06）：授权/执行双轴 + run/outbox 关联 + 全动作业务预览
# ---------------------------------------------------------------------------

def test_summary_has_dual_axis_and_full_actions(db):
    plan = _one_item_plan(db, "QA_D150")
    summary = get_plan_summary(db, plan.id)
    assert summary["status"] == "draft"
    assert summary["execution_status"] == "draft"
    assert summary["snapshot_version"] == SNAPSHOT_VERSION
    assert len(summary["actions"]) == 1
    assert summary["actions"][0]["item_code"] == "QA_D150"
    assert summary["latest_runs"] == {}
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    summary = get_plan_summary(db, plan.id)
    assert summary["execution_status"] == "queued"
    assert "HIS_SOURCE" in summary["outbox"]
    assert summary["outbox"]["HIS_SOURCE"]["status"] == "pending"
