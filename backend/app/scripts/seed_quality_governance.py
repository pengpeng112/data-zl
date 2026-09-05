"""174 S6: 质量治理台账种子工具（T1–T12 + 会议清单 + 现有发现幂等导入）。

用法：
    python -m app.scripts.seed_quality_governance --dry-run   # 默认，零写入
    python -m app.scripts.seed_quality_governance --apply     # 只写平台 asset schema

铁律（174 §10.3）：
  - dry-run 默认；apply 幂等（二次执行零新增、零重复关联）；
  - 不硬编码 open 数量、finding_id 或历史比例，一切按当前数据查询；
  - 旧 ProbeFinding/QualityFinding 不删除、不改主状态；
  - 会议五条事项建 new 手工 Issue，指标留空标“待取证”，不编造样本/比例；
  - 未核验 detector（LIS/超声/Docare 等）保持 blocked，不猜 SQL；
  - 生产 apply 需另行明确授权（本工具不区分环境，由调用方负责）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND_ROOT))

TEMPLATES_DIR = _BACKEND_ROOT / "scripts" / "probe_templates"

# T1–T12 → 稳定质控编码（174 §10.1；编码为清单身份，与模板 code 分离）
_TEMPLATE_CONTROL_CODES = {
    "T1": "DQ-HIS-EXAM-001",
    "T2": "DQ-HIS-EXAM-002",
    "T3": "DQ-HIS-LAB-001",
    "T4": "DQ-HIS-OUTP-001",
    "T5": "DQ-HIS-EXAM-003",
    "T6": "DQ-HIS-LAB-002",
    "T7": "DQ-HIS-PACS-001",
    "T8": "DQ-XSYS-JHEMR-001",
    "T9": "DQ-XSYS-JHEMR-002",
    "T10": "DQ-HIS-ANES-001",
    "T11": "DQ-HIS-MR-001",
    "T12": "DQ-HIS-MR-002",
}

_DIMENSION_BY_CATEGORY = {
    "R-REF": "completeness",
    "R-CNT": "consistency",
    "R-KEY": "referential",
    "R-XSYS": "cross_system",
    "R-DOM": "validity",
}

# 个别模板的维度修正（T5 回写率=时效性）
_DIMENSION_OVERRIDES = {"T5": "timeliness"}

# T7 计划内 BLOCKED（164 §5 口径），其余模板按当前状态 active
_BLOCKED_TEMPLATES = {"T7"}

# 跨系统模板的对端系统编码
_RELATED_SYSTEMS = {
    "T6": ["LIS"],
    "T7": ["DATA_CENTER"],
    "T8": ["JHEMR"],
    "T9": ["JHEMR"],
    "T11": ["JHEMR"],
}

# 会议点名新增清单（174 §10.2；未核验 detector 一律 blocked）
_MEETING_CONTROLS: list[dict[str, Any]] = [
    {
        "control_code": "DQ-HIS-MR-DEATH-001",
        "title": "病案死亡/离院双字段一致性",
        "description": "病案首页死亡信息与离院方式（5=死亡）双字段一致性核对；离院方式 4=非医嘱离院、5=死亡（148 口径）。待完成只读 SQL 核验后自动化。",
        "primary_system_code": "HIS",
        "object_name_snapshot": "MEDREC.PAT_VISIT.DISCHARGE_DISPOSITION / DEATH 相关字段",
        "dimension": "consistency",
        "category": "MANUAL",
        "detector_kind": "manual",
        "detector_status": "blocked",
        "detector_blocked_reason": "优先完成只读 SQL 核验（DEATH_DATE_TIME 源端不填，需先核死亡判定口径）后自动化",
        "issue_title": "病案死亡/离院双字段一致性待核验与治理",
    },
    {
        "control_code": "DQ-HIS-MR-LEGACY-001",
        "title": "2023 首页新旧字段并行",
        "description": "2023 年病案首页新旧字段并行治理清单；只做手工治理跟踪，不做物理删列。",
        "primary_system_code": "HIS",
        "object_name_snapshot": "MEDREC 病案首页 2023 新旧并行字段",
        "dimension": "consistency",
        "category": "MANUAL",
        "detector_kind": "manual",
        "detector_status": "active",
        "detector_blocked_reason": None,
        "issue_title": "2023 首页新旧字段并行治理",
    },
    {
        "control_code": "DQ-LIS-KEY-001",
        "title": "LIS 条码/报告号关联 HIS 住院号+住院次数覆盖率",
        "description": "LIS 条码/报告号与 HIS 住院号+住院次数的关联覆盖率核对；LIS 元数据和关系未核验前 detector 保持 blocked。",
        "primary_system_code": "LIS",
        "related_system_codes": ["HIS"],
        "object_name_snapshot": "LIS 条码/报告号 ↔ HIS 住院号+住院次数",
        "dimension": "referential",
        "category": "R-KEY",
        "detector_kind": "external",
        "detector_status": "blocked",
        "detector_blocked_reason": "LIS 表结构、字段与关联关系未按 sjzc/只读技能核验，禁止猜测 SQL",
        "issue_title": "LIS 条码/报告号关联 HIS 住院键覆盖率待核验",
    },
    {
        "control_code": "DQ-US-VISIT-001",
        "title": "超声回传住院次数一致性",
        "description": "超声系统回传住院次数与 HIS 侧一致性核对；超声元数据和关系未核验前 detector 保持 blocked。",
        "primary_system_code": "US",
        "related_system_codes": ["HIS"],
        "object_name_snapshot": "超声回传住院次数 ↔ HIS 住院次数",
        "dimension": "cross_system",
        "category": "R-XSYS",
        "detector_kind": "external",
        "detector_status": "blocked",
        "detector_blocked_reason": "超声内镜系统表结构与回传字段未核验，禁止猜测 SQL",
        "issue_title": "超声回传住院次数一致性待核验",
    },
    {
        "control_code": "DQ-DOC-VISIT-001",
        "title": "手麻急诊未排班默认住院次数为 1",
        "description": "Docare 手麻系统急诊未排班时住院次数默认为 1 的口径治理；Docare 元数据和关系核验后自动化。",
        "primary_system_code": "DOCARE",
        "related_system_codes": ["HIS"],
        "object_name_snapshot": "Docare 急诊未排班默认住院次数",
        "dimension": "consistency",
        "category": "MANUAL",
        "detector_kind": "external",
        "detector_status": "blocked",
        "detector_blocked_reason": "Docare 元数据和关系核验后再自动化；未核验前不猜 SQL",
        "issue_title": "手麻急诊未排班默认住院次数为 1 的口径治理",
    },
]

_MEETING_EVIDENCE_REF = "会议清单:数据质量主动治理台账方案-174-§10.2"


def _load_templates() -> list[dict[str, Any]]:
    templates = []
    for path in sorted(TEMPLATES_DIR.glob("T*.json")):
        tpl = json.loads(path.read_text(encoding="utf-8"))
        tpl["_code"] = path.stem
        templates.append(tpl)
    return templates


def _control_payload_from_template(tpl: dict[str, Any]) -> dict[str, Any]:
    code = tpl["_code"]
    trig = tpl.get("trigger", {})
    derive = tpl.get("derive", {})
    category = tpl.get("probe_type", "MANUAL")
    priority = tpl.get("severity_default", "P3")
    severity = {"P1": "high", "P2": "medium", "P3": "low"}.get(priority, "low")
    return {
        "control_code": _TEMPLATE_CONTROL_CODES[code],
        "title": tpl["name"],
        "description": f"探查模板 {code}（{category}）：{tpl.get('object_desc_tpl', '')}。执行走 165 夜间探查器。",
        "lifecycle_status": "blocked" if code in _BLOCKED_TEMPLATES else "active",
        "blocked_reason": tpl["sides"][1].get("reason") if code in _BLOCKED_TEMPLATES and len(tpl.get("sides", [])) > 1 else None,
        "dimension": _DIMENSION_OVERRIDES.get(code, _DIMENSION_BY_CATEGORY.get(category)),
        "category": category,
        "primary_system_code": "HIS",
        "related_system_codes": _RELATED_SYSTEMS.get(code),
        "object_key": None,  # 探查对象跨源，object_key 不硬造；快照见 object_name_snapshot
        "object_name_snapshot": tpl.get("object_desc_tpl"),
        "metric_name": derive.get("metric"),
        "metric_unit": derive.get("unit"),
        "comparator": trig.get("op"),
        "threshold_value": float(trig["threshold"]) if trig.get("threshold") is not None else None,
        "no_data_policy": "blocked",
        "default_severity": severity,
        "default_priority": priority,
    }


def _upsert_control(db, payload: dict[str, Any], detectors: list[dict[str, Any]], actor: str) -> str:
    """幂等 upsert；返回 created|existing|updated。"""
    from app.models.quality_governance import QualityControl, QualityControlDetector
    from sqlalchemy import select

    control = db.scalar(
        select(QualityControl).where(QualityControl.control_code == payload["control_code"])
    )
    created = False
    if control is None:
        control = QualityControl(
            **payload,
            lock_version=0,
            created_by=actor,
            updated_by=actor,
        )
        db.add(control)
        db.flush()
        created = True
    else:
        # 只补齐空字段，不覆盖人工后续维护（幂等语义）
        for key, value in payload.items():
            if getattr(control, key, None) in (None, "", []) and value not in (None, "", []):
                setattr(control, key, value)
        control.updated_by = actor

    for det in detectors:
        exists = db.scalar(
            select(QualityControlDetector).where(
                QualityControlDetector.control_id == control.id,
                QualityControlDetector.detector_kind == det["detector_kind"],
                QualityControlDetector.detector_ref == det["detector_ref"],
                QualityControlDetector.detector_version == det.get("detector_version", "1"),
            )
        )
        if exists is None:
            db.add(
                QualityControlDetector(
                    control_id=control.id,
                    detector_kind=det["detector_kind"],
                    detector_ref=det["detector_ref"],
                    detector_version=det.get("detector_version", "1"),
                    status=det["status"],
                    blocked_reason=det.get("blocked_reason"),
                    scope_mapping=det.get("scope_mapping"),
                    result_mapping=det.get("result_mapping"),
                    last_bound_at=datetime.now(timezone.utc),
                    created_by=actor,
                    updated_by=actor,
                )
            )
        else:
            # blocked 理由随种子刷新；active 状态不被种子降级
            if exists.status == "blocked" and det["status"] == "active":
                pass  # 人工解除的 blocked 不回退
            exists.blocked_reason = det.get("blocked_reason") or exists.blocked_reason
            if exists.status == "draft" and det["status"] in ("active", "blocked"):
                exists.status = det["status"]
            exists.updated_by = actor
    return "created" if created else "existing"


def _ensure_meeting_issue(db, control, spec: dict[str, Any], actor: str) -> str:
    """会议五条：仅当该 control 从未有过同名手工问题时创建（含终态，防关闭后重复）。"""
    from sqlalchemy import select

    from app.models.quality_governance import QualityIssue
    from app.services import quality_governance_service as qgs

    exists = db.scalar(
        select(QualityIssue).where(
            QualityIssue.control_id == control.id,
            QualityIssue.title == spec["issue_title"],
        )
    )
    if exists is not None:
        return "existing"
    issue = qgs.create_manual_issue(
        db,
        title=spec["issue_title"],
        description=(
            f"{spec['description']}\n\n证据来源：{_MEETING_EVIDENCE_REF}\n"
            "指标数据：待取证（未编造样本或比例）；核验完成后回填观测。"
        ),
        issue_type="manual",
        primary_system_code=spec.get("primary_system_code"),
        related_system_codes=spec.get("related_system_codes"),
        object_name_snapshot=spec.get("object_name_snapshot"),
        control_id=control.id,
        scope_key=f"meeting:{spec['control_code']}",
        severity="medium",
        priority="P3",
        evidence_ref=_MEETING_EVIDENCE_REF,
        actor=actor,
        reason="会议点名事项建账（指标待取证）",
    )
    _ = issue
    return "created"


def _ensure_t7_monitoring_gap(db, actor: str) -> str:
    """T7：blocked 清单登记 monitoring_gap（种子级观测，run_key 固定幂等）。"""
    from sqlalchemy import select

    from app.models.quality_governance import QualityControl
    from app.services import quality_governance_service as qgs

    control = db.scalar(
        select(QualityControl).where(QualityControl.control_code == "DQ-HIS-PACS-001")
    )
    if control is None:
        return "skipped_no_control"
    result = qgs.apply_observation(
        db,
        control_id=control.id,
        run_key="seed:t7-monitoring-gap:v1",
        scope_key=(control.object_name_snapshot or control.title)[:256],
        result_status="blocked",
        control_version=control.version,
        source_kind="manual",
        source_record_ref="174:seed:t7",
        evidence_ref="164 §5 口径：ODS.PACSREPORT 70 列无申请键/患者键",
        historical_precision="exact",
        actor=actor,
    )
    outcome = result["outcome"]
    return outcome


def run(dry_run: bool, db_url: str | None = None) -> dict[str, Any]:
    if db_url:
        import os

        os.environ["APP_DB_URL"] = db_url
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models.quality_governance import QualityControl
    from app.services import quality_governance_adapters as adapters

    actor = "seed:quality_governance_174"
    report: dict[str, Any] = {
        "mode": "dry-run" if dry_run else "apply",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "controls_created": 0,
        "controls_existing": 0,
        "meeting_issues_created": 0,
        "meeting_issues_existing": 0,
        "t7_monitoring_gap": None,
        "probe_findings_sync": None,
        "probe_run_sync": None,
        "quality_findings_sync": None,
    }
    db = SessionLocal()
    try:
        # 1) T1–T12 Controls + probe_template Detectors
        for tpl in _load_templates():
            payload = _control_payload_from_template(tpl)
            det = {
                "detector_kind": "probe_template",
                "detector_ref": tpl["_code"],
                "detector_version": "1",
                "status": "blocked" if tpl["_code"] in _BLOCKED_TEMPLATES else "active",
                "blocked_reason": payload["blocked_reason"],
                "result_mapping": {
                    "probe_type": tpl.get("probe_type"),
                    "metric_name": tpl.get("derive", {}).get("metric"),
                    "metric_unit": tpl.get("derive", {}).get("unit"),
                    "object_desc": tpl.get("object_desc_tpl"),
                },
            }
            outcome = _upsert_control(db, payload, [det], actor)
            report["controls_created" if outcome == "created" else "controls_existing"] += 1

        # 2) 会议五条 Controls + manual/blocked Detectors + new 手工 Issue
        for spec in _MEETING_CONTROLS:
            payload = {
                "control_code": spec["control_code"],
                "title": spec["title"],
                "description": spec["description"],
                "lifecycle_status": "active",
                "dimension": spec.get("dimension"),
                "category": spec.get("category", "MANUAL"),
                "primary_system_code": spec.get("primary_system_code"),
                "related_system_codes": spec.get("related_system_codes"),
                "object_name_snapshot": spec.get("object_name_snapshot"),
                "no_data_policy": "blocked",
                "default_severity": "medium",
                "default_priority": "P3",
            }
            det = {
                "detector_kind": spec["detector_kind"],
                "detector_ref": spec["control_code"],
                "detector_version": "1",
                "status": spec["detector_status"],
                "blocked_reason": spec.get("detector_blocked_reason"),
            }
            outcome = _upsert_control(db, payload, [det], actor)
            report["controls_created" if outcome == "created" else "controls_existing"] += 1
            control = db.scalar(
                select(QualityControl).where(QualityControl.control_code == spec["control_code"])
            )
            issue_outcome = _ensure_meeting_issue(db, control, spec, actor)
            report[
                "meeting_issues_created" if issue_outcome == "created" else "meeting_issues_existing"
            ] += 1

        # 3) T7 monitoring_gap（blocked 观测 → monitoring_gap Issue）
        report["t7_monitoring_gap"] = _ensure_t7_monitoring_gap(db, actor)

        # 4) 现有失败发现幂等导入（FAIL → Observation → 活动 Issue）
        report["probe_findings_sync"] = adapters.sync_probe_findings(db, actor=actor)
        # 5) 最新 run 的 PASS/BLOCKED/ERROR 回填观测（PASS 不建单）
        report["probe_run_sync"] = adapters.sync_probe_run_summary(db, actor=actor)
        # 6) 元数据质控 QualityFinding 适配（当前无 quality_rule 绑定则零写入）
        report["quality_findings_sync"] = adapters.sync_quality_findings(db, actor=actor)

        if dry_run:
            db.rollback()
            report["committed"] = False
        else:
            db.commit()
            report["committed"] = True
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        return report
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="174 S6: 质量治理台账种子（dry-run 默认）")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--apply", action="store_true", default=False)
    parser.add_argument("--db", default=None, help="目标库 URL（默认读 APP_DB_URL）")
    args = parser.parse_args()
    apply_mode = args.apply and not args.dry_run
    report = run(dry_run=not apply_mode, db_url=args.db)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
