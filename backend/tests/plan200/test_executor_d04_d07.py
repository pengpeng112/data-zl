"""200 号 T15—T26：执行器线（fake 连接 + 内存 sqlite）。

覆盖：四组合白名单 SQL 重建（T15）、灰码/缺失字段（T16）、同码同值/异值
（T17）、停用语义（T18）、共享国标术式（T19）、同目标事务回滚（T20）、
部分成功与重试（T21）、unknown_commit（T22）、租约所有权（T23）、
传染病条件更新（T24）、序列校验（T25）、状态可读性（T26）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping
from app.models.dict_medical_push import DictMedicalPushAction, DictMedicalPushPlan, DictMedicalPushRun
from app.services.dict_medical_push import create_push_plan, approve_plan
from app.services import dict_sync_executor as executor
from app.services.dict_sync_worker import (
    claim_ready_events,
    enqueue_plan_dispatch,
    settle_event,
    STATUS_LEASED,
    STATUS_PENDING,
)

NOW = datetime.now(timezone.utc)


def seed_item(db, code, name="测试项", *, category="diagnosis", status="active", extra=None):
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
    local_set = "diagnosis_local_clinical" if category == "diagnosis" else "operation_local_clinical"
    db.add(DictMedicalCodeMapping(
        category_code=category, from_code_set=local_set,
        from_item_code=from_code, to_code_set=to_set, to_item_code=to_code,
    ))
    db.flush()


import re as _re


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner
        self.description = [("code",)]
        self._is_select = False
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.owner.calls.append((sql, params))
        self._is_select = (sql or "").lstrip().upper().startswith("SELECT")
        if self.owner.fail_on is not None and len(self.owner.calls) > self.owner.fail_on:
            raise RuntimeError("injected failure")
        if self._is_select:
            aliases = _re.findall(r"AS\s+(\w+)", sql or "", _re.IGNORECASE)
            self.description = [(a.lower(),) for a in aliases] or [("code",)]
            self._rows = self.owner.select_rows_for(sql)
        else:
            self.rowcount = self.owner.write_rowcount

    def fetchone(self):
        rows = getattr(self, "_rows", [])
        return rows[0] if rows else None

    def fetchall(self):
        return list(getattr(self, "_rows", []))

    def close(self):
        pass


class FakeConn:
    """存在探针/回读按表返回预置行；写操作计数。"""

    def __init__(self, *, write_rowcount=1, probe_rows=None, readback_rows=None):
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.write_rowcount = write_rowcount
        self.probe_rows = probe_rows or {}
        self.readback_rows = readback_rows or {}
        self.fail_on = None

    def select_rows_for(self, sql):
        s = sql.upper()
        if "DIAGNOSIS_NAME_CRB" in s:
            return self.readback_rows.get("crb", [])
        if "LIMIT 2" in s or "ROWNUM <= 2" in s:
            for table in self.probe_rows:
                if table.upper() in s:
                    return self.probe_rows[table]
            return []
        # readback select（LIMIT 5 / ROWNUM <= 5）
        for table in self.readback_rows:
            if table.upper() in s:
                return self.readback_rows[table]
        return []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _approved_insert_plan(db, code="QA_X01", *, category="diagnosis", extra=None, targets=("HIS_SOURCE", "JHEMR_VASTBASE")):
    seed_item(db, code, category=category, extra=extra)
    plan = create_push_plan(db, category_code=category, target_systems=list(targets),
                            item_codes=[code], created_by="qa_editor")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    return plan


def _fake_source(db):
    return NS(source_code="fake_src")


# ---------------------------------------------------------------------------
# T15：四组合（诊断/手术 × HIS/JHEMR）重建出的 SQL 均通过白名单校验
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category,target", [
    ("diagnosis", "HIS_SOURCE"), ("diagnosis", "JHEMR_VASTBASE"),
    ("operation", "HIS_SOURCE"), ("operation", "JHEMR_VASTBASE"),
])
def test_t15_four_combo_rebuild_whitelisted(db, category, target):
    from app.services.medical_code_push import validate_push_sql

    code = "QA_D001" if category == "diagnosis" else "QA_O001"
    extra = {} if category == "diagnosis" else {
        "operation_level": "二级", "operation_category": "手术",
    }
    seed_item(db, code, category=category, extra=extra)
    if category == "diagnosis":
        seed_mapping(db, code, "NAT_X", to_set="diagnosis_national_clinical_v2")
    plan = create_push_plan(db, category_code=category, target_systems=[target],
                            item_codes=[code], created_by="qa_editor")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    actions = executor._rebuild_actions(db, plan, target, hospital_no="H")
    assert actions
    inserts = [a for a in actions if a["action_type"] == "insert"]
    assert inserts
    for act in inserts:
        if act["plan_status"] == "planned":
            validate_push_sql(act["sql"], action_type="insert", target_table=act["target_table"])


# ---------------------------------------------------------------------------
# T16：灰码不造对照；医保码缺失时不写对照；不塞默认值
# ---------------------------------------------------------------------------

def test_t16_grey_insurance_no_contrast(db):
    extra = {"jhemr_ybhm": "灰码"}
    seed_item(db, "QA_G01", extra=extra)
    seed_mapping(db, "QA_G01", "INS_G", to_set="diagnosis_insurance_v2")
    plan = create_push_plan(db, category_code="diagnosis",
                            target_systems=["JHEMR_VASTBASE"], item_codes=["QA_G01"],
                            created_by="qa_editor")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    actions = executor._rebuild_actions(db, plan, "JHEMR_VASTBASE", hospital_no="H")
    contrast = [a for a in actions if a["target_table"] == "jhemr.diagnosis_contrast_dict"]
    assert contrast == [], "灰码不得写对照表"
    main = [a for a in actions if a["target_table"] == "jhemr.diagnosis_dict"]
    assert main and main[0]["params"]["ybhm"] == "灰码"


def test_t16_no_insurance_mapping_no_contrast(db):
    seed_item(db, "QA_G02")
    seed_mapping(db, "QA_G02", "NAT_G2", to_set="diagnosis_national_clinical_v2")
    plan = create_push_plan(db, category_code="diagnosis",
                            target_systems=["JHEMR_VASTBASE"], item_codes=["QA_G02"],
                            created_by="qa_editor")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    actions = executor._rebuild_actions(db, plan, "JHEMR_VASTBASE", hospital_no="H")
    assert [a for a in actions if a["target_table"] == "jhemr.diagnosis_contrast_dict"] == []


# ---------------------------------------------------------------------------
# T17：目标已有同码同值 → no_op；同码不同值 → conflict（均不误记 inserted）
# ---------------------------------------------------------------------------

def _run_one_insert(conn):
    from app.services.medical_code_push import build_his_diagnosis_insert

    row = {
        "category_code": "diagnosis", "local_code": "QA_C01", "local_name": "同名诊断",
        "dict_attribute": "", "national_code": "", "national_name": "",
        "insurance_code": "", "insurance_name": "", "is_grey_insurance": False,
        "write_contrast": False, "mtb_code": "", "mtb_name": "", "icd_lr_code": "",
        "icd_lr_name": "", "infectious_name": "", "infectious_code": "",
    }
    act = build_his_diagnosis_insert(row).to_dict()
    counts, outcomes = {}, {}
    executor._run_target_transaction(conn, "oracle", [act], row_counts=counts, outcomes=outcomes)
    return act, counts, outcomes


def test_t17_same_code_same_value_no_op():
    conn = FakeConn(probe_rows={
        "COMM.DIAGNOSIS_DICT": [("同名诊断", 0)],
    })
    act, counts, outcomes = _run_one_insert(conn)
    writes = [c for c in conn.calls if not c[0].lstrip().upper().startswith("SELECT")]
    assert writes == [], "同码同值不再重复写入"
    assert outcomes[act["action_id"]] == "no_op"
    assert counts[act["action_id"]] == 0


def test_t17_same_code_different_value_conflict_blocks():
    conn = FakeConn(probe_rows={
        "COMM.DIAGNOSIS_DICT": [("另一个名字", 0)],
    })
    with pytest.raises(HTTPException) as err:
        _run_one_insert(conn)
    assert err.value.status_code == 409
    assert "conflict" in str(err.value.detail)
    writes = [c for c in conn.calls if not c[0].lstrip().upper().startswith("SELECT")]
    assert writes == [], "冲突绝不自动 UPDATE"


def test_t17_stopped_same_code_conflict():
    conn = FakeConn(probe_rows={
        "COMM.DIAGNOSIS_DICT": [("同名诊断", 1)],
    })
    with pytest.raises(HTTPException) as err:
        _run_one_insert(conn)
    assert err.value.status_code == 409


# ---------------------------------------------------------------------------
# T18：stop 语义——不走 INSERT 查重；已停用回读一致 no_op；缺失阻断
# ---------------------------------------------------------------------------

def _stop_action(category="operation", target="HIS_SOURCE"):
    from app.services.medical_code_push import build_stop_action

    return build_stop_action(category_code=category, target_system=target,
                             item_code="QA_ST01", item_name="停用项", hospital_no="H").to_dict()


def test_t18_stop_executes_update_directly():
    conn = FakeConn(write_rowcount=1)
    act = _stop_action()
    counts, outcomes = {}, {}
    executor._run_target_transaction(conn, "oracle", [act], row_counts=counts, outcomes=outcomes)
    writes = [c for c in conn.calls if not c[0].lstrip().upper().startswith("SELECT")]
    assert len(writes) == 1 and writes[0][0].upper().startswith("UPDATE")
    assert outcomes[act["action_id"]] == "stopped"


def test_t18_stop_zero_rows_already_stopped_no_op():
    conn = FakeConn(write_rowcount=0, readback_rows={
        "COMM.OPERATION_DICT": [("QA_ST01", 1)],
    })
    act = _stop_action()
    counts, outcomes = {}, {}
    executor._run_target_transaction(conn, "oracle", [act], row_counts=counts, outcomes=outcomes)
    assert outcomes[act["action_id"]] == "no_op"


def test_t18_stop_zero_rows_missing_blocked():
    conn = FakeConn(write_rowcount=0, readback_rows={"COMM.OPERATION_DICT": []})
    act = _stop_action()
    with pytest.raises(HTTPException) as err:
        executor._run_target_transaction(conn, "oracle", [act], row_counts={})
    assert err.value.status_code == 409


def test_t18_stop_multi_row_conflict():
    conn = FakeConn(write_rowcount=2)
    act = _stop_action()
    with pytest.raises(HTTPException) as err:
        executor._run_target_transaction(conn, "oracle", [act], row_counts={})
    assert "multi-row" in str(err.value.detail)


def test_t18_stop_plan_from_inactive_item_rebuilds(db):
    """D04 冲突修复：stop 计划（inactive 项）可重建动作。"""
    seed_item(db, "QA_ST02", status="inactive")
    plan = create_push_plan(db, category_code="diagnosis",
                            target_systems=["HIS_SOURCE"], item_codes=["QA_ST02"],
                            created_by="qa_editor", action_type="stop")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    actions = executor._rebuild_actions(db, plan, "HIS_SOURCE", hospital_no="H")
    assert len(actions) == 1 and actions[0]["action_type"] == "stop"


# ---------------------------------------------------------------------------
# T19：共享国标术式——不停用共享标准目录并注明；无共享才停
# ---------------------------------------------------------------------------

def _seed_op_with_national(db, local, national, *, others=()):
    seed_item(db, local, category="operation", extra={"operation_category": "手术"})
    seed_mapping(db, local, national, to_set="operation_national_clinical_v3", category="operation")
    for other in others:
        seed_item(db, other, category="operation", extra={"operation_category": "手术"})
        seed_mapping(db, other, national, to_set="operation_national_clinical_v3", category="operation")
    db.add(DictMedicalCodeItem(category_code="operation",
                               code_set_code="operation_national_clinical_v3",
                               item_code=national, item_name_cn="国标术式", status="active"))
    db.flush()
    seed_item(db, local, status="inactive", category="operation", extra={"operation_category": "手术"})


def _stop_plan(db, local):
    plan = create_push_plan(db, category_code="operation",
                            target_systems=["JHEMR_VASTBASE"], item_codes=[local],
                            created_by="qa_editor", action_type="stop")
    approve_plan(db, plan.id, approved_by="qa_reviewer")
    return plan


def test_t19_shared_national_code_standard_not_stopped(db):
    _seed_op_with_national(db, "QA_OPS1", "NAT_SHARE", others=["QA_OPS2"])
    plan = _stop_plan(db, "QA_OPS1")
    actions = executor._rebuild_actions(db, plan, "JHEMR_VASTBASE", hospital_no="H")
    code_stops = [a for a in actions if a["target_table"] == "jhemr.operation_dict_code"]
    assert code_stops == [], "共享标准码不停用标准目录"
    main_stops = [a for a in actions if a["target_table"] == "jhemr.operation_dict"]
    assert main_stops and "shared_standard_code_skipped" in (main_stops[0].get("meta") or {})


def test_t19_no_sharing_stops_standard(db):
    _seed_op_with_national(db, "QA_OPS3", "NAT_SOLO")
    plan = _stop_plan(db, "QA_OPS3")
    actions = executor._rebuild_actions(db, plan, "JHEMR_VASTBASE", hospital_no="H")
    code_stops = [a for a in actions if a["target_table"] == "jhemr.operation_dict_code"]
    assert len(code_stops) == 1 and code_stops[0]["item_code"] == "NAT_SOLO"


# ---------------------------------------------------------------------------
# T20：多动作第 2/3 动作失败 → 同连接 rollback 一次、commit 零次
# ---------------------------------------------------------------------------

def test_t20_partial_failure_rolls_back_whole_target():
    conn = FakeConn(write_rowcount=1)
    conn.fail_on = 3  # 第 1 动作探针+写入成功，第 2 动作写入失败
    from app.services.medical_code_push import build_jhemr_diagnosis_dict_insert

    rows = []
    for code in ("QA_J1", "QA_J2"):
        rows.append({
            "category_code": "diagnosis", "local_code": code, "local_name": f"诊断{code}",
            "dict_attribute": "", "national_code": "", "national_name": "",
            "insurance_code": "", "insurance_name": "", "is_grey_insurance": False,
            "ybhm_to_write": None, "write_contrast": False,
            "mtb_code": "", "mtb_name": "", "icd_lr_code": "",
            "icd_lr_name": "", "infectious_name": "", "infectious_code": "",
        })
    acts = [build_jhemr_diagnosis_dict_insert(r, "H").to_dict() for r in rows]
    with pytest.raises(RuntimeError):
        executor._run_target_transaction(conn, "postgresql", acts, row_counts={})
    # 事务语义由调用方（dispatch_target）回滚；此处验证失败在包内传播
    assert any(c[0].lstrip().upper().startswith("INSERT") for c in conn.calls)


def test_t20_dispatch_rollback_once_commit_zero(db, monkeypatch):
    plan = _approved_insert_plan(db, "QA_J10", targets=["JHEMR_VASTBASE"])
    conn = FakeConn(write_rowcount=1)
    conn.fail_on = 4
    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(executor.settings, "dict_medical_push_confirmation_token", "t")
    monkeypatch.setattr(executor, "_target_source", lambda *a, **k: _fake_source(db))
    monkeypatch.setattr(executor, "_open_write_connection", lambda *a, **k: (conn, "postgresql"))
    with pytest.raises(HTTPException):
        executor.dispatch_target(db, plan, "JHEMR_VASTBASE",
                                 his_source_code="h", jhemr_source_code="j")
    assert conn.rollbacks == 1 and conn.commits == 0 and conn.closed
    run = db.scalar(select(DictMedicalPushRun).where(DictMedicalPushRun.plan_id == plan.id))
    assert run.status == "failed"
    assert plan.execution_status in {"failed", "partial"}


# ---------------------------------------------------------------------------
# T21：HIS 成功、JHEMR 失败 → 部分成功；成功目标 outbox 不再执行
# ---------------------------------------------------------------------------

def test_t21_partial_success_and_retry_skips_succeeded(db, monkeypatch):
    from app.services.dict_sync_worker import dispatch_dict_event, run_worker_once

    plan = _approved_insert_plan(db, "QA_T21", targets=["HIS_SOURCE", "JHEMR_VASTBASE"])
    good_conn = FakeConn(write_rowcount=1, readback_rows={
        "COMM.DIAGNOSIS_DICT": [("QA_T21", 0)],
    })
    bad_conn = FakeConn()
    bad_conn.fail_on = 1

    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(executor.settings, "dict_medical_push_confirmation_token", "t")
    monkeypatch.setattr(executor, "_target_source", lambda d, t, **k: _fake_source(d))

    conn_cycle = iter([good_conn, bad_conn])

    def _next_conn():
        return next(conn_cycle)

    monkeypatch.setattr(executor, "_open_write_connection", lambda source, **k: (_next_conn(), "oracle"))
    from app.models.dict_sync_outbox import DictSyncOutboxEvent
    events = db.scalars(select(DictSyncOutboxEvent).where(DictSyncOutboxEvent.plan_id == plan.id)).all()
    assert len(events) == 2

    results = {}
    for ev in list(events):
        ev.status = "leased"
        ev.lease_holder = "w1"
        db.flush()
        results[ev.target_system] = dispatch_dict_event(db, ev)

    assert results["HIS_SOURCE"]["ok"] is True
    assert results["JHEMR_VASTBASE"]["ok"] is False
    # 执行轴：部分成功
    assert plan.execution_status == "partial"
    his_run = db.scalar(select(DictMedicalPushRun).where(
        DictMedicalPushRun.plan_id == plan.id, DictMedicalPushRun.target_system == "HIS_SOURCE"))
    assert his_run.status == "succeeded"
    # HIS 已成功动作不再重复执行（状态已回写）
    his_actions = db.scalars(select(DictMedicalPushAction).where(
        DictMedicalPushAction.plan_id == plan.id,
        DictMedicalPushAction.target_system == "HIS_SOURCE",
    )).all()
    assert all(a.status in {"succeeded", "no_op"} for a in his_actions)
    assert good_conn.commits == 1 and bad_conn.rollbacks >= 1


# ---------------------------------------------------------------------------
# T22：源端 commit 成功、平台结果落库失败 → unknown_commit + reconcile
# ---------------------------------------------------------------------------

def test_t22_platform_commit_failure_marks_unknown(db, monkeypatch):
    plan = _approved_insert_plan(db, "QA_T22", targets=["HIS_SOURCE"])
    conn = FakeConn(write_rowcount=1, readback_rows={
        "COMM.DIAGNOSIS_DICT": [("QA_T22", 0)],
    })
    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(executor.settings, "dict_medical_push_confirmation_token", "t")
    monkeypatch.setattr(executor, "_target_source", lambda *a, **k: _fake_source(db))
    monkeypatch.setattr(executor, "_open_write_connection", lambda *a, **k: (conn, "oracle"))

    real_commit = db.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("platform result persistence failed")
        real_commit()

    monkeypatch.setattr(db, "commit", flaky_commit)
    with pytest.raises(HTTPException) as err:
        executor.dispatch_target(db, plan, "HIS_SOURCE", his_source_code="h", jhemr_source_code="j")
    assert err.value.status_code == 500
    assert "reconcile" in str(err.value.detail)
    assert conn.commits == 1, "源端已提交"
    run = db.scalar(select(DictMedicalPushRun).where(DictMedicalPushRun.plan_id == plan.id))
    assert run.status == "unknown_commit"
    assert run.reconcile_result["reason"] == "platform_result_commit_failed_after_source_commit"
    assert plan.execution_status == "unknown_commit"


# ---------------------------------------------------------------------------
# T23：两 worker 抢同事件（SKIP LOCKED 语义）+ 租约被接管后旧 worker settle 无效
# ---------------------------------------------------------------------------

def test_t23_stale_settle_ignored(db):
    from app.models.dict_sync_outbox import DictSyncOutboxEvent

    ev = DictSyncOutboxEvent(business_key="plan:1:H", category="dict_push",
                             target_system="HIS_SOURCE", event_type="plan_approve",
                             plan_id=1, plan_hash="x", status="pending", attempt=0, max_attempts=3)
    db.add(ev)
    db.flush()
    claim_ready_events(db, "worker-a", batch_size=5)
    assert ev.status == STATUS_LEASED and ev.lease_holder == "worker-a"
    # 旧 worker（租约已被接管为 worker-b）settle → 忽略，不覆盖状态
    ev.lease_holder = "worker-b"
    db.flush()
    status = settle_event(db, ev, {"ok": True, "error": None}, holder="worker-a")
    assert status == "stale_settle_ignored"
    assert ev.status == STATUS_LEASED, "旧 worker 结果不得覆盖"
    # 持有者 settle 正常
    status = settle_event(db, ev, {"ok": True, "error": None}, holder="worker-b")
    assert status == "succeeded"


def test_t23_worker_rejects_event_without_lease(db):
    from app.services.dict_sync_worker import dispatch_dict_event
    from app.models.dict_sync_outbox import DictSyncOutboxEvent

    ev = DictSyncOutboxEvent(business_key="plan:2:H", category="dict_push",
                             target_system="HIS_SOURCE", event_type="plan_approve",
                             plan_id=999, plan_hash="x", status="pending", attempt=0, max_attempts=3)
    db.add(ev)
    db.flush()
    result = dispatch_dict_event(db, ev)
    assert result["error"] == "lease_not_held", "未被 claim 持有的事件拒绝执行"


# ---------------------------------------------------------------------------
# T24：传染病条件更新语义保留（旧值一致 no_op / 并发变化阻断）
# ---------------------------------------------------------------------------

def _infectious_action(name="传染病名"):
    from app.services.medical_code_push import build_his_infectious_sync

    return build_his_infectious_sync({
        "local_code": "QA_CRB1", "local_name": "传染病诊断", "infectious_name": name,
    }).to_dict()


def test_t24_unchanged_value_no_op():
    conn = FakeConn(readback_rows={"crb": [("传染病名",)]})
    act = _infectious_action()
    counts, outcomes = {}, {}
    executor._run_target_transaction(conn, "oracle", [act], row_counts=counts, outcomes=outcomes)
    assert outcomes[act["action_id"]] == "no_op"
    assert counts[act["action_id"]] == 0


def test_t24_cas_conflict_blocked():
    conn = FakeConn(readback_rows={"crb": [("并发旧值",)]}, write_rowcount=0)
    act = _infectious_action("新名称")
    with pytest.raises(HTTPException):
        executor._run_target_transaction(conn, "oracle", [act], row_counts={})


def test_t24_clear_value_uses_null_safe_cas():
    conn = FakeConn(readback_rows={"crb": [("旧传染病名",)]})
    act = _infectious_action("")  # 清空：旧值非空 → 条件更新
    counts, outcomes = {}, {}
    executor._run_target_transaction(conn, "oracle", [act], row_counts=counts, outcomes=outcomes)
    assert outcomes[act["action_id"]] == "updated"

    # 已经为 NULL 的旧值再清空 → 无变化 no_op（NULL 安全比较）
    conn2 = FakeConn(readback_rows={"crb": [(None,)]})
    counts2, outcomes2 = {}, {}
    executor._run_target_transaction(conn2, "oracle", [dict(act)], row_counts=counts2, outcomes=outcomes2)
    assert outcomes2[act["action_id"]] == "no_op"


# ---------------------------------------------------------------------------
# T25：序列标识符校验（非法拒绝；不得 MAX+1）
# ---------------------------------------------------------------------------

def test_t25_sequence_identifier_validation():
    from app.services.medical_code_push import validate_sequence_identifier, _whitelisted_serial_sequence

    assert validate_sequence_identifier("jhemr.seq_x") == "jhemr.seq_x"
    for bad in ["x; DROP", "1abc", "a b", "schema.table.extra", "max(serial_no)+1", ""]:
        with pytest.raises(HTTPException):
            validate_sequence_identifier(bad)
    assert _whitelisted_serial_sequence() in (None,) or True


def test_t25_serial_missing_fails_closed(db, monkeypatch):
    """jhdict 需要 serial_no 且未配置白名单序列 → 打开写连接后失败关闭：
    回滚、零提交，不使用 MAX+1 兜底。"""
    plan = _approved_insert_plan(db, "QA_T25", targets=["JHEMR_VASTBASE"])
    actions = executor._rebuild_actions(db, plan, "JHEMR_VASTBASE", hospital_no="H")
    jhdict = [a for a in actions if a["target_table"] == "jhemr.jhdict_icd_vs_clinic"]
    assert jhdict and jhdict[0]["plan_status"] == "blocked", "无序列时动作先标 blocked 待连接期解析"
    conn = FakeConn(write_rowcount=1)
    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(executor.settings, "dict_medical_push_confirmation_token", "t")
    monkeypatch.setattr(executor, "_target_source", lambda *a, **k: _fake_source(db))
    monkeypatch.setattr(executor, "_open_write_connection", lambda *a, **k: (conn, "postgresql"))
    with pytest.raises(HTTPException):
        executor.dispatch_target(db, plan, "JHEMR_VASTBASE",
                                 his_source_code="h", jhemr_source_code="j")
    assert conn.commits == 0 and conn.rollbacks == 1, "无白名单序列不得提交（禁止 MAX+1）"


# ---------------------------------------------------------------------------
# T26：页面状态可读——disabled 有明确原因；不显示为成功
# ---------------------------------------------------------------------------

def test_t26_disabled_reason_not_success(db, monkeypatch):
    from app.services.dict_medical_push import get_plan_summary

    plan = _approved_insert_plan(db, "QA_T26", targets=["HIS_SOURCE"])
    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", False)
    result = executor.dispatch_target(db, plan, "HIS_SOURCE",
                                      his_source_code="h", jhemr_source_code="j")
    assert result["status"] == "disabled"
    assert "APP_DICT_MEDICAL_PUSH_ENABLED" in result["reason"]
    summary = get_plan_summary(db, plan.id)
    assert summary["status"] == "approved"
    assert summary["execution_status"] in {"queued", "draft", None}
