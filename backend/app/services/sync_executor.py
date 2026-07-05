"""P5.9-T9 跨系统同步通用框架"""

from ..core.db import SessionLocal
from ..models.governance_base import GovernAuditLog


def run_sync(
    source_system: str,
    target_system: str,
    entity_type: str,
    operator: str | None = None,
) -> dict:
    """通用同步框架入口。

    根据 entity_type 分发到对应的执行器（P12 人员科室 / P13 诊断手术 / F46 元数据）。
    所有同步结果写入 asset_govern_audit_logs（module='sync'）。
    """
    db = SessionLocal()
    try:
        result = {
            "source_system": source_system,
            "target_system": target_system,
            "entity_type": entity_type,
            "status": "pending",
        }

        if entity_type == "identity_department":
            result["status"] = "stub"
            result["note"] = "待实现: 从 HIS dept_dict 采集 → 比对基线 → 同步目标库"
        elif entity_type == "identity_person":
            result["status"] = "stub"
            result["note"] = "待实现: 从 HRP 人员表采集 → 比对基线 → 同步目标库"
        elif entity_type == "medical_code":
            result["status"] = "stub"
            result["note"] = "待实现: 从 HIS/EMR 字典表采集 → 比对三套编码 → 同步目标库"
        elif entity_type == "metadata_collect":
            result["status"] = "stub"
            result["note"] = "待实现: 从源库采集元数据 → 生成快照 → 触发 diff"
        else:
            result["status"] = "skipped"
            result["note"] = f"未知 entity_type: {entity_type}"

        db.add(GovernAuditLog(
            module="sync",
            entity_type=entity_type,
            entity_ref=f"{source_system}→{target_system}",
            action="sync_run",
            before_data={"source": source_system, "target": target_system},
            after_data=result,
            operator=operator,
        ))
        db.commit()
        return result
    finally:
        db.close()
