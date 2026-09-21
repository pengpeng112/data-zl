# -*- coding: utf-8 -*-
"""S2b：对象引用 → 物理身份解析 + 平台元数据存在性核对。
规则：
- 视图部署实例由视图 Owner 推定（ODS→DATA_CENTER、LUNA_MCS_SDSEY→MOBILE_NURSING、HISUSER→HIS、
  DBO→PATHOLOGY、HRPSEY656→HRP、C##NIS5→INFECTION_SURVEILLANCE）。
- 引用对象：带 Owner 用 Owner；裸名用视图 Owner 作默认 schema。
- JHEMR Owner 额外核对 JHEMR_VASTBASE（跨实例歧义）。
产物：platform_check_input.csv（喂给远端查询）、合并后写 source_mapping.csv
"""
import csv
import json
import os
from collections import defaultdict
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = json.load(open(os.path.join(RUN_DIR, "object_refs.json"), encoding="utf-8"))

OWNER2SYS = {
    "ODS": "DATA_CENTER",
    "LUNA_MCS_SDSEY": "MOBILE_NURSING",
    "HISUSER": "HIS",
    "DBO": "PATHOLOGY",
    "HRPSEY656": "HRP",
    "C##NIS5": "INFECTION_SURVEILLANCE",
}

rows = []
seen = set()
for f in REFS["files"]:
    vowner = None
    for vn in f["view_names"]:
        if "." in vn:
            vowner = vn.split(".")[0].strip('"').upper()
            break
    for r in f["refs"]:
        parts = [p.strip('"').upper() for p in r.split(".")]
        if len(parts) == 1:
            schema, tab = vowner, parts[0]
        else:
            schema, tab = parts[-2], parts[-1]
        vname = f["view_names"][0] if f["view_names"] else ""
        key = (schema, tab)
        if key in seen:
            # 记录追加引用文件
            for x in rows:
                if (x["schema"], x["table"]) == key:
                    x["ref_files"] += 1
                    if f["category"] == "root_jhemr_draft":
                        x["draft_ref"] = "Y"
            continue
        seen.add(key)
        sys_primary = OWNER2SYS.get(vowner, "?")
        rows.append({
            "schema": schema, "table": tab,
            "view_owner": vowner or "", "deploy_system": sys_primary,
            "ref_files": 1, "draft_ref": "Y" if f["category"] == "root_jhemr_draft" else "",
        })

# JHEMR schema 或跨实例引用 → 追加 JHEMR_VASTBASE 核对标记
for x in rows:
    x["extra_systems"] = "JHEMR_VASTBASE" if x["schema"] == "JHEMR" else ""

print(f"待核对对象: {len(rows)}")
json.dump(rows, open(os.path.join(RUN_DIR, "platform_check_input.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 生成远端 SQL（VALUES 一次性比对）
vals = ",\n".join(f"('{x['schema']}','{x['table']}')" for x in rows)
sql = f"""
with q(schema_name,table_name) as (values
{vals}
)
select q.schema_name, q.table_name, t.system_code, t.source_code, t.column_count, t.include_status
from q join asset.asset_tables t
  on upper(t.schema_name)=q.schema_name and upper(t.table_name)=q.table_name
order by 1,2,3;
"""
open(os.path.join(RUN_DIR, "sql", "s2_platform_check.sql"), "w", encoding="utf-8").write(sql)
print("sql/s2_platform_check.sql 写出")
with open(os.path.join(RUN_DIR, "platform_check_input.csv"), "w", encoding="utf-8-sig", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
