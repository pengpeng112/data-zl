"""Local account auth: password, lockout, JWT, sessions, admin bootstrap, RBAC."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models.auth import AuthLoginEvent, AuthSession, AuthUser
from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole
from app.services import auth_service
from scripts.create_local_admin import create_local_admin


def _csrf_headers(**extra):
    h = {"X-Requested-With": "XMLHttpRequest"}
    h.update(extra)
    return h


def _make_password() -> str:
    # Test-only synthetic password; never assert plaintext appears in responses.
    return f"Tp{secrets.token_hex(4)}!A1x"


def test_password_hash_and_verify():
    pw = _make_password()
    h = auth_service.hash_password(pw)
    assert h != pw
    assert h.startswith("$argon2")
    assert auth_service.verify_password(pw, h)
    assert not auth_service.verify_password("definitely-wrong", h)


def test_jwt_roundtrip():
    user = AuthUser(
        id=1,
        username="jwt-user",
        password_hash="x",
        user_identifier="jwt-uid",
        enabled=True,
    )
    token, expires = auth_service.create_access_token(user, ["platform_admin"])
    assert expires > datetime.now(timezone.utc)
    payload = auth_service.decode_access_token(token)
    assert payload is not None
    assert payload["username"] == "jwt-user"
    assert payload["user_identifier"] == "jwt-uid"
    assert "platform_admin" in payload["roles"]
    assert auth_service.decode_access_token("not.a.jwt") is None


def test_login_success_and_wrong_password_unified(client: TestClient):
    password = _make_password()
    username = f"u_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
        )
        db.add(AssetUserRole(user_identifier=username, role_code="platform_admin"))
        db.commit()
    finally:
        db.close()

    bare = TestClient(app)
    bad = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "WrongPass!!99"},
        headers=_csrf_headers(),
    )
    missing = bare.post(
        "/api/v1/auth/login",
        json={"username": "no_such_user_zzz", "password": "WrongPass!!99"},
        headers=_csrf_headers(),
    )
    assert bad.status_code == 401
    assert missing.status_code == 401
    # Unified failure message — no account-existence leak
    assert bad.json().get("detail") == missing.json().get("detail")

    ok = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body.get("success") is True or body.get("code") == 0
    data = body["data"]
    assert data.get("accessToken")
    # Response must not echo password fields
    raw = ok.text.lower()
    assert "password" not in raw or "must_change_password" in raw
    assert password not in ok.text


def test_login_refresh_logout_rotation(client: TestClient):
    password = _make_password()
    username = f"u_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
        )
        db.add(AssetUserRole(user_identifier=username, role_code="platform_admin"))
        db.commit()
    finally:
        db.close()

    bare = TestClient(app)
    r = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert r.status_code == 200
    access = r.json()["data"]["accessToken"]
    assert bare.get("/api/v1/summary", headers={"Authorization": f"Bearer {access}"}).status_code == 200

    bare.cookies.update(r.cookies)
    r3 = bare.post("/api/v1/auth/refresh", headers=_csrf_headers())
    assert r3.status_code == 200
    new_access = r3.json()["data"]["accessToken"]
    assert new_access

    bare.cookies.update(r3.cookies)
    assert (
        bare.post(
            "/api/v1/auth/logout",
            headers={**_csrf_headers(), "Authorization": f"Bearer {new_access}"},
        ).status_code
        == 200
    )
    assert bare.post("/api/v1/auth/refresh", headers=_csrf_headers()).status_code in (401, 403)


def test_disabled_account(client: TestClient):
    password = _make_password()
    username = f"dis_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        user = auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
            enabled=False,
        )
        db.commit()
        assert user.enabled is False
    finally:
        db.close()

    bare = TestClient(app)
    r = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert r.status_code == 401
    assert r.json().get("detail") == auth_service.GENERIC_LOGIN_FAILURE


def test_lockout_after_failures(client: TestClient):
    password = _make_password()
    username = f"lock_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
        )
        db.commit()
    finally:
        db.close()

    bare = TestClient(app)
    for _ in range(settings.auth_max_failed_login):
        r = bare.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "WrongPass1!xx"},
            headers=_csrf_headers(),
        )
        assert r.status_code == 401

    r = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert r.status_code == 401

    db = SessionLocal()
    try:
        user = db.scalar(select(AuthUser).where(AuthUser.username == username))
        assert user is not None
        assert user.locked_until is not None
    finally:
        db.close()


def test_change_password_revokes_sessions(client: TestClient):
    password = _make_password()
    new_password = _make_password()
    username = f"cp_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        user = auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
        )
        db.add(AssetUserRole(user_identifier=username, role_code="platform_admin"))
        db.commit()
        user_id = user.id
    finally:
        db.close()

    bare = TestClient(app)
    login = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert login.status_code == 200
    access = login.json()["data"]["accessToken"]
    bare.cookies.update(login.cookies)

    # second session
    bare2 = TestClient(app)
    login2 = bare2.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert login2.status_code == 200
    bare2.cookies.update(login2.cookies)

    ch = bare.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": new_password},
        headers={**_csrf_headers(), "Authorization": f"Bearer {access}"},
    )
    assert ch.status_code == 200, ch.text

    db = SessionLocal()
    try:
        sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)).all()
        assert sessions
        assert all(s.revoked_at is not None for s in sessions)
    finally:
        db.close()

    # old refresh cookies must fail
    assert bare.post("/api/v1/auth/refresh", headers=_csrf_headers()).status_code in (401, 403)
    assert bare2.post("/api/v1/auth/refresh", headers=_csrf_headers()).status_code in (401, 403)


def test_create_local_admin_idempotent(client: TestClient, monkeypatch):
    username = f"adm_{secrets.token_hex(3)}"
    password = _make_password()
    # Avoid creating real API keys repeatedly if create_token hits DB — use no token
    r1 = create_local_admin(
        username=username,
        user_identifier=username,
        password=password,
        password_source="caller",
        issue_api_token=False,
        force=False,
    )
    assert r1["action"] == "created"
    assert r1["must_change_password"] is True

    with pytest.raises(SystemExit):
        create_local_admin(
            username=username,
            user_identifier=username,
            password=password,
            password_source="caller",
            issue_api_token=False,
            force=False,
        )

    r2 = create_local_admin(
        username=username,
        user_identifier=username,
        password=_make_password(),
        password_source="caller",
        issue_api_token=False,
        force=True,
    )
    assert r2["action"] == "reset"

    db = SessionLocal()
    try:
        roles = db.scalars(
            select(AssetUserRole).where(
                AssetUserRole.user_identifier == username,
                AssetUserRole.role_code == "platform_admin",
            )
        ).all()
        assert len(roles) == 1
        user = db.scalar(select(AuthUser).where(AuthUser.username == username))
        assert user is not None
        assert user.must_change_password is True
    finally:
        db.close()


def test_login_audit_has_no_secrets(client: TestClient):
    password = _make_password()
    username = f"aud_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
        )
        db.commit()
    finally:
        db.close()

    bare = TestClient(app)
    bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "WrongPass1!xx"},
        headers=_csrf_headers(),
    )
    bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )

    db = SessionLocal()
    try:
        events = db.scalars(
            select(AuthLoginEvent).where(AuthLoginEvent.username == username)
        ).all()
        assert len(events) >= 2
        for ev in events:
            blob = f"{ev.username}|{ev.user_identifier}|{ev.result}|{ev.reason_code}|{ev.client_ip_masked}"
            assert password not in blob
            assert "Bearer" not in blob
            assert "$argon2" not in blob
    finally:
        db.close()


def test_api_key_still_works(client: TestClient):
    r = client.get("/api/v1/summary")
    assert r.status_code == 200


def test_unbound_token_denied_on_admin(client: TestClient):
    raw = secrets.token_urlsafe(24)
    db = SessionLocal()
    try:
        db.add(
            ApiKey(
                key_name=f"unbound-{secrets.token_hex(3)}",
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                user_identifier=None,
            )
        )
        db.commit()
    finally:
        db.close()

    bare = TestClient(app, headers={"Authorization": f"Bearer {raw}"})
    r = bare.get("/api/v1/admin/keys")
    assert r.status_code == 403


def test_jwt_and_api_key_dual_credential(client: TestClient):
    """Human JWT and machine API key both work against protected read routes."""
    password = _make_password()
    username = f"dual_{secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        auth_service.create_local_user(
            db,
            username=username,
            password=password,
            user_identifier=username,
            must_change_password=False,
        )
        db.add(AssetUserRole(user_identifier=username, role_code="platform_admin"))
        db.commit()
    finally:
        db.close()

    bare = TestClient(app)
    login = bare.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_csrf_headers(),
    )
    assert login.status_code == 200
    jwt_token = login.json()["data"]["accessToken"]
    assert bare.get("/api/v1/summary", headers={"Authorization": f"Bearer {jwt_token}"}).status_code == 200
    # fixture client uses API key
    assert client.get("/api/v1/summary").status_code == 200
