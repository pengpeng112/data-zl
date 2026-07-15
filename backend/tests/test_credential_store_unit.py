"""Unit tests for credential_store (no DB)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services import credential_store


def test_mask_username():
    assert credential_store.mask_username("ab") == "a*"
    assert credential_store.mask_username("readonly_user").startswith("r")
    assert credential_store.mask_username("readonly_user").endswith("r")
    assert "*" in credential_store.mask_username("readonly_user")


def test_path_traversal_rejected():
    with pytest.raises(credential_store.CredentialStoreError):
        credential_store._safe_source_code("../etc/passwd")
    with pytest.raises(credential_store.CredentialStoreError):
        credential_store._safe_source_code("a/b")


def test_store_rotate_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_CREDENTIAL_DIR", str(tmp_path))
    # reload path resolution uses env
    ref = credential_store.store("demo_src", "readonly_user", "s3cret")
    assert ref.startswith("file://")
    path = Path(ref[7:])
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "readonly_user:s3cret"
    assert credential_store.status("demo_src") == "configured"

    ref2 = credential_store.rotate("demo_src", "u2", "p2")
    assert Path(ref2[7:]).read_text(encoding="utf-8") == "u2:p2"

    credential_store.delete("demo_src")
    assert credential_store.status("demo_src") == "missing"


def test_pending_activate(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_CREDENTIAL_DIR", str(tmp_path))
    pending = credential_store.store("pend_src", "u", "p", activate=False)
    assert pending.endswith(".pending") or "pending" in pending
    final = credential_store.activate(pending, "pend_src")
    assert credential_store.status("pend_src") == "configured"
    assert Path(final[7:]).exists()
