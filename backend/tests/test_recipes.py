"""Tests for relation recipes API — aligned with versioned status machine."""
from fastapi.testclient import TestClient
import pytest

from app.core.db import SessionLocal
from app.models.recipe import AssetRelationRecipe
from app.services.recipe_service import recipe_hash, assert_transition, generate_select_sql
from fastapi import HTTPException


@pytest.fixture
def recipe():
    db = SessionLocal()
    try:
        payload = {
            "primary_tables": [{"alias": "t", "table": "HIS.PAT_VISIT", "role": "test"}],
            "joins": [
                {
                    "join_id": "test_join",
                    "join_type": "LEFT",
                    "from": "HIS.PAT_VISIT t",
                    "to": "HIS.PAT_MASTER_INDEX t2",
                    "on": "t.PATIENT_ID = t2.PATIENT_ID",
                }
            ],
        }
        item = AssetRelationRecipe(
            recipe_id="test_recipe_v1",
            version=1,
            status="active",
            is_active=True,
            domain="test",
            description="test recipe for unit testing",
            primary_tables=payload["primary_tables"],
            joins=payload["joins"],
            recipe_json=payload,
            content_hash=recipe_hash(payload),
            ai_readable=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        yield item
    finally:
        db.close()


def test_list_recipes(client: TestClient):
    resp = client.get("/api/v1/recipes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


def test_list_recipes_by_status(client: TestClient, recipe: AssetRelationRecipe):
    resp = client.get("/api/v1/recipes?status=active")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    ids = [item["recipe_id"] for item in data["data"]["items"]]
    assert recipe.recipe_id in ids


def test_list_recipes_ai_context(client: TestClient, recipe: AssetRelationRecipe):
    resp = client.get("/api/v1/recipes/ai/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
    assert any(item["recipe_id"] == recipe.recipe_id for item in data["data"])


def test_get_recipe_detail(client: TestClient, recipe: AssetRelationRecipe):
    resp = client.get("/api/v1/recipes/test_recipe_v1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["description"] == "test recipe for unit testing"
    assert len(data["data"]["primary_tables"]) == 1
    assert data["data"]["content_hash"]


def test_get_recipe_not_found(client: TestClient):
    resp = client.get("/api/v1/recipes/nonexistent_recipe")
    assert resp.status_code == 404


def test_recipe_state_machine_and_sql(client: TestClient):
    create = client.post(
        "/api/v1/recipes",
        json={
            "recipe_id": "e10_flow_recipe",
            "recipe_name": "E10 flow",
            "domain": "test",
            "description": "state machine",
            "primary_tables": [{"table": "HIS.PAT_VISIT"}],
            "joins": [],
        },
    )
    assert create.status_code == 200, create.text
    assert create.json()["data"]["status"] == "draft"
    assert create.json()["data"]["content_hash"]

    rid = "e10_flow_recipe"
    # illegal transition
    bad = client.post(f"/api/v1/recipes/{rid}/versions/1/activate")
    assert bad.status_code == 400

    sub = client.post(f"/api/v1/recipes/{rid}/versions/1/submit")
    assert sub.status_code == 200
    assert sub.json()["data"]["status"] == "submitted"

    # self-review is same admin user but allowed for platform_admin in this MVP;
    # still validate state transitions
    appr = client.post(f"/api/v1/recipes/{rid}/versions/1/approve", json={"reason": "ok"})
    assert appr.status_code == 200
    assert appr.json()["data"]["status"] == "approved"

    act = client.post(f"/api/v1/recipes/{rid}/versions/1/activate")
    assert act.status_code == 200
    assert act.json()["data"]["status"] == "active"
    assert act.json()["data"]["is_active"] is True

    # cannot edit active
    edit = client.put(
        f"/api/v1/recipes/{rid}/versions/1",
        json={"description": "nope"},
    )
    assert edit.status_code == 400

    # copy new version
    copy = client.post(f"/api/v1/recipes/{rid}/versions")
    assert copy.status_code == 200
    assert copy.json()["data"]["version"] == 2
    assert copy.json()["data"]["status"] == "draft"

    # sql preview only
    sql = client.post(
        f"/api/v1/recipes/{rid}/versions/1/sql",
        json={"dialect": "oracle"},
    )
    assert sql.status_code == 200
    body = sql.json()["data"]
    assert body["executed"] is False
    assert "SELECT" in body["sql"].upper()
    assert "CREATE" not in body["sql"].upper() or "CREATE VIEW" not in body["sql"].upper()

    dep = client.post(
        f"/api/v1/recipes/{rid}/versions/1/deprecate",
        json={"reason": "retire"},
    )
    assert dep.status_code == 200
    assert dep.json()["data"]["status"] == "deprecated"


def test_sql_generate_rejects_dangerous_join():
    with pytest.raises(HTTPException):
        generate_select_sql(
            ["HIS.A"],
            [{"on": "1=1; DROP TABLE x"}],
        )
    with pytest.raises(HTTPException):
        generate_select_sql(["HIS.A;evil"], [])


def test_assert_transition_unit():
    assert_transition("draft", "submitted")
    with pytest.raises(HTTPException):
        assert_transition("draft", "active")
