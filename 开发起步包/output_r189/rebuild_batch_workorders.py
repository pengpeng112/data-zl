# -*- coding: utf-8 -*-
"""189 批次工单离线重建（203 L2，OFFLINE_REBUILT_NOT_LIVE）。

依据：189 v1.1 §7.1（ODS 41）/§7.2（MTL 18）/§7.3（HISUSER 3）+ output_r189/view_ddl_backup/
的活库 DDL 备份（ODS=GET_DDL、HISUSER=ALL_VIEWS.TEXT，证据日期见 manifest/收尾复核_20260918）。
不连接任何数据库；时间谓词来自备份 DDL 离线解析，未做 live 复核。
"""
import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).parent
DDL = BASE / "view_ddl_backup"

ODS41 = [
    "V_EMR_ADMISSION_RECORD", "V_EMR_ADMISSION_RECORD_EXAM", "V_EMR_ADMISSION_DIAGNOSIS",
    "V_EMR_DISCHARGE_RECORD", "EMR_DISCHARGE_RECORD_DIAGNOSIS", "V_EMR_DOC_ORDER_DRUG",
    "V_EMR_DOC_ORDER_CHECK", "V_EMR_OUTPATIENT_RECIPE", "V_EMR_OUTPATIENT_RECIPE_ITEM",
    "V_EMR_ICH", "V_EMR_ICH_OPERATION", "V_EMR_ICH_ALLERGIES", "V_EMR_ICH_CHARGE",
    "V_EMR_ICH_DIAGNOSIS", "V_EMR_CONSUMABLES", "V_EMR_HOS_POSTOPER_RECORD",
    "V_EMR_HOS_PREOP_DISCUSS", "V_EMR_HOS_DND_RECORD", "V_EMR_HOS_DIFFIC_CASE_DISCUSS",
    "V_EMR_HOS_CHANGE_MAJOR_RECORD", "V_EMR_REFERRAL_HOS_RECORD", "V_EMR_HOS_CONSUL_RECORD",
    "V_EMR_HOS_SUCCESSION_RECORD", "V_EMR_HOS_SAVE_RECORD", "V_EMR_ADMISSION_DEAD_RECORD_TF",
    "V_EMR_OPERA_RECORD", "V_EMR_BOFORE_OPERA_RECORD", "V_EMR_ANESTHESIA_RECORD",
    "V_EMR_ANES_RECORD_BLOOD", "V_EMR_ANES_RECORD_MED", "V_EMR_ANES_AFTER_RECORD",
    "V_EMR_INFOR_OPERATION", "V_EMR_INFOR_ANESTHESIA", "V_EMR_IN_FEE_INFO_MAIN",
    "V_EMR_IN_FEE_INFO_CHILD", "V_EMR_OUT_FEE_INFO_MAIN", "V_EMR_OUT_FEE_INFO_CHILD",
    "V_EMR_OUTPATIENT_REGISTER", "V_EMR_OUTPATIENT_RECORD", "V_EMR_OUTPATIENT_DIAG",
    "V_EMR_OPERATION_NURSING",
]
HISUSER3 = ["V_EMR_EXAM_IMAGE_REP", "V_EMR_EXAM_IMAGE_PATH", "V_EMR_CONSUMABLES"]
MTL18 = [
    "V_EMR_ADMISSION_DEAD_RECORD_TF", "V_EMR_ADMISSION_RECORD", "V_EMR_DEATH_RECORD",
    "V_EMR_DISCHARGE_RECORD", "V_EMR_HOS_CHANGE_MAJOR_RECORD", "V_EMR_HOS_DIFFIC_CASE_DISCUSS",
    "V_EMR_HOS_DND_RECORD", "V_EMR_HOS_POSTOPER_RECORD", "V_EMR_HOS_PREOP_DISCUSS",
    "V_EMR_HOS_SAVE_RECORD", "V_EMR_HOS_SUCCESSION_RECORD", "V_EMR_INFOR_CRITICALLY_ILL",
    "V_EMR_INFOR_OPERATION", "V_EMR_INFOR_OTHERS", "V_EMR_INFOR_SPEC_EXAM_TREAT",
    "V_EMR_MEDICAL_RECORD_INFO", "V_EMR_NURSING_ASSESSMENT", "V_EMR_OPERA_RECORD",
]

manifest = {it["name"]: it for it in json.loads((DDL / "manifest.json").read_text(encoding="utf-8")) if it.get("name")}
DATE_RE = r"(?:to_?date\s*\(\s*|date\s+)['\"](\d{4}-\d{2}-\d{2})(?:[ T]\d{2}:\d{2}:\d{2})?['\"](?:\s*,\s*['\"][^'\"]+['\"]\s*\))?"
PRED_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*(<=|>=|<|>|=)\s*" + DATE_RE, re.I)
BETWEEN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s+between\s+" + DATE_RE + r"\s+and\s+" + DATE_RE, re.I)


def parse_predicates(sql_text):
    flat = re.sub(r"\s+", " ", sql_text)
    preds = []
    for m in PRED_RE.finditer(flat):
        col, op, lit = m.group(1), m.group(2).upper(), m.group(3)
        if op in ("<", "<="):
            role = "上界(改)"
        elif op in (">=", ">"):
            role = "下界(不改)"
        else:
            role = "等于(不改)"
        preds.append((col, op, lit, role))
    for m in BETWEEN_RE.finditer(flat):
        col, lo, hi = m.group(1), m.group(2), m.group(3)
        preds.append((col, "BETWEEN", f"{lo}~{hi}", f"BETWEEN上界(改{hi}→2026-01-01)/下界不动({lo})"))
    return preds


def find_ddl(source, owner, name):
    for f in DDL.glob(f"{source}__{owner}.{name}.sql"):
        return f
    return None


rows, unparsed = [], []
for owner, names, source, sub_batch in (("ODS", ODS41, "ods_8_216", "批次1-ODS"),
                                        ("HISUSER", HISUSER3, "his_source_10_10_10_15", "批次1-HISUSER")):
    for name in names:
        f = find_ddl(source, owner, name)
        meta = manifest.get(name, {})
        if not f:
            rows.append({
                "owner": owner, "view": name, "sub_batch": sub_batch,
                "时间列": "【待活库解析：无备份文件】", "比较方向": "", "旧字面量": "",
                "拟新字面量": "", "改或不改": "HOLD", "理由": "DDL 备份缺失，须 GET_DDL/ALL_VIEWS.TEXT 取证后填工单",
                "回滚DDL": "", "备份SHA256": "", "证据日期": "2026-09-14/18 备份；本对象缺",
            })
            unparsed.append(f"{owner}.{name}")
            continue
        preds = parse_predicates(f.read_text(encoding="utf-8", errors="replace"))
        ub = [p for p in preds if p[3].startswith("上界") or p[3].startswith("BETWEEN")]
        lb = [p for p in preds if p[3].startswith("下界") or p[3].startswith("等于")]
        if not preds:
            rows.append({
                "owner": owner, "view": name, "sub_batch": sub_batch,
                "时间列": "【待活库解析：备份中未见日期谓词】", "比较方向": "", "旧字面量": "",
                "拟新字面量": "", "改或不改": "HOLD",
                "理由": f"备份 DDL（{meta.get('method')}）无日期字面量；与 §7.1『含2025-01-01』口径冲突，须 live 复核",
                "回滚DDL": f"view_ddl_backup/{f.name}", "备份SHA256": meta.get("sha256", "")[:16],
                "证据日期": "备份 2026-09-14/18；解析 2026-09-25",
            })
            unparsed.append(f"{owner}.{name}")
            continue
        # 每个上界谓词一行；无上界时列下界并 HOLD
        items = ub if ub else [(p[0], p[1], p[2], "仅下界(HOLD)") for p in lb]
        for col, op, lit, role in items:
            change = "改" if role.startswith(("上界", "BETWEEN")) else "HOLD"
            new = "2026-01-01" if change == "改" else ""
            reason = ("上界角色，左闭右开改 <2026-01-01（BETWEEN 上端含 12-31 白天丢失风险，统一改左闭右开）"
                      if change == "改" else
                      "下界/等于/分段点，189 §4 批次1 明令不改")
            rows.append({
                "owner": owner, "view": name, "sub_batch": sub_batch,
                "时间列": col, "比较方向": op, "旧字面量": lit, "拟新字面量": new,
                "改或不改": change, "理由": reason,
                "回滚DDL": f"view_ddl_backup/{f.name}（SHA-256 见 manifest.json）",
                "备份SHA256": str(meta.get("sha256", ""))[:16],
                "证据日期": f"备份 {meta.get('method')} 2026-09-14/18；离线解析 2026-09-25，未 live",
            })

with open(BASE / "批次1_上界工单_44对象.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

n_change = sum(1 for r in rows if r["改或不改"] == "改")
n_hold = len(rows) - n_change
summary = {
    "rebuilt_at": "2026-09-25", "mark": "OFFLINE_REBUILT_NOT_LIVE",
    "source": "189 v1.1 §7.1/§7.3 + view_ddl_backup（GET_DDL/ALL_VIEWS.TEXT，2026-09-14/18 备份）",
    "ods41_rows": sum(1 for r in rows if r["owner"] == "ODS"),
    "hisuser3_rows": sum(1 for r in rows if r["owner"] == "HISUSER"),
    "pred_rows": len(rows), "to_change": n_change, "hold": n_hold,
    "unparsed_or_missing": unparsed,
    "mtl_caliber": {
        "batch1_intersect_12": sorted(set(ODS41) & set(MTL18)),
        "mtl_total_18": MTL18,
        "remaining_6_to_batch2": sorted(set(MTL18) - set(ODS41)),
    },
}
(BASE / "批次工单重建_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 20 else f"[{len(v)}项]") for k, v in summary.items()},
                 ensure_ascii=False, indent=1))
