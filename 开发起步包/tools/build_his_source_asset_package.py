from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
META_PATH = BASE_DIR / "16_hisuser业务库元数据快照.json"
ODS_PATH = BASE_DIR / "08_数据中心元数据快照.json"
COVERAGE_PATH = BASE_DIR / "22_HIS源端字段主题与ODS覆盖差异结果.json"
SCOPE_PATH = BASE_DIR / "23_HIS源端资产范围复核与下一步计划结果.json"
OUT_DIR = BASE_DIR / "数据资产_HIS源端资产包"

SOURCE_DB = "10.10.10.15:1521/his"

TARGET_OWNERS = {
    "MEDREC",
    "INPADM",
    "ORDADM",
    "LAB",
    "EXAM",
    "INPBILL",
    "OUTPBILL",
    "OUTPADM",
    "DRUG_USER",
    "PHARMACY",
    "COMM",
    "MEDADM",
}

OWNER_DOMAIN = {
    "MEDREC": "住院/病案主线",
    "INPADM": "住院管理",
    "ORDADM": "医嘱",
    "LAB": "检验",
    "EXAM": "检查",
    "INPBILL": "住院费用",
    "OUTPBILL": "门诊费用",
    "OUTPADM": "门诊就诊",
    "DRUG_USER": "药品/药库/发药",
    "PHARMACY": "药房/处方/发药",
    "COMM": "公共字典/基础资料",
    "MEDADM": "医疗管理/住院管理",
}

FORCE_INCLUDE = {
    "COMM.DEPT_DICT": ("dimension", "科室字典，用户确认纳入"),
    "COMM.STAFF_DICT": ("dimension", "人员字典，用户确认纳入"),
    "COMM.PRICE_LIST": ("dimension", "价格/收费字典，用户确认纳入"),
    "COMM.DIAGNOSIS_DICT": ("dimension", "诊断字典，用户确认纳入"),
    "MEDADM.BEDPATS_IN_HOSPITAL": ("inpatient_management_fact", "在院/床位日快照，用户确认纳入"),
    "ORDADM.ORDERS_EXECUTE_DETAILS": ("execution_fact", "医嘱执行事实，已样本验证"),
    "DRUG_USER.INP_ORDER_EXECDATA": ("execution_fact", "住院用药/医嘱执行事实，已样本验证"),
    "INPBILL.PREPAYMENT_RCPT": ("payment_fact", "患者预交金/缴费事实，用户确认纳入"),
}

FORCE_EXCLUDE = {
    "COMM.OPERATION_LOG": "操作日志，用户确认排除",
}

CORE_FACTS = {
    "MEDREC.PAT_MASTER_INDEX",
    "MEDREC.PAT_VISIT",
    "MEDREC.DIAGNOSIS",
    "MEDREC.OPERATION",
    "INPADM.PATS_IN_HOSPITAL",
    "INPADM.ADT_LOG",
    "ORDADM.ORDERS",
    "ORDADM.ORDERS_COSTS",
    "LAB.LAB_TEST_MASTER",
    "LAB.LAB_TEST_ITEMS",
    "LAB.LAB_RESULT",
    "LAB.LAB_TEST_ITEMS_DETAIL",
    "EXAM.EXAM_MASTER",
    "EXAM.EXAM_REPORT",
    "EXAM.EXAM_ITEMS",
    "EXAM.EXAM_BILL_ITEMS",
    "INPBILL.INP_SETTLE_MASTER",
    "INPBILL.INP_BILL_DETAIL",
    "OUTPADM.CLINIC_MASTER",
    "OUTPBILL.OUTP_RCPT_MASTER",
    "OUTPBILL.OUTP_BILL_ITEMS",
    "DRUG_USER.PHA_INP_REQUEST_DRUG",
    "DRUG_USER.PHA_INP_DISPDETAIL",
    "DRUG_USER.PHA_CLI_REQUEST_DRUG",
    "PHARMACY.DRUG_DISPENSE_REC",
    "PHARMACY.DRUG_PRESC_MASTER",
    "PHARMACY.DRUG_PRESC_DETAIL",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    def clean(value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.replace("\r", " ").replace("\n", " ").strip()
        return value

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: clean(v) for k, v in row.items()} for row in rows)


def table_domain(owner: str, table: str) -> str:
    text = f"{owner}.{table}".upper()
    if any(x in text for x in ["PAT_MASTER", "PAT_VISIT", "PATS_IN_HOSPITAL", "ADT_LOG"]):
        return "患者就诊"
    if any(x in text for x in ["DIAG", "ICD"]):
        return "诊断"
    if "ORDER" in text or "ORDERS" in text:
        return "医嘱"
    if any(x in text for x in ["LAB", "TEST", "SPECIMEN"]):
        return "检验"
    if any(x in text for x in ["EXAM", "REPORT"]):
        return "检查"
    if any(x in text for x in ["BILL", "SETTLE", "RCPT", "CHARGE", "COST", "PRICE", "PAY"]):
        return "费用"
    if any(x in text for x in ["DRUG", "PHA", "PRESC", "DISPENSE", "STOCK"]):
        return "药品"
    if any(x in text for x in ["OPERATION", "OPER"]):
        return "手术"
    if any(x in text for x in ["DEPT", "WARD", "BED", "STAFF", "DOCTOR", "NURSE", "USER", "EMP"]):
        return "组织人员"
    if any(x in text for x in ["DICT", "CLASS", "TYPE", "CODE"]):
        return "字典"
    return OWNER_DOMAIN.get(owner, "其他")


def column_theme(name: str) -> str:
    n = name.upper()
    if n in {"PATIENT_ID", "INP_NO", "OUTPATIENT_NO", "OUTPATIENT_NUM", "CARD_NO", "ID_NO"} or "PATIENT" in n:
        return "患者标识"
    if "VISIT" in n or "ADMISSION" in n or "DISCHARGE" in n:
        return "就诊标识/过程"
    if "TEST_NO" in n or "SPECIMEN" in n or "RESULT" in n:
        return "检验字段"
    if "EXAM_NO" in n or "EXAM" in n or "REPORT" in n:
        return "检查字段"
    if "ORDER" in n:
        return "医嘱字段"
    if "DIAG" in n or "ICD" in n:
        return "诊断字段"
    if "DRUG" in n or "PRESC" in n or "DISPENSE" in n:
        return "药品字段"
    if "BILL" in n or "RCPT" in n or "CHARGE" in n or "COST" in n or "PRICE" in n or "AMOUNT" in n or "PAY" in n:
        return "费用字段"
    if "DEPT" in n or "WARD" in n or "BED" in n:
        return "机构科室字段"
    if "DOCTOR" in n or "NURSE" in n or "STAFF" in n or "USER" in n or "EMP" in n or "OPERATOR" in n:
        return "人员字段"
    if n.endswith("CODE") or "CLASS" in n or "TYPE" in n or "STATUS" in n or "FLAG" in n:
        return "状态/字典字段"
    if "DATE" in n or "TIME" in n:
        return "时间字段"
    if "NAME" in n or "DESC" in n or "MEMO" in n or "NOTE" in n:
        return "描述字段"
    return "其他字段"


def exclusion_reason(owner: str, table: str) -> str:
    full = f"{owner}.{table}"
    t = table.upper()
    if full in FORCE_EXCLUDE:
        return FORCE_EXCLUDE[full]
    if t.startswith("ST_"):
        return "ST_* 统计汇总表，用户确认第一版排除"
    if t.endswith("_LOG") or "LOG" in t:
        return "日志类表，用户确认第一版排除"
    if any(x in t for x in ["TEMP", "TMP", "BACKUP", "_BK", "COPY", "TEST_ONE"]):
        return "临时/备份/测试表，第一版排除"
    if any(x in t for x in ["INSERT_DATA", "UPDATE_DATA", "INTERFACE", "UPLOAD", "DOWNLOAD", "EXCHANGE"]):
        return "接口中间表，第一版排除"
    if t.endswith("_DAY") or t.endswith("_MONTH") or "STATISTICS" in t:
        return "统计日/月汇总表，第一版排除"
    return ""


def infer_role(owner: str, table: str) -> tuple[str, str, str]:
    full = f"{owner}.{table}"
    if full in FORCE_INCLUDE:
        role, note = FORCE_INCLUDE[full]
        return "included", role, note
    reason = exclusion_reason(owner, table)
    if reason:
        return "excluded", "excluded", reason
    if full in CORE_FACTS:
        return "included", "core_fact", "核心业务事实/主线表"
    if table_domain(owner, table) in {"字典", "组织人员"} or table.endswith("_DICT") or owner in {"COMM"}:
        return "included", "dimension", "基础字典/维表"
    if owner == "MEDADM":
        return "candidate", "candidate", "MEDADM 非统计管理表，需二次裁剪"
    if owner in {"DRUG_USER", "PHARMACY"} and table_domain(owner, table) == "药品":
        return "candidate", "candidate", "药品相关扩展表，待药品闭环二次确认"
    return "candidate", "candidate", "非核心表，保留候选"


def coverage_map(meta: dict, ods: dict) -> dict[str, dict]:
    ods_tables = ods["schemas"].get("HIS", {}).get("tables", {})
    ods_by_name = {name.upper(): table_meta for name, table_meta in ods_tables.items()}
    rows = {}
    for full_name, table_meta in meta["tables"].items():
        owner = table_meta.get("owner", "").upper()
        table = table_meta.get("table", "").upper()
        if owner not in TARGET_OWNERS:
            continue
        source_cols = {c["name"].upper() for c in table_meta.get("columns", [])}
        ods_meta = ods_by_name.get(table)
        if not ods_meta:
            rows[full_name] = {"in_ods_his_same_name": False, "coverage_ratio": 0}
            continue
        ods_cols = {c["name"].upper() for c in ods_meta.get("columns", [])}
        common = source_cols & ods_cols
        rows[full_name] = {
            "in_ods_his_same_name": True,
            "coverage_ratio": round(len(common) / len(source_cols), 4) if source_cols else None,
        }
    return rows


def build_relationships() -> list[dict]:
    rels = [
        ("R001", "MEDREC.PAT_VISIT", "MEDREC.PAT_MASTER_INDEX", "PATIENT_ID", "full_pass", "21/M01"),
        ("R002", "MEDREC.DIAGNOSIS", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "full_pass", "21/M02"),
        ("R003", "MEDREC.OPERATION", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "full_pass_with_note", "21/M03; OPER_ID 全空"),
        ("R004", "INPADM.PATS_IN_HOSPITAL", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "full_pass", "21/M04"),
        ("R005", "INPADM.ADT_LOG", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "sample_pass", "21/M05"),
        ("R006", "ORDADM.ORDERS", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "sample_pass", "21/O01"),
        ("R007", "ORDADM.ORDERS_COSTS", "ORDADM.ORDERS", "PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO", "sample_pass", "21/O02"),
        ("R008", "ORDADM.ORDERS_EXECUTE_DETAILS", "ORDADM.ORDERS", "PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO", "sample_pass", "23/OED01"),
        ("R009", "DRUG_USER.INP_ORDER_EXECDATA", "ORDADM.ORDERS", "PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO", "sample_pass", "23/OED02"),
        ("R010", "DRUG_USER.INP_ORDER_EXECDATA", "DRUG_USER.PHA_INP_REQUEST_DRUG", "PATIENT_ID/PAT_ID+VISIT_ID/IN_COUNT+ORDER_NO/MO_ORDER+ORDER_SUB_NO", "sample_pass", "23/OED03"),
        ("R011", "LAB.LAB_TEST_MASTER", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "pass_with_subset", "21/L01; 仅非零 VISIT_ID 住院子集"),
        ("R012", "LAB.LAB_TEST_ITEMS", "LAB.LAB_TEST_MASTER", "TEST_NO", "full_pass", "21/L02"),
        ("R013", "LAB.LAB_RESULT", "LAB.LAB_TEST_MASTER", "TEST_NO", "sample_pass", "21/L03"),
        ("R014", "LAB.LAB_TEST_ITEMS_DETAIL", "LAB.LAB_TEST_ITEMS", "TEST_NO+ITEM_NO", "partial", "21/L04"),
        ("R015", "LAB.LAB_TEST_MASTER", "OUTPADM.CLINIC_MASTER", "PATIENT_ID+REQUESTED_DATE_TIME~VISIT_DATE", "candidate", "23/V01; VISIT_ID=0/NULL 门诊候选"),
        ("R016", "EXAM.EXAM_MASTER", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "pass_with_subset", "21/E01; 仅非零 VISIT_ID 住院子集"),
        ("R017", "EXAM.EXAM_REPORT", "EXAM.EXAM_MASTER", "EXAM_NO", "full_pass", "21/E02"),
        ("R018", "EXAM.EXAM_ITEMS", "EXAM.EXAM_MASTER", "EXAM_NO", "partial", "21/E03"),
        ("R019", "EXAM.EXAM_BILL_ITEMS", "EXAM.EXAM_MASTER", "EXAM_NO", "full_pass", "21/E04"),
        ("R020", "EXAM.EXAM_MASTER", "OUTPADM.CLINIC_MASTER", "PATIENT_ID+REQ_DATE_TIME~VISIT_DATE", "candidate", "23/V02; VISIT_ID=0/NULL 门诊候选"),
        ("R021", "INPBILL.INP_SETTLE_MASTER", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "full_pass", "21/B01"),
        ("R022", "INPBILL.INP_BILL_DETAIL", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "sample_pass", "21/B02"),
        ("R023", "INPBILL.INP_BILL_DETAIL", "INPBILL.INP_SETTLE_MASTER", "RCPT_NO", "sample_pass", "21/B03"),
        ("R024", "INPBILL.PREPAYMENT_RCPT", "MEDREC.PAT_MASTER_INDEX", "PATIENT_ID", "sample_pass", "23/P01"),
        ("R025", "INPBILL.PREPAYMENT_RCPT", "MEDREC.PAT_VISIT", "PATIENT_ID+VISIT_ID", "pass_with_subset", "23/P02; 非零 VISIT_ID 子集"),
        ("R026", "INPBILL.PREPAYMENT_RCPT", "INPBILL.PREPAYMENT_RCPT", "REFUNDED_RCPT_NO->RCPT_NO", "sample_pass", "23/P03"),
        ("R027", "OUTPADM.CLINIC_MASTER", "MEDREC.PAT_MASTER_INDEX", "PATIENT_ID", "full_pass", "21/B04"),
        ("R028", "OUTPBILL.OUTP_BILL_ITEMS", "OUTPBILL.OUTP_RCPT_MASTER", "RCPT_NO", "sample_pass", "21/B05"),
        ("R029", "OUTPBILL.OUTP_RCPT_MASTER", "MEDREC.PAT_MASTER_INDEX", "PATIENT_ID", "sample_pass", "21/B06"),
        ("R030", "DRUG_USER.PHA_INP_REQUEST_DRUG", "MEDREC.PAT_VISIT", "PAT_ID+IN_COUNT", "verified", "19"),
        ("R031", "DRUG_USER.PHA_INP_REQUEST_DRUG", "ORDADM.ORDERS", "PAT_ID+IN_COUNT+MO_ORDER+ORDER_SUB_NO", "verified", "19"),
        ("R032", "DRUG_USER.PHA_INP_DISPDETAIL", "DRUG_USER.PHA_INP_REQUEST_DRUG", "REQUEST_NO", "verified", "19"),
        ("R033", "DRUG_USER.PHA_CLI_REQUEST_DRUG", "MEDREC.PAT_MASTER_INDEX", "PAT_ID", "verified", "19"),
    ]
    rows = []
    for rel_id, src, dst, keys, status, note in rels:
        rows.append(
            {
                "relationship_id": rel_id,
                "source_db": SOURCE_DB,
                "from_table": src,
                "to_table": dst,
                "join_keys": keys,
                "relationship_type": "foreign_key_like",
                "validation_status": status,
                "validation_source": note,
            }
        )
    return rows


def main() -> None:
    meta = load_json(META_PATH)
    ods = load_json(ODS_PATH)
    coverage = load_json(COVERAGE_PATH)
    scope = load_json(SCOPE_PATH)
    cov = coverage_map(meta, ods)
    tables_meta = meta["tables"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tables_rows = []
    columns_rows = []
    for full_name, table_meta in sorted(tables_meta.items()):
        owner = table_meta.get("owner", "").upper()
        table = table_meta.get("table", "").upper()
        if owner not in TARGET_OWNERS:
            continue
        include_status, role, reason = infer_role(owner, table)
        full = f"{owner}.{table}"
        cov_row = cov.get(full, {})
        ods_same = bool(cov_row.get("in_ods_his_same_name", False))
        pk = table_meta.get("primary_key", []) or []
        domain = table_domain(owner, table)
        tables_rows.append(
            {
                "source_db": SOURCE_DB,
                "source_owner": owner,
                "table_name": table,
                "full_name": full,
                "domain": domain,
                "table_role": role,
                "include_status": include_status,
                "exclude_reason": reason if include_status == "excluded" else "",
                "include_note": reason if include_status != "excluded" else "",
                "num_rows_stats": table_meta.get("num_rows_stats"),
                "column_count": len(table_meta.get("columns", [])),
                "primary_key": "+".join(pk),
                "ods_same_name_covered": str(ods_same).lower(),
                "ods_field_coverage_ratio": cov_row.get("coverage_ratio", ""),
            }
        )
        for col in table_meta.get("columns", []):
            col_name = col["name"].upper()
            columns_rows.append(
                {
                    "source_db": SOURCE_DB,
                    "source_owner": owner,
                    "table_name": table,
                    "column_id": col.get("column_id"),
                    "column_name": col_name,
                    "data_type": col.get("type"),
                    "length": col.get("length"),
                    "precision": col.get("precision"),
                    "scale": col.get("scale"),
                    "nullable": str(col.get("nullable", True)).lower(),
                    "comment": col.get("comment") or "",
                    "column_theme": column_theme(col_name),
                    "is_primary_key": str(col_name in {p.upper() for p in pk}).lower(),
                    "table_role": role,
                    "include_status": include_status,
                }
            )

    rel_rows = build_relationships()
    catalog = {
        "meta": {
            "generated_at": "2026-07-03",
            "source_db": SOURCE_DB,
            "source_metadata": META_PATH.name,
            "coverage_basis": COVERAGE_PATH.name,
            "scope_basis": SCOPE_PATH.name,
        },
        "summary": {
            "table_count": len(tables_rows),
            "column_count": len(columns_rows),
            "relationship_count": len(rel_rows),
            "include_status_counts": dict(Counter(r["include_status"] for r in tables_rows)),
            "table_role_counts": dict(Counter(r["table_role"] for r in tables_rows)),
            "owner_counts": dict(Counter(r["source_owner"] for r in tables_rows)),
            "ods_same_name_covered_count": sum(1 for r in tables_rows if r["ods_same_name_covered"] == "true"),
        },
        "scope_decisions": scope.get("user_decisions", {}),
        "tables": tables_rows,
        "relationships": rel_rows,
    }

    write_csv(
        OUT_DIR / "his_source_tables.csv",
        [
            "source_db",
            "source_owner",
            "table_name",
            "full_name",
            "domain",
            "table_role",
            "include_status",
            "exclude_reason",
            "include_note",
            "num_rows_stats",
            "column_count",
            "primary_key",
            "ods_same_name_covered",
            "ods_field_coverage_ratio",
        ],
        tables_rows,
    )
    write_csv(
        OUT_DIR / "his_source_columns.csv",
        [
            "source_db",
            "source_owner",
            "table_name",
            "column_id",
            "column_name",
            "data_type",
            "length",
            "precision",
            "scale",
            "nullable",
            "comment",
            "column_theme",
            "is_primary_key",
            "table_role",
            "include_status",
        ],
        columns_rows,
    )
    write_csv(
        OUT_DIR / "his_source_relationships.csv",
        [
            "relationship_id",
            "source_db",
            "from_table",
            "to_table",
            "join_keys",
            "relationship_type",
            "validation_status",
            "validation_source",
        ],
        rel_rows,
    )
    (OUT_DIR / "his_source_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(catalog["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
