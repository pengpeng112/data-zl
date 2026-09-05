# -*- coding: utf-8 -*-
"""171 后续（2026-09-01 用户授权）：CDMS 无纸化人员权限关系 → 平台关系复核草稿。

仿 backend/scripts/import_ecg_relation_reviews.py 先例：
- 仅落 asset_relation_reviews（draft），不进正式关系层；
- 端点表/字段先对平台元数据校验，缺则 blocked；
- 对正式关系与既有草稿双重防重；--dry-run 回滚。
关系证据：2026-09-01 只读 live 核对（T_MSS_AUTHMAPPING：FUSER=操作人恒 admin、FID=被授权人工号、
FTYPE 模板 0/2/3/5/10；30 在户用户仅 6 人有权限行；模板科室码=EMP_DICT.FDEPT=KESHID.AAA）。
"""
from __future__ import annotations

import argparse
import json

import psycopg

DSN = "postgresql://postgres@127.0.0.1:15432/data_asset"
SOURCE = "paperless_cdms_oracle_10_10_10_93"
EVIDENCE = (
    "171 后续 2026-09-01 CDMS 只读 live 核对：T_MSS_AUTHMAPPING.FUSER=操作人(恒admin)，"
    "被授权人在 FID；FTYPE 0=角色GUID/2=科室码/3=人员权限100005/5=A00001/10=标志位，"
    "FST=0 生效；全库 1872 个 FID 有权限行；下乡 30 在户用户仅 6 人有权限行；"
    "模板科室码与 T_MSS_EMP_DICT.FDEPT、KESHID.AAA 三方一致；candidate-only，无声明外键"
)

CANDIDATES = [
    {
        "from_table": "CDMS.T_MSS_EMP_DICT", "from_columns": ["FLOGINNAME"],
        "to_table": "CDMS.T_MSS_AUTHMAPPING", "to_columns": ["FID"],
        "confidence": "C",
        "desc": "无纸化用户(T_MSS_EMP_DICT)与权限映射(T_MSS_AUTHMAPPING)按工号 1:N",
        "logic": "用户-权限映射：一人最多 5 行模板（角色/科室/人员/其他/标志）；FUSER 是操作人不是被授权人",
    },
    {
        "from_table": "CDMS.T_MSS_EMP_DICT", "from_columns": ["FDEPT"],
        "to_table": "CDMS.KESHID", "to_columns": ["AAA"],
        "confidence": "C",
        "desc": "无纸化用户所属科室(FDEPT)关联科室字典(KESHID.AAA=码/BBB=名)",
        "logic": "科室字典：KESHID.AAA=6 位科室码、BBB=科室名；EMP_DICT.FDEPT 与权限模板 FTYPE=2 行取值同源",
    },
    {
        "from_table": "CDMS.T_MSS_AUTHMAPPING", "from_columns": ["FAUTHORITYID"],
        "to_table": "CDMS.KESHID", "to_columns": ["AAA"],
        "confidence": "C",
        "desc": "无纸化科室权限行(FTYPE='2')的 FAUTHORITYID 关联科室字典",
        "logic": "仅 FTYPE='2'（科室权限）行成立；FTYPE='3' 的 100005 为人员权限常量，不入本关系",
    },
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    c = psycopg.connect(DSN, connect_timeout=8)
    cur = c.cursor()
    summary = {"dry_run": args.dry_run, "inserted": 0, "existing": 0, "blocked": []}

    cur.execute("select coalesce(max(id),0) from asset.asset_relation_reviews")
    next_id = cur.fetchone()[0] + 1

    for item in CANDIDATES:
        ft = item["from_table"].split(".")[-1]
        tt = item["to_table"].split(".")[-1]
        missing = []
        for tbl, cols in ((ft, item["from_columns"]), (tt, item["to_columns"])):
            cur.execute(
                "select 1 from asset.asset_tables where source_code=%s and table_name=%s",
                (SOURCE, tbl))
            if not cur.fetchone():
                missing.append(f"table:{tbl}")
                continue
            for col in cols:
                cur.execute(
                    "select 1 from asset.asset_columns where source_code=%s and table_name=%s and column_name=%s",
                    (SOURCE, tbl, col))
                if not cur.fetchone():
                    missing.append(f"column:{tbl}.{col}")
        if missing:
            summary["blocked"].append({"edge": item["desc"], "reason": missing})
            continue

        condition = " AND ".join(
            f"{item['from_table']}.{a} = {item['to_table']}.{b}"
            for a, b in zip(item["from_columns"], item["to_columns"]))
        cur.execute(
            "select 1 from asset.asset_relations where from_table=%s and to_table=%s and join_condition=%s",
            (item["from_table"], item["to_table"], condition))
        if cur.fetchone():
            summary["existing"] += 1
            continue
        cur.execute(
            "select 1 from asset.asset_relation_reviews where from_table=%s and to_table=%s and join_condition=%s",
            (item["from_table"], item["to_table"], condition))
        if cur.fetchone():
            summary["existing"] += 1
            continue

        cur.execute(
            """insert into asset.asset_relation_reviews
            (id, relation_scope, from_system_code, from_source_code, from_table, from_columns,
             to_system_code, to_source_code, to_table, to_columns, join_condition,
             relation_desc_cn, business_logic_cn, confidence, validation_status, review_status, source_evidence)
            values (%s,'formal','PAPERLESS_CDMS',%s,%s,%s,'PAPERLESS_CDMS',%s,%s,%s,%s,%s,%s,%s,'pending','draft',%s)""",
            (next_id, SOURCE, item["from_table"], "+".join(item["from_columns"]),
             SOURCE, item["to_table"], "+".join(item["to_columns"]), condition,
             item["desc"], item["logic"], item["confidence"], EVIDENCE[:2000]))
        next_id += 1
        summary["inserted"] += 1

    if args.dry_run:
        c.rollback()
    else:
        c.commit()
    c.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
