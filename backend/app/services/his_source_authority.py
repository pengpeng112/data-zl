"""HISUSER / HIS_SOURCE is authoritative for HIS relations mirrored in ODS."""
from __future__ import annotations

RULE_CODE = "HIS_SOURCE_AUTHORITATIVE_SYNC"
RULE_NAME_CN = "HIS源端为准同步ODS HIS关系"

ODS_HIS_TO_HISUSER: dict[str, str] = {
    "HIS.PAT_VISIT": "MEDREC.PAT_VISIT",
    "HIS.PAT_MASTER_INDEX": "MEDREC.PAT_MASTER_INDEX",
    "HIS.DIAGNOSIS": "MEDREC.DIAGNOSIS",
    "HIS.OPERATION": "MEDREC.OPERATION",
    "HIS.DEPT_DICT": "COMM.DEPT_DICT",
    "HIS.STAFF_DICT": "COMM.STAFF_DICT",
    "HIS.DIAGNOSIS_TYPE_DICT": "COMM.DIAGNOSIS_TYPE_DICT",
    "HIS.ORDERS": "ORDADM.ORDERS",
    "HIS.ORDERS_COSTS": "ORDADM.ORDERS_COSTS",
    "HIS.LAB_TEST_MASTER": "LAB.LAB_TEST_MASTER",
    "HIS.LAB_TEST_ITEMS": "LAB.LAB_TEST_ITEMS",
    "HIS.LAB_RESULT": "LAB.LAB_RESULT",
    "HIS.EXAM_MASTER": "EXAM.EXAM_MASTER",
    "HIS.EXAM_REPORT": "EXAM.EXAM_REPORT",
    "HIS.EXAM_ITEMS": "EXAM.EXAM_ITEMS",
    "HIS.INP_SETTLE_MASTER": "INPBILL.INP_SETTLE_MASTER",
    "HIS.INP_BILL_DETAIL": "INPBILL.INP_BILL_DETAIL",
    "HIS.OUTP_BILL_ITEMS": "OUTPBILL.OUTP_BILL_ITEMS",
    "HIS.OUTP_RCPT_MASTER": "OUTPBILL.OUTP_RCPT_MASTER",
    "HIS.OUTP_ORDER_DESC": "OUTPBILL.OUTP_ORDER_DESC",
    "HIS.CLINIC_MASTER": "OUTPADM.CLINIC_MASTER",
    "HIS.PATS_IN_HOSPITAL": "INPADM.PATS_IN_HOSPITAL",
}

HISUSER_TO_ODS_HIS = {value: key for key, value in ODS_HIS_TO_HISUSER.items()}

RULE_DESCRIPTION = (
    "更新 ODS 中 HIS schema 的正式关系时，必须同步处理 HISUSER/HIS_SOURCE 对应 Owner 表。"
    "HISUSER 是原始业务库，口径以 HISUSER 实测为准；ODS HIS.* 只是镜像。"
    "两边表名按本规则映射（例如 HIS.PAT_VISIT ↔ MEDREC.PAT_VISIT）。"
    "检查/检验必须拆住院（VISIT_ID<>0）和门诊（VISIT_ID=0/NULL，收据号 RCPT_NO）。"
)


def map_ods_his_table(table_name: str | None) -> str | None:
    key = (table_name or "").strip().upper()
    return ODS_HIS_TO_HISUSER.get(key)


def map_hisuser_table(table_name: str | None) -> str | None:
    key = (table_name or "").strip().upper()
    return HISUSER_TO_ODS_HIS.get(key)


def authority_payload(*, persisted: bool = False, enabled: bool = True) -> dict:
    return {
        "rule_code": RULE_CODE,
        "rule_name_cn": RULE_NAME_CN,
        "authority_system_code": "HIS_SOURCE",
        "mirror_system_code": "DATA_CENTER",
        "authority_source_code": "his_source_10_10_10_15",
        "mirror_source_code": "ods_8_216",
        "enabled": enabled,
        "persisted": persisted,
        "description": RULE_DESCRIPTION,
        "table_map": [
            {"ods_table": ods, "hisuser_table": hisuser}
            for ods, hisuser in ODS_HIS_TO_HISUSER.items()
        ],
    }
