"""Unit/API tests for medical dict push (plan 96 hard rules)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping, DictMedicalCodeSet
from app.services.medical_code_push import (
    _build_connector,
    _execute_write_sql,
    build_jhemr_diagnosis_dict_insert,
    build_stop_action,
    plan_push_actions,
    validate_push_sql,
    apply_one_action,
    _is_grey_insurance,
)


def test_validate_push_sql_rejects_batch_and_business_update():
    ok = validate_push_sql(
        "INSERT INTO COMM.DIAGNOSIS_DICT (DIAGNOSIS_CODE, DIAGNOSIS_NAME) VALUES (:a, :b)",
        action_type="insert",
        target_table="COMM.DIAGNOSIS_DICT",
    )
    assert ok.startswith("INSERT")

    try:
        validate_push_sql(
            "INSERT INTO COMM.DIAGNOSIS_DICT (DIAGNOSIS_CODE) VALUES (:a), (:b)",
            action_type="insert",
            target_table="COMM.DIAGNOSIS_DICT",
        )
        assert False, "multi-row should fail"
    except ValueError as exc:
        assert "multi-row" in str(exc).lower() or "VALUES" in str(exc)

    try:
        validate_push_sql(
            "UPDATE COMM.DIAGNOSIS_DICT SET STOP_FLAG=1 WHERE DIAGNOSIS_CODE IN ('A','B')",
            action_type="stop",
            target_table="COMM.DIAGNOSIS_DICT",
        )
        assert False, "IN list should fail"
    except ValueError as exc:
        assert "IN" in str(exc) or "in-list" in str(exc).lower()

    try:
        validate_push_sql(
            "UPDATE COMM.DIAGNOSIS_DICT SET DIAGNOSIS_NAME='x' WHERE DIAGNOSIS_CODE=:c",
            action_type="stop",
            target_table="COMM.DIAGNOSIS_DICT",
        )
        assert False, "business update should fail"
    except ValueError as exc:
        assert "business" in str(exc).lower() or "STOP" in str(exc)


def test_grey_insurance_detection():
    assert _is_grey_insurance("灰码", "", "")
    assert _is_grey_insurance("", "灰码", "")
    assert _is_grey_insurance("I63.800", "x", "source_marker_not_mapping")
    assert not _is_grey_insurance("I63.001", "名", "valid")


def test_jhemr_grey_ybhm_and_no_contrast(client: TestClient):
    db = SessionLocal()
    codes = ["PUSH_GREY_001", "PUSH_OK_001"]
    try:
        for code_set, name, ctype in [
            ("diagnosis_local_clinical", "院内临床", "clinical"),
            ("diagnosis_national_clinical_v2", "国临", "national"),
            ("diagnosis_insurance_v2", "医保", "insurance"),
        ]:
            if not db.scalar(select(DictMedicalCodeSet).where(DictMedicalCodeSet.code_set_code == code_set)):
                db.add(DictMedicalCodeSet(
                    category_code="diagnosis",
                    code_set_code=code_set,
                    code_set_type=ctype,
                    code_set_name_cn=name,
                    enabled=True,
                ))
        db.execute(delete(DictMedicalCodeMapping).where(DictMedicalCodeMapping.from_item_code.in_(codes)))
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.item_code.in_(codes + ["N_GREY", "N_OK", "I_GREY", "I_OK"])))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_local_clinical", item_code="PUSH_GREY_001",
            item_name_cn="灰码测试诊断", category_code="diagnosis", status="active",
            extra={"dict_attribute": "院内扩展", "insurance_mapping_status": "source_marker_not_mapping",
                   "insurance_raw_code": "灰码", "insurance_raw_name": "", "national_clinical_code": "N_GREY",
                   "national_clinical_name": "国临灰"},
        ))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_local_clinical", item_code="PUSH_OK_001",
            item_name_cn="正常对照诊断", category_code="diagnosis", status="active",
            extra={"dict_attribute": "院内扩展", "insurance_mapping_status": "valid",
                   "national_clinical_code": "N_OK", "national_clinical_name": "国临正",
                   "insurance_raw_code": "I_OK", "insurance_raw_name": "医保正"},
        ))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_national_clinical_v2", item_code="N_GREY",
            item_name_cn="国临灰", category_code="diagnosis", status="active",
        ))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_national_clinical_v2", item_code="N_OK",
            item_name_cn="国临正", category_code="diagnosis", status="active",
        ))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_insurance_v2", item_code="I_OK",
            item_name_cn="医保正", category_code="diagnosis", status="active",
        ))
        db.add(DictMedicalCodeMapping(
            category_code="diagnosis", from_code_set="diagnosis_local_clinical", from_item_code="PUSH_GREY_001",
            to_code_set="diagnosis_national_clinical_v2", to_item_code="N_GREY",
        ))
        db.add(DictMedicalCodeMapping(
            category_code="diagnosis", from_code_set="diagnosis_local_clinical", from_item_code="PUSH_OK_001",
            to_code_set="diagnosis_national_clinical_v2", to_item_code="N_OK",
        ))
        db.add(DictMedicalCodeMapping(
            category_code="diagnosis", from_code_set="diagnosis_local_clinical", from_item_code="PUSH_OK_001",
            to_code_set="diagnosis_insurance_v2", to_item_code="I_OK",
        ))
        db.commit()

        plan = plan_push_actions(
            db,
            category_code="diagnosis",
            targets=["JHEMR_VASTBASE"],
            item_codes=codes,
            max_items=10,
            hospital_no="H001",
            include_jhdict=False,
        )
        actions = plan["actions"]
        grey_dict = [a for a in actions if a["item_code"] == "PUSH_GREY_001" and a["target_table"] == "jhemr.diagnosis_dict"]
        grey_contrast = [a for a in actions if a["item_code"] == "PUSH_GREY_001" and "contrast" in a["target_table"]]
        ok_contrast = [a for a in actions if a["item_code"] == "PUSH_OK_001" and "contrast" in a["target_table"]]
        assert len(grey_dict) == 1
        assert grey_dict[0]["params"].get("ybhm") == "灰码"
        assert grey_contrast == []
        assert len(ok_contrast) == 1
        assert plan["summary"]["skipped_grey_or_empty_contrast"] >= 1
    finally:
        db.execute(delete(DictMedicalCodeMapping).where(DictMedicalCodeMapping.from_item_code.in_(codes)))
        db.execute(delete(DictMedicalCodeItem).where(
            DictMedicalCodeItem.item_code.in_(codes + ["N_GREY", "N_OK", "I_OK"])
        ))
        db.commit()
        db.close()


def test_apply_one_dry_run_and_apply_gate(client: TestClient, monkeypatch):
    row = {
        "local_code": "I63.0011",
        "local_name": "基底动脉血栓形成的急性脑梗死",
        "dict_attribute": "院内扩展",
        "national_code": "I63.001",
        "national_name": "基底动脉血栓形成脑梗死",
        "insurance_code": "I63.001",
        "insurance_name": "基底动脉血栓形成脑梗死",
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
    }
    action = build_jhemr_diagnosis_dict_insert(row, "H001").to_dict()

    # API dry_run
    resp = client.post("/api/v1/dict-medical/push/apply-one", json={"action": action, "mode": "dry_run"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["mode"] == "dry_run"
    assert data["executed"] is False

    # apply-one 已被 101号整改为"仅 dry_run"，不再受写开关控制（forced_mode = "dry_run"）
    # 验证：即使传 mode=apply，也强制降级为 dry_run 预览，并返回 _notice 提示
    monkeypatch.setattr("app.services.medical_code_push.settings.dict_medical_push_enabled", False)
    resp2 = client.post("/api/v1/dict-medical/push/apply-one", json={
        "action": action,
        "mode": "apply",
        "confirmation_token": "x",
        "jhemr_source_code": "any",
    })
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["mode"] == "dry_run"
    assert data2["executed"] is False
    assert data2.get("_notice") is not None
    assert "dry_run" in data2["_notice"].lower() or "关闭" in data2["_notice"]


def test_stop_one_sql_shape():
    act = build_stop_action(
        category_code="diagnosis",
        target_system="HIS_SOURCE",
        item_code="I63.0011",
    )
    sql = validate_push_sql(act.sql, action_type="stop", target_table=act.target_table)
    assert "STOP_FLAG" in sql.upper()
    assert "I63.0011" not in sql  # parameterized
    assert "IN (" not in sql.upper()


def test_push_plan_api(client: TestClient):
    db = SessionLocal()
    try:
        if not db.scalar(select(DictMedicalCodeSet).where(DictMedicalCodeSet.code_set_code == "diagnosis_local_clinical")):
            db.add(DictMedicalCodeSet(
                category_code="diagnosis",
                code_set_code="diagnosis_local_clinical",
                code_set_type="clinical",
                code_set_name_cn="院内临床",
                enabled=True,
            ))
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.item_code == "PUSH_API_001"))
        db.add(DictMedicalCodeItem(
            code_set_code="diagnosis_local_clinical",
            item_code="PUSH_API_001",
            item_name_cn="API计划测试",
            category_code="diagnosis",
            status="active",
            extra={"dict_attribute": "院内扩展", "national_clinical_code": "N1", "national_clinical_name": "国1"},
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/dict-medical/push/plan", json={
        "category_code": "diagnosis",
        "targets": ["HIS_SOURCE"],
        "item_codes": ["PUSH_API_001"],
        "max_items": 5,
        "include_jhdict": False,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["action_count"] >= 1
    assert data["hard_rules"]["single_row_only"] is True
    assert any(a["target_table"] == "COMM.DIAGNOSIS_DICT" for a in data["actions"])

    cfg = client.get("/api/v1/dict-medical/push/config")
    assert cfg.status_code == 200
    assert "whitelist_tables" in cfg.json()["data"]

    exp = client.post("/api/v1/dict-medical/push/export-preview", json={
        "category_code": "diagnosis",
        "item_codes": ["PUSH_API_001"],
        "max_items": 5,
    })
    assert exp.status_code == 200
    assert exp.json()["data"]["total"] >= 1

    db = SessionLocal()
    try:
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.item_code == "PUSH_API_001"))
        db.commit()
    finally:
        db.close()


def test_apply_one_with_fake_writer(monkeypatch):
    from app.core.config import settings
    from app.models.asset_system import AssetDataSource
    from sqlalchemy import select

    monkeypatch.setattr(settings, "dict_medical_push_enabled", True)
    monkeypatch.setattr(settings, "dict_medical_push_confirmation_token", "PUSH-OK")

    db = SessionLocal()
    written = []

    def fake_writer(source, dialect, sql, params):
        written.append((source.source_code, dialect, sql, params))
        return 1

    try:
        src = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == "pytest_push_jhemr"))
        if src is None:
            db.add(AssetDataSource(
                system_code="JHEMR_VASTBASE",
                source_code="pytest_push_jhemr",
                source_name_cn="pytest push",
                db_type="vastbase",
                host_masked="localhost",
                target_host="localhost",
                port=5432,
                database_name="jhemr",
                connection_mode="direct",
                write_policy="medical_dict_push",
                write_credential_ref="env:CRED_TEST_PUSH",
                environment="test",
                enabled=True,
            ))
            db.commit()

        row = {
            "local_code": "I63.TEST1",
            "local_name": "测试写",
            "dict_attribute": "院内扩展",
            "national_code": "I63.T",
            "national_name": "测",
            "insurance_code": "",
            "insurance_name": "",
            "is_grey_insurance": False,
            "ybhm_to_write": None,
            "write_contrast": False,
            "mtb_code": "", "mtb_name": "", "icd_lr_code": "", "icd_lr_name": "",
            "infectious_name": "", "operation_level": "", "operation_category": "",
            "level4_flag": "", "mini_flag": "", "limit_flag": "",
        }
        action = build_jhemr_diagnosis_dict_insert(row, "H001").to_dict()
        result = apply_one_action(
            db,
            action,
            mode="apply",
            operator="pytest",
            confirmation_token="PUSH-OK",
            jhemr_source_code="pytest_push_jhemr",
            writer=fake_writer,
        )
        assert result["executed"] is True
        assert result["rowcount"] == 1
        assert len(written) == 1
        assert "INSERT INTO jhemr.diagnosis_dict" in written[0][2]
    finally:
        db.execute(delete(AssetDataSource).where(AssetDataSource.source_code == "pytest_push_jhemr"))
        db.commit()
        db.close()


def test_medical_push_never_falls_back_to_readonly_credentials():
    from app.models.asset_system import AssetDataSource

    source = AssetDataSource(
        system_code="HIS_SOURCE",
        source_code="pytest_no_write_credential",
        db_type="oracle",
        target_host="127.0.0.1",
        port=1521,
        service_name="his",
        write_policy="medical_dict_push",
        credential_ref="env:READONLY_MUST_NOT_BE_USED",
        write_credential_ref=None,
    )
    try:
        _build_connector(source, write=True)
        assert False, "write connector must require a dedicated write credential"
    except Exception as exc:
        assert "dedicated write credential" in str(exc)

    try:
        _execute_write_sql(source, "oracle", "SELECT 1 FROM DUAL", {})
        assert False, "write execution must require a dedicated write credential"
    except Exception as exc:
        assert "dedicated write credentials" in str(exc)
