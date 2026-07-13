"""Tests for relation recipes API."""
from fastapi.testclient import TestClient
import pytest

from app.core.db import SessionLocal
from app.models.recipe import AssetRelationRecipe


@pytest.fixture
def recipe():
    db = SessionLocal()
    try:
        item = AssetRelationRecipe(
            recipe_id="test_recipe_v1",
            status="verified",
            domain="test",
            description="test recipe for unit testing",
            primary_tables=[{"alias": "t", "table": "TEST.TABLE", "role": "test"}],
            joins=[{"join_id": "test_join", "type": "left_join", "from": "TEST.TABLE t", "to": "TEST.TABLE2 t2", "condition": "t.id = t2.id"}],
            ai_readable=True,
        )
        db.add(item)
        db.commit()
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
    resp = client.get("/api/v1/recipes?status=verified")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert [item["recipe_id"] for item in data["data"]["items"]] == [recipe.recipe_id]


def test_list_recipes_ai_context(client: TestClient, recipe: AssetRelationRecipe):
    resp = client.get("/api/v1/recipes/ai/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
    assert [item["recipe_id"] for item in data["data"]] == [recipe.recipe_id]


def test_get_recipe_detail(client: TestClient, recipe: AssetRelationRecipe):
    resp = client.get("/api/v1/recipes/test_recipe_v1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["description"] == "test recipe for unit testing"
    assert len(data["data"]["primary_tables"]) == 1
    assert len(data["data"]["joins"]) == 1


def test_get_recipe_not_found(client: TestClient):
    resp = client.get("/api/v1/recipes/nonexistent_recipe")
    assert resp.status_code == 404
