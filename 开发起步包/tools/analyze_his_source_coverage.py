from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
HISUSER_META = BASE_DIR / "16_hisuser业务库元数据快照.json"
ODS_META = BASE_DIR / "08_数据中心元数据快照.json"
OUT_JSON = BASE_DIR / "22_HIS源端字段主题与ODS覆盖差异结果.json"

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
    "MEDADM": "医疗管理/字典",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def table_domain(owner: str, table: str) -> str:
    text = f"{owner}.{table}".upper()
    if any(x in text for x in ["PAT_MASTER", "PAT_VISIT", "PATS_IN_HOSPITAL", "ADT_LOG", "INPADM"]):
        return "患者就诊"
    if any(x in text for x in ["DIAG", "DIAGNOSIS", "ICD"]):
        return "诊断"
    if any(x in text for x in ["ORDER", "ORDERS", "DOCTOR_ADVICE"]):
        return "医嘱"
    if any(x in text for x in ["LAB", "TEST", "SPECIMEN", "BACT", "MICRO"]):
        return "检验"
    if any(x in text for x in ["EXAM", "REPORT", "RIS"]):
        return "检查"
    if any(x in text for x in ["BILL", "SETTLE", "RCPT", "CHARGE", "PAY", "FEE", "PRICE", "COST"]):
        return "费用"
    if any(x in text for x in ["DRUG", "PHA", "PRESC", "DISPENSE", "STOCK", "STORE", "INVENTORY"]):
        return "药品"
    if any(x in text for x in ["OPERATION", "OPER", "SURGERY"]):
        return "手术"
    if any(x in text for x in ["DEPT", "WARD", "BED", "STAFF", "DOCTOR", "NURSE", "USER", "EMP"]):
        return "组织人员"
    if any(x in text for x in ["DICT", "CLASS", "TYPE", "CATEGORY", "CODE"]):
        return "字典"
    return OWNER_DOMAIN.get(owner, "其他")


def column_theme(name: str) -> str:
    n = name.upper()
    if n in {"PATIENT_ID", "INP_NO", "OUTPATIENT_NO", "OUTPATIENT_NUM", "CARD_NO", "ID_NO"} or "PATIENT" in n:
        return "患者标识"
    if n in {"VISIT_ID", "VISIT_NO", "VISIT_DATE"} or "VISIT" in n or "ADMISSION" in n or "DISCHARGE" in n:
        return "就诊标识/就诊过程"
    if "TEST_NO" in n or "SPECIMEN" in n or "RESULT" in n or n.startswith("LAB_"):
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
    if n.endswith("CODE") or n.endswith("_CODE") or "CLASS" in n or "TYPE" in n or "STATUS" in n or "FLAG" in n:
        return "状态/字典字段"
    if "DATE" in n or "TIME" in n:
        return "时间字段"
    if "NAME" in n or "DESC" in n or "MEMO" in n or "NOTE" in n:
        return "描述字段"
    return "其他字段"


def col_names(table_meta: dict) -> set[str]:
    return {c["name"].upper() for c in table_meta.get("columns", [])}


def main() -> None:
    hisuser = load_json(HISUSER_META)
    ods = load_json(ODS_META)
    source_tables = hisuser["tables"]
    ods_his_tables = ods["schemas"].get("HIS", {}).get("tables", {})
    ods_by_name = {name.upper(): meta for name, meta in ods_his_tables.items()}

    target_tables = []
    for full_name, meta in source_tables.items():
        owner = meta.get("owner", "").upper()
        table = meta.get("table", "").upper()
        if owner in TARGET_OWNERS:
            target_tables.append((owner, table, full_name, meta))

    owner_summary = {}
    domain_counter = Counter()
    coverage_rows = []
    missing_in_ods = []
    same_name_in_ods = []
    partial_field_coverage = []

    by_owner = defaultdict(list)
    for owner, table, full_name, meta in target_tables:
        by_owner[owner].append((table, full_name, meta))

    for owner, rows in sorted(by_owner.items()):
        table_count = len(rows)
        column_count = sum(len(meta.get("columns", [])) for _, _, meta in rows)
        row_count_stats = sum(int(meta.get("num_rows_stats") or 0) for _, _, meta in rows)
        owner_summary[owner] = {
            "domain": OWNER_DOMAIN.get(owner, "其他"),
            "table_count": table_count,
            "column_count": column_count,
            "row_count_stats_sum": row_count_stats,
        }

    for owner, table, full_name, meta in target_tables:
        domain = table_domain(owner, table)
        domain_counter[domain] += 1
        source_cols = col_names(meta)
        ods_meta = ods_by_name.get(table)
        row = {
            "source_owner": owner,
            "table": table,
            "domain": domain,
            "num_rows_stats": meta.get("num_rows_stats"),
            "source_column_count": len(source_cols),
            "primary_key": meta.get("primary_key", []),
            "in_ods_his_same_name": ods_meta is not None,
        }
        if ods_meta:
            ods_cols = col_names(ods_meta)
            common = sorted(source_cols & ods_cols)
            missing = sorted(source_cols - ods_cols)
            extra = sorted(ods_cols - source_cols)
            row.update(
                {
                    "ods_column_count": len(ods_cols),
                    "common_column_count": len(common),
                    "source_missing_in_ods_count": len(missing),
                    "ods_extra_count": len(extra),
                    "coverage_ratio": round(len(common) / len(source_cols), 4) if source_cols else None,
                    "sample_missing_source_columns": missing[:20],
                    "sample_ods_extra_columns": extra[:20],
                }
            )
            same_name_in_ods.append(row)
            if missing or extra:
                partial_field_coverage.append(row)
        else:
            row.update(
                {
                    "ods_column_count": 0,
                    "common_column_count": 0,
                    "source_missing_in_ods_count": len(source_cols),
                    "ods_extra_count": 0,
                    "coverage_ratio": 0,
                    "sample_missing_source_columns": sorted(source_cols)[:20],
                    "sample_ods_extra_columns": [],
                }
            )
            missing_in_ods.append(row)
        coverage_rows.append(row)

    column_theme_counts = Counter()
    table_theme_samples = []
    for owner, table, full_name, meta in target_tables:
        themes = Counter(column_theme(c["name"]) for c in meta.get("columns", []))
        column_theme_counts.update(themes)
        if table in {
            "PAT_MASTER_INDEX",
            "PAT_VISIT",
            "DIAGNOSIS",
            "OPERATION",
            "ORDERS",
            "LAB_TEST_MASTER",
            "LAB_TEST_ITEMS",
            "LAB_RESULT",
            "EXAM_MASTER",
            "EXAM_REPORT",
            "INP_SETTLE_MASTER",
            "INP_BILL_DETAIL",
            "OUTP_RCPT_MASTER",
            "OUTP_BILL_ITEMS",
            "CLINIC_MASTER",
        }:
            key_columns = [c["name"] for c in meta.get("columns", []) if column_theme(c["name"]) != "其他字段"][:30]
            table_theme_samples.append(
                {
                    "source_owner": owner,
                    "table": table,
                    "domain": table_domain(owner, table),
                    "primary_key": meta.get("primary_key", []),
                    "column_theme_counts": dict(themes.most_common()),
                    "key_columns_sample": key_columns,
                }
            )

    missing_top = sorted(
        missing_in_ods,
        key=lambda r: (int(r.get("num_rows_stats") or 0), r["source_column_count"]),
        reverse=True,
    )[:80]
    partial_top = sorted(
        partial_field_coverage,
        key=lambda r: (r.get("coverage_ratio") is not None, r.get("coverage_ratio") or 0, -int(r.get("num_rows_stats") or 0)),
    )[:80]

    result = {
        "generated_at": "2026-07-03",
        "source": {
            "hisuser_snapshot": str(HISUSER_META.name),
            "ods_snapshot": str(ODS_META.name),
            "compare_rule": "按 HIS 源端 table_name 与 ODS.HIS table_name 同名匹配；字段按大写同名匹配。未处理同义词、视图映射和字段改名。",
        },
        "scope": {
            "target_owners": sorted(TARGET_OWNERS),
            "source_table_count": len(target_tables),
            "source_column_count": sum(len(meta.get("columns", [])) for _, _, _, meta in target_tables),
            "ods_his_table_count": len(ods_by_name),
        },
        "summary": {
            "same_name_table_count": len(same_name_in_ods),
            "missing_table_count": len(missing_in_ods),
            "same_name_table_ratio": round(len(same_name_in_ods) / len(target_tables), 4) if target_tables else None,
            "partial_field_diff_table_count": len(partial_field_coverage),
            "table_domain_counts": dict(domain_counter.most_common()),
            "column_theme_counts": dict(column_theme_counts.most_common()),
        },
        "owner_summary": owner_summary,
        "core_table_theme_samples": sorted(table_theme_samples, key=lambda x: (x["source_owner"], x["table"])),
        "same_name_in_ods_top": sorted(
            same_name_in_ods,
            key=lambda r: int(r.get("num_rows_stats") or 0),
            reverse=True,
        )[:80],
        "missing_in_ods_top_by_rows": missing_top,
        "partial_field_coverage_top": partial_top,
        "uncertainties": [
            "ODS 覆盖差异目前只做同名表/同名字段匹配；源端表可能通过 ODS 视图、改名表或融合表间接覆盖。",
            "字段主题分类为规则推断，适合建初版资产目录；正式口径需业务确认。",
            "COMM/MEDADM 字典类 owner 表很多，是否纳入第一版 HIS 源端资产包需要确认。",
            "VISIT_ID=0/NULL 的检验/检查子集需要业务确认门诊、体检、外送或历史接口来源。",
            "同名字段的类型/长度差异本次仅保留计数和样例，未判定是否影响入仓或视图生成。",
        ],
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
