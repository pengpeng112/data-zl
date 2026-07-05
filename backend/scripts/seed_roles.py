"""种子数据：插入 asset_roles 初始角色"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.governance_base import AssetRole

ROLES = [
    {"role_code": "platform_admin", "role_name_cn": "平台管理员", "role_type": "platform"},
    {"role_code": "asset_viewer", "role_name_cn": "资产查看者", "role_type": "asset"},
    {"role_code": "ops_admin", "role_name_cn": "运维管理员", "role_type": "ops"},
    {"role_code": "identity_admin", "role_name_cn": "人员科室管理员", "role_type": "identity"},
    {"role_code": "quality_admin", "role_name_cn": "质量管理管理员", "role_type": "quality"},
    {"role_code": "approver", "role_name_cn": "审批人", "role_type": "govern"},
]

def run():
    db = SessionLocal()
    try:
        for r in ROLES:
            e = db.query(AssetRole).filter_by(role_code=r["role_code"]).first()
            if not e:
                db.add(AssetRole(**r))
        db.commit()
        print(f"Inserted {len(ROLES)} roles")
    finally:
        db.close()

if __name__ == "__main__":
    run()
