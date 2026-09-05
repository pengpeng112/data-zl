# -*- coding: utf-8 -*-
"""仅用于 data_asset_test：从 round-3 脱敏导出重建 169 浏览器验收基准。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models.asset import AssetColumn, AssetRelation, AssetTable
from app.models.governance import ApiKey
from app.models.governance_base import AssetRole, AssetUserRole
from app.services.relation_identity import derive_layer

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "verify" / "round-3" / "graph_data_export.json"
TOKEN = "verify-token-graph-r3-0001"
USER = "accept169"


def assert_test_database() -> None:
    raw = os.environ.get("APP_TEST_DB_URL", "")
    parsed = urlparse(raw.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path.rstrip("/") != "/data_asset_test":
        raise RuntimeError("refuse: APP_TEST_DB_URL must target local data_asset_test")


def main() -> None:
    assert_test_database()
    payload = json.loads(EXPORT.read_text(encoding="utf-8"))
    tables = payload["tables"]
    relations = payload["relations"]
    if len(tables) != 12702 or len(relations) != 1329:
        raise RuntimeError(f"unexpected fixture size: tables={len(tables)} relations={len(relations)}")
    for relation in relations:
        relation["relation_layer"] = derive_layer(relation.get("confidence"), relation.get("validation_status"))

    db = SessionLocal()
    try:
        db.execute(delete(AssetRelation))
        db.execute(delete(AssetColumn))
        db.execute(delete(AssetTable))
        db.bulk_insert_mappings(AssetTable, tables)
        db.bulk_insert_mappings(AssetRelation, relations)

        key = db.query(ApiKey).filter(ApiKey.key_name == "accept-r169").first()
        if key is None:
            key = ApiKey(key_name="accept-r169")
            db.add(key)
        key.token = None
        key.token_hash = hashlib.sha256(TOKEN.encode("utf-8")).hexdigest()
        key.user_identifier = USER
        key.enabled = True
        if not db.query(AssetRole).filter(AssetRole.role_code == "platform_admin").first():
            db.add(AssetRole(role_code="platform_admin", role_name_cn="平台管理员", role_type="builtin"))
        if not db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == USER,
            AssetUserRole.role_code == "platform_admin",
        ).first():
            db.add(AssetUserRole(user_identifier=USER, role_code="platform_admin", status="active"))
        db.commit()
        print(f"RESTORED tables={len(tables)} relations={len(relations)} token_bound=true")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
