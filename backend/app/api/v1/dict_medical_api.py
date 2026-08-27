from datetime import datetime, timezone
import json
from html import escape
from io import BytesIO
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.dict_medical import (
    DictMedicalCodeItem,
    DictMedicalCodeMapping,
    DictMedicalCodeSet,
    DictMedicalImportRun,
    DictMedicalSyncDiff,
)
from ...models.governance_base import GovernAuditLog, GovernChangeRequest
from ...models.governance_ops import SchedulerJob
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/dict-medical", tags=["dict-medical"])


@router.get("/code-sets", summary="诊断/手术三套编码体系列表")
def list_code_sets(
    category_code: str | None = Query(None, description="diagnosis/operation"),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    stmt = select(DictMedicalCodeSet)
    if category_code:
        stmt = stmt.where(DictMedicalCodeSet.category_code == category_code)
    rows = db.scalars(stmt.order_by(DictMedicalCodeSet.category_code, DictMedicalCodeSet.code_set_code)).all()
    return ApiResponse(data=[
        {
            "id": r.id, "code_set_code": r.code_set_code,
            "code_set_name_cn": r.code_set_name_cn,
            "code_set_type": r.code_set_type,
            "category_code": r.category_code,
            "standard_system": r.standard_system,
            "enabled": r.enabled,
        }
        for r in rows
    ])


@router.get("/code-sets/{code_set_code}/items", summary="编码项列表")
def list_items(
    code_set_code: str,
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="active/inactive"),
    has_infectious: bool | None = Query(None, description="是否传染病诊断"),
    minimally_invasive_flag: str | None = Query(None, description="绩效微创标识"),
    performance_level4_flag: str | None = Query(None, description="绩效四级标识"),
    restricted_tech_flag: str | None = Query(None, description="限制技术标识"),
    operation_level: str | None = Query(None, description="院内手术等级"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code == code_set_code)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            DictMedicalCodeItem.item_name_cn.ilike(like)
            | DictMedicalCodeItem.item_code.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalCodeItem.item_code)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "item_code": r.item_code, "item_name_cn": r.item_name_cn,
         "item_name_alias": r.item_name_alias, "status": r.status}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/mappings", summary="编码对照关系列表")
def list_mappings(
    category_code: str | None = Query(None),
    review_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="active/inactive"),
    has_infectious: bool | None = Query(None, description="是否传染病诊断"),
    minimally_invasive_flag: str | None = Query(None, description="绩效微创标识"),
    performance_level4_flag: str | None = Query(None, description="绩效四级标识"),
    restricted_tech_flag: str | None = Query(None, description="限制技术标识"),
    operation_level: str | None = Query(None, description="院内手术等级"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalCodeMapping)
    if category_code:
        stmt = stmt.where(DictMedicalCodeMapping.category_code == category_code)
    if review_status:
        stmt = stmt.where(DictMedicalCodeMapping.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalCodeMapping.category_code, DictMedicalCodeMapping.from_code_set)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "category_code": r.category_code,
            "from_code_set": r.from_code_set, "from_item_code": r.from_item_code,
            "to_code_set": r.to_code_set, "to_item_code": r.to_item_code,
            "mapping_type": r.mapping_type, "mapping_cardinality": r.mapping_cardinality,
            "confidence": r.confidence, "review_status": r.review_status,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})



def _mapping_row_extra(local: DictMedicalCodeItem) -> dict:
    return local.extra or {}


@router.get("/mapping-rows", summary="按院内编码展示诊断/手术完整映射宽表")
def list_mapping_rows(
    category_code: str = Query("diagnosis", description="diagnosis/operation"),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="active/inactive"),
    has_infectious: bool | None = Query(None, description="是否传染病诊断"),
    minimally_invasive_flag: str | None = Query(None, description="绩效微创标识"),
    performance_level4_flag: str | None = Query(None, description="绩效四级标识"),
    restricted_tech_flag: str | None = Query(None, description="限制技术标识"),
    operation_level: str | None = Query(None, description="院内手术等级"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    local_code_set, national_code_set, insurance_code_set = _code_sets_for_category(category_code)
    stmt = _local_code_item_stmt(
        category_code, keyword, status, has_infectious,
        minimally_invasive_flag, performance_level4_flag, restricted_tech_flag, operation_level,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    local_items = db.scalars(
        stmt.order_by(DictMedicalCodeItem.item_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    local_codes = [r.item_code for r in local_items]

    mapping_rows = db.scalars(select(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == category_code,
        DictMedicalCodeMapping.from_code_set == local_code_set,
        DictMedicalCodeMapping.from_item_code.in_(local_codes),
    )).all() if local_codes else []
    mapping_by_key = {(m.from_item_code, m.to_code_set): m.to_item_code for m in mapping_rows}

    target_codes = [m.to_item_code for m in mapping_rows if m.to_item_code]
    target_items = db.scalars(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code.in_([national_code_set, insurance_code_set]),
        DictMedicalCodeItem.item_code.in_(target_codes),
    )).all() if target_codes else []
    target_name = {(i.code_set_code, i.item_code): i.item_name_cn for i in target_items}

    items = []
    for local in local_items:
        extra = _mapping_row_extra(local)
        national_code = mapping_by_key.get((local.item_code, national_code_set)) or extra.get("national_clinical_code")
        insurance_code = mapping_by_key.get((local.item_code, insurance_code_set)) or extra.get("insurance_raw_code")
        items.append({
            "id": local.id,
            "category_code": category_code,
            "local_code_set": local_code_set,
            "local_code": local.item_code,
            "local_name": local.item_name_cn,
            "dict_attribute": extra.get("dict_attribute"),
            "ybhm": extra.get("jhemr_ybhm"),
            "national_code_set": national_code_set,
            "national_code": national_code,
            "national_name": target_name.get((national_code_set, national_code)) or extra.get("national_clinical_name"),
            "insurance_code_set": insurance_code_set,
            "insurance_code": insurance_code,
            "insurance_name": target_name.get((insurance_code_set, insurance_code)) or extra.get("insurance_raw_name"),
            "operation_level": extra.get("operation_level"),
            "operation_category": extra.get("operation_category"),
            "performance_level4_flag": extra.get("performance_level4_flag"),
            "performance_minimally_invasive_flag": extra.get("performance_minimally_invasive_flag"),
            "restricted_tech_flag": extra.get("restricted_tech_flag"),
            "special_disease_code": extra.get("special_disease_code"),
            "special_disease_name": extra.get("special_disease_name"),
            "low_risk_category_code": extra.get("low_risk_category_code"),
            "low_risk_disease_name": extra.get("low_risk_disease_name"),
            "infectious_disease_name": extra.get("infectious_disease_name"),
            "source_file": extra.get("source_file"),
            "source_sheet": extra.get("source_sheet"),
            "status": local.status,
        })
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/mapping-options", summary="诊断手术维护下拉值域")
def list_mapping_options(category_code: str = Query("diagnosis"), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Return values already used by maintained rows; never invent target-system values."""
    code_set = "operation_local_clinical" if category_code == "operation" else "diagnosis_local_clinical"
    rows = db.scalars(select(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code == code_set)).all()
    def values(key: str) -> list[str]:
        return sorted({str((r.extra or {}).get(key)).strip() for r in rows if (r.extra or {}).get(key) not in (None, "")})
    data = {
        "dict_attributes": sorted(set(values("dict_attribute") + ["院内扩展"])),
        "ybhm": ["灰码"],
    }
    if category_code == "operation":
        data.update({
            "operation_category": values("operation_category"),
            "operation_level": values("operation_level"),
            "performance_level4_flag": values("performance_level4_flag"),
            "performance_minimally_invasive_flag": values("performance_minimally_invasive_flag"),
            "restricted_tech_flag": values("restricted_tech_flag"),
        })
    return ApiResponse(data=data)


def _local_code_item_stmt(
    category_code: str,
    keyword: str | None,
    status: str | None,
    has_infectious: bool | None,
    minimally_invasive_flag: str | None,
    performance_level4_flag: str | None,
    restricted_tech_flag: str | None,
    operation_level: str | None,
):
    """D3：list_mapping_rows 与导出共用的本地编码项过滤构造（单份实现）。

    只负责过滤条件与 code-set 选择；分页（offset/limit）由列表端点自加，
    导出走全量，两者语义不互串。
    """
    local_code_set = _code_sets_for_category(category_code)[0]
    stmt = select(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code == local_code_set)
    if status:
        stmt = stmt.where(DictMedicalCodeItem.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            DictMedicalCodeItem.item_code.ilike(like)
            | DictMedicalCodeItem.item_name_cn.ilike(like)
        )
    if category_code == "diagnosis" and has_infectious is not None:
        infectious_expr = func.coalesce(DictMedicalCodeItem.extra.op("->>")("infectious_disease_name"), "")
        stmt = stmt.where(infectious_expr != "" if has_infectious else infectious_expr == "")
    if category_code == "operation":
        def flag_value(value: str | None) -> str | None:
            return "" if value == "__empty" else value

        if minimally_invasive_flag is not None:
            stmt = stmt.where(func.coalesce(DictMedicalCodeItem.extra.op("->>")("performance_minimally_invasive_flag"), "") == flag_value(minimally_invasive_flag))
        if performance_level4_flag is not None:
            stmt = stmt.where(func.coalesce(DictMedicalCodeItem.extra.op("->>")("performance_level4_flag"), "") == flag_value(performance_level4_flag))
        if restricted_tech_flag is not None:
            stmt = stmt.where(func.coalesce(DictMedicalCodeItem.extra.op("->>")("restricted_tech_flag"), "") == flag_value(restricted_tech_flag))
        if operation_level:
            stmt = stmt.where(func.coalesce(DictMedicalCodeItem.extra.op("->>")("operation_level"), "") == operation_level)
    return stmt


def _excel_col_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


# C6：导出行数上限与分批写 sheet 的批大小（防止无界导出打爆内存/响应体）。
EXPORT_MAX_ROWS = 50_000
_SHEET_WRITE_BATCH = 5_000


def _xlsx_bytes(headers: list[str], rows: list[list[object]], sheet_name: str) -> bytes:
    def cell_xml(row_index: int, col_index: int, value: object) -> str:
        value_text = "" if value is None else str(value)
        ref = f"{_excel_col_name(col_index)}{row_index}"
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value_text)}</t></is></c>'

    def sheet_xml_chunks():
        # C6：按批产出 sheet XML 片段，避免一次性拼全量字符串。
        yield f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:{_excel_col_name(len(headers))}{max(len(rows) + 1, 1)}"/>
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>'''
        row_index = 1
        header_cells = "".join(cell_xml(row_index, col_index, value) for col_index, value in enumerate(headers, start=1))
        yield f'<row r="{row_index}">{header_cells}</row>'
        for start in range(0, len(rows), _SHEET_WRITE_BATCH):
            batch: list[str] = []
            for offset, row in enumerate(rows[start : start + _SHEET_WRITE_BATCH]):
                row_index = start + offset + 2
                cells = "".join(cell_xml(row_index, col_index, value) for col_index, value in enumerate(row, start=1))
                batch.append(f'<row r="{row_index}">{cells}</row>')
            yield "".join(batch)
        yield "</sheetData></worksheet>"

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        with zf.open("xl/worksheets/sheet1.xml", "w") as sheet_file:
            for chunk in sheet_xml_chunks():
                sheet_file.write(chunk.encode("utf-8"))
    return buffer.getvalue()


def _mapping_rows_for_export(
    db: Session,
    category_code: str,
    keyword: str | None,
    status: str | None,
    has_infectious: bool | None,
    minimally_invasive_flag: str | None,
    performance_level4_flag: str | None,
    restricted_tech_flag: str | None,
    operation_level: str | None,
) -> list[dict]:
    local_code_set, national_code_set, insurance_code_set = _code_sets_for_category(category_code)
    stmt = _local_code_item_stmt(
        category_code, keyword, status, has_infectious,
        minimally_invasive_flag, performance_level4_flag, restricted_tech_flag, operation_level,
    )
    local_items = db.scalars(stmt.order_by(DictMedicalCodeItem.item_code)).all()
    local_codes = [r.item_code for r in local_items]
    mapping_rows = db.scalars(select(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == category_code,
        DictMedicalCodeMapping.from_code_set == local_code_set,
        DictMedicalCodeMapping.from_item_code.in_(local_codes),
    )).all() if local_codes else []
    mapping_by_key = {(m.from_item_code, m.to_code_set): m.to_item_code for m in mapping_rows}
    target_codes = [m.to_item_code for m in mapping_rows if m.to_item_code]
    target_items = db.scalars(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code.in_([national_code_set, insurance_code_set]),
        DictMedicalCodeItem.item_code.in_(target_codes),
    )).all() if target_codes else []
    target_name = {(i.code_set_code, i.item_code): i.item_name_cn for i in target_items}

    result = []
    for local in local_items:
        extra = local.extra or {}
        national_code = mapping_by_key.get((local.item_code, national_code_set)) or extra.get("national_clinical_code") or ""
        insurance_code = mapping_by_key.get((local.item_code, insurance_code_set)) or extra.get("insurance_raw_code") or ""
        result.append({
            "local_code": local.item_code,
            "local_name": local.item_name_cn,
            "dict_attribute": extra.get("dict_attribute"),
            "ybhm": extra.get("jhemr_ybhm"),
            "national_code": national_code,
            "national_name": target_name.get((national_code_set, national_code)) or extra.get("national_clinical_name") or "",
            "insurance_code": insurance_code,
            "insurance_name": target_name.get((insurance_code_set, insurance_code)) or extra.get("insurance_raw_name") or "",
            "operation_level": extra.get("operation_level"),
            "operation_category": extra.get("operation_category"),
            "performance_level4_flag": extra.get("performance_level4_flag"),
            "performance_minimally_invasive_flag": extra.get("performance_minimally_invasive_flag"),
            "restricted_tech_flag": extra.get("restricted_tech_flag"),
            "special_disease_code": extra.get("special_disease_code"),
            "special_disease_name": extra.get("special_disease_name"),
            "low_risk_category_code": extra.get("low_risk_category_code"),
            "low_risk_disease_name": extra.get("low_risk_disease_name"),
            "infectious_disease_name": extra.get("infectious_disease_name"),
            "source_file": extra.get("source_file"),
            "source_sheet": extra.get("source_sheet"),
            "status": local.status,
        })
    # C6：导出行数上限，超限截断（保护内存与响应体大小）。
    return result[:EXPORT_MAX_ROWS]


@router.get("/mapping-rows/export", summary="导出诊断/手术映射宽表 Excel")
def export_mapping_rows(
    category_code: str = Query("diagnosis", description="diagnosis/operation"),
    keyword: str | None = Query(None),
    status: str | None = Query(None, description="active/inactive"),
    has_infectious: bool | None = Query(None, description="是否传染病诊断"),
    minimally_invasive_flag: str | None = Query(None, description="绩效微创标识"),
    performance_level4_flag: str | None = Query(None, description="绩效四级标识"),
    restricted_tech_flag: str | None = Query(None, description="限制技术标识"),
    operation_level: str | None = Query(None, description="院内手术等级"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = _mapping_rows_for_export(
        db, category_code, keyword, status, has_infectious,
        minimally_invasive_flag, performance_level4_flag, restricted_tech_flag, operation_level,
    )
    if category_code == "operation":
        headers = ["字典属性", "院内临床手术编码", "院内临床手术名称", "院内手术等级", "国家临床版3.0手术编码", "国家临床版3.0手术名称", "手术类别", "绩效考核四级手术标识", "绩效考核微创手术标识", "限制类技术标识", "国家医保版2.0手术代码", "国家医保版2.0手术名称", "状态", "来源文件", "来源工作表"]
        data_rows = [[r.get("dict_attribute"), r.get("local_code"), r.get("local_name"), r.get("operation_level"), r.get("national_code"), r.get("national_name"), r.get("operation_category"), r.get("performance_level4_flag"), r.get("performance_minimally_invasive_flag"), r.get("restricted_tech_flag"), r.get("insurance_code"), r.get("insurance_name"), "停用" if r.get("status") == "inactive" else "启用", r.get("source_file"), r.get("source_sheet")] for r in rows]
        filename = "手术映射维护.xlsx"
    else:
        headers = ["字典属性", "院内临床诊断编码", "院内临床诊断名称", "JHEMR灰码", "国家临床版2.0疾病编码", "国家临床版2.0疾病名称", "国家医保版2.0疾病编码", "国家医保版2.0疾病名称", "门诊慢特病编码", "门诊慢特病名称", "ICD低风险编码类目", "ICD低风险病种名称", "传染病诊断", "状态", "来源文件", "来源工作表"]
        data_rows = [[r.get("dict_attribute"), r.get("local_code"), r.get("local_name"), r.get("ybhm"), r.get("national_code"), r.get("national_name"), r.get("insurance_code"), r.get("insurance_name"), r.get("special_disease_code"), r.get("special_disease_name"), r.get("low_risk_category_code"), r.get("low_risk_disease_name"), r.get("infectious_disease_name"), "停用" if r.get("status") == "inactive" else "启用", r.get("source_file"), r.get("source_sheet")] for r in rows]
        filename = "诊断映射维护.xlsx"

    content = _xlsx_bytes(headers, data_rows, "Sheet1")
    encoded = quote(filename)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


class MappingRowUpsert(BaseModel):
    category_code: str
    local_code: str
    local_name: str
    dict_attribute: str | None = None
    ybhm: str | None = None
    national_code: str | None = None
    national_name: str | None = None
    insurance_code: str | None = None
    insurance_name: str | None = None
    operation_level: str | None = None
    operation_category: str | None = None
    performance_level4_flag: str | None = None
    performance_minimally_invasive_flag: str | None = None
    restricted_tech_flag: str | None = None
    special_disease_code: str | None = None
    special_disease_name: str | None = None
    low_risk_category_code: str | None = None
    low_risk_disease_name: str | None = None
    infectious_disease_name: str | None = None
    status: str | None = "active"


def _code_sets_for_category(category_code: str) -> tuple[str, str, str]:
    if category_code == "operation":
        return "operation_local_clinical", "operation_national_clinical_v3", "operation_insurance_v2"
    return "diagnosis_local_clinical", "diagnosis_national_clinical_v2", "diagnosis_insurance_v2"


def _upsert_code_item(db: Session, code_set_code: str, item_code: str | None, item_name: str | None, category_code: str, extra: dict | None = None, status: str | None = None, update_name: bool = True) -> None:
    item_code = (item_code or "").strip()
    item_name = (item_name or "").strip()
    if not item_code:
        return
    item = db.scalar(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == code_set_code,
        DictMedicalCodeItem.item_code == item_code,
    ))
    if item:
        if update_name and item_name:
            item.item_name_cn = item_name
        if extra is not None:
            item.extra = extra
        if status:
            item.status = status
        else:
            item.status = item.status or "active"
    else:
        db.add(DictMedicalCodeItem(
            code_set_code=code_set_code,
            item_code=item_code,
            item_name_cn=item_name or item_code,
            category_code=category_code,
            status=status or "active",
            extra=extra,
        ))


def _replace_mapping(db: Session, category_code: str, from_code_set: str, from_code: str, to_code_set: str, to_code: str | None) -> None:
    db.execute(delete(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == category_code,
        DictMedicalCodeMapping.from_code_set == from_code_set,
        DictMedicalCodeMapping.from_item_code == from_code,
        DictMedicalCodeMapping.to_code_set == to_code_set,
    ))
    to_code = (to_code or "").strip()
    if not to_code:
        return
    db.add(DictMedicalCodeMapping(
        category_code=category_code,
        from_code_set=from_code_set,
        from_item_code=from_code,
        to_code_set=to_code_set,
        to_item_code=to_code,
        mapping_type="equivalent",
        mapping_cardinality="many_to_one",
        confidence="high",
        review_status="approved",
    ))


@router.put("/mapping-rows", summary="按院内编码新增/更新诊断手术映射宽表行", dependencies=[Depends(require_permission("dict.medical.edit"))])
def upsert_mapping_row(
    req: MappingRowUpsert,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    local_code = (req.local_code or "").strip()
    local_name = (req.local_name or "").strip()
    if not local_code or not local_name:
        raise HTTPException(status_code=400, detail="院内编码和院内名称不能为空")
    if req.category_code not in {"diagnosis", "operation"}:
        raise HTTPException(status_code=400, detail="category_code must be diagnosis or operation")
    if req.ybhm not in (None, "", "灰码"):
        raise HTTPException(status_code=400, detail="ybhm 只能为灰码或为空")

    local_code_set, national_code_set, insurance_code_set = _code_sets_for_category(req.category_code)
    extra = {
        "dict_attribute": (req.dict_attribute or "院内扩展").strip(),
        "jhemr_ybhm": req.ybhm or None,
        "national_clinical_code": req.national_code,
        "national_clinical_name": req.national_name,
        "insurance_raw_code": req.insurance_code,
        "insurance_raw_name": req.insurance_name,
        "operation_level": req.operation_level,
        "operation_category": req.operation_category,
        "performance_level4_flag": req.performance_level4_flag,
        "performance_minimally_invasive_flag": req.performance_minimally_invasive_flag,
        "restricted_tech_flag": req.restricted_tech_flag,
        "special_disease_code": req.special_disease_code,
        "special_disease_name": req.special_disease_name,
        "low_risk_category_code": req.low_risk_category_code,
        "low_risk_disease_name": req.low_risk_disease_name,
        "infectious_disease_name": req.infectious_disease_name,
        "source_file": "系统页面维护",
        "source_sheet": "编码映射维护",
    }

    _upsert_code_item(db, local_code_set, local_code, local_name, req.category_code, extra, status=req.status or "active", update_name=False)
    _upsert_code_item(db, national_code_set, req.national_code, req.national_name, req.category_code)
    _upsert_code_item(db, insurance_code_set, req.insurance_code, req.insurance_name, req.category_code)
    _replace_mapping(db, req.category_code, local_code_set, local_code, national_code_set, req.national_code)
    _replace_mapping(db, req.category_code, local_code_set, local_code, insurance_code_set, req.insurance_code)
    db.commit()
    result = {"local_code": local_code, "category_code": req.category_code}
    from ...core.config import settings as app_settings
    if (
        app_settings.dict_medical_push_enabled
        and app_settings.dict_medical_auto_approve_enabled
        and (req.status or "active") == "active"
    ):
        from ...services.dict_medical_push import approve_plan, create_push_plan

        current_user = get_current_user(request)
        plan = create_push_plan(
            db,
            category_code=req.category_code,
            target_systems=["HIS_SOURCE", "JHEMR_VASTBASE"],
            item_codes=[local_code],
            created_by=str(current_user),
            action_type="insert",
        )
        approve_plan(
            db,
            plan.id,
            approved_by="dict-auto-approver",
            note="system auto-approved after mapping-row create",
        )
        result.update({"auto_sync": "queued", "plan_id": plan.id})
    return ApiResponse(data=result)
class MappingUpsert(BaseModel):
    category_code: str
    from_code_set: str
    from_item_code: str
    to_code_set: str
    to_item_code: str
    mapping_type: str | None = "manual"
    mapping_cardinality: str | None = None
    confidence: str | None = "unknown"


@router.put("/mappings", summary="新增/更新诊断手术编码对照关系", dependencies=[Depends(require_permission("dict.medical.edit"))])
def upsert_mapping(req: MappingUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictMedicalCodeMapping).where(
        DictMedicalCodeMapping.category_code == req.category_code,
        DictMedicalCodeMapping.from_code_set == req.from_code_set,
        DictMedicalCodeMapping.from_item_code == req.from_item_code,
        DictMedicalCodeMapping.to_code_set == req.to_code_set,
        DictMedicalCodeMapping.to_item_code == req.to_item_code,
    ))
    if existing:
        existing.mapping_type = req.mapping_type
        existing.mapping_cardinality = req.mapping_cardinality
        existing.confidence = req.confidence
        existing.updated_at = datetime.now(timezone.utc)
        m = existing
    else:
        m = DictMedicalCodeMapping(
            category_code=req.category_code,
            from_code_set=req.from_code_set, from_item_code=req.from_item_code,
            to_code_set=req.to_code_set, to_item_code=req.to_item_code,
            mapping_type=req.mapping_type or "manual",
            mapping_cardinality=req.mapping_cardinality,
            confidence=req.confidence or "unknown",
        )
        db.add(m)
    db.commit()
    db.refresh(m)
    return ApiResponse(data={"id": m.id})


@router.get("/sync-diffs", summary="HIS/EMR 诊断手术字典同步差异")
def list_medical_diffs(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalSyncDiff)
    if status:
        stmt = stmt.where(DictMedicalSyncDiff.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalSyncDiff.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {"id": r.id, "category_code": r.category_code, "target_system": r.target_system,
         "diff_type": r.diff_type, "code_set_code": r.code_set_code,
         "item_code": r.item_code, "status": r.status, "severity": r.severity}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class MedicalSyncRunRequest(BaseModel):
    source_system: str
    target_system: str = "asset"
    category_code: str | None = None
    max_rows: int = 5000

class MedicalSyncDiffUpdate(BaseModel):
    status: str
    note: str | None = None

def _medical_sync_job_status(sync_status: str | None) -> str:
    if sync_status == "success":
        return "success"
    if sync_status in {"failed", "skipped"}:
        return "failed"
    return "blocked"


def _store_medical_sync_job(
    db: Session,
    *,
    req: MedicalSyncRunRequest,
    result: dict,
) -> SchedulerJob:
    now = datetime.now(timezone.utc)
    job = SchedulerJob(
        job_type="dict_medical_sync",
        source_code=req.source_system,
        trigger_mode="manual",
        status=_medical_sync_job_status(result.get("status")),
        started_at=now,
        finished_at=now,
        result_ref=json.dumps({
            "source_system": req.source_system,
            "target_system": req.target_system,
            "category_code": req.category_code,
            "entity_type": "medical_code",
            "max_rows": req.max_rows,
            "result": result,
        }, ensure_ascii=False),
        total_processed=result.get("scanned"),
        total_changes=result.get("diffs_created"),
        error_message=result.get("error") or result.get("note") if result.get("status") != "success" else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/sync/run", summary="Run diagnosis/operation dictionary sync", dependencies=[Depends(require_permission("dict.medical.execute"))])
def run_medical_sync(req: MedicalSyncRunRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    get_current_user(request)
    from ...services.medical_code_source_collector import collect_medical_code_diffs

    result = collect_medical_code_diffs(
        db,
        source_code=req.source_system,
        target_system=req.target_system,
        category_code=req.category_code,
        max_rows=req.max_rows,
    )
    job = _store_medical_sync_job(db, req=req, result=result)
    db.commit()
    return ApiResponse(data={**result, "job_id": job.id, "job_status": job.status})


@router.post("/sync/jobs/{job_id}/retry", summary="Retry diagnosis/operation dictionary sync job", dependencies=[Depends(require_permission("dict.medical.retry"))])
def retry_medical_sync_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    job = db.get(SchedulerJob, job_id)
    if not job or job.job_type != "dict_medical_sync":
        raise HTTPException(status_code=404, detail="dict medical sync job not found")
    try:
        payload = json.loads(job.result_ref or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="sync job result_ref is not valid JSON")

    req = MedicalSyncRunRequest(
        source_system=payload.get("source_system") or job.source_code or "",
        target_system=payload.get("target_system") or "asset",
        category_code=payload.get("category_code"),
        max_rows=payload.get("max_rows") or (payload.get("result") or {}).get("max_rows") or 5000,
    )
    if not req.source_system:
        raise HTTPException(status_code=400, detail="sync job is missing source_system")

    from ...services.medical_code_source_collector import collect_medical_code_diffs

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    result = collect_medical_code_diffs(
        db,
        source_code=req.source_system,
        target_system=req.target_system,
        category_code=req.category_code,
        max_rows=req.max_rows,
    )
    job.status = _medical_sync_job_status(result.get("status"))
    job.finished_at = datetime.now(timezone.utc)
    job.result_ref = json.dumps({
        "source_system": req.source_system,
        "target_system": req.target_system,
        "category_code": req.category_code,
        "entity_type": "medical_code",
        "result": result,
    }, ensure_ascii=False)
    job.total_processed = result.get("scanned")
    job.total_changes = result.get("diffs_created")
    job.error_message = result.get("error") or result.get("note") if result.get("status") != "success" else None
    db.add(GovernAuditLog(
        module="dict_medical",
        entity_type="sync_job",
        entity_ref=str(job.id),
        action="retry",
        after_data={"status": job.status, "result": result},
        operator=current_user,
    ))
    db.commit()
    return ApiResponse(data={**result, "job_id": job.id, "job_status": job.status})

@router.patch("/sync-diffs/{diff_id}", summary="Update diagnosis/operation sync diff status", dependencies=[Depends(require_permission("dict.medical.reconcile"))])
def update_medical_diff(
    diff_id: int,
    req: MedicalSyncDiffUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    if req.status not in {"open", "resolved", "ignored"}:
        raise HTTPException(status_code=400, detail="status must be open/resolved/ignored")
    diff = db.get(DictMedicalSyncDiff, diff_id)
    if not diff:
        raise HTTPException(status_code=404, detail="medical sync diff not found")

    before = {"status": diff.status, "handled_at": diff.handled_at.isoformat() if diff.handled_at else None}
    diff.status = req.status
    diff.handled_at = None if req.status == "open" else datetime.now(timezone.utc)
    db.add(GovernAuditLog(
        module="dict_medical",
        entity_type="sync_diff",
        entity_ref=str(diff.id),
        action="update_status",
        before_data=before,
        after_data={"status": diff.status, "handled_at": diff.handled_at.isoformat() if diff.handled_at else None},
        operator=current_user,
        reason=req.note,
    ))
    db.commit()
    return ApiResponse(data={
        "id": diff.id,
        "status": diff.status,
        "handled_at": diff.handled_at.isoformat() if diff.handled_at else None,
    })

class CodeSetUpsert(BaseModel):
    category_code: str
    code_set_code: str
    code_set_type: str
    code_set_name_cn: str
    standard_system: str | None = None
    version_no: str | None = None
    source_system: str | None = None
    enabled: bool = True


@router.put("/code-sets", summary="新增/更新诊断手术编码体系", dependencies=[Depends(require_permission("dict.medical.edit"))])
def upsert_code_set(req: CodeSetUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictMedicalCodeSet).where(
        DictMedicalCodeSet.code_set_code == req.code_set_code
    ))
    if existing:
        existing.category_code = req.category_code
        existing.code_set_type = req.code_set_type
        existing.code_set_name_cn = req.code_set_name_cn
        existing.standard_system = req.standard_system
        existing.version_no = req.version_no
        existing.source_system = req.source_system
        existing.enabled = req.enabled
        existing.updated_at = datetime.now(timezone.utc)
        cs = existing
    else:
        cs = DictMedicalCodeSet(
            category_code=req.category_code,
            code_set_code=req.code_set_code,
            code_set_type=req.code_set_type,
            code_set_name_cn=req.code_set_name_cn,
            standard_system=req.standard_system,
            version_no=req.version_no,
            source_system=req.source_system,
            enabled=req.enabled,
        )
        db.add(cs)
    db.commit()
    db.refresh(cs)
    return ApiResponse(data={"id": cs.id, "code_set_code": cs.code_set_code})


class CodeItemUpsert(BaseModel):
    code_set_code: str
    item_code: str
    item_name_cn: str
    item_name_alias: str | None = None
    category_code: str
    parent_code: str | None = None
    status: str | None = "active"


@router.put("/items", summary="新增/更新编码项", dependencies=[Depends(require_permission("dict.medical.edit"))])
def upsert_code_item(req: CodeItemUpsert, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == req.code_set_code,
        DictMedicalCodeItem.item_code == req.item_code,
    ))
    if existing:
        existing.item_name_cn = req.item_name_cn
        existing.item_name_alias = req.item_name_alias
        existing.category_code = req.category_code
        existing.parent_code = req.parent_code
        existing.status = req.status or "active"
        item = existing
    else:
        item = DictMedicalCodeItem(
            code_set_code=req.code_set_code,
            item_code=req.item_code,
            item_name_cn=req.item_name_cn,
            item_name_alias=req.item_name_alias,
            category_code=req.category_code,
            parent_code=req.parent_code,
            status=req.status or "active",
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data={"id": item.id, "code_set_code": item.code_set_code, "item_code": item.item_code})


class DictCRCreate(BaseModel):
    entity_type: str
    entity_ref: str | None = None
    request_type: str
    request_payload: dict | None = None


@router.post("/change-requests", summary="创建字典变更请求", dependencies=[Depends(require_permission("dict.medical.plan.create"))])
def create_dict_cr(req: DictCRCreate, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = GovernChangeRequest(
        module="dict",
        entity_type=req.entity_type,
        entity_ref=req.entity_ref,
        request_type=req.request_type,
        request_payload=req.request_payload,
        requested_by=current_user,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.get("/change-requests", summary="字典变更请求列表")
def list_dict_crs(
    approval_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(GovernChangeRequest).where(GovernChangeRequest.module == "dict")
    if approval_status:
        stmt = stmt.where(GovernChangeRequest.approval_status == approval_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(GovernChangeRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_ref": r.entity_ref,
            "request_type": r.request_type, "approval_status": r.approval_status,
            "requested_by": r.requested_by, "approved_by": r.approved_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


class ApproveBody(BaseModel):
    note: str | None = None


@router.patch("/change-requests/{cr_id}/approve", summary="审批字典变更请求", dependencies=[Depends(require_permission("dict.medical.approve"))])
def approve_dict_cr(cr_id: int, req: ApproveBody, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if cr.module != "dict":
        raise HTTPException(status_code=400, detail="非字典变更请求")
    if current_user == cr.requested_by:
        raise HTTPException(status_code=400, detail="审批人与申请人不能为同一人")
    cr.approval_status = "approved"
    cr.approved_by = current_user
    cr.note = req.note
    cr.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status})


@router.post("/change-requests/{cr_id}/execute", summary="执行字典变更请求", dependencies=[Depends(require_permission("dict.medical.execute"))])
def execute_dict_cr(cr_id: int, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    cr = db.get(GovernChangeRequest, cr_id)
    if not cr:
        raise HTTPException(status_code=404)
    if cr.approval_status != "approved":
        raise HTTPException(status_code=400, detail="仅已审批通过的请求可执行")
    cr.approval_status = "executed"
    cr.executed_by = current_user
    cr.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ApiResponse(data={"id": cr.id, "approval_status": cr.approval_status, "executed": True})


@router.get("/versions", summary="编码体系版本列表")
def list_versions(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    rows = db.scalars(
        select(DictMedicalCodeSet).order_by(DictMedicalCodeSet.category_code, DictMedicalCodeSet.code_set_code)
    ).all()
    return ApiResponse(data=[
        {
            "id": r.id, "code_set_code": r.code_set_code,
            "code_set_name_cn": r.code_set_name_cn,
            "category_code": r.category_code,
            "version_no": r.version_no,
            "source_system": r.source_system,
        }
        for r in rows
    ])


@router.get("/import-runs", summary="诊断手术导入批次日志")
def list_import_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalImportRun)
    if status:
        stmt = stmt.where(DictMedicalImportRun.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalImportRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApiResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "batch_code": r.batch_code,
                "status": r.status,
                "mode": r.mode,
                "operator": r.operator,
                "diagnosis_file_name": r.diagnosis_file_name,
                "operation_file_name": r.operation_file_name,
                "diagnosis_sha256": r.diagnosis_sha256,
                "operation_sha256": r.operation_sha256,
                "stats": r.stats,
                "error_summary": r.error_summary,
                "correlation_id": getattr(r, "correlation_id", None),
                "duration_ms": getattr(r, "duration_ms", None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ],
    })


@router.get("/import-runs/{run_id}", summary="导入批次详情")
def get_import_run(run_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    r = db.get(DictMedicalImportRun, run_id)
    if not r:
        raise HTTPException(status_code=404)
    return ApiResponse(data={
        "id": r.id,
        "batch_code": r.batch_code,
        "status": r.status,
        "mode": r.mode,
        "operator": r.operator,
        "source_dir": r.source_dir,
        "diagnosis_file_name": r.diagnosis_file_name,
        "operation_file_name": r.operation_file_name,
        "diagnosis_sha256": r.diagnosis_sha256,
        "operation_sha256": r.operation_sha256,
        "stats": r.stats,
        "error_summary": r.error_summary,
        "correlation_id": getattr(r, "correlation_id", None),
        "duration_ms": getattr(r, "duration_ms", None),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    })


@router.get("/sync-logs", summary="字典同步差异日志摘要")
def list_sync_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(DictMedicalSyncDiff)
    if status:
        stmt = stmt.where(DictMedicalSyncDiff.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DictMedicalSyncDiff.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApiResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "category_code": r.category_code,
                "target_system": r.target_system,
                "diff_type": r.diff_type,
                "code_set_code": r.code_set_code,
                "item_code": r.item_code,
                "severity": r.severity,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    })


# ---------------------------------------------------------------------------
# Plan 96: medical dict push (HIS / JHEMR) — insert + single-row stop only
# ---------------------------------------------------------------------------

class MedicalPushPlanRequest(BaseModel):
    category_code: str  # diagnosis | operation
    targets: list[str]  # HIS_SOURCE / JHEMR_VASTBASE
    item_codes: list[str] | None = None
    max_items: int = 50
    hospital_no: str | None = None
    include_jhdict: bool = True
    check_remote: bool = False
    his_source_code: str | None = None
    jhemr_source_code: str | None = None


class MedicalPushApplyOneRequest(BaseModel):
    action: dict
    mode: str = "dry_run"  # dry_run | apply
    confirmation_token: str | None = None
    his_source_code: str | None = None
    jhemr_source_code: str | None = None


class MedicalPushStopOneRequest(BaseModel):
    category_code: str
    target_system: str
    item_code: str
    item_name: str | None = None
    hospital_no: str | None = None
    target_table: str | None = None
    mode: str = "dry_run"
    confirmation_token: str | None = None
    his_source_code: str | None = None
    jhemr_source_code: str | None = None


class MedicalPushExportRequest(BaseModel):
    category_code: str
    item_codes: list[str] | None = None
    max_items: int = 100


@router.get("/push/config", summary="诊断手术下发开关与硬限制说明")
def medical_push_config(request: Request) -> ApiResponse[dict]:
    get_current_user(request)
    from ...core.config import settings as app_settings
    from ...services.medical_code_push import push_enabled, WHITELIST_TABLES

    return ApiResponse(data={
        "push_enabled": push_enabled(),
        "default_hospital_no": getattr(app_settings, "dict_medical_push_default_hospital_no", "49557032X"),
        "allowed_actions": ["insert", "stop"],
        "hard_rules": {
            "single_row_only": True,
            "no_business_field_update": True,
            "no_batch_update": True,
            "grey_insurance_ybhm": "灰码",
            "no_contrast_when_grey_or_empty": True,
        },
        "whitelist_tables": sorted(WHITELIST_TABLES),
        "note": "apply 需 APP_DICT_MEDICAL_PUSH_ENABLED=true 且 confirmation_token 匹配",
    })


@router.post("/push/export-preview", summary="从平台字典导出待下发宽表（只读）")
def medical_push_export_preview(
    req: MedicalPushExportRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    get_current_user(request)
    from ...services.medical_code_push import export_platform_preview

    return ApiResponse(data=export_platform_preview(
        db,
        category_code=req.category_code,
        item_codes=req.item_codes,
        max_items=req.max_items,
    ))


@router.post("/push/plan", summary="生成诊断/手术单行新增下发计划（默认不写业务库）", dependencies=[Depends(require_permission("dict.medical.plan.create"))])
def medical_push_plan(
    req: MedicalPushPlanRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    from ...core.config import settings as app_settings
    from ...services.medical_code_push import (
        check_exists_remote,
        plan_push_actions,
    )

    hospital_no = req.hospital_no or getattr(app_settings, "dict_medical_push_default_hospital_no", "49557032X")
    plan = plan_push_actions(
        db,
        category_code=req.category_code,
        targets=req.targets,
        item_codes=req.item_codes,
        max_items=req.max_items,
        hospital_no=hospital_no,
        include_jhdict=req.include_jhdict,
    )
    if req.check_remote:
        checked = []
        for action in plan["actions"]:
            checked.append(check_exists_remote(
                db,
                action,
                his_source_code=req.his_source_code,
                jhemr_source_code=req.jhemr_source_code,
            ))
        plan["actions"] = checked
        plan["summary"]["skip_exists"] = sum(1 for a in checked if a.get("plan_status") == "skip_exists")
        plan["summary"]["planned"] = sum(1 for a in checked if a.get("plan_status") == "planned")
        plan["check_remote"] = True

    db.add(GovernAuditLog(
        module="dict_medical_push",
        entity_type="push_plan",
        entity_ref=req.category_code,
        action="plan",
        after_data={
            "targets": req.targets,
            "item_codes": req.item_codes,
            "action_count": plan.get("action_count"),
            "summary": plan.get("summary"),
        },
        operator=current_user,
    ))
    db.commit()
    return ApiResponse(data=plan)


@router.post("/push/apply-one", summary="单条下发（101号整改：仅 dry_run，apply 已关闭）", deprecated=True, dependencies=[Depends(require_permission("dict.medical.execute"))])
def medical_push_apply_one(
    req: MedicalPushApplyOneRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """101号安全整改：此接口仅允许 dry_run。实际执行请使用 /push/plans 流程。"""
    current_user = get_current_user(request)
    from ...services.medical_code_push import apply_one_action

    forced_mode = "dry_run"
    result = apply_one_action(
        db,
        req.action,
        mode=forced_mode,
        operator=current_user,
        confirmation_token=req.confirmation_token,
        his_source_code=req.his_source_code,
        jhemr_source_code=req.jhemr_source_code,
    )
    result["_notice"] = "apply 模式已关闭（101号整改）。本接口仅返回 dry_run 预览。实际执行请使用 /push/plans 流程。"
    return ApiResponse(data=result)


@router.post("/push/stop-one", summary="单条停用（唯一允许的 UPDATE 形态）", dependencies=[Depends(require_permission("dict.medical.execute"))])
def medical_push_stop_one(
    req: MedicalPushStopOneRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    from ...core.config import settings as app_settings
    from ...services.medical_code_push import apply_one_action, build_stop_action

    hospital_no = req.hospital_no or getattr(app_settings, "dict_medical_push_default_hospital_no", "49557032X")
    action = build_stop_action(
        category_code=req.category_code,
        target_system=req.target_system,
        item_code=req.item_code,
        item_name=req.item_name or "",
        hospital_no=hospital_no if req.target_system == "JHEMR_VASTBASE" else None,
        target_table=req.target_table,
    )
    forced_mode = "dry_run"
    result = apply_one_action(
        db,
        action.to_dict(),
        mode=forced_mode,
        operator=current_user,
        confirmation_token=req.confirmation_token,
        his_source_code=req.his_source_code,
        jhemr_source_code=req.jhemr_source_code,
    )
    result["_notice"] = "apply 模式已关闭（101号整改）。本接口仅返回 dry_run 预览。"
    return ApiResponse(data=result)


