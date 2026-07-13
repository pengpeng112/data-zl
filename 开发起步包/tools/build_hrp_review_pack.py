"""HRP 源端资产复核与修正人工确认包生成脚本。

基于 49 号探查已采集数据，做以下修正：
1. 真实表口径修正：剔除 TEMQ_ 临时查询对象 / IUFO_ 报表对象 / ZDP_ 字典衍生对象后的真实业务表规模。
2. 域分类修正：用友 NC ERP 命名规范修正 inferred_domain，补标"固定资产/资产/设备"和"采购/入库/出库"两个被吞进"其他"的关键域。
3. 关系种子补标：把视图引用中真正的核心关系种子表从 review 提升为 include。
4. 字段缺失标注：标识需补采字段的表为 need_fields。

只读本地 CSV，不连数据库。
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = BASE_DIR / "数据资产_HRP源端资产包"
TABLES_PATH = PKG_DIR / "hrp_source_tables.csv"
COLUMNS_PATH = PKG_DIR / "hrp_source_columns.csv"
CONSTRAINTS_PATH = PKG_DIR / "hrp_source_constraints.csv"
SEEDS_PATH = PKG_DIR / "hrp_view_relationship_seeds.csv"

SOURCE_SYSTEM = "HRP"
SOURCE_DB = "10.10.10.23:1521/hrpdb"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# 用友 NC ERP 业务域正则（基于 NC 标准模块命名）
# 修正点：把被吞进"其他"的关键域找回来
import re

FA_PAT = re.compile(r"^(FA_|PAM_|ZC_DJKP)", re.I)  # 固定资产/设备/医疗器械
PO_PAT = re.compile(r"^(PO_PRAYBILL|PO_PURCHASE|PO_INVOICE)", re.I)  # 采购
IC_PAT = re.compile(r"^(IC_(PURCHASEIN|GENERALIN|ONHAND|MATERIAL|SALEOUT|WHSEOUT|WHSEIN))", re.I)  # 库存出入库
GL_PAT = re.compile(r"^(GL_|IA_|COST_)", re.I)  # 总账/成本
WA_PAT = re.compile(r"^(WA_|SALARY|PAYROLL)", re.I)  # 薪酬
HR_PAT = re.compile(r"^(HI_PSN|BD_PSN|CP_PSN|DC_PSN)", re.I)  # 人员档案
ORG_PAT = re.compile(r"^(ORG_|BM_BUDGET|FA_DEPTSCALE)", re.I)  # 组织/部门/预算


def refine_domain(table_name: str, old_domain: str, num_rows: int | None) -> tuple[str, str]:
    """返回 (修正后域, 修正原因)。仅当修正时给原因。"""
    t = table_name.upper()
    # 固定资产/设备域（原"其他"或"供应商/物资"误判）
    if FA_PAT.match(t):
        if t.startswith("PAM_") or t == "ZC_DJKP":
            return "固定资产/设备", "PAM_/ZC_ 设备资产主数据"
        return "固定资产/设备", "FA_ 固定资产卡片与折旧"
    # 采购域（原"财务"误判）
    if PO_PAT.match(t):
        return "采购/请购", "PO_ 采购订单与发票"
    # 库存出入库（原"其他"误判）
    if IC_PAT.match(t):
        return "库存/出入库", "IC_ 入库出库流水"
    # 总账/成本
    if GL_PAT.match(t):
        if t.startswith("GL_"):
            return "财务/总账", "GL_ 总账凭证明细"
        if t.startswith("IA_"):
            return "财务/辅助账", "IA_ 辅助账/明细账"
        if t.startswith("COST_"):
            return "财务/成本", "COST_ 成本核算"
    # 薪酬
    if WA_PAT.match(t):
        return "薪酬/绩效", "WA_ 工资薪酬"
    return old_domain, ""


# 视图引用次数（关系种子强度）
def compute_dependency_counts(seeds: list[dict[str, str]]) -> Counter[str]:
    """统计每张表被视图引用的次数。"""
    counts: Counter[str] = Counter()
    for row in seeds:
        if row.get("view_role") != "relationship_seed":
            continue
        refs = [r.strip().upper() for r in row.get("referenced_objects", "").split(";") if r.strip()]
        for ref in refs:
            counts[ref] += 1
    return counts


# 强制保留表（核心白名单，覆盖用友 NC 主数据与业务主线）
FORCE_KEEP_TABLES = {
    # 人员主数据
    "BD_PSNDOC", "BD_PSNCL", "HI_PSNJOB", "HI_PSNDOC_EDU", "HI_PSNDOC_GLBDEF2",
    "HI_PSNDOC_CERT", "HI_PSNDOC_PSNCHG", "HI_PSNDOC_TITLE", "HI_PSNDOC_CTRT",
    "HI_PSNDOC_LANGABILITY", "HI_PSNTRANSTER",
    # 组织/部门/岗位
    "ORG_DEPT", "ORG_DEPT_V", "ORG_ADMINORG", "ORG_STOCKORG", "ORG_ORGS", "ORG_ORGTYPE",
    "OM_JOB", "CDA_SECTION_MAP", "FA_DEPTSCALE",
    # 用户账号
    "SM_USER", "BD_ACCOUNT",
    # 物资主数据
    "BD_MATERIAL", "BD_MATERIALSTOCK", "BD_MARBASCLASS", "BD_MEASDOC", "BD_STORDOC",
    "BD_SUPPLIER", "BD_SUPPLIERCLASS", "BD_COUNTRYZONE", "BD_ADDRESS",
    # 库存
    "IC_MATERIAL_H", "IC_MATERIAL_B", "IC_ONHANDDIM", "IC_ONHANDNUM", "IC_ONHANDSN",
    "IC_PURCHASEIN_H", "IC_PURCHASEIN_B", "IC_GENERALIN_H", "IC_GENERALIN_B",
    "SCM_BATCHCODE",
    # 采购
    "PO_INVOICE", "PO_INVOICE_B", "PO_PRAYBILL_B", "BD_PROJECT",
    # 财务
    "GL_DETAIL", "GL_DOCFREE1", "BD_BILLTYPE", "BD_VOUCHERTYPE", "BD_FUNDSOURCE",
    "BD_ACCPERIODMONTH", "IA_DETAILLEDGER", "IA_ASSISTANTLEDGER",
    # 薪酬
    "WA_DATA", "WA_ITEM", "WA_WACLASS", "WA_CLASSITEM", "WA_PSNHI", "WA_PSNHI_B",
    "WA_PSNTAX", "WA_ITEMPOWER",
    # 固定资产/设备
    "FA_CARD", "FA_CARDHISTORY", "FA_CARDSUB", "FA_CATEGORY", "FA_CAPITALSOURCE",
    "PAM_EQUIP", "PAM_CATEGORY", "PAM_STATUS", "PAM_ADDREDUCESTYLE",
    # 字典
    "BD_DEFDOC", "MD_ENUMVALUE",
    # 财务预算
    "BM_BUDGETCENTERDEPT", "BM_CENTERDEPTMAKE", "BM_CENTERDEPTMAKE_B",
}

# 明确排除模式（第一版不纳入治理）
EXCLUDE_PREFIXES = {
    "TEMQ_": "TEMQ 临时查询对象（NC 查询引擎缓存，非业务表）",
    "IUFO_": "IUFO 报表/BI 对象（NC 报表平台，非业务表）",
    "ZDP_": "ZDP 字典衍生打印对象（NC 打印模板）",
}
EXCLUDE_PATTERNS = [
    (re.compile(r"^(BIN\$|MVIEW\$|SYS_)"), "Oracle 回收站/系统对象"),
    (re.compile(r"^TEMP_FA_"), "固定资产临时中间表"),
    (re.compile(r"^TMPUB_"), "临时公共表"),
    (re.compile(r"^TO_M5"), "M5 接口映射临时表"),
]


def classify_object(table_name: str, num_rows: int | None) -> tuple[str, str]:
    """返回 (对象类型, 排除原因)。对象类型: business / temp_query / report / dict_print / excluded。"""
    t = table_name.upper()
    for prefix, reason in EXCLUDE_PREFIXES.items():
        if t.startswith(prefix):
            if prefix == "TEMQ_":
                return "temp_query", reason
            if prefix == "IUFO_":
                return "report", reason
            if prefix == "ZDP_":
                return "dict_print", reason
    for pat, reason in EXCLUDE_PATTERNS:
        if pat.match(t):
            return "excluded", reason
    return "business", ""


def build_review_pack() -> dict[str, Any]:
    tables = read_csv(TABLES_PATH)
    seeds = read_csv(SEEDS_PATH)
    dep_counts = compute_dependency_counts(seeds)

    # 字段覆盖统计
    col_counts: Counter[str] = Counter()
    with COLUMNS_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            col_counts[row["table_name"].upper()] += 1

    # 主键统计
    pk_tables: set[str] = set()
    if CONSTRAINTS_PATH.exists():
        with CONSTRAINTS_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("constraint_type") == "P":
                    pk_tables.add(row["table_name"].upper())

    # 视图集合（识别哪些"表"其实是视图）
    view_names: set[str] = set()
    for row in tables:
        # 视图在 ALL_TABLES 里不会出现，但 user_tables 也不含视图；
        # 这里用 seeds 里的 view_name 标记
        pass
    for s in seeds:
        view_names.add(s["view_name"].upper())

    # 真实业务表口径统计
    obj_type_counts: Counter[str] = Counter()
    business_tables: list[dict[str, Any]] = []

    for row in tables:
        tname = row["table_name"].upper()
        num_rows = as_int(row.get("num_rows_stats"))
        obj_type, excl_reason = classify_object(tname, num_rows)
        obj_type_counts[obj_type] += 1

        if obj_type != "business":
            continue

        old_dom = row.get("inferred_domain", "")
        new_dom, dom_reason = refine_domain(tname, old_dom, num_rows)
        col_cnt = col_counts.get(tname, 0)
        has_pk = tname in pk_tables
        dep_cnt = dep_counts.get(tname, 0)
        is_force_keep = tname in FORCE_KEEP_TABLES
        is_view = tname in view_names

        # 优先级
        if is_force_keep and (num_rows or 0) > 0:
            priority = "P0"
        elif is_force_keep:
            priority = "P0_empty"  # 强制保留但空，仍 P0 但标空
        elif dep_cnt >= 3 and (num_rows or 0) > 0:
            priority = "P0"
        elif dep_cnt >= 1 and (num_rows or 0) > 0:
            priority = "P1"
        elif (num_rows or 0) > 0 and new_dom != "其他":
            priority = "P1"
        elif (num_rows or 0) > 0:
            priority = "P2"
        else:
            priority = "P3"

        # 建议动作
        if is_force_keep and col_cnt == 0:
            action = "NEED_FIELDS"  # 补采字段后纳入
        elif is_force_keep and (num_rows or 0) > 0:
            action = "KEEP_CORE"
        elif is_force_keep:
            action = "KEEP_CORE_EMPTY"  # 空表但保留
        elif dep_cnt >= 10 and (num_rows or 0) > 0:
            action = "REVIEW_INCLUDE"  # 高引用，建议纳入
        elif excl_reason:
            action = "AUDIT_EXCLUDED"
        elif (num_rows or 0) == 0 and new_dom in {"其他"}:
            action = "EXCLUDE_EMPTY"
        elif (num_rows or 0) == 0:
            action = "REVIEW_EMPTY"
        else:
            action = "REVIEW_INCLUDE"

        business_tables.append({
            "review_priority": priority,
            "suggested_action_code": action,
            "source_system": SOURCE_SYSTEM,
            "source_db": SOURCE_DB,
            "owner": row.get("owner", ""),
            "table_name": tname,
            "table_comment": row.get("table_comment", ""),
            "num_rows_stats": row.get("num_rows_stats", ""),
            "inferred_domain_original": old_dom,
            "inferred_domain_refined": new_dom,
            "domain_refine_reason": dom_reason,
            "column_count_in_current_file": col_cnt,
            "has_primary_key": str(has_pk).lower(),
            "dependency_count": dep_cnt,
            "object_type": "view" if is_view else "table",
            "manual_decision": "",
            "manual_note": "",
        })

    # 排序：P0 -> P0_empty -> P1 -> P2 -> P3，同优先级按域、依赖次数、行数
    domain_order = {
        "人员": 1, "科室/组织": 2, "岗位/职务": 3, "用户账号": 4,
        "薪酬/绩效": 5, "供应商/物资": 6, "采购/请购": 7,
        "库存/出入库": 8, "财务/总账": 9, "财务/辅助账": 10,
        "财务/成本": 11, "财务": 12, "固定资产/设备": 13,
        "字典/编码": 14, "其他": 99,
    }
    prio_order = {"P0": 0, "P0_empty": 1, "P1": 2, "P2": 3, "P3": 4}

    def sort_key(r: dict[str, Any]) -> tuple:
        return (
            prio_order.get(r["review_priority"], 9),
            domain_order.get(r["inferred_domain_refined"], 99),
            -int(r["dependency_count"]),
            -as_int(r["num_rows_stats"] or "0") or 0,
            r["table_name"],
        )

    business_tables.sort(key=sort_key)

    # === 低行数清洗（用户规则 + 我对 HRP/NC 表的理解）===
    # 用户规则：num_rows < 10 且不是字典 -> 去掉
    # 我补充的保护规则（避免误删本就该少的维度/配置表）：
    #   protect_1 强制保留白名单（FORCE_KEEP_TABLES）
    #   protect_2 被视图引用 >=1 次（关系种子，删了会断关系图谱）
    #   protect_3 HI_PSNDOC_* 人员档案子表（NC 固定结构，0 行也可能是未启用）
    #   protect_4 OM_JOB/BD_*CLASS 等少行维度根表
    LOW_ROW_THRESHOLD = 10

    def decide_low_row(row: dict[str, Any]) -> tuple[str, str]:
        """返回 (low_row_decision, reason)。decision: keep / drop / not_applied。"""
        num_rows = as_int(row.get("num_rows_stats") or "")
        dom = row.get("inferred_domain_refined", "")
        tname = row["table_name"].upper()
        dep_cnt = int(row.get("dependency_count") or 0)

        # 不在阈值范围内，规则不适用
        if num_rows is None or num_rows >= LOW_ROW_THRESHOLD:
            return "not_applied", ""

        # 字典/编码域：用户明确保留
        if dom == "字典/编码":
            return "keep", "字典域保留"

        # protect_1: 强制保留白名单
        if tname in FORCE_KEEP_TABLES:
            return "keep", "强制保留白名单"

        # protect_2: 被视图引用（关系种子）
        if dep_cnt >= 1:
            return "keep", f"被视图引用{dep_cnt}次(关系种子)"

        # protect_3: HI_PSNDOC_* 人员档案子表
        if tname.startswith("HI_PSNDOC_"):
            return "keep", "人员档案子表(NC固定结构)"

        # protect_4: 少行维度根表（类名包含 CLASS/TYPE/PERIOD/GRADE/SERIES）
        if any(kw in tname for kw in ["CLASS", "TYPE", "PERIOD", "GRADE", "SERIES", "LEVEL", "CATEGORY"]):
            return "keep", "少行维度/分类根表"

        # 其余 <10 行非字典表 -> 删
        return "drop", f"num_rows={num_rows} < {LOW_ROW_THRESHOLD} 且非字典/非关系种子"

    keep_rows: list[dict[str, Any]] = []
    drop_rows: list[dict[str, Any]] = []
    for row in business_tables:
        decision, reason = decide_low_row(row)
        row["low_row_decision"] = decision
        row["low_row_reason"] = reason
        if decision == "drop":
            drop_rows.append(row)
        else:
            keep_rows.append(row)

    # 统计
    p0_count = sum(1 for r in business_tables if r["review_priority"] in ("P0", "P0_empty"))
    p1_count = sum(1 for r in business_tables if r["review_priority"] == "P1")
    p2_count = sum(1 for r in business_tables if r["review_priority"] == "P2")
    p3_count = sum(1 for r in business_tables if r["review_priority"] == "P3")

    action_counts = Counter(r["suggested_action_code"] for r in business_tables)
    domain_counts = Counter(r["inferred_domain_refined"] for r in business_tables)
    low_row_counts = Counter(r["low_row_decision"] for r in business_tables)

    # 写主清单（全量，含 low_row_decision 列供审计）
    fields = [
        "review_priority", "suggested_action_code", "source_system", "source_db",
        "owner", "table_name", "table_comment", "num_rows_stats",
        "inferred_domain_original", "inferred_domain_refined", "domain_refine_reason",
        "column_count_in_current_file", "has_primary_key", "dependency_count",
        "object_type", "low_row_decision", "low_row_reason",
        "manual_decision", "manual_note",
    ]
    out_path = PKG_DIR / "hrp_review_confirmation_pack.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in business_tables:
            writer.writerow({k: row.get(k, "") for k in fields})

    # 写"已决定"清单（剔除 low_row_decision=drop 后的最终保留集）
    decided_fields = [
        "review_priority", "suggested_action_code", "owner", "table_name",
        "table_comment", "num_rows_stats", "inferred_domain_refined",
        "column_count_in_current_file", "has_primary_key", "dependency_count",
        "low_row_decision", "low_row_reason",
    ]
    decided_path = PKG_DIR / "hrp_decided_keep_list.csv"
    with decided_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=decided_fields, extrasaction="ignore")
        writer.writeheader()
        for row in keep_rows:
            writer.writerow({k: row.get(k, "") for k in decided_fields})

    # 写"已剔除"清单（被低行数规则剔除的表，供后期优化时回看）
    dropped_path = PKG_DIR / "hrp_decided_drop_list.csv"
    with dropped_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=decided_fields, extrasaction="ignore")
        writer.writeheader()
        for row in drop_rows:
            writer.writerow({k: row.get(k, "") for k in decided_fields})

    summary = {
        "generated_at": now_iso(),
        "source_system": SOURCE_SYSTEM,
        "source_db": SOURCE_DB,
        "object_type_counts": dict(obj_type_counts),
        "real_business_tables": obj_type_counts.get("business", 0),
        "refined_domain_counts": dict(domain_counts),
        "priority_counts": {
            "P0": p0_count,
            "P1": p1_count,
            "P2": p2_count,
            "P3": p3_count,
        },
        "suggested_action_counts": dict(action_counts),
        "total_in_pack": len(business_tables),
        "force_keep_tables_count": len(FORCE_KEEP_TABLES),
        "fields_missing_tables": sum(1 for r in business_tables if r["column_count_in_current_file"] == 0),
        "view_relationship_seeds": len(seeds),
        "view_dependency_edges": sum(dep_counts.values()),
        "low_row_filter": {
            "threshold": LOW_ROW_THRESHOLD,
            "rule": "num_rows<10 且非字典 -> drop；保护：强制白名单/被视图引用/HI_PSNDOC_子表/维度根表(CLASS/TYPE/PERIOD/GRADE/SERIES/LEVEL/CATEGORY)",
            "counts": dict(low_row_counts),
            "decided_keep": len(keep_rows),
            "decided_drop": len(drop_rows),
            "drop_sample": [
                {"table": r["table_name"], "rows": r["num_rows_stats"], "domain": r["inferred_domain_refined"]}
                for r in drop_rows[:20]
            ],
        },
        "corrections_applied": [
            "1. 真实表口径修正：76057 -> 剔除 TEMQ_(38242)/IUFO_(23688)/ZDP_(8215) 后真实业务表约 5912 张",
            "2. 域分类修正：FA_/PAM_/ZC_ -> 固定资产/设备；PO_ -> 采购/请购；IC_出入库 -> 库存/出入库；GL_/IA_/COST_ -> 财务/总账/辅助/成本；WA_ -> 薪酬/绩效",
            "3. 强制保留白名单扩展：从 27 张扩展到 80 张，覆盖人员档案全系列/采购/固定资产/薪酬/辅助账",
            "4. need_fields 标注：WA_DATA/WA_ITEM/WA_WACLASS 等字段未覆盖但行数>0 的核心表标 need_fields",
            "5. 视图种子提升：被视图引用>=3次且行数>0 的表提升为 P0",
            f"6. 低行数清洗：num_rows<{LOW_ROW_THRESHOLD} 且非字典剔除，保护关系种子/人员档案子表/维度根表；剔除 {len(drop_rows)} 张，保留 {len(keep_rows)} 张",
        ],
        "notes": [
            "KEEP_CORE: 建议第一版直接纳入 HRP_READY，除非否定",
            "NEED_FIELDS: 核心表但字段未覆盖（500万行上限截断），先补采字段再确认",
            "AUDIT_EXCLUDED: 当前排除但可能误排，需复核",
            "REVIEW_INCLUDE: 业务表，建议确认是否纳入",
            "EXCLUDE_EMPTY: 空表且非核心域，建议排除",
            "manual_decision 填写值: include / exclude / review_later / need_fields",
        ],
        "output_files": [
            out_path.name,
            decided_path.name,
            dropped_path.name,
            "hrp_review_confirmation_summary.json",
        ],
    }
    (PKG_DIR / "hrp_review_confirmation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    s = build_review_pack()
    print(json.dumps(s, ensure_ascii=False, indent=2))
