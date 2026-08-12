"""Register unavailable placeholder metrics for core institution numbers without SQL."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .metric_service import get_metric, ingest_metric

# Official titles from 48项核心制度监测指标(1).docx (2025 年版).
# These numbers have no extractable SQL in repo yet (non-EMR or not yet split).
MISSING_CORE_METRICS: dict[int, str] = {
    1: "患者入院48小时内转科率",
    2: "患者入院8小时内查房率",
    11: "急会诊及时到位率",
    12: "普通会诊及时完成率",
    13: "二级护理/三级护理出院率",
    14: "住院患者自理能力及时评估率",
    15: "值班期间诊疗处置记录率",
    22: "抢救成功率",
    29: "长期医嘱当日终止率",
    30: "术者符合授权目录一致率",
    33: "四级手术与三级手术并发症发生率比",
    34: "四级手术与三级手术患者死亡率比值",
    35: "三、四级手术实际开展率",
    36: "临床新技术和新项目（手术）实施人符合率",
    37: "新技术/新项目留存转化率",
    38: "危急值病程记录符合率",
    39: "手术安全核查手术医师规范率",
    40: "手术安全核查麻醉医师规范率",
    46: "抗菌药物处方权落实合格率",
    47: "特殊使用级抗菌药物会诊率",
    48: "临床用血后评估记录率",
}


def import_missing_metric_stubs(
    db: Session,
    *,
    dry_run: bool = True,
    created_by: str = "metric_stub_import",
    refresh_titles: bool = True,
) -> dict:
    items = []
    for num, title in sorted(MISSING_CORE_METRICS.items()):
        code = f"MET_CORE_{num:02d}"
        existing = get_metric(db, code)
        if existing:
            changed = False
            if refresh_titles and existing.title != title:
                if not dry_run:
                    existing.title = title
                    existing.meaning = existing.meaning or "官方口径标题已回写；尚无可用 SQL。"
                    changed = True
                items.append(
                    {
                        "metric_code": code,
                        "status": "title_updated" if not dry_run else "would_update_title",
                        "title": title,
                    }
                )
            else:
                items.append({"metric_code": code, "status": "exists", "title": existing.title})
            if changed:
                db.flush()
            continue
        if dry_run:
            items.append({"metric_code": code, "status": "would_create", "title": title})
            continue
        # force blocked/unavailable: no query, only definition text
        r = ingest_metric(
            db,
            metric_code=code,
            title=title,
            meaning="官方口径已登记；仓库无可用 SQL，禁止作为现行可执行指标。",
            category="48项核心制度",
            definition_text="无 SQL 源文件；状态 candidate/blocked，待业务补录后修订。",
            formula=None,
            query_code=None,
            limitations=["无可用SQL", "不可提取", "占位登记"],
            created_by=created_by,
            auto_activate=False,
        )
        items.append(
            {
                "metric_code": code,
                "status": r["version"]["status"],
                "is_active": r["version"]["is_active"],
                "title": title,
            }
        )
    if not dry_run:
        db.commit()
    return {"dry_run": dry_run, "count": len(items), "items": items}
