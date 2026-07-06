from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import delete, or_

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
ROOT_DIR = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT_DIR / "开发起步包" / "诊断与手术维护"

from app.core.db import SessionLocal
from app.models.dict_medical import (
    DictMedicalCodeItem,
    DictMedicalCodeMapping,
    DictMedicalCodeSet,
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


def add_item(items: dict[tuple[str, str], dict], code_set_code: str, item_code: str, item_name: str, category_code: str, extra: dict) -> None:
    item_code = (item_code or "").strip()
    item_name = (item_name or "").strip()
    if not item_code or not item_name:
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
    if item_name != items[key]["item_name_cn"] and item_name not in items[key]["aliases"]:
        items[key]["aliases"].append(item_name)

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
    """The diagnosis workbook currently stores HIS/version markers in these columns."""
    code = (code or "").strip()
    name = (name or "").strip()
    if not code or not name:
        return False
    marker_codes = {"HIS"}
    if code.upper() in marker_codes and re.fullmatch(r"\d{8}", name):
        return False
    return True


def find_source_files() -> tuple[Path, Path]:
    xlsx_files = list(SOURCE_DIR.glob("*.xlsx"))
    diagnosis = next((p for p in xlsx_files if "诊断" in p.name), None)
    operation = next((p for p in xlsx_files if "手术" in p.name), None)
    if diagnosis is None or operation is None:
        raise FileNotFoundError(f"未找到诊断/手术维护 Excel：{SOURCE_DIR}")
    return diagnosis, operation


def build_payload() -> tuple[list[dict], list[dict]]:
    diagnosis_path, operation_path = find_source_files()
    items: dict[tuple[str, str], dict] = {}
    mappings: dict[tuple[str, str, str, str, str], dict] = {}

    diagnosis_rows = read_sheet_rows(diagnosis_path, "门诊诊断和出入院诊断")
    diagnosis_headers = header_map(diagnosis_rows[0])
    seen_diag: set[str] = set()
    duplicate_diag: list[str] = []
    for row in diagnosis_rows[1:]:
        local_code = hcell(row, diagnosis_headers, "院内临床诊断疾病编码")
        local_name = hcell(row, diagnosis_headers, "院内临床诊断疾病名称")
        national_code = hcell(row, diagnosis_headers, "国家临床版2.0映疾病编码", "国家临床版2.0疾病编码")
        national_name = hcell(row, diagnosis_headers, "对应国家临床版2.0疾病名称", "国家临床版2.0疾病名称")
        insurance_code_raw = hcell(row, diagnosis_headers, "国家医保版2.0疾病编码")
        insurance_name_raw = hcell(row, diagnosis_headers, "国家医保版2.0疾病名称")
        has_valid_insurance = is_valid_diagnosis_insurance_mapping(insurance_code_raw, insurance_name_raw)
        insurance_code = insurance_code_raw if has_valid_insurance else ""
        insurance_name = insurance_name_raw if has_valid_insurance else ""
        if local_code in seen_diag:
            duplicate_diag.append(local_code)
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
            "special_disease_name": hcell(row, diagnosis_headers, "病种名称"),
            "low_risk_category_code": hcell(row, diagnosis_headers, "ICD低风险编码类目"),
            "low_risk_disease_name": hcell(row, diagnosis_headers, "ICD低风险病种名称"),
            "infectious_disease_name": hcell(row, diagnosis_headers, "传染病诊断"),
        }
        add_item(items, "diagnosis_local_clinical", local_code, local_name, "diagnosis", extra)
        add_item(items, "diagnosis_national_clinical_v2", national_code, national_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "门诊诊断和出入院诊断"})
        add_item(items, "diagnosis_insurance_v2", insurance_code, insurance_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "门诊诊断和出入院诊断", "note": "按 Excel 国家医保版2.0映射列导入"})
        add_mapping(mappings, "diagnosis", "diagnosis_local_clinical", local_code, "diagnosis_national_clinical_v2", national_code, "门诊诊断和出入院诊断：院内码映射国家临床版2.0")
        add_mapping(mappings, "diagnosis", "diagnosis_local_clinical", local_code, "diagnosis_insurance_v2", insurance_code, "门诊诊断和出入院诊断：院内码映射国家医保版2.0")

    pathology_rows = read_sheet_rows(diagnosis_path, "病理诊断")
    pathology_headers = header_map(pathology_rows[1])
    for row in pathology_rows[2:]:
        local_code = hcell(row, pathology_headers, "疾病编码")
        local_name = hcell(row, pathology_headers, "疾病名称")
        national_code = hcell(row, pathology_headers, "肿瘤形态学编码")
        national_name = hcell(row, pathology_headers, "肿瘤形态学名称")
        add_item(items, "diagnosis_local_pathology", local_code, local_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "病理诊断", "dict_attribute": cell(row, 1)})
        add_item(items, "diagnosis_national_clinical_v2", national_code, national_name, "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "病理诊断", "code_kind": "肿瘤形态学编码"})
        add_mapping(mappings, "diagnosis", "diagnosis_local_pathology", local_code, "diagnosis_national_clinical_v2", national_code, "病理诊断：院内形态学码映射国家临床版2.0")

    external_rows = read_sheet_rows(diagnosis_path, "外部原因")
    external_headers = header_map(external_rows[0])
    for row in external_rows[1:]:
        add_item(items, "diagnosis_external_cause_clinical_v2", hcell(row, external_headers, "疾病编码"), hcell(row, external_headers, "疾病名称"), "diagnosis", {"source_file": diagnosis_path.name, "source_sheet": "外部原因", "dict_attribute": hcell(row, external_headers, "字典属性")})

    operation_rows = read_sheet_rows(operation_path, "手术操作字典")
    operation_headers = header_map(operation_rows[0])
    seen_oper: set[str] = set()
    duplicate_oper: list[str] = []
    for row in operation_rows[1:]:
        local_code = hcell(row, operation_headers, "院内临床手术编码")
        local_name = hcell(row, operation_headers, "院内临床手术名称")
        national_code = hcell(row, operation_headers, "国家临床版3.0手术编码")
        national_name = hcell(row, operation_headers, "国家临床版3.0手术名称")
        insurance_code = hcell(row, operation_headers, "国家医保版2.0手术代码", "国家医保版2.0手术编码")
        insurance_name = hcell(row, operation_headers, "国家医保版2.0手术名称")
        if local_code in seen_oper:
            duplicate_oper.append(local_code)
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
            "insurance_source_marker_code": insurance_code_raw,
            "insurance_source_marker_name": insurance_name_raw,
            "insurance_mapping_status": "valid" if has_valid_insurance else "source_marker_not_mapping",
        }
        add_item(items, "operation_local_clinical", local_code, local_name, "operation", extra)
        add_item(items, "operation_national_clinical_v3", national_code, national_name, "operation", {"source_file": operation_path.name, "source_sheet": "手术操作字典"})
        add_item(items, "operation_insurance_v2", insurance_code, insurance_name, "operation", {"source_file": operation_path.name, "source_sheet": "手术操作字典"})
        add_mapping(mappings, "operation", "operation_local_clinical", local_code, "operation_national_clinical_v3", national_code, "手术操作字典：院内码映射国家临床版3.0")
        add_mapping(mappings, "operation", "operation_local_clinical", local_code, "operation_insurance_v2", insurance_code, "手术操作字典：院内码映射国家医保版2.0")

    item_rows = []
    for item in items.values():
        aliases = item.pop("aliases", [])
        item["item_name_alias"] = "；".join(aliases) if aliases else None
        item_rows.append(item)
    return item_rows, list(mappings.values())

def import_payload() -> dict:
    item_rows, mapping_rows = build_payload()
    with SessionLocal() as db:
        db.execute(delete(DictMedicalCodeMapping).where(or_(DictMedicalCodeMapping.from_code_set.in_(MANAGED_CODE_SETS), DictMedicalCodeMapping.to_code_set.in_(MANAGED_CODE_SETS))))
        db.execute(delete(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code.in_(MANAGED_CODE_SETS)))
        db.execute(delete(DictMedicalCodeSet).where(DictMedicalCodeSet.code_set_code.in_(MANAGED_CODE_SETS)))
        db.flush()

        for seed in CODE_SETS:
            db.add(DictMedicalCodeSet(**seed.__dict__))
        db.flush()

        by_set: dict[str, int] = {}
        for item in item_rows:
            db.add(DictMedicalCodeItem(**item))
            by_set[item["code_set_code"]] = by_set.get(item["code_set_code"], 0) + 1

        by_mapping: dict[str, int] = {}
        for mapping in mapping_rows:
            db.add(DictMedicalCodeMapping(**mapping))
            key = f'{mapping["from_code_set"]}->{mapping["to_code_set"]}'
            by_mapping[key] = by_mapping.get(key, 0) + 1

        db.commit()

    return {
        "source_dir": str(SOURCE_DIR),
        "code_sets": len(CODE_SETS),
        "items": len(item_rows),
        "mappings": len(mapping_rows),
        "items_by_code_set": by_set,
        "mappings_by_pair": by_mapping,
    }


def main() -> None:
    result = import_payload()
    print(result)


if __name__ == "__main__":
    main()
