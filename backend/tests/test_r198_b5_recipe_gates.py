"""198 B5 / T11-T12：配方 API 治理门禁（隔离库集成）。

create 允许知识型 dict joins 入库（readiness 标记），submit/activate/生成端
按结构校验拒绝；单表合法配方不得被过度校验误伤。
"""
from fastapi.testclient import TestClient


def _create(client: TestClient, recipe_id: str, **overrides):
    body = {
        "recipe_id": recipe_id,
        "recipe_name": recipe_id,
        "domain": "r198",
        "primary_tables": ["OUTP_RCPT_MASTER", "OUTP_BILL_ITEMS", "OUTP_ORDER_DESC"],
        "joins": {
            "time_fields": ["VISIT_DATE", "CHARGE_DATE_TIME"],
            "dedup_strategy": "明细↔开单必须三列复合键（RCPT_NO+VISIT_NO+VISIT_DATE）",
            "join_family_ids": ["S2F-B460DFC719"],
        },
    }
    body.update(overrides)
    return client.post("/api/v1/recipes", json=body)


def test_create_dict_joins_marks_not_executable(client: TestClient):
    resp = _create(client, "r198-knowledge-recipe")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["recipe_json"]["readiness"] == "not_executable"
    assert data["recipe_json"]["not_ready_reasons"]
    assert any("知识型" in r for r in data["recipe_json"]["not_ready_reasons"])


def test_submit_rejects_dict_join_draft(client: TestClient):
    rid = "r198-knowledge-recipe-submit"
    assert _create(client, rid).status_code == 200
    resp = client.post(f"/api/v1/recipes/{rid}/versions/1/submit")
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "recipe_structure_invalid"
    assert any("知识型" in r for r in detail["reasons"])


def test_sql_generate_rejects_dict_join_draft(client: TestClient):
    rid = "r198-knowledge-recipe-sql"
    assert _create(client, rid).status_code == 200
    resp = client.post(f"/api/v1/recipes/{rid}/versions/1/sql", json={"dialect": "oracle"})
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "recipe_not_executable"
    assert detail["reasons"]


def test_create_rejects_illegal_table_identifier(client: TestClient):
    resp = _create(
        client,
        "r198-bad-table-recipe",
        primary_tables=["DRUG_IMPORT_MASTER/DETAIL", "DRUG_STOCK"],
        joins=[],
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "invalid_table_identifier"


def test_valid_recipe_full_flow_not_overblocked(client: TestClient):
    rid = "r198-valid-flow"
    create = client.post(
        "/api/v1/recipes",
        json={
            "recipe_id": rid,
            "recipe_name": "r198 valid",
            "domain": "r198",
            "primary_tables": ["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"],
            "joins": [
                {
                    "join_type": "INNER",
                    "on": "HIS.PAT_VISIT.PATIENT_ID = HIS.PAT_MASTER_INDEX.PATIENT_ID",
                }
            ],
        },
    )
    assert create.status_code == 200, create.text
    assert create.json()["data"]["recipe_json"]["readiness"] == "ready"
    assert client.post(f"/api/v1/recipes/{rid}/versions/1/submit").status_code == 200
    assert client.post(f"/api/v1/recipes/{rid}/versions/1/approve", json={"reason": "r198"}).status_code == 200
    activate = client.post(f"/api/v1/recipes/{rid}/versions/1/activate")
    assert activate.status_code == 200, activate.text
    sql = client.post(f"/api/v1/recipes/{rid}/versions/1/sql", json={"dialect": "oracle"})
    assert sql.status_code == 200, sql.text
    body = sql.json()["data"]
    assert body["executed"] is False
    assert "INNER JOIN HIS.PAT_MASTER_INDEX ON" in body["sql"]


def test_empty_on_recipe_blocked_at_submit(client: TestClient):
    rid = "r198-empty-on"
    create = client.post(
        "/api/v1/recipes",
        json={
            "recipe_id": rid,
            "recipe_name": "r198 empty on",
            "domain": "r198",
            "primary_tables": ["HIS.PAT_VISIT", "HIS.PAT_MASTER_INDEX"],
            "joins": [{"join_type": "LEFT", "on": ""}],
        },
    )
    assert create.status_code == 200, create.text  # draft 允许未完备
    # 未完备必须在 recipe_json 内机器可读标记（readiness + not_ready_reasons）
    assert create.json()["data"]["recipe_json"]["readiness"] == "not_executable"
    assert any("空 ON" in r for r in create.json()["data"]["recipe_json"]["not_ready_reasons"])
    resp = client.post(f"/api/v1/recipes/{rid}/versions/1/submit")
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "recipe_structure_invalid"
    assert any("空 ON" in r for r in detail["reasons"])
