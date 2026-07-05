"""种子数据：插入 asset_systems 初始系统"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.asset_system import AssetSystem

SYSTEMS = [
    {"system_code": "DATA_CENTER", "system_name_cn": "数据中心/ODS", "system_type": "ODS"},
    {"system_code": "HIS_SOURCE", "system_name_cn": "HIS 源端", "system_type": "HIS"},
    {"system_code": "LIS", "system_name_cn": "检验系统", "system_type": "LIS"},
    {"system_code": "PACS", "system_name_cn": "影像系统", "system_type": "PACS"},
    {"system_code": "EMR", "system_name_cn": "电子病历", "system_type": "EMR"},
    {"system_code": "MOBILE_NURSING", "system_name_cn": "移动护理", "system_type": "NURSING"},
    {"system_code": "SM", "system_name_cn": "手麻系统", "system_type": "OTHER"},
]

def run():
    db = SessionLocal()
    try:
        for s in SYSTEMS:
            existing = db.query(AssetSystem).filter_by(system_code=s["system_code"]).first()
            if not existing:
                db.add(AssetSystem(**s))
        db.commit()
        print(f"Inserted {len(SYSTEMS)} systems")
    finally:
        db.close()

if __name__ == "__main__":
    run()
