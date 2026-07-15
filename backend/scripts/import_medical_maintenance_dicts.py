"""Import diagnosis/operation maintenance Excel into platform medical dict tables.

Default mode is --dry-run (parse + validate only, no DB writes).
Apply requires --apply --confirmation IMPORT-MEDICAL-DICTS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import delete, or_, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = ROOT_DIR / "开发起步包" / "诊断与手术维护"

from app.core.db import SessionLocal
from app.models.dict_medical import (
    DictMedicalCodeItem,
    DictMedicalCodeMapping,
    DictMedicalCodeSet,
    DictMedicalImportRun,
)

XML_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

MANAGED_CODE_SETS = {
    "diagnosis_local_clinical",
    "diagnosis_local_pathology",
    "diagnosis_national_clinical_v2",
    "diagnosis_insurance_v2",
    "diagnosis_external_cause_clinical_v2",
    "operation_local_clinical",
    "operation_national_clinical_v3",
    "operation_insurance_v2",
}

CONFIRMATION = "IMPORT-MEDICAL-DICTS"


@dataclass(frozen=True)
class CodeSetSeed:
    category_code: str
    code_set_code: str
    code_set_type: str
    code_set_name_cn: str
    standard_system: str | None
    version_no: str
    source_system: str


CODE_SETS = [
    CodeSetSeed("diagnosis", "diagnosis_local_clinical", "clinical", "院内临床诊断字典", "院内", "2026.06.04", "Excel维护源"),
    CodeSetSeed("diagnosis", "diagnosis_local_pathology", "clinical", "院内病理诊断字典", "院内", "2026.06.04", "Excel维护源"),
    CodeSetSeed("diagnosis", "diagnosis_national_clinical_v2", "national", "国家临床版2.0诊断字典", "国家临床版2.0", "2.0", "Excel维护源"),
    CodeSetSeed("diagnosis", "diagnosis_insurance_v2", "insurance", "国家医保版2.0诊断字典", "国家医保版2.0", "2.0", "Excel维护源"),
    CodeSetSeed("diagnosis", "diagnosis_external_cause_clinical_v2", "national", "国家临床版2.0外部原因字典", "国家临床版2.0", "2.0", "Excel维护源"),
    CodeSetSeed("operation", "operation_local_clinical", "clinical", "院内临床手术操作字典", "院内", "2026.06.02", "Excel维护源"),
    CodeSetSeed("operation", "operation_national_clinical_v3", "national", "国家临床版3.0手术操作字典", "国家临床版3.0", "3.0", "Excel维护源"),
    CodeSetSeed("operation", "operation_insurance_v2", "insurance", "国家医保版2.0手术操作字典", "国家医保版2.0", "2.0", "Excel维护源"),
]


def col_num(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref or "")
    if not match:
        return 0
    value = 0
    for ch in match.group(1):
        value = value * 26 + ord(ch) - 64
    return value


def read_shared_strings(zf: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall("a:si", XML_NS):
        values.append("".join(text.text or "" for text in item.findall(".//a:t", XML_NS)))
    return values


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//a:t", XML_NS)).strip()
    value = cell.find("a:v", XML_NS)
    if value is None:
        return ""
    raw = (value.text or "").strip()
    if cell_type == "s":
        try:
            return shared_strings[int(raw)].strip()
        except (ValueError, IndexError):
            return raw
    return raw


def workbook_sheets(zf: ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("rel:Relationship", REL_NS)
    }
    sheets: dict[str, str] = {}
    for sheet in workbook.findall(".//a:sheets/a:sheet", XML_NS):
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rid_to_target[rid]
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheets[sheet.attrib["name"]] = target
    return sheets


def read_sheet_rows(path: Path, sheet_name: str) -> list[list[str]]:
    with ZipFile(path) as zf:
        shared_strings = read_shared_strings(zf)
        sheet_path = workbook_sheets(zf)[sheet_name]
        root = ET.fromstring(zf.read(sheet_path))
        rows: list[list[str]] = []
        for row in root.findall(".//a:sheetData/a:row", XML_NS):
            values: dict[int, str] = {}
            max_col = 0
            for cell in row.findall("a:c", XML_NS):
                idx = col_num(cell.attrib.get("r", ""))
                max_col = max(max_col, idx)
                values[idx] = cell_value(cell, shared_strings)
            rows.append([values.get(i, "") for i in range(1, max_col + 1)])
        return rows


def cell(row: list[str], index: int) -> str:
    if index < 1 or index > len(row):
        return ""
    return (row[index - 1] or "").strip()


def normalized_header(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def header_map(row: list[str]) -> dict[str, int]:
    return {normalized_header(value): idx + 1 for idx, value in enumerate(row) if normalized_header(value)}


def hcell(row: list[str], headers: dict[str, int], *names: str) -> str:
    for name in names:
        idx = headers.get(normalized_header(name))
        if idx:
            return cell(row, idx)
    return ""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def add_item(items: dict[tuple[str, str], dict], code_set_code: str, item_code: str, item_name: str, category_code: str, extra: dict, stats: dict) -> None:
    item_code = (item_code or "").strip()
    item_name = (item_name or "").strip()
    # optional secondary columns may be empty; only incomplete pairs are errors
    if not item_code and not item_name:
        stats["skipped_empty_pair"] += 1
        return
    if not item_code and item_name:
        stats["empty_code"] += 1
        return
    if item_code and not item_name:
        stats["empty_name"] += 1
        return
    key = (code_set_code, item_code)
    if key not in items:
        items[key] = {
            "code_set_code": code_set_code,
            "item_code": item_code,
            "item_name_cn": item_name,
            "category_code": category_code,
            "status": "active",
            "extra": extra,
            "aliases": [],
        }
        return
    if item_name != items[key]["item_name_cn"]:
        if item_name not in items[key]["aliases"]:
            items[key]["aliases"].append(item_name)
        stats["same_code_diff_name"] += 1
    else:
        stats["duplicate_code"] += 1


def add_mapping(mappings: dict[tuple[str, str, str, str, str], dict], category_code: str, from_code_set: str, from_code: str, to_code_set: str, to_code: str, note: str, cardinality: str = "many_to_one") -> None:
    from_code = (from_code or "").strip()
    to_code = (to_code or "").strip()
    if not from_code or not to_code:
        return
    key = (category_code, from_code_set, from_code, to_code_set, to_code)
    mappings[key] = {
        "category_code": category_code,
        "from_code_set": from_code_set,
        "from_item_code": from_code,
        "to_code_set": to_code_set,
        "to_item_code": to_code,
        "mapping_type": "equivalent",
        "mapping_cardinality": cardinality,
        "confidence": "high",
        "review_status": "approved",
        "review_note": note,
    }


def is_valid_diagnosis_insurance_mapping(code: str, name: str) -> bool:
    code = (code or "").strip()
    name = (name or "").strip()
    if not code or not name:
        return False
    if code.upper() in {"HIS"} and re.fullmatch(r"\d{8}", name):
        return False
    return True


def find_source_files(source_dir: Path) -> tuple[Path, Path]:
    xlsx_files = list(source_dir.glob("*.xlsx"))
    diagnosis = next((p for p in xlsx_files if "诊断" in p.name), None)
    operation = next((p for p in xlsx_files if "手术" in p.name), None)
    if diagnosis is None or operation is None:
        raise FileNotFoundError(f"未找到诊断/手术维护 Excel：{source_dir}")
    return diagnosis, operation


def build_payload(source_dir: Path) -> tuple[list[dict], list[dict], dict]:
    diagnosis_path, operation_path = find_source_files(source_dir)
    items: dict[tuple[str, str], dict] = {}
    mappings: dict[tuple[str, str, str, str, str], dict] = {}
    stats = {
        "empty_code": 0,
        "empty_name": 0,
        "skipped_empty_pair": 0,
        "duplicate_code": 0,
        "same_code_diff_name": 0,
        "input_rows_diagnosis": 0,
        "input_rows_operation": 0,
    }

    with ZipFile(diagnosis_path) as zf:
        diag_sheets = list(workbook_sheets(zf).keys())
    with ZipFile(operation_path) as zf:
        oper_sheets = list(workbook_sheets(zf).keys())

    diagnosis_rows = read_sheet_rows(diagnosis_path, "门诊诊断和出入院诊断")
    diagnosis_headers = header_map(diagnosis_rows[0])
    seen_diag: set[str] = set()
    for row in diagnosis_rows[1:]:
        stats["input_rows_diagnosis"] += 1
        local_code = hcell(row, diagnosis_headers, "院内临床诊断编码", "院内临床诊断疾病编码")
        local_name = hcell(row, diagnosis_headers, "院内临床诊断名称", "院内临床诊断疾病名称")
        national_code = hcell(row, diagnosis_headers, "国家临床版2.0映疾病编码", "国家临床版2.0疾病编码")
        national_name = hcell(row, diagnosis_headers, "对应国家临床版2.0疾病名称", "国家临床版2.0疾病名称")
        insurance_code_raw = hcell(row, diagnosis_headers, "国家医保版2.0疾病编码")
        insurance_name_raw = hcell(row, diagnosis_headers, "国家医保版2.0疾病名称")
        has_valid_insurance = is_valid_diagnosis_insurance_mapping(insurance_code_raw, insurance_name_raw)
        insurance_code = insurance_code_raw if has_valid_insurance else ""
        insurance_name = insurance_name_raw if has_valid_insurance else ""
        if local_code in seen_diag:
            stats["duplicate_code"] += 1
            continue
        if local_code:
            seen_diag.add(local_code)
        extra = {
            "source_file": diagnosis_path.name,
            "source_sheet": "门诊诊断和出入院诊断",
            "dict_attribute": hcell(row, diagnosis_headers, "字典属性"),
            "national_clinical_code": national_code,
            "national_clinical_name": national_name,
            "insurance_raw_code": insurance_code,
            "insurance_raw_name": insurance_name,
            "insurance_source_marker_code": insurance_code_raw,
            "insurance_source_marker_name": insurance_name_raw,
            "insurance_mapping_status": "valid" if has_valid_insurance else "source_marker_not_mapping",
            "special_disease_code": hcell(row, diagnosis_headers, "门诊慢特病编码"),
            "special_disease_name": hcell(row, diagnosis_headers, "门诊慢特病名称", "病种名称"),
            "low_risk_category_code": hcell(row, diagnosis_headers, "ICD低风险编码类目"),
            "low_risk_disease_name": hcell(row, diagnosis_headers, "ICD低风险病种名称"),
            "infectious_disease_name": hcell(row, diagnosis_headers, "传染病诊断"),
        }
        add_item(items, "diagnosis_local_clinical", local_code, local_name, "diagnosis", extra, stats)
        add_item(items, "diagnosis_national_clinical_v2", national_code, national_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "门诊诊断和出入院诊断"}, stats)
        add_item(items, "diagnosis_insurance_v2", insurance_code, insurance_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "门诊诊断和出入院诊断", "note": "按 Excel 国家医保版2.0映射列导入"}, stats)
        add_mapping(mappings, "diagnosis", "diagnosis_local_clinical", local_code, "diagnosis_national_clinical_v2", national_code, "门诊诊断和出入院诊断：院内码映射国家临床版2.0")
        add_mapping(mappings, "diagnosis", "diagnosis_local_clinical", local_code, "diagnosis_insurance_v2", insurance_code, "门诊诊断和出入院诊断：院内码映射国家医保版2.0")

    pathology_rows = read_sheet_rows(diagnosis_path, "病理诊断")
    pathology_headers = header_map(pathology_rows[1])
    for row in pathology_rows[2:]:
        local_code = hcell(row, pathology_headers, "疾病编码")
        local_name = hcell(row, pathology_headers, "疾病名称")
        national_code = hcell(row, pathology_headers, "肿瘤形态学编码")
        national_name = hcell(row, pathology_headers, "肿瘤形态学名称")
        add_item(items, "diagnosis_local_pathology", local_code, local_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "病理诊断", "dict_attribute": cell(row, 1)}, stats)
        add_item(items, "diagnosis_national_clinical_v2", national_code, national_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "病理诊断", "code_kind": "肿瘤形态学编码"}, stats)
        add_mapping(mappings, "diagnosis", "diagnosis_local_pathology", local_code, "diagnosis_national_clinical_v2", national_code, "病理诊断：院内形态学码映射国家临床版2.0")

    external_rows = read_sheet_rows(diagnosis_path, "外部原因")
    external_headers = header_map(external_rows[0])
    for row in external_rows[1:]:
        add_item(items, "diagnosis_external_cause_clinical_v2", hcell(row, external_headers, "疾病编码"), hcell(row, external_headers, "疾病名称"), "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "外部原因", "dict_attribute": hcell(row, external_headers, "字典属性")}, stats)

    operation_rows = read_sheet_rows(operation_path, "手术操作字典")
    operation_headers = header_map(operation_rows[0])
    seen_oper: set[str] = set()
    for row in operation_rows[1:]:
        stats["input_rows_operation"] += 1
        local_code = hcell(row, operation_headers, "院内临床手术编码")
        local_name = hcell(row, operation_headers, "院内临床手术名称")
        national_code = hcell(row, operation_headers, "国家临床版3.0手术编码")
        national_name = hcell(row, operation_headers, "国家临床版3.0手术名称")
        insurance_code = hcell(row, operation_headers, "国家医保版2.0手术代码", "国家医保版2.0手术编码")
        insurance_name = hcell(row, operation_headers, "国家医保版2.0手术名称")
        if local_code in seen_oper:
            stats["duplicate_code"] += 1
            continue
        if local_code:
            seen_oper.add(local_code)
        extra = {
            "source_file": operation_path.name,
            "source_sheet": "手术操作字典",
            "dict_attribute": hcell(row, operation_headers, "字典属性"),
            "operation_level": hcell(row, operation_headers, "院内手术等级"),
            "national_clinical_code": national_code,
            "national_clinical_name": national_name,
            "operation_category": hcell(row, operation_headers, "手术类别"),
            "performance_level4_flag": hcell(row, operation_headers, "绩效考核四级手术标识"),
            "performance_minimally_invasive_flag": hcell(row, operation_headers, "绩效考核微创手术标识"),
            "restricted_tech_flag": hcell(row, operation_headers, "限制类技术标识"),
            "insurance_raw_code": insurance_code,
            "insurance_raw_name": insurance_name,
        }
        add_item(items, "operation_local_clinical", local_code, local_name, "operation", extra, stats)
        add_item(items, "operation_national_clinical_v3", national_code, national_name, "operation", {"source_file": operation_path.name, "source_sheet": "手术操作字典"}, stats)
        add_item(items, "operation_insurance_v2", insurance_code, insurance_name, "operation", {"source_file": operation_path.name, "source_sheet": "手术操作字典"}, stats)
        add_mapping(mappings, "operation", "operation_local_clinical", local_code, "operation_national_clinical_v3", national_code, "手术操作字典：院内码映射国家临床版3.0")
        add_mapping(mappings, "operation", "operation_local_clinical", local_code, "operation_insurance_v2", insurance_code, "手术操作字典：院内码映射国家医保版2.0")

    item_rows = []
    for item in items.values():
        aliases = item.pop("aliases", [])
        item["item_name_alias"] = "；".join(aliases) if aliases else None
        item_rows.append(item)
    mapping_rows = list(mappings.values())

    item_keys = {(i["code_set_code"], i["item_code"]) for i in item_rows}
    missing_fk = 0
    for m in mapping_rows:
        if (m["from_code_set"], m["from_item_code"]) not in item_keys:
            missing_fk += 1
        if (m["to_code_set"], m["to_item_code"]) not in item_keys:
            missing_fk += 1

    by_set: dict[str, int] = {}
    for item in item_rows:
        by_set[item["code_set_code"]] = by_set.get(item["code_set_code"], 0) + 1
    diag_items = sum(v for k, v in by_set.items() if k.startswith("diagnosis_"))
    oper_items = sum(v for k, v in by_set.items() if k.startswith("operation_"))
    diag_maps = sum(1 for m in mapping_rows if m["category_code"] == "diagnosis")
    oper_maps = sum(1 for m in mapping_rows if m["category_code"] == "operation")

    meta = {
        "source_dir": str(source_dir),
        "diagnosis_file": diagnosis_path.name,
        "operation_file": operation_path.name,
        "diagnosis_size": diagnosis_path.stat().st_size,
        "operation_size": operation_path.stat().st_size,
        "diagnosis_sha256": file_sha256(diagnosis_path),
        "operation_sha256": file_sha256(operation_path),
        "diagnosis_sheets": diag_sheets,
        "operation_sheets": oper_sheets,
        "code_sets": len(CODE_SETS),
        "items": len(item_rows),
        "items_diagnosis": diag_items,
        "items_operation": oper_items,
        "mappings": len(mapping_rows),
        "mappings_diagnosis": diag_maps,
        "mappings_operation": oper_maps,
        "items_by_code_set": by_set,
        "parse_stats": stats,
        "missing_mapping_fk": missing_fk,
    }
    return item_rows, mapping_rows, meta


def compare_with_platform(db, item_rows: list[dict], mapping_rows: list[dict]) -> dict:
    existing_items = db.scalars(
        select(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code.in_(MANAGED_CODE_SETS))
    ).all()
    existing_maps = db.scalars(
        select(DictMedicalCodeMapping).where(
            or_(
                DictMedicalCodeMapping.from_code_set.in_(MANAGED_CODE_SETS),
                DictMedicalCodeMapping.to_code_set.in_(MANAGED_CODE_SETS),
            )
        )
    ).all()
    existing_item_keys = {(r.code_set_code, r.item_code): r.item_name_cn for r in existing_items}
    new_item_keys = {(r["code_set_code"], r["item_code"]): r["item_name_cn"] for r in item_rows}
    existing_map_keys = {
        (r.category_code, r.from_code_set, r.from_item_code, r.to_code_set, r.to_item_code)
        for r in existing_maps
    }
    new_map_keys = {
        (r["category_code"], r["from_code_set"], r["from_item_code"], r["to_code_set"], r["to_item_code"])
        for r in mapping_rows
    }
    return {
        "existing_managed_items": len(existing_items),
        "existing_managed_mappings": len(existing_maps),
        "items_new": len(set(new_item_keys) - set(existing_item_keys)),
        "items_removed": len(set(existing_item_keys) - set(new_item_keys)),
        "items_same_key": len(set(new_item_keys) & set(existing_item_keys)),
        "mappings_new": len(new_map_keys - existing_map_keys),
        "mappings_removed": len(existing_map_keys - new_map_keys),
        "replace_scope": sorted(MANAGED_CODE_SETS),
    }


def apply_import(db, item_rows: list[dict], mapping_rows: list[dict], meta: dict, operator: str) -> dict:
    # idempotent: same SHA pair already succeeded -> no_change
    prev = db.scalar(
        select(DictMedicalImportRun)
        .where(
            DictMedicalImportRun.diagnosis_sha256 == meta["diagnosis_sha256"],
            DictMedicalImportRun.operation_sha256 == meta["operation_sha256"],
            DictMedicalImportRun.status == "succeeded",
            DictMedicalImportRun.mode == "apply",
        )
        .order_by(DictMedicalImportRun.id.desc())
    )
    if prev:
        return {
            "status": "no_change",
            "batch_code": prev.batch_code,
            "reason": "same file SHA-256 already imported",
            "items": meta["items"],
            "mappings": meta["mappings"],
        }

    batch_code = f"med-import-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    run = DictMedicalImportRun(
        batch_code=batch_code,
        source_dir=meta["source_dir"],
        diagnosis_file_name=meta["diagnosis_file"],
        operation_file_name=meta["operation_file"],
        diagnosis_sha256=meta["diagnosis_sha256"],
        operation_sha256=meta["operation_sha256"],
        status="running",
        mode="apply",
        operator=operator,
        stats=meta,
    )
    db.add(run)
    db.flush()

    try:
        # single transaction replace of managed sets only
        db.execute(
            delete(DictMedicalCodeMapping).where(
                or_(
                    DictMedicalCodeMapping.from_code_set.in_(MANAGED_CODE_SETS),
                    DictMedicalCodeMapping.to_code_set.in_(MANAGED_CODE_SETS),
                )
            )
        )
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code.in_(MANAGED_CODE_SETS)))
        db.execute(delete(DictMedicalCodeSet).where(DictMedicalCodeSet.code_set_code.in_(MANAGED_CODE_SETS)))
        db.flush()

        for seed in CODE_SETS:
            db.add(DictMedicalCodeSet(**seed.__dict__))
        db.flush()

        for item in item_rows:
            db.add(DictMedicalCodeItem(**item))
        for mapping in mapping_rows:
            db.add(DictMedicalCodeMapping(**mapping))

        # SessionLocal disables autoflush. Persist all staged rows inside the
        # current transaction before running the conservation counts; without
        # this explicit flush both counts incorrectly read as zero and the
        # otherwise valid import is rolled back.
        db.flush()

        from sqlalchemy import func
        item_count = db.scalar(
            select(func.count()).select_from(DictMedicalCodeItem).where(
                DictMedicalCodeItem.code_set_code.in_(MANAGED_CODE_SETS)
            )
        )
        map_count = db.scalar(
            select(func.count()).select_from(DictMedicalCodeMapping).where(
                or_(
                    DictMedicalCodeMapping.from_code_set.in_(MANAGED_CODE_SETS),
                    DictMedicalCodeMapping.to_code_set.in_(MANAGED_CODE_SETS),
                )
            )
        )
        if int(item_count or 0) != len(item_rows) or int(map_count or 0) != len(mapping_rows):
            raise RuntimeError(
                f"count mismatch items={item_count}/{len(item_rows)} mappings={map_count}/{len(mapping_rows)}"
            )

        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.stats = {**meta, "applied_items": int(item_count), "applied_mappings": int(map_count)}
        db.commit()
        return {
            "status": "succeeded",
            "batch_code": batch_code,
            "items": int(item_count),
            "mappings": int(map_count),
        }
    except Exception as exc:
        db.rollback()
        # re-open run record as failed in new transaction
        with SessionLocal() as db2:
            failed = DictMedicalImportRun(
                batch_code=batch_code + "-failed",
                source_dir=meta["source_dir"],
                diagnosis_file_name=meta["diagnosis_file"],
                operation_file_name=meta["operation_file"],
                diagnosis_sha256=meta["diagnosis_sha256"],
                operation_sha256=meta["operation_sha256"],
                status="failed",
                mode="apply",
                operator=operator,
                stats=meta,
                error_summary=str(exc)[:500],
                finished_at=datetime.now(timezone.utc),
            )
            db2.add(failed)
            db2.commit()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Import medical maintenance dicts")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", type=str, default="")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--operator", type=str, default="script:import_medical_maintenance_dicts")
    args = parser.parse_args()

    item_rows, mapping_rows, meta = build_payload(args.source_dir)
    total_input = meta["parse_stats"]["input_rows_diagnosis"] + meta["parse_stats"]["input_rows_operation"]
    # incomplete pairs only; optional blank secondary columns are skipped_empty_pair
    errorish = meta["parse_stats"]["empty_code"] + meta["parse_stats"]["empty_name"]
    error_rate = (errorish / total_input) if total_input else 0.0
    meta["error_rate"] = error_rate
    meta["incomplete_pairs"] = errorish
    meta["mode"] = "apply" if args.apply else "dry_run"

    report = {
        **meta,
        "platform_diff": None,
        "apply_result": None,
    }

    if args.apply:
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
        if error_rate > args.max_error_rate:
            raise SystemExit(f"error_rate {error_rate} exceeds max {args.max_error_rate}")
        with SessionLocal() as db:
            report["platform_diff"] = compare_with_platform(db, item_rows, mapping_rows)
            report["apply_result"] = apply_import(db, item_rows, mapping_rows, meta, args.operator)
    else:
        # dry-run: optional platform compare if DB available
        try:
            with SessionLocal() as db:
                report["platform_diff"] = compare_with_platform(db, item_rows, mapping_rows)
        except Exception as exc:
            report["platform_diff"] = {"error": f"db compare skipped: {exc}"[:200]}
        report["apply_result"] = {"status": "dry_run", "writes": 0}

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
