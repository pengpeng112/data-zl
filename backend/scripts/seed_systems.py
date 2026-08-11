"""种子数据：插入 asset_systems 初始系统"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.asset_system import AssetSystem
from app.services.asset_catalog import CANONICAL_SYSTEMS

SYSTEM_TYPES = {"DATA_CENTER": "ODS", "HIS_SOURCE": "HIS", "HRP": "HRP", "JHEMR_VASTBASE": "EMR", "DOCARE": "ANESTHESIA", "MOBILE_NURSING": "NURSING", "LIS_SOURCE": "LIS", "PACS_SOURCE": "PACS", "PAPERLESS_CDMS": "CDMS", "ULTRASOUND_ENDOSCOPY": "OTHER"}
SYSTEMS = [{"system_code": code, "system_name_cn": name, "system_type": SYSTEM_TYPES.get(code, "business")} for code, name in CANONICAL_SYSTEMS.items()]

def run():
    db = SessionLocal()
    try:
        for s in SYSTEMS:
            existing = db.query(AssetSystem).filter_by(system_code=s["system_code"]).first()
            if not existing:
                db.add(AssetSystem(**s))
            elif not (existing.system_name_cn or "").strip():
                existing.system_name_cn = s["system_name_cn"]
        db.commit()
        print(f"Inserted {len(SYSTEMS)} systems")
    finally:
        db.close()

if __name__ == "__main__":
    run()
