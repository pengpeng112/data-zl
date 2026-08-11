"""Import one diagnosis mapping workbook and optionally dispatch it.

Existing platform rows are never overwritten. Existing target rows are
handled by the server-side transactional executor and skipped per table.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping
from app.models.dict_sync_outbox import DictSyncOutboxEvent
from app.services.dict_medical_import import parse_diagnosis_mapping_excel
from app.services.dict_medical_push import approve_plan, create_push_plan
from app.services.dict_sync_worker import dispatch_dict_event, settle_event

LOCAL_SET = "diagnosis_local_clinical"
NATIONAL_SET = "diagnosis_national_clinical_v2"
INSURANCE_SET = "diagnosis_insurance_v2"
CATEGORY = "diagnosis"


def _mapping(db, local_code: str, target_set: str) -> DictMedicalCodeMapping | None:
    return db.scalar(select(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == CATEGORY,
        DictMedicalCodeMapping.from_code_set == LOCAL_SET,
        DictMedicalCodeMapping.from_item_code == local_code,
        DictMedicalCodeMapping.to_code_set == target_set,
    ))


def _ensure_target_item(db, code_set: str, code: str | None, name: str | None) -> None:
    code = (code or "").strip()
    if not code:
        return
    existing = db.scalar(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == code_set,
        DictMedicalCodeItem.item_code == code,
    ))
    if existing is None:
        db.add(DictMedicalCodeItem(
            code_set_code=code_set,
            item_code=code,
            item_name_cn=(name or code).strip(),
            category_code=CATEGORY,
            status="active",
        ))
        db.flush()


def _ensure_mapping(db, local_code: str, target_set: str, target_code: str | None) -> str:
    target_code = (target_code or "").strip()
    if not target_code:
        return "empty"
    existing = _mapping(db, local_code, target_set)
    if existing is not None:
        return "exists" if existing.to_item_code == target_code else "conflict"
    db.add(DictMedicalCodeMapping(
        category_code=CATEGORY,
        from_code_set=LOCAL_SET,
        from_item_code=local_code,
        to_code_set=target_set,
        to_item_code=target_code,
        mapping_type="import",
        mapping_cardinality="many_to_one",
        confidence="high",
        review_status="approved",
        reviewer="controlled-excel-import",
        reviewed_at=datetime.now(timezone.utc),
    ))
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    if args.dispatch and not args.apply:
        parser.error("--dispatch requires --apply")

    parsed = parse_diagnosis_mapping_excel(args.workbook.read_bytes(), args.workbook.name)
    if parsed.get("error"):
        raise SystemExit(parsed["error"])
    rows = [row["values"] for row in parsed["rows"]]
    codes = [str(row.get("hospital_code") or "").strip() for row in rows]
    if len(codes) != len(set(codes)):
        raise SystemExit("duplicate hospital codes in workbook")
    if any(not code or not str(row.get("hospital_name") or "").strip() for code, row in zip(codes, rows)):
        raise SystemExit("hospital code/name must not be empty")

    db = SessionLocal()
    summary = {
        "workbook_rows": len(rows),
        "platform_created": 0,
        "platform_existing": 0,
        "mapping_created": 0,
        "conflicts": 0,
        "eligible": 0,
        "plan_id": None,
        "dispatch": [],
    }
    eligible: list[str] = []
    try:
        for row in rows:
            local_code = str(row["hospital_code"]).strip()
            local_name = str(row["hospital_name"]).strip()
            national_code = str(row.get("national_clinical_code") or "").strip()
            insurance_code = str(row.get("insurance_code") or "").strip()
            insurance_name = str(row.get("insurance_name") or "").strip()
            existing = db.scalar(select(DictMedicalCodeItem).where(
                DictMedicalCodeItem.code_set_code == LOCAL_SET,
                DictMedicalCodeItem.item_code == local_code,
            ))
            if existing is not None and existing.item_name_cn != local_name:
                summary["conflicts"] += 1
                continue

            current_nc = _mapping(db, local_code, NATIONAL_SET)
            current_ins = _mapping(db, local_code, INSURANCE_SET)
            if current_nc is not None and current_nc.to_item_code != national_code:
                summary["conflicts"] += 1
                continue
            if current_ins is not None and current_ins.to_item_code != insurance_code:
                summary["conflicts"] += 1
                continue

            if existing is None:
                extra = {
                    "dict_attribute": (row.get("dict_attribute") or "院内扩展").strip(),
                    "jhemr_ybhm": "灰码" if insurance_code and not insurance_name else None,
                    "national_clinical_code": national_code or None,
                    "national_clinical_name": row.get("national_clinical_name"),
                    "insurance_raw_code": insurance_code or None,
                    "insurance_raw_name": insurance_name or None,
                    "insurance_mapping_status": "grey" if insurance_code and not insurance_name else "valid",
                    "source_file": args.workbook.name,
                    "source_sheet": parsed["sheet"],
                }
                db.add(DictMedicalCodeItem(
                    code_set_code=LOCAL_SET,
                    item_code=local_code,
                    item_name_cn=local_name,
                    category_code=CATEGORY,
                    status="active",
                    extra=extra,
                ))
                db.flush()
                summary["platform_created"] += 1
            else:
                summary["platform_existing"] += 1

            _ensure_target_item(db, NATIONAL_SET, national_code, row.get("national_clinical_name"))
            _ensure_target_item(db, INSURANCE_SET, insurance_code, insurance_name)
            for target_set, target_code in ((NATIONAL_SET, national_code), (INSURANCE_SET, insurance_code)):
                result = _ensure_mapping(db, local_code, target_set, target_code)
                if result == "created":
                    summary["mapping_created"] += 1
                elif result == "conflict":
                    raise RuntimeError("mapping changed during controlled import")
            eligible.append(local_code)

        summary["eligible"] = len(eligible)
        if not args.apply:
            db.rollback()
            print(json.dumps(summary, ensure_ascii=False))
            return 0
        if not eligible:
            raise RuntimeError("no eligible rows")
        db.commit()

        plan = create_push_plan(
            db,
            category_code=CATEGORY,
            target_systems=["HIS_SOURCE", "JHEMR_VASTBASE"],
            item_codes=eligible,
            created_by="controlled-excel-import",
            action_type="insert",
        )
        approve_plan(
            db,
            plan.id,
            approved_by="dict-auto-approver",
            note="user-authorized diagnosis workbook dispatch",
        )
        summary["plan_id"] = plan.id

        if args.dispatch:
            events = list(db.scalars(select(DictSyncOutboxEvent).where(
                DictSyncOutboxEvent.plan_id == plan.id,
            )).all())
            for event in events:
                event.status = "leased"
                event.attempt = (event.attempt or 0) + 1
                event.lease_holder = "controlled-excel-import"
                db.commit()
                result = dispatch_dict_event(db, event)
                status = settle_event(db, event, result)
                db.commit()
                summary["dispatch"].append({
                    "target": event.target_system,
                    "status": status,
                    "error": result.get("error"),
                })
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
