"""E9 permission matching unit tests (no DB)."""
from app.core.security import _permission_matches


def test_permission_wildcard_and_legacy_forms():
    assert _permission_matches("*", "identity.person.view")
    assert _permission_matches("*:*", "ops:sql:execute")
    assert _permission_matches("identity.person.view", "identity.person.view")
    assert _permission_matches("identity:person:view", "identity.person.view")
    assert _permission_matches("ops.sql.execute", "ops:sql:execute")
    assert not _permission_matches("ops.sql.view", "ops:sql:execute")


def test_recipe_transition_matrix():
    from app.services.recipe_service import assert_transition
    from fastapi import HTTPException
    import pytest

    assert_transition("draft", "submitted")
    assert_transition("submitted", "approved")
    assert_transition("submitted", "draft")  # reject
    assert_transition("approved", "active")
    assert_transition("active", "deprecated")
    with pytest.raises(HTTPException):
        assert_transition("active", "draft")
    with pytest.raises(HTTPException):
        assert_transition("deprecated", "active")
