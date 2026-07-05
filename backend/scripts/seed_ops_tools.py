"""种子数据：插入 asset_ops_tool_templates 初始运维工具模板"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.ops_tool import OpsToolTemplate

TEMPLATES = [
    {
        "tool_code": "msg_resend",
        "tool_name_cn": "消息补发/重推",
        "system_code": "HIS_SOURCE",
        "tool_type": "resend",
        "risk_level": "medium",
        "input_schema": {"fields": ["patient_id", "visit_id", "msg_type"]},
        "execution_mode": "stored_procedure",
        "sql_or_endpoint_ref": "SP_MSG_RESEND",
        "require_approval": True,
        "require_second_confirm": True,
        "enabled": False,
        "description_cn": "患者消息未发送到目标系统时补发/重推",
        "rollback_note_cn": "补发操作不可回滚，执行前请确认业务状态",
    },
    {
        "tool_code": "order_status_check",
        "tool_name_cn": "医嘱状态只读核查",
        "system_code": "HIS_SOURCE",
        "tool_type": "query",
        "risk_level": "low",
        "input_schema": {"fields": ["patient_id", "visit_id", "order_id"]},
        "execution_mode": "readonly_sql",
        "sql_or_endpoint_ref": "SELECT * FROM MEDREC.ORDERS WHERE ...",
        "require_approval": False,
        "require_second_confirm": False,
        "enabled": False,
        "description_cn": "查询患者医嘱状态、执行状态、属性信息",
    },
    {
        "tool_code": "sync_status_check",
        "tool_name_cn": "数据同步状态核查",
        "system_code": "DATA_CENTER",
        "tool_type": "query",
        "risk_level": "low",
        "input_schema": {"fields": ["patient_id", "visit_id", "biz_type"]},
        "execution_mode": "readonly_sql",
        "sql_or_endpoint_ref": "SELECT sync_status FROM ...",
        "require_approval": False,
        "require_second_confirm": False,
        "enabled": False,
        "description_cn": "核查患者/就诊/业务单号在各系统间同步状态",
    },
]

def run():
    db = SessionLocal()
    try:
        for t in TEMPLATES:
            e = db.query(OpsToolTemplate).filter_by(tool_code=t["tool_code"]).first()
            if not e:
                db.add(OpsToolTemplate(**t))
        db.commit()
        print(f"Inserted {len(TEMPLATES)} ops tool templates")
    finally:
        db.close()

if __name__ == "__main__":
    run()
