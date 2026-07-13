"""L13 主数据差异复核：只生成可追溯差异与合并建议，不自动覆盖主数据。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.identity import IdentityPerson, IdentityPersonSource, IdentitySyncDiff
from .sync_executor import _add_identity_diff, _person_payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_his_master_review(
    db: Session,
    *,
    source_system: str = "HIS",
    target_system: str = "asset",
    max_diffs: int = 5000,
) -> dict[str, Any]:
    """Compare multi-source HIS person rows vs master; emit open diffs + suggestions."""
    sources = db.scalars(
        select(IdentityPersonSource).where(IdentityPersonSource.source_system == source_system)
    ).all()
    by_code: dict[str, list[IdentityPersonSource]] = defaultdict(list)
    for src in sources:
        code = (src.person_code or src.source_person_id or "").strip()
        if code:
            by_code[code].append(src)

    created = 0
    skipped = 0
    multi = 0
    mismatch = 0
    staff_only = 0

    for person_code, rows in by_code.items():
        if created >= max_diffs:
            break
        person = db.scalar(select(IdentityPerson).where(IdentityPerson.person_code == person_code))
        tables = {r.source_table for r in rows if r.source_table}
        names = {r.source_person_name for r in rows if r.source_person_name}
        depts = {r.source_dept_code for r in rows if r.source_dept_code}

        # 多来源字段冲突（如 STAFF vs SYS_EMPLOYEE）
        if len(tables) > 1 and (len(names) > 1 or len(depts) > 1):
            suggestion = {
                "action": "manual_confirm",
                "prefer_source_table": "FXHIS.SYS_EMPLOYEE",
                "note": "用户口径：SYS_EMPLOYEE 为主；冲突字段需人工确认，禁止自动覆盖",
                "candidate_values": {
                    "names": sorted(names),
                    "depts": sorted(depts),
                    "tables": sorted(tables),
                },
            }
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_person",
                entity_code=person_code,
                diff_type="multi_source_conflict",
                before_data=_person_payload(person) if person else None,
                after_data={
                    "sources": [
                        {
                            "source_table": r.source_table,
                            "source_person_id": r.source_person_id,
                            "source_person_name": r.source_person_name,
                            "source_dept_code": r.source_dept_code,
                            "source_status": r.source_status,
                        }
                        for r in rows
                    ],
                    "merge_suggestion": suggestion,
                },
                severity="high",
            )
            created += int(added)
            skipped += int(not added)
            multi += int(added)
            continue

        # 仅 STAFF 有、无员工主表记录的补充人员
        only_staff = all(
            (r.source_table or "").upper().endswith("STAFF_DICT") or (r.source_table or "") == "COMM.STAFF_DICT"
            for r in rows
        )
        has_employee = any("SYS_EMPLOYEE" in (r.source_table or "").upper() for r in rows)
        if only_staff and not has_employee and person:
            suggestion = {
                "action": "keep_as_supplement",
                "prefer_source_table": "COMM.STAFF_DICT",
                "note": "STAFF 独有人员，可保留为补充主档；不与 SYS_EMPLOYEE 强行合并",
            }
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_person",
                entity_code=person_code,
                diff_type="staff_only_supplement",
                before_data=_person_payload(person),
                after_data={
                    "sources": [
                        {
                            "source_table": r.source_table,
                            "source_person_name": r.source_person_name,
                            "source_dept_code": r.source_dept_code,
                        }
                        for r in rows
                    ],
                    "merge_suggestion": suggestion,
                },
                severity="low",
            )
            created += int(added)
            skipped += int(not added)
            staff_only += int(added)
            continue

        if not person:
            continue

        # 主档与任一来源字段不一致
        for r in rows:
            changed: dict[str, dict[str, Any]] = {}
            if r.source_person_name and person.person_name_cn and r.source_person_name != person.person_name_cn:
                changed["person_name_cn"] = {"master": person.person_name_cn, "source": r.source_person_name}
            if r.source_dept_code and person.dept_code and r.source_dept_code != person.dept_code:
                changed["dept_code"] = {"master": person.dept_code, "source": r.source_dept_code}
            if not changed:
                continue
            prefer = "FXHIS.SYS_EMPLOYEE" if "SYS_EMPLOYEE" in (r.source_table or "").upper() else (r.source_table or "")
            suggestion = {
                "action": "manual_confirm",
                "prefer_source_table": prefer,
                "note": "字段不一致：保留 master 或按 prefer_source_table 人工改主档；本接口不自动覆盖",
                "changed_fields": changed,
            }
            added = _add_identity_diff(
                db,
                source_system=source_system,
                target_system=target_system,
                entity_type="identity_person",
                entity_code=person_code,
                diff_type="field_mismatch",
                before_data=_person_payload(person),
                after_data={
                    "source_table": r.source_table,
                    "source_person_name": r.source_person_name,
                    "source_dept_code": r.source_dept_code,
                    "changed_fields": changed,
                    "merge_suggestion": suggestion,
                },
                severity="medium",
            )
            created += int(added)
            skipped += int(not added)
            mismatch += int(added)
            break

    from sqlalchemy import func

    db.flush()
    open_total = db.scalar(
        select(func.count()).select_from(IdentitySyncDiff).where(IdentitySyncDiff.status == "open")
    ) or 0

    return {
        "status": "success",
        "mode": "review_only",
        "auto_apply": False,
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "source_system": source_system,
        "target_system": target_system,
        "scanned_person_codes": len(by_code),
        "scanned_source_rows": len(sources),
        "diffs_created": created,
        "diffs_skipped_existing": skipped,
        "stats": {
            "multi_source_conflict": multi,
            "field_mismatch": mismatch,
            "staff_only_supplement": staff_only,
            "open_diffs_total": open_total,
        },
        "note": "差异仅供人工复核；resolved/ignored 由前端/API 更新状态，不自动写主数据",
    }
