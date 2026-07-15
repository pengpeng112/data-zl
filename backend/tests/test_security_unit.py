from app.core.security import _permission_matches


def test_permission_match_accepts_legacy_and_colon_codes():
    assert _permission_matches("identity.person.view", "identity:person:view")
    assert _permission_matches("identity/person/view", "identity:person:view")
    assert not _permission_matches("identity:person:view", "identity:person:edit")


def test_permission_match_accepts_wildcards():
    assert _permission_matches("*", "recipe:edit")
    assert _permission_matches("*:*:*", "recipe:edit")
