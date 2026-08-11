"""Backfill catalog display names from explored platform metadata only.

No business database is contacted.  Apply mode writes only the platform
catalog and requires an explicit confirmation string.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal
from app.models.asset import AssetTable
from app.models.asset_system import AssetDataSource, AssetSourceSchema, AssetSystem
from app.services.asset_catalog import CANONICAL_SYSTEMS

CONFIRMATION = "BACKFILL-CATALOG-DISPLAY-NAMES"

SYSTEM_NAMES = CANONICAL_SYSTEMS

SCHEMA_NAMES = {
    "HIS": "HIS业务镜像区", "ODS": "标准视图区", "CDA": "标准字典区",
    "MTL": "老电子病历区", "JHEMR": "新电子病历区", "YBEMR": "电子病历交换区",
    "YDHL": "移动护理镜像区", "SM": "手术麻醉镜像区", "LIS": "检验镜像区",
    "PACS": "影像镜像区", "MEDSURGERY": "手术麻醉业务库", "MEDCOMM": "手麻公共字典库",
    "MEDICU": "重症监护业务库", "LUNA_MCS_SDSEY": "移动护理业务库",
    "DBO": "LIS业务库", "CDMS": "无纸化病案业务库", "JHFILE": "电子病历文件库",
    "JHCDR": "电子病历临床数据仓库", "PUBLIC": "公共模式",
}

TOKENS = {
    "PAT": "患者", "PATIENT": "患者", "MASTER": "主记录", "INDEX": "索引", "VISIT": "就诊",
    "INP": "住院", "OUTP": "门诊", "ORDER": "医嘱", "ORDERS": "医嘱", "EXAM": "检查",
    "LAB": "检验", "RESULT": "结果", "REPORT": "报告", "ITEM": "项目", "ITEMS": "项目",
    "OPERATION": "手术", "OPER": "手术", "ANESTHESIA": "麻醉", "ANES": "麻醉",
    "SCHEDULE": "排班", "PLAN": "计划", "RECORD": "记录", "DETAIL": "明细", "DICT": "字典",
    "DEPT": "科室", "STAFF": "人员", "USER": "用户", "ROLE": "角色", "PERMISSION": "权限",
    "NURSING": "护理", "NURSE": "护理", "VITAL": "生命体征", "DOC": "文档", "DOCUMENT": "文档",
    "FILE": "文件", "CONTENT": "内容", "DIAGNOSIS": "诊断", "DRUG": "药品", "FEE": "费用",
    "BILL": "费用", "PRESC": "处方", "APPOINT": "预约", "ARCHIVE": "归档", "LOG": "日志",
    "CONFIG": "配置", "MAP": "映射", "MAPPING": "映射", "CLASS": "分类", "TYPE": "类型",
    "INFO": "信息", "FORM": "表单", "ASSESS": "评估", "MONITOR": "监护", "DATA": "数据",
}


def _has_chinese(value: str | None) -> bool:
    return bool(value and re.search(r"[\u4e00-\u9fff]", value))


def _suggest(table_name: str, schema_cn: str) -> str:
    parts = [p for p in re.split(r"[^A-Z0-9]+", (table_name or "").upper()) if p and not p.isdigit()]
    translated = []
    for part in parts:
        word = TOKENS.get(part)
        if word and word not in translated:
            translated.append(word)
    if translated:
        return "".join(translated) + ("表" if not translated[-1].endswith(("表", "记录", "字典", "明细")) else "")
    return f"{schema_cn}数据表"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    with SessionLocal() as db:
        systems = db.scalars(select(AssetSystem)).all()
        sources = {r.source_code: r for r in db.scalars(select(AssetDataSource)).all()}
        tables = db.scalars(select(AssetTable)).all()
        inventory = {
            (r.source_code, (r.schema_name or "").upper()): r
            for r in db.scalars(select(AssetSourceSchema)).all()
        }
        schema_keys = {
            (t.source_code or "", (t.schema_name or t.namespace_name or "").upper()) for t in tables
        }
        summary = {"systems_named": 0, "schemas_created": 0, "schemas_named": 0, "database_comments": 0, "ai_suggestions": 0}
        for row in systems:
            if row.system_code in SYSTEM_NAMES and row.system_name_cn != SYSTEM_NAMES[row.system_code]:
                row.system_name_cn = SYSTEM_NAMES[row.system_code]
                summary["systems_named"] += 1
        for source_code, schema_name in sorted(schema_keys):
            row = inventory.get((source_code, schema_name))
            if not row:
                row = AssetSourceSchema(source_code=source_code, schema_name=schema_name)
                db.add(row)
                inventory[(source_code, schema_name)] = row
                summary["schemas_created"] += 1
            label = SCHEMA_NAMES.get(schema_name)
            if label:
                row.schema_name_cn = label
                row.name_cn_source = "探库确认"
                row.name_cn_status = "confirmed"
                summary["schemas_named"] += 1
        for table in tables:
            if table.table_name_cn:
                if not table.name_cn_source:
                    table.name_cn_source = "已有资产"
                    table.name_cn_status = "confirmed"
                continue
            if _has_chinese(table.comment):
                table.table_name_cn = (table.comment or "").strip()[:200]
                table.name_cn_source = "数据库原始注释"
                table.name_cn_status = "confirmed"
                summary["database_comments"] += 1
                continue
            schema = (table.schema_name or table.namespace_name or "").upper()
            schema_cn = SCHEMA_NAMES.get(schema, "业务")
            table.table_name_cn = _suggest(table.table_name or "", schema_cn)
            table.name_cn_source = "AI建议名称"
            table.name_cn_status = "pending_review"
            summary["ai_suggestions"] += 1
        summary["source_writes"] = 0
        summary["platform_rows_to_update"] = sum(summary.values())
        if not args.apply:
            db.rollback()
            print(summary)
            return
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
        db.commit()
        print({"mode": "apply", **summary})


if __name__ == "__main__":
    main()
