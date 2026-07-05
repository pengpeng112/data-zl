"""种子数据：插入 asset_quality_rules 初始质量规则"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.quality import QualityRule

RULES = [
    ("SOURCE_CONNECTIVITY", "数据源连通性检测", "source", "metadata_only", "检查数据源连接是否可用"),
    ("TABLE_NO_CN_NAME", "表缺少中文名", "table", "metadata_only", "表缺少中文名相关提示"),
    ("COLUMN_NO_CN_NAME", "字段缺少中文名", "column", "metadata_only", "字段缺少中文名或注释"),
    ("COLUMN_SENSITIVE_UNMARKED", "敏感字段未标识", "column", "metadata_only", "疑似敏感字段但未标记"),
    ("RELATION_NOT_REVIEWED", "关系未复核", "relation", "metadata_only", "关系未经过人工复核"),
    ("CANDIDATE_TOO_MANY", "候选关系积压", "source", "metadata_only", "候选关系长期未处理"),
    ("SOURCE_METADATA_STALE", "元数据过旧", "source", "metadata_only", "元数据快照超过阈值未更新"),
    ("SAMPLE_ORPHAN_RATE", "小样本孤儿率", "relation", "sample_query", "小样本孤儿率检查（需白名单）"),
]

def run():
    db = SessionLocal()
    try:
        for rc, desc, tt, em, detail in RULES:
            r = db.query(QualityRule).filter_by(rule_code=rc).first()
            if not r:
                db.add(QualityRule(rule_code=rc, rule_type="quality", target_type=tt, execution_mode=em, description=f"{desc}。{detail}"))
        db.commit()
        print(f"Inserted {len(RULES)} quality rules")
    finally:
        db.close()

if __name__ == "__main__":
    run()
