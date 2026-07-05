"""种子数据：插入 asset_govern_enum_values 初始枚举值"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.governance_base import GovernEnumValue

ENUMS = [
    # review_status
    ("review_status", "unreviewed", "未审核", 1),
    ("review_status", "draft", "草稿", 2),
    ("review_status", "reviewing", "审核中", 3),
    ("review_status", "approved", "已通过", 4),
    ("review_status", "rejected", "已拒绝", 5),
    ("review_status", "deprecated", "已废弃", 6),
    # approval_status
    ("approval_status", "draft", "草稿", 1),
    ("approval_status", "pending", "待审批", 2),
    ("approval_status", "approved", "已通过", 3),
    ("approval_status", "rejected", "已拒绝", 4),
    ("approval_status", "executed", "已执行", 5),
    ("approval_status", "failed", "执行失败", 6),
    ("approval_status", "cancelled", "已取消", 7),
    # validation_status
    ("validation_status", "verified", "已验证", 1),
    ("validation_status", "manual_reviewed", "人工复核", 2),
    ("validation_status", "rejected", "已拒绝", 3),
    ("validation_status", "needs_check", "需复查", 4),
    # account_status
    ("account_status", "active", "启用", 1),
    ("account_status", "disabled", "禁用", 2),
    ("account_status", "locked", "锁定", 3),
    ("account_status", "unknown", "未知", 4),
    # dict_status (P13)
    ("dict_status", "draft", "草稿", 1),
    ("dict_status", "published", "已发布", 2),
    ("dict_status", "rollback", "已回滚", 3),
    ("dict_status", "deprecated", "已废弃", 4),
    # change_type (F46)
    ("change_type", "table_added", "表新增", 1),
    ("change_type", "table_removed", "表删除", 2),
    ("change_type", "column_added", "字段新增", 3),
    ("change_type", "column_removed", "字段删除", 4),
    ("change_type", "column_type_changed", "字段类型变更", 5),
    ("change_type", "column_length_changed", "字段长度变更", 6),
    ("change_type", "column_nullable_changed", "字段可空性变更", 7),
    ("change_type", "column_comment_changed", "字段注释变更", 8),
]

def run():
    db = SessionLocal()
    try:
        for ec, vc, vn, so in ENUMS:
            e = db.query(GovernEnumValue).filter_by(enum_code=ec, value_code=vc).first()
            if not e:
                db.add(GovernEnumValue(enum_code=ec, value_code=vc, value_name_cn=vn, sort_order=so))
        db.commit()
        print(f"Inserted {len(ENUMS)} enum values")
    finally:
        db.close()

if __name__ == "__main__":
    run()
