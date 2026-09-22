"""Child-process cases: pure fakes, no platform/source connections."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

from app.services import medical_code_push as sqls
from app.services import dict_sync_executor as executor
from app.services import dict_medical_push as plans


def action(name="模拟传染诊断"):
    return sqls.build_his_infectious_sync({"local_code": "SIM_CRB_1", "local_name": "模拟诊断", "infectious_name": name}).to_dict()


@pytest.mark.parametrize("name", ["模拟传染诊断", "", "  ", "O'Brien"])
def test_exact_field_template_and_bound_value(name):
    a = action(name)
    assert sqls.validate_push_sql(a["sql"], action_type="sync_infectious", target_table=a["target_table"]) == sqls.INFECTIOUS_SYNC_SQL
    assert a["params"] == {"code": "SIM_CRB_1", "crb_name": name.strip() or None}
    assert "DIAGNOSIS_CODE_CRB" not in a["sql"]


@pytest.mark.parametrize("bad", [
    "UPDATE COMM.DIAGNOSIS_DICT SET DIAGNOSIS_NAME_CRB=:crb_name WHERE 1=1",
    sqls.INFECTIOUS_SYNC_SQL.replace("SET DIAGNOSIS_NAME_CRB", "SET DIAGNOSIS_NAME"),
    sqls.INFECTIOUS_SYNC_SQL + " OR 1=1",
    sqls.INFECTIOUS_SYNC_SQL + "; DELETE FROM COMM.DIAGNOSIS_DICT",
    sqls.INFECTIOUS_SYNC_SQL.replace("COMM.DIAGNOSIS_DICT", "jhemr.diagnosis_dict"),
])
def test_template_cannot_expand_write_scope(bad):
    with pytest.raises(ValueError):
        sqls.validate_push_sql(bad, action_type="sync_infectious", target_table="COMM.DIAGNOSIS_DICT")


@pytest.mark.parametrize("before,target,expected_writes", [(None, "模拟", 1), ("旧名称", "模拟", 1), ("旧名称", "", 1), ("模拟", "模拟", 0), (None, "", 0)])
def test_existing_row_update_clear_and_idempotency(monkeypatch, before, target, expected_writes):
    a, writes, counts = action(target), [], {}
    monkeypatch.setattr(executor, "_run_select_on_conn", lambda *args: [{"crb_name": before}])
    def write(conn, dialect, sql, params):
        writes.append(params)
        assert params["old_crb_name"] == before
        return 1
    monkeypatch.setattr(executor, "_run_write_on_conn", write)
    executor._run_target_transaction(object(), "oracle", [a], row_counts=counts)
    assert len(writes) == expected_writes
    assert counts[a["action_id"]] == expected_writes
    assert executor._actions_requiring_readback([a], counts) == [a]
    monkeypatch.setattr(sqls, "_run_select_on_conn", lambda *args: [{"code": "SIM_CRB_1", "crb_name": target or None}])
    result = sqls.readback_actions_on_conn(object(), "oracle", [a])
    assert result["ok"]
    assert result["details"][0]["before_value"] == before


@pytest.mark.parametrize("rows", [[], [{"crb_name": None}, {"crb_name": None}]])
def test_missing_or_duplicate_his_code_never_writes(monkeypatch, rows):
    monkeypatch.setattr(executor, "_run_select_on_conn", lambda *args: rows)
    monkeypatch.setattr(executor, "_run_write_on_conn", lambda *args: pytest.fail("must not write"))
    with pytest.raises(HTTPException):
        executor._run_target_transaction(object(), "oracle", [action()], row_counts={})


@pytest.mark.parametrize("count", [0, 2, -1])
def test_cas_conflict_refuses_success(monkeypatch, count):
    monkeypatch.setattr(executor, "_run_select_on_conn", lambda *args: [{"crb_name": "旧名称"}])
    monkeypatch.setattr(executor, "_run_write_on_conn", lambda *args: count)
    with pytest.raises(HTTPException):
        executor._run_target_transaction(object(), "oracle", [action()], row_counts={})


@pytest.mark.parametrize("rows", [[], [{"crb_name": "错误名称"}], [{"crb_name": "模拟"}, {"crb_name": "模拟"}]])
def test_readback_rejects_missing_wrong_or_duplicate(monkeypatch, rows):
    monkeypatch.setattr(sqls, "_run_select_on_conn", lambda *args: rows)
    with pytest.raises(HTTPException):
        sqls.readback_actions_on_conn(object(), "oracle", [action("模拟")])


def test_legacy_apply_cannot_bypass_approved_plan():
    with pytest.raises(HTTPException) as err:
        sqls.apply_one_action(None, action(), mode="apply", writer=lambda *args: pytest.fail("bypass"))
    assert err.value.status_code == 403


@pytest.mark.parametrize("category,targets,codes", [("operation", ["HIS_SOURCE"], ["A"]), ("diagnosis", ["JHEMR_VASTBASE"], ["A"]), ("diagnosis", ["HIS_SOURCE"], None), ("diagnosis", ["HIS_SOURCE"], [" "])])
def test_scope_rejected_before_database(category, targets, codes):
    with pytest.raises(ValueError):
        plans.create_push_plan(None, category_code=category, target_systems=targets, item_codes=codes, created_by="test", action_type="sync_infectious")


def plan_fixture():
    payload = dict(item_code="SIM_CRB_1", item_name_cn="模拟诊断", national_clinical_code="", insurance_code="", status="active", hash_version=2,
                   action_type="sync_infectious", target_systems=["HIS_SOURCE"], category_code="diagnosis", infectious_disease_name="模拟", infectious_disease_code="")
    a = NS(item_code="SIM_CRB_1", item_name_cn="模拟诊断", action_type="sync_infectious", target_system="HIS_SOURCE", payload=deepcopy(payload))
    p = NS(id=1, category_code="diagnosis", target_systems=["HIS_SOURCE"], content_hash=plans._compute_plan_hash([payload]))
    item = NS(item_code="SIM_CRB_1", item_name_cn="模拟诊断", status="active", extra={"infectious_disease_name": "模拟"})
    class DB:
        def __init__(self): self.calls = 0
        def scalars(self, stmt):
            self.calls += 1
            return NS(all=lambda: [a] if self.calls == 1 else [])
        def scalar(self, stmt): return item
    return DB(), a, p, item


def test_integrity_includes_infectious_value():
    db, a, p, item = plan_fixture()
    assert plans.verify_plan_integrity(db, p)
    db.calls = 0
    item.extra["infectious_disease_name"] = "已修改"
    assert not plans.verify_plan_integrity(db, p)


def test_plan_creation_freezes_value_and_summary():
    item = NS(item_code="SIM_CRB_1", item_name_cn="模拟诊断", status="active", extra={"infectious_disease_name": " 模拟 "})
    class DB:
        def __init__(self): self.saved = []; self.calls = 0
        def scalars(self, stmt):
            self.calls += 1
            return NS(all=lambda: [item] if self.calls == 1 else [])
        def scalar(self, stmt): return None
        def add(self, obj): self.saved.append(obj)
        def flush(self): self.saved[0].id = 1
        def commit(self): pass
    db = DB()
    p = plans.create_push_plan(db, category_code="diagnosis", target_systems=["HIS_SOURCE"], item_codes=["SIM_CRB_1"], created_by="creator", action_type="sync_infectious")
    assert p.status == "draft"
    a = db.saved[1]
    assert a.payload["infectious_disease_name"] == "模拟"
    assert a.action_type == "sync_infectious" and a.diff_type == "changed"
    assert plans._compute_plan_hash([a.payload]) == p.content_hash
    # 200 D02：新计划一律 v3 完整快照（传染病也走同一快照形态）。
    assert a.payload["snapshot_version"] == plans.SNAPSHOT_VERSION
    class SummaryDB:
        def __init__(self): self.calls = 0
        def get(self, model, key): return p
        def scalars(self, stmt):
            self.calls += 1
            return NS(all=lambda: [a] if self.calls == 1 else [])
        def scalar(self, stmt): return None
    summary = plans.get_plan_summary(SummaryDB(), p.id)
    assert summary["id"] == 1
    assert summary["actions"][0]["infectious_disease_name"] == "模拟"
    assert summary["execution_status"] == "draft"


def test_rebuild_uses_approved_name_even_if_current_value_races():
    db, a, p, item = plan_fixture()
    # 200 D02：worker 按已审快照重建，不再读当前平台行——平台值并发变化
    # 也不影响冻结值（当前值漂移由 verify_plan_integrity 在写前拦截）。
    rebuilt = executor._rebuild_actions(db, p, "HIS_SOURCE", hospital_no="test")
    assert len(rebuilt) == 1 and rebuilt[0]["params"]["crb_name"] == "模拟"


def test_rebuild_refuses_legacy_insert_snapshot():
    # 200 D02：缺少 v3 完整快照绑定的老版 insert 计划必须重新生成，
    # 禁止静默补哈希继续写；选择完整性在创建端由 resolve_item_snapshots 整包拒绝。
    payload = dict(item_code="A", item_name_cn="B", hash_version=2)
    a = NS(item_code="A", item_name_cn="B", action_type="insert", target_system="HIS_SOURCE", payload=payload)
    p = NS(id=1, category_code="diagnosis", target_systems=["HIS_SOURCE"])
    db = NS(scalars=lambda stmt: NS(all=lambda: [a]))
    with pytest.raises(HTTPException):
        executor._rebuild_actions(db, p, "HIS_SOURCE", hospital_no="test")


def test_legacy_v1_payload_no_longer_hashes_as_before():
    # 200 D02：v1 管道格式哈希不再被静默接受——canonical JSON 重算不等，
    # 老 v1 计划 verify 失败并要求重新生成（不允许静默补哈希继续写）。
    import hashlib, json
    data = {"item_code": "A", "item_name_cn": "B", "national_clinical_code": "C", "insurance_code": "D", "status": "active"}
    legacy_pipe = hashlib.sha256(b"A|B|C|D|active").hexdigest()[:32]
    assert plans._compute_plan_hash([data]) != legacy_pipe
    canonical = hashlib.sha256(json.dumps([data], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:32]
    assert plans._compute_plan_hash([data]) == canonical


@pytest.mark.parametrize("mutation", ["payload", "action", "target", "legacy", "category"])
def test_approved_snapshot_tampering_rejected(mutation):
    db, a, p, item = plan_fixture()
    if mutation == "payload": a.payload["infectious_disease_name"] = "篡改"
    if mutation == "action": a.action_type = "insert"
    if mutation == "target": a.target_system = "JHEMR_VASTBASE"
    if mutation == "legacy": a.payload.pop("hash_version")
    if mutation == "category": p.category_code = "operation"
    assert not plans.verify_plan_integrity(db, p)


@pytest.mark.parametrize("bad", ["missing", "disabled", "source", "field", "system", "mode", "approval"])
def test_executor_registration_gate(bad):
    reg = NS(enabled=True, require_approval=True, execution_mode="sync_executor", target_system_code="HIS_SOURCE", target_source_code="test_his", sql_or_endpoint_ref="COMM.DIAGNOSIS_DICT.DIAGNOSIS_NAME_CRB")
    source = NS(system_code="HIS", source_code="test_his", db_type="oracle")
    if bad == "disabled": reg.enabled = False
    if bad == "source": reg.target_source_code = "other"
    if bad == "field": reg.sql_or_endpoint_ref = "COMM.DIAGNOSIS_DICT"
    if bad == "system": source.system_code = "DATA_CENTER"
    if bad == "mode": reg.execution_mode = "sql"
    if bad == "approval": reg.require_approval = False
    db = NS(scalar=lambda stmt: None if bad == "missing" else reg)
    with pytest.raises(HTTPException):
        executor._require_infectious_executor(db, source)


@pytest.mark.parametrize("readback_fails", [True, False])
def test_dispatch_commits_only_after_readback(monkeypatch, readback_fails):
    a = action()
    source = NS(source_code="test_his")
    p = NS(id=1, status="approved", expires_at=datetime.now(timezone.utc)+timedelta(hours=1), target_systems=["HIS_SOURCE"], approved_by="reviewer", created_by="creator")
    calls = []
    conn = NS(commit=lambda: calls.append("commit"), rollback=lambda: calls.append("rollback"), close=lambda: calls.append("close"))
    db = NS(add=lambda obj: None, flush=lambda: None, commit=lambda: None,
            scalars=lambda stmt: NS(all=lambda: []))
    monkeypatch.setattr(executor.settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(executor.settings, "dict_medical_push_confirmation_token", "test-only")
    monkeypatch.setattr(executor, "verify_plan_integrity", lambda *args: True)
    monkeypatch.setattr(executor, "_rebuild_actions", lambda *args, **kw: [a])
    monkeypatch.setattr(executor, "_target_source", lambda *args, **kw: source)
    monkeypatch.setattr(executor, "_require_infectious_executor", lambda *args: None)
    monkeypatch.setattr(executor, "_open_write_connection", lambda *args: (conn, "oracle"))
    monkeypatch.setattr(executor, "_run_target_transaction", lambda *args, **kw: kw["row_counts"].update({a["action_id"]: 1}))
    def readback(*args):
        calls.append("readback")
        if readback_fails:
            raise HTTPException(status_code=409, detail="bad readback")
        return {"ok": True, "checked": 1}
    monkeypatch.setattr(executor, "readback_actions_on_conn", readback)
    if readback_fails:
        with pytest.raises(HTTPException):
            executor.dispatch_target(db, p, "HIS_SOURCE", his_source_code="test_his", jhemr_source_code="")
        assert calls == ["readback", "rollback", "close"]
    else:
        result = executor.dispatch_target(db, p, "HIS_SOURCE", his_source_code="test_his", jhemr_source_code="")
        assert result["status"] == "succeeded"
        assert calls == ["readback", "commit", "close"]
