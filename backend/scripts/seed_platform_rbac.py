"""Seed builtin roles + default permissions + ensure platform-admin role binding.

Safe for platform DB only. Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal
from app.api.v1.permissions import BUILTIN_ROLES, ROLE_DEFAULT_PERMISSIONS, RESOURCE_CATALOG
from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole


def run() -> None:
    db = SessionLocal()
    try:
        for r in BUILTIN_ROLES:
            row = db.query(AssetRole).filter_by(role_code=r["role_code"]).first()
            if not row:
                db.add(
                    AssetRole(
                        role_code=r["role_code"],
                        role_name_cn=r["role_name_cn"],
                        role_type=r.get("role_type") or "builtin",
                        description=r.get("description"),
                    )
                )
        db.flush()

        for role_code, perms in ROLE_DEFAULT_PERMISSIONS.items():
            existing = {
                p.resource
                for p in db.query(AssetRolePermission).filter_by(role_code=role_code).all()
            }
            for code in perms:
                if code in existing:
                    continue
                db.add(
                    AssetRolePermission(
                        role_code=role_code,
                        resource=code,
                        action="allow",
                    )
                )

        # ensure platform-admin user_identifier has platform_admin role
        ur = (
            db.query(AssetUserRole)
            .filter_by(user_identifier="platform-admin", role_code="platform_admin")
            .first()
        )
        if not ur:
            db.add(
                AssetUserRole(
                    user_identifier="platform-admin",
                    role_code="platform_admin",
                    granted_by="seed_platform_rbac",
                )
            )

        db.commit()
        n_roles = db.query(AssetRole).count()
        n_perms = db.query(AssetRolePermission).count()
        print(f"seed_ok roles={n_roles} permissions={n_perms} catalog={len(RESOURCE_CATALOG)}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
