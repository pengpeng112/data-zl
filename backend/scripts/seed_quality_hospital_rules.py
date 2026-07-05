"""种子数据：插入医院级质控模板规则（14 条，默认 disabled）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.quality import QualityRule

HOSPITAL_RULES = [
    {
        "rule_code": "R_COMMON_001", "rule_name": "ID 主键唯一性校验",
        "rule_category": "UNIQUE", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "通用", "rule_type": "primary_key_duplicate",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查主键或业务主键是否存在重复值",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_COMMON_002", "rule_name": "必填字段空值校验",
        "rule_category": "COMPLETE", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "通用", "rule_type": "required_empty",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查必填字段是否存在空值",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_COMMON_003", "rule_name": "字段长度超长校验",
        "rule_category": "STANDARD", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "通用", "rule_type": "length_overflow",
        "execution_mode": "sql_template", "error_level": "minor",
        "description": "检查字段值是否超过定义长度",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_COMMON_004", "rule_name": "值域代码合法性校验",
        "rule_category": "STANDARD", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "通用", "rule_type": "value_domain_invalid",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查字段值是否在合法值域范围内",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_INP_001", "rule_name": "入院时间不能晚于出院时间",
        "rule_category": "ACCURACY", "check_scope": "BUSINESS_LOGIC", "constraint_level": "HARD",
        "business_domain": "住院", "rule_type": "time_logic_error",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查入院时间是否晚于出院时间（逻辑错误）",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_INP_002", "rule_name": "住院唯一标识不能为空",
        "rule_category": "COMPLETE", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "住院", "rule_type": "required_empty",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查住院记录唯一标识是否为空的逻辑错误",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_DIAG_001", "rule_name": "主要诊断只能有一条",
        "rule_category": "UNIQUE", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "诊断", "rule_type": "primary_key_duplicate",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查主要诊断是否有多条记录",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_ORDER_001", "rule_name": "医嘱必须关联住院患者",
        "rule_category": "RELATION", "check_scope": "TABLE_RELATION", "constraint_level": "HARD",
        "business_domain": "医嘱", "rule_type": "orphan_record",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查医嘱记录是否能关联到有效的住院患者",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_FEE_001", "rule_name": "费用明细必须关联就诊",
        "rule_category": "RELATION", "check_scope": "TABLE_RELATION", "constraint_level": "HARD",
        "business_domain": "费用", "rule_type": "orphan_record",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查费用明细记录是否关联到有效就诊",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_LIS_001", "rule_name": "检验报告必须关联检验申请",
        "rule_category": "RELATION", "check_scope": "TABLE_RELATION", "constraint_level": "HARD",
        "business_domain": "检验", "rule_type": "orphan_record",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查检验报告是否能关联到检验申请单",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_PACS_001", "rule_name": "检查报告必须关联检查申请",
        "rule_category": "RELATION", "check_scope": "TABLE_RELATION", "constraint_level": "HARD",
        "business_domain": "检查", "rule_type": "orphan_record",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查检查报告是否能关联到检查申请单",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_OP_001", "rule_name": "手术开始时间不能晚于结束时间",
        "rule_category": "ACCURACY", "check_scope": "TABLE_INNER", "constraint_level": "HARD",
        "business_domain": "手术", "rule_type": "time_logic_error",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查手术开始时间是否晚于结束时间（逻辑错误）",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_OP_002", "rule_name": "手术记录应与病案首页手术一致",
        "rule_category": "ACCURACY", "check_scope": "SYSTEM_CROSS", "constraint_level": "SOFT",
        "business_domain": "手术", "rule_type": "cross_system_mismatch",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "跨系统检查手术记录与病案首页中的手术编码是否一致",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
    {
        "rule_code": "R_NURSE_001", "rule_name": "护理记录必须关联住院患者",
        "rule_category": "RELATION", "check_scope": "TABLE_RELATION", "constraint_level": "HARD",
        "business_domain": "护理", "rule_type": "orphan_record",
        "execution_mode": "sql_template", "error_level": "major",
        "description": "检查护理记录是否能关联到有效的住院患者",
        "enabled": False, "sample_limit": 20, "version": 1,
    },
]

def run():
    db = SessionLocal()
    try:
        for r in HOSPITAL_RULES:
            e = db.query(QualityRule).filter_by(rule_code=r["rule_code"]).first()
            if not e:
                db.add(QualityRule(**r))
        db.commit()
        print(f"Inserted {len(HOSPITAL_RULES)} hospital QC rules")
    finally:
        db.close()

if __name__ == "__main__":
    run()
