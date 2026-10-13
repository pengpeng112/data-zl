"""207 B4: 既有质量治理数据只读盘点 + 修订快照 dry-run/幂等回填工具。

原则（207 §4.2/§B4）：
  - 只读盘点：不修改任何数据；输出旧单/观测/检测器与 207 契约的差异清单；
  - 历史 scope 无物理身份（object_key/source 缺失或 scope_key 为标题截断）→
    列入待映射清单，不强合并不同源同名表；
  - --apply 仅对既有清单的**当前版本**补建修订快照（origin=backfill，不伪造
    历史版本），二次执行幂等；不升级旧证据、不写观测、不改问题状态。

用法：
  python scripts/quality_backfill_207.py                # 只读盘点
  python scripts/quality_backfill_207.py --apply        # 补建当前版本修订快照（幂等）
  python scripts/quality_backfill_207.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.quality_governance import (  # noqa: E402
    QualityControl,
    QualityControlDetector,
    QualityControlRevision,
    QualityIssue,
    QualityObservation,
)
from app.services import quality_execution_service as qes  # noqa: E402


def inventory(db) -> dict:
    controls = db.scalars(select(QualityControl)).all()
    detectors = db.scalars(select(QualityControlDetector)).all()
    issues = db.scalars(select(QualityIssue)).all()
    obs_total = db.scalar(select(func.count()).select_from(QualityObservation)) or 0
    revisions = db.scalars(select(QualityControlRevision)).all()

    pending_scope_mapping: list[str] = []
    controls_without_source: list[str] = []
    for c in controls:
        if not (c.source_code or "").strip():
            controls_without_source.append(c.control_code)
    # scope 契约判定：207 新链观测/问题的 scope_key 以 sk: 或 monitoring: 开头；
    # 其余视为历史口径（保留，不计可信自动复测，不强改）
    legacy_scope_issues = [
        i.issue_code for i in issues
        if (i.scope_key or "") and not (i.scope_key.startswith(("sk:", "monitoring:")))
    ]
    controls_needing_revision = [
        c.control_code for c in controls
        if not any(r.control_id == c.id and r.version == (c.version or 1) for r in revisions)
    ]
    return {
        "statistics_time": datetime.now(timezone.utc).isoformat(),
        "controls": len(controls),
        "detectors": len(detectors),
        "issues": len(issues),
        "observations": obs_total,
        "revisions_existing": len(revisions),
        "controls_without_source_code": controls_without_source,
        "controls_needing_revision_snapshot": controls_needing_revision,
        "legacy_scope_issues_not_trusted_for_auto_verify": legacy_scope_issues[:500],
        "legacy_scope_issue_count": len(legacy_scope_issues),
        "notes": [
            "历史 scope 无物理身份的旧单保留原样，列入待映射清单，不与 sk: 新链强合并",
            "旧观测（latest_snapshot/summary_backfill）保留历史精度标记，不计可信自动复测证据",
            "probe-finding 适配器写入的 scope 为对象描述文本，仅作历史证据",
        ],
    }


def apply_revisions(db, actor: str) -> dict:
    created = []
    for c in db.scalars(select(QualityControl)).all():
        existing = db.scalar(
            select(QualityControlRevision).where(
                QualityControlRevision.control_id == c.id,
                QualityControlRevision.version == (c.version or 1),
            )
        )
        if existing is None:
            qes.ensure_revision(db, c, actor=actor, origin="backfill")
            created.append(c.control_code)
    db.commit()
    return {"revisions_created": created, "created_count": len(created)}


def main() -> int:
    ap = argparse.ArgumentParser(description="207 B4 盘点与回填")
    ap.add_argument("--apply", action="store_true", help="补建当前版本修订快照（幂等）")
    ap.add_argument("--json", default=None, help="盘点结果 JSON 输出路径")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        result = inventory(db)
        if args.apply:
            result["apply"] = apply_revisions(db, actor="script:quality_backfill_207")
            # 幂等性验证：二次执行零新建
            result["apply"]["second_pass_created"] = len(apply_revisions(db, actor="verify")["revisions_created"])
        else:
            result["apply"] = None
    finally:
        db.close()

    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
