from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECONDARY_DIR = ROOT / "数据资产_HIS_READY二次优化包"
OUTPUT_DIR = ROOT / "数据资产_HIS_READY治理导入包"

SYSTEM_CODE = "HIS_SOURCE"
SOURCE_CODE = "his_ready_10_10_10_15"
SOURCE_DB = "10.10.10.15:1521/his"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split_full_name(full_name: str) -> tuple[str, str]:
    if "." not in full_name:
        return "", full_name
    owner, table = full_name.split(".", 1)
    return owner.strip(), table.strip()


def normalize_key(owner: str, table: str) -> str:
    return f"{owner.strip().upper()}.{table.strip().upper()}"


def table_role(table_type: str) -> str:
    mapping = {
        "主数据表": "master_data",
        "事实主表": "core_fact",
        "事实明细表": "detail_fact",
        "字典表": "dimension",
        "映射表": "mapping",
        "宽表": "wide_table",
        "指标表": "metric",
        "中间表": "intermediate",
        "历史表": "history",
        "待确认表": "pending_review",
    }
    return mapping.get((table_type or "").strip(), "asset_table")


def pk_status(pk: str) -> str:
    return "present" if (pk or "").strip() else "missing"


def build_join_condition(child_table: str, child_cols: str, parent_table: str, parent_cols: str) -> str:
    child_parts = [p.strip() for p in child_cols.split("+") if p.strip()]
    parent_parts = [p.strip() for p in parent_cols.split("+") if p.strip()]
    if len(child_parts) != len(parent_parts) or not child_parts:
        return f"{child_table}.{child_cols} -> {parent_table}.{parent_cols}"
    return " AND ".join(
        f"{child_table}.{child_col}={parent_table}.{parent_col}"
        for child_col, parent_col in zip(child_parts, parent_parts)
    )


def relation_domain(child_table: str, parent_table: str, table_domains: dict[str, str]) -> str:
    return table_domains.get(child_table.upper()) or table_domains.get(parent_table.upper()) or "待确认"


def convert_core_tables(core_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in core_rows:
        owner = row.get("Schema", "").strip()
        table = row.get("表名", "").strip()
        rows.append(
            {
                "system_code": SYSTEM_CODE,
                "source_code": SOURCE_CODE,
                "source_db": SOURCE_DB,
                "source_owner": owner,
                "namespace_name": owner,
                "schema_name": owner,
                "table_name": table,
                "full_name": f"{owner}.{table}",
                "table_comment": row.get("表中文名") or row.get("表备注") or "",
                "domain": row.get("业务域", ""),
                "table_role": table_role(row.get("表类型", "")),
                "include_status": "included",
                "governance_import_status": "active",
                "review_status": "approved",
                "num_rows_stats": row.get("总行数", ""),
                "last_analyzed": "",
                "column_count": "",
                "primary_key": row.get("候选主键", ""),
                "primary_key_status": pk_status(row.get("候选主键", "")),
                "unique_key_count": "",
                "scope_note": row.get("判断依据", "38/39/40 二次复核后纳入治理"),
                "source_file_name": row.get("来源文件名称", ""),
                "confirmation_status": row.get("确认状态", ""),
                "activity_status": row.get("活跃度判断", ""),
                "data_granularity": row.get("数据粒度", ""),
                "candidate_relation_fields": row.get("候选关联字段", ""),
            }
        )
    return rows


def convert_excluded_tables(excluded_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in excluded_rows:
        owner = row.get("Schema", "").strip()
        table = row.get("表名", "").strip()
        rows.append(
            {
                "system_code": SYSTEM_CODE,
                "source_code": SOURCE_CODE,
                "source_db": SOURCE_DB,
                "schema_name": owner,
                "table_name": table,
                "full_name": f"{owner}.{table}",
                "table_comment": row.get("表中文名") or row.get("表备注") or "",
                "domain": row.get("业务域", ""),
                "table_role": table_role(row.get("表类型", "")),
                "include_status": "excluded",
                "governance_import_status": "excluded",
                "review_status": "excluded_by_recheck",
                "num_rows_stats": row.get("总行数", ""),
                "exclude_reason": row.get("判断依据", ""),
                "source_file_name": row.get("来源文件名称", ""),
                "confirmation_status": row.get("确认状态", ""),
                "manual_confirm_question": row.get("需要人工确认的问题", ""),
            }
        )
    return rows


def convert_relations(a_rows: list[dict[str, str]], table_domains: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, row in enumerate(a_rows, start=1):
        parent_table = row.get("主表", "").strip()
        child_table = row.get("子表", "").strip()
        parent_cols = row.get("主表字段", "").strip()
        child_cols = row.get("子表字段", "").strip()
        rows.append(
            {
                "system_code": SYSTEM_CODE,
                "source_code": SOURCE_CODE,
                "relationship_id": f"A{idx:03d}",
                "domain": relation_domain(child_table, parent_table, table_domains),
                "from_table": child_table,
                "from_columns": child_cols,
                "to_table": parent_table,
                "to_columns": parent_cols,
                "join_condition": build_join_condition(child_table, child_cols, parent_table, parent_cols),
                "relationship_type": row.get("关系类型", ""),
                "confidence": "A",
                "validation_level": "sample_100k",
                "validation_status": "sample_pass",
                "validation_metrics": row.get("覆盖率验证", ""),
                "import_action": "import_formal",
                "review_status": "approved",
                "source_evidence": row.get("业务依据", ""),
                "risk_note": row.get("风险说明", ""),
                "suggestion": row.get("建议处理", ""),
            }
        )
    return rows


def outpatient_strong_key_relations() -> list[dict[str, str]]:
    return [
        {
            "system_code": SYSTEM_CODE,
            "source_code": SOURCE_CODE,
            "relationship_id": "OUT_LAB_RCPT",
            "domain": "检验",
            "from_table": "LAB.LAB_TEST_MASTER",
            "from_columns": "PATIENT_ID+RCPT_NO",
            "to_table": "OUTPBILL.OUTP_ORDER_DESC",
            "to_columns": "PATIENT_ID+RCPT_NO",
            "join_condition": "LAB.LAB_TEST_MASTER.PATIENT_ID=OUTPBILL.OUTP_ORDER_DESC.PATIENT_ID AND LAB.LAB_TEST_MASTER.RCPT_NO=OUTPBILL.OUTP_ORDER_DESC.RCPT_NO",
            "relationship_type": "outpatient_rcpt_strong_key",
            "confidence": "A",
            "validation_level": "sample_100k",
            "validation_status": "sample_pass",
            "validation_metrics": json.dumps(
                {
                    "sample_limit": 100000,
                    "has_rcpt_ratio": 0.941,
                    "matched_count": 94795,
                    "sample_matched_rows": 94795,
                    "orphan_count": 2,
                    "match_rate": 0.99998,
                },
                ensure_ascii=False,
            ),
            "import_action": "import_formal",
            "review_status": "approved",
            "source_evidence": "42_下一步工作与整改交接说明.md 3.4 门诊检验/检查强键；用户确认纳入 final 包",
            "risk_note": "仅适用于有 RCPT_NO 的门诊检验记录；剩余无收据记录需按条件挂接规则后续验证",
            "suggestion": "纳入当前 HIS_READY 正式关系，并保留无收据门诊检验作为后续质量/关系任务",
        },
        {
            "system_code": SYSTEM_CODE,
            "source_code": SOURCE_CODE,
            "relationship_id": "OUT_EXAM_RCPT",
            "domain": "检查",
            "from_table": "EXAM.EXAM_MASTER",
            "from_columns": "PATIENT_ID+RCPT_NO",
            "to_table": "OUTPBILL.OUTP_ORDER_DESC",
            "to_columns": "PATIENT_ID+RCPT_NO",
            "join_condition": "EXAM.EXAM_MASTER.PATIENT_ID=OUTPBILL.OUTP_ORDER_DESC.PATIENT_ID AND EXAM.EXAM_MASTER.RCPT_NO=OUTPBILL.OUTP_ORDER_DESC.RCPT_NO",
            "relationship_type": "outpatient_rcpt_strong_key",
            "confidence": "A",
            "validation_level": "sample_100k",
            "validation_status": "sample_pass",
            "validation_metrics": json.dumps(
                {
                    "sample_limit": 100000,
                    "has_rcpt_ratio": 0.9999,
                    "matched_count": 99975,
                    "sample_matched_rows": 99975,
                    "orphan_count": 3,
                    "match_rate": 0.99997,
                },
                ensure_ascii=False,
            ),
            "import_action": "import_formal",
            "review_status": "approved",
            "source_evidence": "42_下一步工作与整改交接说明.md 3.4 门诊检验/检查强键；用户确认纳入 final 包",
            "risk_note": "仅适用于有 RCPT_NO 的门诊检查记录",
            "suggestion": "纳入当前 HIS_READY 正式关系",
        },
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    core_rows = read_csv(SECONDARY_DIR / "secondary_core_tables_rechecked.csv")
    excluded_rows = read_csv(SECONDARY_DIR / "secondary_excluded_tables_rechecked.csv")
    relation_a_rows = read_csv(SECONDARY_DIR / "secondary_relationships_A_rechecked.csv")
    old_columns = read_csv(OUTPUT_DIR / "governance_columns.csv")

    table_rows = convert_core_tables(core_rows)
    table_keys = {normalize_key(row["schema_name"], row["table_name"]) for row in table_rows}
    table_domains = {row["full_name"].upper(): row["domain"] for row in table_rows}

    filtered_columns = [
        row
        for row in old_columns
        if normalize_key(row.get("schema_name", ""), row.get("table_name", "")) in table_keys
    ]
    column_counts: dict[str, int] = {}
    for row in filtered_columns:
        key = normalize_key(row.get("schema_name", ""), row.get("table_name", ""))
        column_counts[key] = column_counts.get(key, 0) + 1
    for row in table_rows:
        row["column_count"] = str(column_counts.get(normalize_key(row["schema_name"], row["table_name"]), 0))

    excluded_final = convert_excluded_tables(excluded_rows)
    relation_rows = convert_relations(relation_a_rows, table_domains)
    relation_rows.extend(outpatient_strong_key_relations())

    table_fields = list(table_rows[0].keys())
    excluded_fields = list(excluded_final[0].keys())
    column_fields = list(old_columns[0].keys())
    relation_fields = list(relation_rows[0].keys())

    write_csv(OUTPUT_DIR / "governance_tables_final.csv", table_rows, table_fields)
    write_csv(OUTPUT_DIR / "governance_excluded_tables_final.csv", excluded_final, excluded_fields)
    write_csv(OUTPUT_DIR / "governance_columns_final.csv", filtered_columns, column_fields)
    write_csv(OUTPUT_DIR / "governance_relations_formal_final.csv", relation_rows, relation_fields)
    write_csv(OUTPUT_DIR / "governance_deferred_relations_final.csv", [], relation_fields)

    missing_column_tables = sorted(
        row["full_name"] for row in table_rows if column_counts.get(normalize_key(row["schema_name"], row["table_name"]), 0) == 0
    )
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "secondary rechecked HIS_READY assets",
        "system_code": SYSTEM_CODE,
        "source_code": SOURCE_CODE,
        "inputs": {
            "core_tables": "secondary_core_tables_rechecked.csv",
            "excluded_tables": "secondary_excluded_tables_rechecked.csv",
            "relationships_A": "secondary_relationships_A_rechecked.csv",
            "columns_base": "governance_columns.csv",
        },
        "outputs": {
            "tables": "governance_tables_final.csv",
            "columns": "governance_columns_final.csv",
            "formal_relations": "governance_relations_formal_final.csv",
            "excluded_tables": "governance_excluded_tables_final.csv",
            "deferred_relations": "governance_deferred_relations_final.csv",
        },
        "counts": {
            "input_core_tables": len(core_rows),
            "output_tables": len(table_rows),
            "input_excluded_tables": len(excluded_rows),
            "output_excluded_tables": len(excluded_final),
            "output_columns": len(filtered_columns),
            "input_A_relations": len(relation_a_rows),
            "added_outpatient_strong_key_relations": 2,
            "output_formal_relations": len(relation_rows),
            "output_deferred_relations": 0,
        },
        "acceptance": {
            "table_count_matches_core_input": len(table_rows) == len(core_rows),
            "excluded_count_matches_input": len(excluded_final) == len(excluded_rows),
            "relation_count_matches_A_plus_outpatient": len(relation_rows) == len(relation_a_rows) + 2,
            "outpatient_strong_keys_present": all(
                relation_id in {row["relationship_id"] for row in relation_rows}
                for relation_id in ["OUT_LAB_RCPT", "OUT_EXAM_RCPT"]
            ),
            "tables_without_columns_in_base_snapshot": len(missing_column_tables),
        },
        "tables_without_columns_in_base_snapshot": missing_column_tables,
    }
    with (OUTPUT_DIR / "governance_import_final_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["acceptance"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
