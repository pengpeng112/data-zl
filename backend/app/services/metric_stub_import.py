"""Register unavailable placeholder metrics for core institution numbers without SQL."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.metric_asset import AssetMetricVersion
from ..models.governance_base import GovernAuditLog
from .metric_service import get_metric, ingest_metric

# Official titles from 48项核心制度监测指标(1).docx (2025 年版).
# These numbers still lack a fully validated executable SQL. Metric 22 was
# removed after the 130 S4 bounded Oracle validation made it publishable.
MISSING_CORE_METRICS: dict[int, str] = {
    1: "患者入院48小时内转科率",
    2: "患者入院8小时内查房率",
    11: "急会诊及时到位率",
    12: "普通会诊及时完成率",
    13: "二级护理/三级护理出院率",
    14: "住院患者自理能力及时评估率",
    15: "值班期间诊疗处置记录率",
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

# Evidence-backed closeout reasons from the 130 S4 audit.  These explanations
# are deliberately specific enough for the next owner to resume work without
# treating a title-only placeholder as an executable metric.
MISSING_CORE_METRIC_LIMITATIONS: dict[int, list[str]] = {
    1: ["候选SQL未按转科事件时间严格限定入院48小时", "ADT_LOG转科动作值域及急诊/ICU排除口径待确认"],
    2: ["候选SQL以诊疗/治疗医嘱代理首次查房", "查房代理口径需业务部门确认"],
    11: ["缺急会诊类型、撤销状态和到位时间值域确认"],
    12: ["缺普通会诊完成状态及时间值域确认"],
    13: ["候选结果分子持续为0，护理医嘱值域需复核", "未完整按离院方式排除非医嘱离院"],
    14: ["缺Barthel评估项编码、2小时规则及护理医嘱时间口径"],
    15: ["缺午夜值班识别及医嘱与病程记录结构化对应关系"],
    29: ["长期医嘱值域、当日终止定义及日间/死亡/转科排除规则待确认"],
    30: ["缺医院手术授权目录；抗菌药权限不能替代"],
    33: ["缺机构三四级手术目录及并发症代码集合"],
    34: ["手术级别目录、死亡口径和分母拆分待确认"],
    35: ["缺机构三四级手术术种目录口径"],
    36: ["缺新技术新项目管理目录及授权人员清单"],
    37: ["未发现新技术新项目登记及留存转化结构化数据源"],
    38: ["缺医院危急值闭环、处置医嘱及6小时病程记录关联"],
    39: ["未找到结构化手术安全核查三节点及手术医师字段"],
    40: ["缺手术安全核查麻醉医师字段及已验证关系"],
    46: ["缺有效抗菌药物授权目录；现有权限表为空"],
    47: ["缺特殊使用级抗菌药目录、会诊专家目录及值域"],
    48: ["仅能取得候选输血分母，缺输血后评估记录结构化来源和时间字段"],
}


def import_missing_metric_stubs(
    db: Session,
    *,
    dry_run: bool = True,
    created_by: str = "metric_stub_import",
    refresh_titles: bool = True,
    commit: bool = True,
) -> dict:
    items = []
    for num, title in sorted(MISSING_CORE_METRICS.items()):
        code = f"MET_CORE_{num:02d}"
        existing = get_metric(db, code)
        if existing:
            changed = False
            before = {"title": existing.title, "status": existing.status, "current_version_id": existing.current_version_id}
            limitations = MISSING_CORE_METRIC_LIMITATIONS[num]
            if refresh_titles and existing.title != title:
                if not dry_run:
                    existing.title = title
                    changed = True
            versions = list(db.scalars(
                select(AssetMetricVersion)
                .where(AssetMetricVersion.metric_id == existing.id)
                .order_by(AssetMetricVersion.version.desc())
            ).all())
            latest = versions[0] if versions else None
            needs_closeout = (
                existing.status != "blocked"
                or not latest
                or latest.status != "blocked"
                or latest.is_active
                or latest.limitations != limitations
            )
            if not dry_run and needs_closeout:
                existing.status = "blocked"
                existing.current_version_id = None
                existing.meaning = "已登记官方指标；当前缺少经门禁验证的完整SQL或权威业务口径，禁止执行和发布。"
                for version in versions:
                    version.is_active = False
                if latest:
                    latest.status = "blocked"
                    latest.definition_text = "130号S4已逐项审计；当前证据不足，保持blocked，待补齐限制项后修订。"
                    latest.limitations = limitations
                    latest.revision_reason = "130号S4逐项证据审计"
                changed = True
            items.append({
                "metric_code": code,
                "status": ("would_closeout" if dry_run and needs_closeout else "closed_out" if changed else "exists"),
                "title": title,
                "limitations": limitations,
            })
            if changed:
                db.add(GovernAuditLog(
                    module="plan130",
                    entity_type="metric_definition",
                    entity_ref=code,
                    action="closeout_blocked_metric",
                    before_data=before,
                    after_data={"title": existing.title, "status": existing.status, "current_version_id": existing.current_version_id},
                    operator=created_by,
                    reason="S4 evidence audit",
                ))
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
            limitations=MISSING_CORE_METRIC_LIMITATIONS[num],
            created_by=created_by,
            auto_activate=False,
        )
        definition = get_metric(db, code)
        definition.status = "blocked"
        db.add(GovernAuditLog(
            module="plan130",
            entity_type="metric_definition",
            entity_ref=code,
            action="create_blocked_metric",
            before_data=None,
            after_data={"status": "blocked", "current_version_id": None},
            operator=created_by,
            reason="S4 evidence audit",
        ))
        items.append(
            {
                "metric_code": code,
                "status": r["version"]["status"],
                "is_active": r["version"]["is_active"],
                "title": title,
            }
        )
    if not dry_run and commit:
        db.commit()
    return {"dry_run": dry_run, "count": len(items), "items": items}
