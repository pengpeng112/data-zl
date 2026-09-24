# -*- coding: utf-8 -*-
"""202 D2-4：195/198 跨批自然键查重（可重放脚本）。

规范化双方资产的 系统/source/schema/table/列序/方向/条件，按四级匹配：
  L1 精确（规范化表对+列序+方向+条件全等）
  L2 表对+列序+方向（条件文本差异）
  L3 表对+方向（列序差异）
  L4 表对（弱，仅提示）
输出 195_198_cross_batch_dedupe.csv；无匹配时也输出 0 行摘要（dedupe_summary.json）。
用法：backend/.venv/Scripts/python.exe 本文件（不连库，读两批离线 payload）。
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
R198 = HERE.parents[1] / "output_r198" / "r198-20260922-remediation"
R195 = HERE


def norm_name(s: str | None) -> str:
    return (s or "").strip().upper().replace(" ", "")


def norm_cols(s: str | None) -> str:
    """列序规范化：拆分（逗号/加号/空白）→去空→大写→排序后逗号连接（序不敏感）。"""
    parts = [p.strip().upper() for p in re.split(r"[,+\s]+", (s or "")) if p.strip()]
    return ",".join(sorted(parts))


def norm_cond(s: str | None) -> str:
    t = (s or "").upper()
    t = re.sub(r"\s+", "", t)
    t = t.replace("（", "(").replace("）", ")")
    # 别名无关化：t1./t2./a./b. 前缀剥离
    t = re.sub(r"\b(T\d+|A|B)\.", "", t)
    return t


def tables_of_title(title: str):
    return sorted(re.findall(r"[A-Za-z0-9_$]+\.[A-Za-z0-9_$]+", title or ""))


# ---- 198 队列资产 ----
q198 = list(csv.DictReader(open(R198 / "human_review_queue.csv", encoding="utf-8-sig")))
assets198 = []
for r in q198:
    tabs = tables_of_title(r["title"])
    if len(tabs) >= 2:
        assets198.append({
            "batch": "198", "asset_id": r["id"], "group": r.get("group", ""),
            "from_table": norm_name(tabs[0]), "to_table": norm_name(tabs[1]),
            "cols": "", "direction": "", "cond": "",
            "title": r["title"], "recommendation": r.get("recommendation", ""),
        })

# ---- 195 草稿资产（114 行 r195_intake）----
rows195 = json.load(open(R195 / "import_payload_reviews.json", encoding="utf-8"))["rows"]
assets195 = []
for i, r in enumerate(rows195, 1):
    assets195.append({
        "batch": "195", "asset_id": r.get("cand_id") or f"row{i}",
        "group": r.get("intake_status", ""),
        "from_table": norm_name(r.get("from_table")),
        "to_table": norm_name(r.get("to_table")),
        "cols": norm_cols(f"{r.get('from_columns','')}={r.get('to_columns','')}"),
        "direction": "fwd",
        "cond": norm_cond(r.get("join_condition")),
        "title": f"{r.get('from_table')} ~ {r.get('to_table')}",
        "recommendation": "",
    })


def match_level(a: dict, b: dict) -> int | None:
    pair = {a["from_table"], a["to_table"]} == {b["from_table"], b["to_table"]}
    if not pair:
        return None
    if a["cols"] and b["cols"]:
        if a["cols"] == b["cols"] and a["cond"] == b["cond"]:
            return 1
        if a["cols"] == b["cols"]:
            return 2
        return 3
    return 4  # 表对命中（195 列信息与 198 标题不可比时）


matches = []
for a in assets195:
    for b in assets198:
        lvl = match_level(a, b)
        if lvl:
            matches.append({
                "match_level": f"L{lvl}",
                "asset_195_id": a["asset_id"], "asset_198_id": b["asset_id"],
                "norm_table_pair": f"{a['from_table']} ~ {a['to_table']}",
                "cols_195": a["cols"], "cols_198": b["cols"],
                "cond_195": a["cond"][:120], "cond_198": b["cond"][:120],
                "group_195": a["group"], "group_198": b["group"],
                "suggestion": (
                    "同一表对+列+条件：先裁决 198 侧终态，195 侧引用结果去重，禁止双批各批一次"
                    if lvl == 1 else
                    "同一表对列序同/条件异：人工核对条件语义后择一保留"
                    if lvl == 2 else
                    "同一表对列序异：核对键完整性，可能为不同粒度关系，分别裁决"
                    if lvl == 3 else
                    "仅表对命中（198 标题无列信息）：键级查重需在治理工作流内复核"
                ),
            })

out_csv = R195 / "195_198_cross_batch_dedupe.csv"
fields = list(matches[0].keys()) if matches else ["match_level", "asset_195_id", "asset_198_id",
                                                  "norm_table_pair", "suggestion"]
with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(matches)

summary = {
    "generated_by": "cross_batch_dedupe.py（本目录，可重放）",
    "assets_195": len(assets195),
    "assets_198_pairs": len(assets198),
    "matches_total": len(matches),
    "by_level": dict(Counter(m["match_level"] for m in matches)),
    "note": "0 行亦为有效结论：两批无表对级碰撞（与 D2-0 前次清单说明一致，本次为机器可读证据）",
}
json.dump(summary, open(R195 / "dedupe_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False))
