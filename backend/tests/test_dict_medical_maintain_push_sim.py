"""模拟正式维护 + 下发链路（隔离库，不连 HIS/JHEMR 业务库）。

路径：dict_admin 维护宽表 → 服务端生成计划 → 他人审批 → execute 仅 dry-run
→ SQL 预览白名单 → apply-one 强制 dry_run → 执行器在门禁+假写入下可提交。
"""
from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models.asset_system import AssetDataSource
from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping, DictMedicalCodeSet
from app.models.dict_medical_push import DictMedicalPushAction, DictMedicalPushPlan
from app.models.dict_sync_outbox import DictSyncOutboxEvent
from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetUserRole
from app.services.medical_code_push import apply_one_action, build_his_diagnosis_insert, plan_push_actions

DX_CODE = "SIM_DX_0920A"
OP_CODE = "SIM_OP_0920A"
DX_NAT = "SIMN_DX_A"
DX_INS = "SIMI_DX_A"
OP_NAT = "00.7000x001"
OP_INS = "00.7000x001"


def _bind_role_client(admin_client: TestClient, *, user: str, token: str, role_code: str) -> TestClient:
    seeded = admin_client.post("/api/v1/permissions/seed?operator=tester")
    assert seeded.status_code == 200, seeded.text
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        if not db.query(AssetRole).filter(AssetRole.role_code == role_code).first():
            db.add(AssetRole(role_code=role_code, role_name_cn=role_code, role_type="builtin"))
        key = db.query(ApiKey).filter(ApiKey.key_name == f"sim-{user}").first()
        if not key:
            db.add(ApiKey(key_name=f"sim-{user}", token_hash=token_hash, user_identifier=user, enabled=True))
        else:
            key.token_hash = token_hash
            key.user_identifier = user
            key.enabled = True
        if not db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == user,
            AssetUserRole.role_code == role_code,
        ).first():
            db.add(AssetUserRole(user_identifier=user, role_code=role_code, status="active"))
        db.commit()
    finally:
        db.close()
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def _ensure_code_sets(db) -> None:
    rows = [
        ("diagnosis", "diagnosis_local_clinical", "clinical", "院内临床诊断"),
        ("diagnosis", "diagnosis_national_clinical_v2", "national", "国临诊断"),
        ("diagnosis", "diagnosis_insurance_v2", "insurance", "医保诊断"),
        ("operation", "operation_local_clinical", "clinical", "院内临床手术"),
        ("operation", "operation_national_clinical_v3", "national", "国临手术"),
        ("operation", "operation_insurance_v2", "insurance", "医保手术"),
    ]
    for category, code, ctype, name in rows:
        if not db.scalar(select(DictMedicalCodeSet).where(DictMedicalCodeSet.code_set_code == code)):
            db.add(DictMedicalCodeSet(
                category_code=category,
                code_set_code=code,
                code_set_type=ctype,
                code_set_name_cn=name,
                enabled=True,
            ))


def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.execute(delete(DictSyncOutboxEvent).where(
            DictSyncOutboxEvent.business_key.like("plan:%")
        ))
        plan_ids = list(db.scalars(select(DictMedicalPushPlan.id).where(
            DictMedicalPushPlan.created_by.in_(["sim-dict-admin", "test-platform-admin"])
        )))
        if plan_ids:
            db.execute(delete(DictMedicalPushAction).where(DictMedicalPushAction.plan_id.in_(plan_ids)))
            db.execute(delete(DictMedicalPushPlan).where(DictMedicalPushPlan.id.in_(plan_ids)))
        codes = [DX_CODE, OP_CODE, DX_NAT, DX_INS, OP_NAT, OP_INS]
        db.execute(delete(DictMedicalCodeMapping).where(DictMedicalCodeMapping.from_item_code.in_(codes)))
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.item_code.in_(codes)))
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_sim_his_push"))
        db.commit()
    finally:
        db.close()


def test_official_maintain_and_push_dry_run_chain(client: TestClient, monkeypatch):
    _cleanup()
    db = SessionLocal()
    try:
        _ensure_code_sets(db)
        db.commit()
    finally:
        db.close()

    dict_admin = _bind_role_client(
        client,
        user="sim-dict-admin",
        token="test-token-sim-dict-admin",
        role_code="dict_admin",
    )

    dx = dict_admin.put("/api/v1/dict-medical/mapping-rows", json={
        "category_code": "diagnosis",
        "local_code": DX_CODE,
        "local_name": "模拟测试脑梗死",
        "dict_attribute": "院内扩展",
        "national_code": DX_NAT,
        "national_name": "模拟国临脑梗死",
        "insurance_code": DX_INS,
        "insurance_name": "模拟医保脑梗死",
        "infectious_disease_name": "",
        "status": "active",
    })
    assert dx.status_code == 200, dx.text
    assert dx.json()["data"]["local_code"] == DX_CODE

    op = dict_admin.put("/api/v1/dict-medical/mapping-rows", json={
        "category_code": "operation",
        "local_code": OP_CODE,
        "local_name": "模拟测试腹腔镜探查",
        "dict_attribute": "院内扩展",
        "national_code": OP_NAT,
        "national_name": "腹腔镜探查术",
        "insurance_code": OP_INS,
        "insurance_name": "腹腔镜探查术",
        "operation_level": "三",
        "operation_category": "手术",
        "performance_level4_flag": "否",
        "performance_minimally_invasive_flag": "是",
        "restricted_tech_flag": "否",
        "status": "active",
    })
    assert op.status_code == 200, op.text

    listed = dict_admin.get(
        "/api/v1/dict-medical/mapping-rows",
        params={"category_code": "diagnosis", "keyword": DX_CODE, "page_size": 20},
    )
    assert listed.status_code == 200, listed.text
    items = (listed.json().get("data") or {}).get("items") or []
    assert any(r["local_code"] == DX_CODE and r["national_code"] == DX_NAT for r in items)

    cfg = dict_admin.get("/api/v1/dict-medical/push/config")
    assert cfg.status_code == 200
    cfg_data = cfg.json()["data"]
    assert cfg_data["push_enabled"] is False
    assert "COMM.DIAGNOSIS_DICT" in cfg_data["whitelist_tables"]
    assert "COMM.OPERATION_DICT" in cfg_data["whitelist_tables"]

    preview = dict_admin.post("/api/v1/dict-medical/push/plan", json={
        "category_code": "diagnosis",
        "targets": ["HIS_SOURCE", "JHEMR_VASTBASE"],
        "item_codes": [DX_CODE],
        "max_items": 5,
        "include_jhdict": True,
        "check_remote": False,
    })
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()["data"]
    assert preview_data["status"] == "success"
    assert preview_data["action_count"] >= 1
    his_inserts = [a for a in preview_data["actions"] if a["target_table"] == "COMM.DIAGNOSIS_DICT"]
    assert his_inserts, preview_data["actions"]
    assert his_inserts[0]["sql"].startswith("INSERT INTO COMM.DIAGNOSIS_DICT")
    assert his_inserts[0]["params"]["diagnosis_code"] == DX_CODE
    assert ":diagnosis_code" in his_inserts[0]["sql"]

    created = dict_admin.post("/api/v1/dict-medical/push/plans", json={
        "category_code": "diagnosis",
        "target_systems": ["HIS_SOURCE", "JHEMR_VASTBASE"],
        "item_codes": [DX_CODE],
        "action_type": "insert",
    })
    assert created.status_code == 200, created.text
    plan = created.json()["data"]
    plan_id = plan["id"]
    assert plan["status"] == "draft"
    assert plan["item_count"] == 1
    assert plan["created_by"] == "sim-dict-admin"
    assert set(plan["target_systems"]) == {"HIS_SOURCE", "JHEMR_VASTBASE"}

    self_approve = dict_admin.post(f"/api/v1/dict-medical/push/plans/{plan_id}/approve", json={"note": "self"})
    assert self_approve.status_code == 400, self_approve.text

    approved = client.post(f"/api/v1/dict-medical/push/plans/{plan_id}/approve", json={"note": "sim dual-control"})
    assert approved.status_code == 200, approved.text
    approved_data = approved.json()["data"]
    assert approved_data["status"] == "approved"
    assert approved_data["approved_by"] == "test-platform-admin"
    assert approved_data["dispatch"]["status"] == "queued"

    intact = client.get(f"/api/v1/dict-medical/push/plans/{plan_id}/integrity")
    assert intact.status_code == 200
    assert intact.json()["data"]["intact"] is True

    executed = dict_admin.post(f"/api/v1/dict-medical/push/plans/{plan_id}/execute")
    assert executed.status_code == 200, executed.text
    exec_data = executed.json()["data"]
    assert exec_data["status"] == "dry_run_only"
    assert exec_data["plan_id"] == plan_id

    apply_one = dict_admin.post("/api/v1/dict-medical/push/apply-one", json={
        "action": his_inserts[0],
        "mode": "apply",
        "confirmation_token": "should-not-matter",
        "his_source_code": "his_source_10_10_10_15",
    })
    assert apply_one.status_code == 200, apply_one.text
    apply_data = apply_one.json()["data"]
    assert apply_data["mode"] == "dry_run"
    assert apply_data["executed"] is False
    assert apply_data.get("_notice")

    written: list[tuple] = []

    def fake_writer(source, dialect, sql, params):
        written.append((source.source_code, dialect, sql, params))
        return 1

    monkeypatch.setattr(settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(settings, "dict_medical_push_confirmation_token", "SIM-PUSH-OK")

    db = SessionLocal()
    try:
        db.add(AssetDataSource(
            system_code="HIS_SOURCE",
            source_code="pytest_sim_his_push",
            source_name_cn="sim his push",
            db_type="oracle",
            host_masked="localhost",
            target_host="127.0.0.1",
            port=1521,
            service_name="his",
            connection_mode="direct",
            write_policy="medical_dict_push",
            write_credential_ref="env:CRED_TEST_PUSH",
            environment="test",
            enabled=True,
        ))
        db.commit()
        action = build_his_diagnosis_insert({
            "local_code": DX_CODE,
            "local_name": "模拟测试脑梗死",
            "dict_attribute": "院内扩展",
            "national_code": DX_NAT,
            "national_name": "模拟国临脑梗死",
            "insurance_code": DX_INS,
            "insurance_name": "模拟医保脑梗死",
            "is_grey_insurance": False,
            "ybhm_to_write": None,
            "write_contrast": True,
            "mtb_code": "",
            "mtb_name": "",
            "icd_lr_code": "",
            "icd_lr_name": "",
            "infectious_name": "",
            "operation_level": "",
            "operation_category": "",
            "level4_flag": "",
            "mini_flag": "",
            "limit_flag": "",
        }).to_dict()
        result = apply_one_action(
            db,
            action,
            mode="apply",
            operator="pytest",
            confirmation_token="SIM-PUSH-OK",
            his_source_code="pytest_sim_his_push",
            writer=fake_writer,
        )
        assert result["executed"] is True
        assert result["rowcount"] == 1
        assert written and "INSERT INTO COMM.DIAGNOSIS_DICT" in written[0][2]
        assert written[0][3]["diagnosis_code"] == DX_CODE

        readonly_src = db.scalar(select(AssetDataSource).where(
            AssetDataSource.source_code == "his_source_10_10_10_15"
        ))
        assert readonly_src is not None
        assert (readonly_src.write_policy or "readonly").lower() != "medical_dict_push"
        blocked = False
        try:
            apply_one_action(
                db,
                action,
                mode="apply",
                operator="pytest",
                confirmation_token="SIM-PUSH-OK",
                his_source_code="his_source_10_10_10_15",
                writer=fake_writer,
            )
        except Exception as exc:
            blocked = True
            assert "not approved for medical dictionary push" in str(exc.detail if hasattr(exc, "detail") else exc)
        assert blocked, "readonly HIS source must not accept apply"
    finally:
        db.close()
        _cleanup()


def test_plan_push_actions_covers_operation_his_table(client: TestClient):
    _cleanup()
    db = SessionLocal()
    try:
        _ensure_code_sets(db)
        db.commit()
    finally:
        db.close()

    dict_admin = _bind_role_client(
        client,
        user="sim-dict-admin",
        token="test-token-sim-dict-admin",
        role_code="dict_admin",
    )
    saved = dict_admin.put("/api/v1/dict-medical/mapping-rows", json={
        "category_code": "operation",
        "local_code": OP_CODE,
        "local_name": "模拟测试腹腔镜探查",
        "dict_attribute": "院内扩展",
        "national_code": OP_NAT,
        "national_name": "腹腔镜探查术",
        "insurance_code": OP_INS,
        "insurance_name": "腹腔镜探查术",
        "operation_level": "三",
        "operation_category": "手术",
        "status": "active",
    })
    assert saved.status_code == 200, saved.text

    db = SessionLocal()
    try:
        plan = plan_push_actions(
            db,
            category_code="operation",
            targets=["HIS_SOURCE"],
            item_codes=[OP_CODE],
            max_items=5,
            include_jhdict=False,
        )
        assert plan["action_count"] >= 1
        assert any(a["target_table"] == "COMM.OPERATION_DICT" for a in plan["actions"])
        his = next(a for a in plan["actions"] if a["target_table"] == "COMM.OPERATION_DICT")
        assert his["params"]["operation_code"] == OP_CODE
        assert his["sql"].startswith("INSERT INTO COMM.OPERATION_DICT")
    finally:
        db.close()
        _cleanup()
