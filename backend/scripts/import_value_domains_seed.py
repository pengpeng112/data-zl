"""149 P2: 幂等导入 148 已确认值域（唯一约束 upsert，只导已确认；待核入 pending）。

数据源：开发起步包/148_病案首页关键值域与离院方式口径字典.md（2026-08-24 实测+JHEMR 交叉+用户确认）。
导入规则（149 §4）：
  - 离院方式 1/2/4/5（各带 live_probe/cross_system/manual 证据）+ trap（勿用 DISCHARGE_DISPOSITION_DICT、
    DEATH_DATE_TIME 不填）→ confirmed
  - 手术急诊标志 1/2 → confirmed；诊断类别 1/2/3/7/8 → confirmed
  - OPER_STATUS >=35 / -80 → confirmed（threshold）
  - 免疫组化主项目 literal + 加收项 trap → confirmed
  - VISIT_TYPE='急诊' / REGISTTYPE='6' → confirmed
  - 离院方式 code 9、手术标志 3（148 标注"语义待核"）→ pending，绝不 confirmed

用法：
  python scripts/import_value_domains_seed.py --dry-run   # 只读预演，幂等零重复
  python scripts/import_value_domains_seed.py             # 实际导入（目标库由 APP_DB_URL 决定）
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.governance_base import GovernAuditLog  # noqa: E402
from app.models.value_domain import AssetColumnValueDomain  # noqa: E402
from app.services import value_domain_service as vds  # noqa: E402

HIS = {"system_code": "HIS_SOURCE", "source_code": "his_source_10_10_10_15"}
DC = {"system_code": "DATA_CENTER", "source_code": "ods_8_216"}

CONFIRMED_BY = "148导入（用户2026-08-24确认）"
CONFIRMED_AT = "2026-08-24T00:00:00+08:00"
OBSERVED_AT = "2026-08-24T00:00:00+08:00"


def _ev(source_type, method=None, sample_count=None, source_system=None, snippet="148", actor="148导入"):
    return {
        "source_type": source_type,
        "source_system": source_system,
        "method": method,
        "sample_count": sample_count,
        "observed_at": OBSERVED_AT,
        "actor": actor,
        "snippet_ref": snippet,
    }


def _manual(snippet, method=None):
    return _ev("manual", method=method or "用户确认（148 文档）", snippet=snippet)


SEED = [
    # ── 离院方式 MEDREC.PAT_VISIT.DISCHARGE_DISPOSITION（★2026-08-24 事故字段） ──
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION", "code": "1",
        "meaning": "医嘱离院", "domain_kind": "enum",
        "note": "占绝对多数（2026-08 实测 3,169+ 例）",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="HIS 源端 2026-08 实测", sample_count=3169, source_system="HIS_SOURCE", snippet="148 §1"),
            _manual("148 §1"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION", "code": "2",
        "meaning": "医嘱转院", "domain_kind": "enum",
        "note": "2026-08 实测 3 例",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="HIS 源端 2026-08 实测", sample_count=3, source_system="HIS_SOURCE", snippet="148 §1"),
            _manual("148 §1"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION", "code": "4",
        "meaning": "非医嘱离院（自愿离院）", "domain_kind": "enum",
        "note": "正确核对基准：JHEMR report.r_pat_visit「非医嘱离院」128 例（同步时点差异）；勿据 COMM.DISCHARGE_DISPOSITION_DICT 反推",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="HIS 源端 2026-08 实测", sample_count=120, source_system="HIS_SOURCE", snippet="148 §1"),
            _ev("cross_system", method="JHEMR report.r_pat_visit 按 patient_id+visit_id 交叉验证", sample_count=128, source_system="JHEMR", snippet="148 §1"),
            _manual("148 §1", method="用户 2026-08-24 确认（事故纠正后口径）"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION", "code": "5",
        "meaning": "死亡", "domain_kind": "enum",
        "note": "与 JHEMR report.r_pat_visit「死亡」15 例完全吻合；DEATH_DATE_TIME 源端不填，死亡识别以本码为准",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="HIS 源端 2026-08 实测", sample_count=15, source_system="HIS_SOURCE", snippet="148 §1"),
            _ev("cross_system", method="JHEMR report.r_pat_visit 交叉验证完全吻合", sample_count=15, source_system="JHEMR", snippet="148 §1"),
            _manual("148 §1", method="用户 2026-08-24 确认（事故纠正后口径）"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION", "code": "9",
        "meaning": "其他（语义待核，仅偶发）", "domain_kind": "enum",
        "note": "148 标注语义待核：2025-08 仅出现 2 例；人工核实前不得用于统计口径",
        "status": "pending",
        "evidences": [
            _ev("live_probe", method="HIS 源端 2025-08 观测", sample_count=2, source_system="HIS_SOURCE", snippet="148 §1"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION", "code": "COMM.DISCHARGE_DISPOSITION_DICT",
        "meaning": "勿用此字典判读离院方式：其内容为治疗结果（1治愈/2转院/3死亡/4好转/5自愿/6其他/7未愈），与病案首页离院方式是两套代码，2026-08-24 曾据此误判 4/5 含义",
        "domain_kind": "trap",
        "note": "负知识：正确基准是 JHEMR report.r_pat_visit（中文名称）与 148 值域库",
        "status": "confirmed",
        "evidences": [
            _ev("dict_table", method="字典内容核对：与离院方式代码体系不一致", source_system="HIS_SOURCE", snippet="148 §1 关键坑1"),
            _manual("148 §1 关键坑1"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "PAT_VISIT",
        "column_name": "DEATH_DATE_TIME", "code": "NOT_FILLED",
        "meaning": "DEATH_DATE_TIME 在 HIS 源端基本不填，不能用于识别死亡；死亡识别用 DISCHARGE_DISPOSITION=5",
        "domain_kind": "trap",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="HIS 源端实测基本不填", source_system="HIS_SOURCE", snippet="148 §1 关键坑2"),
            _manual("148 §1 关键坑2"),
        ],
    },
    # ── 手术急诊标志 MEDREC.OPERATION.OPERATION_EMER_INDICATOR ──
    {
        **HIS, "schema_name": "MEDREC", "table_name": "OPERATION",
        "column_name": "OPERATION_EMER_INDICATOR", "code": "1",
        "meaning": "择期", "domain_kind": "enum",
        "note": "占绝对多数（2025 泌尿科 1,183 台）",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="2025 泌尿科实测", sample_count=1183, source_system="HIS_SOURCE", snippet="148 §2"),
            _manual("148 §2"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "OPERATION",
        "column_name": "OPERATION_EMER_INDICATOR", "code": "2",
        "meaning": "急诊手术", "domain_kind": "enum",
        "note": "全院 2025 年 7,415 台 / 2,803 例",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="2025 泌尿科 63 台；全院 2025 年 7,415 台/2,803 例", sample_count=7415, source_system="HIS_SOURCE", snippet="148 §2"),
            _manual("148 §2", method="用户 2026-08-20 确认"),
        ],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "OPERATION",
        "column_name": "OPERATION_EMER_INDICATOR", "code": "3",
        "meaning": "语义待核", "domain_kind": "enum",
        "note": "148 标注语义待核（2025 泌尿科 10 台；另有空值约 5 台）；人工核实前不得用于统计口径",
        "status": "pending",
        "evidences": [
            _ev("live_probe", method="2025 泌尿科实测", sample_count=10, source_system="HIS_SOURCE", snippet="148 §2"),
        ],
    },
    # ── 诊断类别 MEDREC.DIAGNOSIS.DIAGNOSIS_TYPE（09 文档已验证） ──
    {
        **HIS, "schema_name": "MEDREC", "table_name": "DIAGNOSIS",
        "column_name": "DIAGNOSIS_TYPE", "code": "1",
        "meaning": "门急诊诊断（病案首页，仅住院患者携带）", "domain_kind": "enum",
        "status": "confirmed", "evidences": [_manual("148 §3 / 09 已验证", method="09 文档数据库验证汇总")],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "DIAGNOSIS",
        "column_name": "DIAGNOSIS_TYPE", "code": "2",
        "meaning": "入院诊断", "domain_kind": "enum",
        "status": "confirmed", "evidences": [_manual("148 §3 / 09 已验证", method="09 文档数据库验证汇总")],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "DIAGNOSIS",
        "column_name": "DIAGNOSIS_TYPE", "code": "3",
        "meaning": "出院诊断（病种统计默认口径）", "domain_kind": "enum",
        "status": "confirmed", "evidences": [_manual("148 §3 / 09 已验证", method="09 文档数据库验证汇总")],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "DIAGNOSIS",
        "column_name": "DIAGNOSIS_TYPE", "code": "7",
        "meaning": "损伤/中毒", "domain_kind": "enum",
        "status": "confirmed", "evidences": [_manual("148 §3 / 09 已验证", method="09 文档数据库验证汇总")],
    },
    {
        **HIS, "schema_name": "MEDREC", "table_name": "DIAGNOSIS",
        "column_name": "DIAGNOSIS_TYPE", "code": "8",
        "meaning": "病理", "domain_kind": "enum",
        "status": "confirmed", "evidences": [_manual("148 §3 / 09 已验证", method="09 文档数据库验证汇总")],
    },
    # ── 手麻口径 SM.MED_OPERATION_MASTER.OPER_STATUS（数据中心 8.216） ──
    {
        **DC, "schema_name": "SM", "table_name": "MED_OPERATION_MASTER",
        "column_name": "OPER_STATUS", "code": ">=35",
        "meaning": "麻醉/手术完成口径（台数统计）", "domain_kind": "threshold",
        "scope_condition": "麻醉台数统计：MED_OPERATION_MASTER 且 OPER_STATUS>=35",
        "note": "2025 年 22,287 台，与三甲复审一致；MEDSURGERY「麻醉记录」一台多条不可作台数",
        "status": "confirmed",
        "evidences": [
            _ev("live_probe", method="2025 年实测 22,287 台，与三甲复审一致", sample_count=22287, source_system="DATA_CENTER", snippet="148 §4"),
            _manual("148 §4"),
        ],
    },
    {
        **DC, "schema_name": "SM", "table_name": "MED_OPERATION_MASTER",
        "column_name": "OPER_STATUS", "code": "-80",
        "meaning": "取消/作废手术状态，台数与完成口径统计须排除", "domain_kind": "threshold",
        "scope_condition": "手术统计排除口径：OPER_STATUS=-80",
        "status": "confirmed",
        "evidences": [_manual("149 §4", method="149 P2 导入清单（v1 口径沿用）")],
    },
    # ── 免疫组化 INPBILL.INP_BILL_DETAIL.ITEM_NAME ──
    {
        **HIS, "schema_name": "INPBILL", "table_name": "INP_BILL_DETAIL",
        "column_name": "ITEM_NAME", "code": "免疫组织化学染色诊断",
        "meaning": "免疫组化统计主项目（按收费明细 ITEM_NAME 精确匹配）", "domain_kind": "literal",
        "scope_condition": "病理免疫组化统计：HIS 收费明细主项目",
        "status": "confirmed",
        "evidences": [_manual("148 §4")],
    },
    {
        **HIS, "schema_name": "INPBILL", "table_name": "INP_BILL_DETAIL",
        "column_name": "ITEM_NAME", "code": "免疫组织化学染色诊断（液盖膜涡流混匀法加收）",
        "meaning": "加收项陷阱：勿与主项目「免疫组织化学染色诊断」相加统计", "domain_kind": "trap",
        "note": "名称含「（液盖膜涡流混匀法加收）」，数量/费用统计不得并入主项目",
        "status": "confirmed",
        "evidences": [_manual("148 §4")],
    },
    # ── 急诊认定 OUTPADM.CLINIC_MASTER ──
    {
        **HIS, "schema_name": "OUTPADM", "table_name": "CLINIC_MASTER",
        "column_name": "VISIT_TYPE", "code": "急诊",
        "meaning": "急诊认定口径：VISIT_TYPE='急诊'（急诊科挂号在 HIS 中无法拆分内/外科）", "domain_kind": "literal",
        "note": "字段值域（注释）：普通门诊/急诊/特需门诊/互联网诊疗/MDT门诊/其他",
        "status": "confirmed",
        "evidences": [_manual("148 §4")],
    },
    {
        **HIS, "schema_name": "OUTPADM", "table_name": "CLINIC_MASTER",
        "column_name": "REGISTTYPE", "code": "6",
        "meaning": "急诊号——急诊交叉核对口径（与 VISIT_TYPE='急诊' 互为校验）", "domain_kind": "enum",
        "note": "字段注释值域：1 普通/便民/义诊/优抚/核酸，4 专家副，5 知名/专家主，6 急诊号，7 留观",
        "status": "confirmed",
        "evidences": [
            _manual("148 §4"),
            _ev("dict_table", method="字段注释值域核对", source_system="HIS_SOURCE", snippet="HIS源端资产包 OUTPADM.CLINIC_MASTER.REGISTTYPE"),
        ],
    },
]


def _find(db, item):
    return vds.find_by_key(
        db,
        system_code=item["system_code"],
        source_code=item["source_code"],
        schema_name=item["schema_name"],
        table_name=item["table_name"],
        column_name=item["column_name"],
        code=item["code"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="149 P2 值域种子导入（幂等）")
    parser.add_argument("--dry-run", action="store_true", help="只读预演：不写库，报告将要创建/追加的条目")
    args = parser.parse_args()

    db = SessionLocal()
    stats = {"to_create": 0, "created": 0, "to_attach": 0, "attached": 0,
             "already_current": 0, "meaning_conflicts": 0, "pending_total": 0, "confirmed_total": 0}
    conflicts: list[str] = []
    try:
        for item in SEED:
            key = (f"{item['system_code']}|{item['source_code']}|{item['schema_name']}|"
                   f"{item['table_name']}|{item['column_name']}|{item['code']}")
            if item["status"] == "pending":
                stats["pending_total"] += 1
            else:
                stats["confirmed_total"] += 1
            existing = _find(db, item)
            missing_evidence = []
            if existing is not None:
                if vds.meanings_differ(existing.meaning, item["meaning"]):
                    stats["meaning_conflicts"] += 1
                    conflicts.append(f"{key}: 库内={existing.meaning!r} 种子={item['meaning']!r}")
                    continue
                for ev in item["evidences"]:
                    if not vds.evidence_duplicate(db, existing.id, ev):
                        missing_evidence.append(ev)

            if existing is None:
                stats["to_create" if args.dry_run else "created"] += 1
                if args.dry_run:
                    continue
                row = AssetColumnValueDomain(
                    system_code=item["system_code"],
                    source_code=item["source_code"],
                    schema_name=item["schema_name"],
                    table_name=item["table_name"],
                    column_name=item["column_name"],
                    code=item["code"],
                    meaning=item["meaning"],
                    note=item.get("note"),
                    domain_kind=item["domain_kind"],
                    scope_condition=item.get("scope_condition"),
                    status=item["status"],
                    conflict_status="none",
                )
                if item["status"] == "confirmed":
                    row.confirmed_by = CONFIRMED_BY
                    row.confirmed_at = datetime.fromisoformat(CONFIRMED_AT)
                db.add(row)
                db.flush()
                for ev in item["evidences"]:
                    db.add(vds.evidence_row(row.id, ev))
                vds.next_version(
                    db, row,
                    change_reason="seed_import_148" + ("_confirmed" if item["status"] == "confirmed" else "_pending"),
                    actor="seed_script",
                    evidence_ref="148",
                )
            elif missing_evidence:
                stats["to_attach" if args.dry_run else "attached"] += 1
                if args.dry_run:
                    continue
                for ev in missing_evidence:
                    db.add(vds.evidence_row(existing.id, ev))
                existing.updated_at = datetime.now(timezone.utc)
            else:
                stats["already_current"] += 1

        if args.dry_run:
            db.rollback()
            print(f"[dry-run] 种子共 {len(SEED)} 条（confirmed {stats['confirmed_total']} / pending {stats['pending_total']}）")
            print(f"[dry-run] 将创建 {stats['to_create']} 条，将追加证据 {stats['to_attach']} 条，"
                  f"已就绪 {stats['already_current']} 条，含义冲突 {stats['meaning_conflicts']} 条")
            for line in conflicts:
                print(f"[dry-run] 冲突: {line}")
            ok = (stats["to_create"] == 0 and stats["to_attach"] == 0 and stats["meaning_conflicts"] == 0)
            print(f"[dry-run] {'幂等：无待导入项' if ok else '存在待导入/冲突项（重复运行应收敛为 0）'}")
            return 0

        db.add(GovernAuditLog(
            module="value_domain",
            entity_type="column_value_domain",
            entity_ref="seed:148",
            action="seed_import",
            after_data={"created": stats["created"], "attached": stats["attached"],
                        "already_current": stats["already_current"],
                        "meaning_conflicts": stats["meaning_conflicts"]},
            operator="seed_script",
            reason="149 P2 幂等导入 148 已确认值域",
        ))
        db.commit()
        print(f"[import] created={stats['created']} attached={stats['attached']} "
              f"already_current={stats['already_current']} meaning_conflicts={stats['meaning_conflicts']}")
        for line in conflicts:
            print(f"[import] 冲突（未改动，需人工裁决）: {line}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
