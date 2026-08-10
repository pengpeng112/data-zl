"""Diagnosis/operation dictionary push: plan + single-row insert/stop only.

Hard rules (plan 96 §1.0):
- INSERT one row per DML only
- STOP is the only allowed UPDATE (single key)
- No business-field UPDATE / MERGE / batch / INSERT SELECT / DELETE
- Grey insurance: diagnosis_dict.ybhm = '灰码'; no contrast row
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException
from pypinyin import Style, lazy_pinyin
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.asset_system import AssetDataSource
from ..models.dict_medical import DictMedicalCodeItem, DictMedicalCodeMapping
from ..models.governance_base import GovernAuditLog
from ..services.credentials import resolve
from ..services.data_masking import sanitize_text
from ..services.db_connectors import DB_CONNECTOR_MAP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCAL_CODE_SETS = {
    "diagnosis": "diagnosis_local_clinical",
    "operation": "operation_local_clinical",
}
NATIONAL_CODE_SETS = {
    "diagnosis": "diagnosis_national_clinical_v2",
    "operation": "operation_national_clinical_v3",
}
INSURANCE_CODE_SETS = {
    "diagnosis": "diagnosis_insurance_v2",
    "operation": "operation_insurance_v2",
}

TARGET_HIS = "HIS_SOURCE"
TARGET_JHEMR = "JHEMR_VASTBASE"
ALLOWED_TARGETS = {TARGET_HIS, TARGET_JHEMR}
TARGET_SYSTEM_ALIASES = {
    TARGET_HIS: {"HIS", "HIS_SOURCE"},
    TARGET_JHEMR: {"JHEMR", "JHEMR_VASTBASE"},
}
ACTION_INSERT = "insert"
ACTION_STOP = "stop"

OPERATION_INDICATOR_MAP = {
    "手术": "0",
    "治疗性操作": "1",
    "诊断性操作": "2",
    "介入治疗": "3",
}

WHITELIST_TABLES = {
    "COMM.DIAGNOSIS_DICT",
    "COMM.OPERATION_DICT",
    "jhemr.diagnosis_dict",
    "jhemr.jhdict_icd_vs_clinic",
    "jhemr.diagnosis_contrast_dict",
    "jhemr.operation_dict",
    "jhemr.operation_dict_code",
    "jhemr.operation_contrast_dict",
    "jhemr.jhdict_operation_vs_clinic",
}

_FORBIDDEN_SQL = re.compile(
    r"\b(?:DELETE|MERGE|UPSERT|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|"
    r"EXEC(?:UTE)?|CALL|COPY|VACUUM|ANALYZE|INSERT\s+SELECT)\b",
    re.IGNORECASE,
)
_MULTI_VALUES = re.compile(r"VALUES\s*\([^)]*\)\s*,\s*\(", re.IGNORECASE)
_IN_LIST = re.compile(r"\bIN\s*\([^)]*,[^)]*\)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PushAction:
    action_id: str
    action_type: str  # insert | stop
    category_code: str
    target_system: str
    target_table: str
    item_code: str
    item_name: str
    sql_dialect: str  # oracle | postgresql
    sql: str
    params: dict[str, Any]
    plan_status: str  # planned | skip_exists | skip_no_contrast | blocked
    reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _flag_is_yes(value: Any) -> bool:
    t = _text(value)
    return t in {"是", "1", "Y", "y", "true", "TRUE", "yes", "YES"}


def _pinyin_initials(value: Any, *, max_length: int) -> str:
    text = _text(value)
    if not text:
        return ""
    code = "".join(lazy_pinyin(text, style=Style.FIRST_LETTER, errors="default")).upper()
    return code[:max_length]


def _is_grey_insurance(insurance_code: str, insurance_name: str, mapping_status: str) -> bool:
    if mapping_status == "source_marker_not_mapping":
        return True
    if insurance_code == "灰码" or insurance_name == "灰码":
        return True
    return False


def _action_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def validate_push_sql(sql: str, *, action_type: str, target_table: str) -> str:
    """Validate a single-row medical-dict DML statement."""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("sql must not be empty")
    cleaned = " ".join(sql.strip().split())
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    if ";" in cleaned:
        raise ValueError("sql must contain exactly one statement")
    if "--" in cleaned or "/*" in cleaned:
        raise ValueError("sql comments are not allowed")
    if _FORBIDDEN_SQL.search(cleaned):
        raise ValueError("forbidden keyword in medical push sql")
    if _MULTI_VALUES.search(cleaned):
        raise ValueError("multi-row VALUES are not allowed")
    if _IN_LIST.search(cleaned):
        raise ValueError("IN-list predicates are not allowed (single-row only)")

    table_norm = target_table.strip()
    if table_norm not in WHITELIST_TABLES:
        raise ValueError(f"target table not whitelisted: {target_table}")

    if action_type == ACTION_INSERT:
        if not re.match(r"^INSERT\s+INTO\s+", cleaned, re.IGNORECASE):
            raise ValueError("insert action must be INSERT INTO")
        if not re.search(r"\bVALUES\s*\(", cleaned, re.IGNORECASE):
            raise ValueError("insert must use VALUES")
        # ensure table appears
        if target_table.split(".")[-1].lower() not in cleaned.lower():
            raise ValueError("insert table mismatch")
    elif action_type == ACTION_STOP:
        if not re.match(r"^UPDATE\s+", cleaned, re.IGNORECASE):
            raise ValueError("stop action must be UPDATE")
        upper = cleaned.upper()
        if "STOP_FLAG" not in upper and "ISSTOP" not in upper:
            raise ValueError("stop update must set STOP_FLAG or isstop only")
        # block other business columns being set (simple heuristic)
        set_part = re.search(r"\bSET\s+(.+)\s+WHERE\b", cleaned, re.IGNORECASE | re.DOTALL)
        if not set_part:
            raise ValueError("stop update must have SET ... WHERE")
        set_body = set_part.group(1)
        # allow STOP_FLAG, isstop, last_update_date only
        for token in re.findall(r"([A-Za-z_][\w]*)\s*=", set_body):
            if token.lower() not in {"stop_flag", "isstop", "last_update_date"}:
                raise ValueError(f"stop update cannot set business column: {token}")
        if not re.search(r"\bWHERE\b", cleaned, re.IGNORECASE):
            raise ValueError("stop update requires WHERE")
    else:
        raise ValueError(f"unsupported action_type: {action_type}")
    return cleaned


def push_enabled() -> bool:
    return bool(getattr(settings, "dict_medical_push_enabled", False))


def push_confirmation_ok(token: str | None) -> bool:
    expected = (getattr(settings, "dict_medical_push_confirmation_token", "") or "").strip()
    if not expected:
        return False
    return (token or "").strip() == expected


# ---------------------------------------------------------------------------
# Row builder from platform
# ---------------------------------------------------------------------------

def _load_platform_rows(
    db: Session,
    *,
    category_code: str,
    item_codes: list[str] | None,
    max_items: int,
) -> list[dict[str, Any]]:
    if category_code not in LOCAL_CODE_SETS:
        raise HTTPException(status_code=400, detail="category_code must be diagnosis/operation")
    local_set = LOCAL_CODE_SETS[category_code]
    national_set = NATIONAL_CODE_SETS[category_code]
    insurance_set = INSURANCE_CODE_SETS[category_code]

    stmt = select(DictMedicalCodeItem).where(
        DictMedicalCodeItem.code_set_code == local_set,
        DictMedicalCodeItem.status == "active",
    )
    if item_codes:
        stmt = stmt.where(DictMedicalCodeItem.item_code.in_(item_codes))
    items = db.scalars(stmt.order_by(DictMedicalCodeItem.item_code).limit(max_items)).all()
    if not items:
        return []

    codes = [i.item_code for i in items]
    mappings = db.scalars(
        select(DictMedicalCodeMapping).where(
            DictMedicalCodeMapping.category_code == category_code,
            DictMedicalCodeMapping.from_code_set == local_set,
            DictMedicalCodeMapping.from_item_code.in_(codes),
            DictMedicalCodeMapping.to_code_set.in_([national_set, insurance_set]),
        )
    ).all()
    map_by = {(m.from_item_code, m.to_code_set): m.to_item_code for m in mappings}

    target_codes = [c for c in map_by.values() if c]
    name_by: dict[tuple[str, str], str] = {}
    if target_codes:
        targets = db.scalars(
            select(DictMedicalCodeItem).where(
                DictMedicalCodeItem.code_set_code.in_([national_set, insurance_set]),
                DictMedicalCodeItem.item_code.in_(target_codes),
            )
        ).all()
        name_by = {(t.code_set_code, t.item_code): t.item_name_cn for t in targets}

    rows: list[dict[str, Any]] = []
    for item in items:
        extra = item.extra or {}
        national_code = _text(map_by.get((item.item_code, national_set)) or extra.get("national_clinical_code"))
        national_name = _text(
            name_by.get((national_set, national_code))
            or extra.get("national_clinical_name")
        )
        insurance_code = _text(
            map_by.get((item.item_code, insurance_set))
            or extra.get("insurance_raw_code")
        )
        insurance_name = _text(
            name_by.get((insurance_set, insurance_code))
            or extra.get("insurance_raw_name")
        )
        mapping_status = _text(extra.get("insurance_mapping_status"))
        requested_ybhm = _text(extra.get("jhemr_ybhm"))
        grey = requested_ybhm == "灰码" or _is_grey_insurance(insurance_code, insurance_name, mapping_status)
        write_contrast = (not grey) and bool(insurance_code) and insurance_code != "灰码"
        rows.append({
            "category_code": category_code,
            "local_code": item.item_code,
            "local_name": item.item_name_cn,
            "dict_attribute": _text(extra.get("dict_attribute")),
            "national_code": national_code,
            "national_name": national_name,
            "insurance_code": insurance_code,
            "insurance_name": insurance_name,
            "is_grey_insurance": grey,
            "ybhm_to_write": "灰码" if grey else None,
            "write_contrast": write_contrast,
            "mtb_code": _text(extra.get("special_disease_code")),
            "mtb_name": _text(extra.get("special_disease_name")),
            "icd_lr_code": _text(extra.get("low_risk_category_code")),
            "icd_lr_name": _text(extra.get("low_risk_disease_name")),
            "infectious_name": _text(extra.get("infectious_disease_name")),
            "operation_level": _text(extra.get("operation_level")),
            "operation_category": _text(extra.get("operation_category")),
            "level4_flag": _text(extra.get("performance_level4_flag")),
            "mini_flag": _text(extra.get("performance_minimally_invasive_flag")),
            "limit_flag": _text(extra.get("restricted_tech_flag")),
        })
    return rows


def _oper_indicator(category_cn: str) -> str:
    return OPERATION_INDICATOR_MAP.get(category_cn, "0")


def _merit_num(flag: str) -> int:
    return 1 if _flag_is_yes(flag) else 0


def _operation_scale(value: Any, *, jhemr: bool) -> str | None:
    raw = _text(value).replace("级", "").strip()
    if not raw:
        return None
    cn_to_num = {"一": "1", "二": "2", "三": "3", "四": "4"}
    num_to_cn = {v: k for k, v in cn_to_num.items()}
    return cn_to_num.get(raw, raw) if jhemr else num_to_cn.get(raw, raw)


# ---------------------------------------------------------------------------
# SQL builders (parameterized, single row)
# ---------------------------------------------------------------------------

def build_his_diagnosis_insert(row: dict[str, Any]) -> PushAction:
    sql = (
        "INSERT INTO COMM.DIAGNOSIS_DICT ("
        "DIAGNOSIS_CODE, DIAGNOSIS_NAME, STD_INDICATOR, APPROVED_INDICATOR, "
        "CREATE_DATE, INPUT_CODE, DIAG_INDICATOR, NM1, "
        "YB_CODE, YB_NAME, STOP_FLAG, "
        "DIAGNOSIS_CODE_GUO, DIAGNOSIS_NAME_GUO, DIAGNOSIS_TYPE, "
        "MTB_FLAG, MTB_CODE, MTB_NAME, "
        "DIAGNOSIS_CODE_MB, DIAGNOSIS_NAME_MB, "
        "DIAGNOSIS_CODE_ICD, DIAGNOSIS_NAME_ICD, "
        "DIAGNOSIS_CODE_CRB, DIAGNOSIS_NAME_CRB"
        ") VALUES ("
        ":diagnosis_code, :diagnosis_name, 1, 1, "
        "SYSDATE, :input_code, 1, '1', "
        ":yb_code, :yb_name, 0, "
        ":guo_code, :guo_name, :diagnosis_type, "
        ":mtb_flag, :mtb_code, :mtb_name, "
        ":mtb_code, :mtb_name, "
        ":icd_lr_code, :icd_lr_name, "
        ":crb_code, :crb_name"
        ")"
    )
    mtb_code = row["mtb_code"] or None
    mtb_flag = "1" if mtb_code else "0"
    crb = row["infectious_name"] or None
    params = {
        "diagnosis_code": row["local_code"],
        "diagnosis_name": row["local_name"][:140],
        "input_code": _pinyin_initials(row["local_name"], max_length=50),
        "yb_code": row["insurance_code"] or None,
        "yb_name": row["insurance_name"] or None,
        "guo_code": row["national_code"] or None,
        "guo_name": (row["national_name"] or None),
        "diagnosis_type": row["dict_attribute"] or None,
        "mtb_flag": mtb_flag,
        "mtb_code": mtb_code,
        "mtb_name": row["mtb_name"] or None,
        "icd_lr_code": row["icd_lr_code"] or None,
        "icd_lr_name": row["icd_lr_name"] or None,
        "crb_code": crb,
        "crb_name": crb,
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_HIS, "COMM.DIAGNOSIS_DICT", row["local_code"]),
        action_type=ACTION_INSERT,
        category_code="diagnosis",
        target_system=TARGET_HIS,
        target_table="COMM.DIAGNOSIS_DICT",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="oracle",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"is_grey_insurance": row["is_grey_insurance"], "yb_not_written": True},
    )


def build_his_operation_insert(row: dict[str, Any]) -> PushAction:
    sql = (
        "INSERT INTO COMM.OPERATION_DICT ("
        "OPERATION_CODE, OPERATION_NAME, OPERATION_SCALE, "
        "STD_INDICATOR, APPROVED_INDICATOR, CREATE_DATE, INPUT_CODE, "
        "OPERATION_INDICATOR, STOP_FLAG, "
        "OPERATION_CODE_GB, OPERATION_NAME_GB, YB_CODE, YB_NAME, "
        "FOUR_MERIT_STATUS, MIN_MERIT_STATUS, LIMIT_STATUS, OPERATION_TYPE"
        ") VALUES ("
        ":operation_code, :operation_name, :operation_scale, "
        ":std_indicator, :approved_indicator, SYSDATE, :input_code, "
        ":operation_indicator, 0, "
        ":gb_code, :gb_name, :yb_code, :yb_name, "
        ":four_merit, :min_merit, :limit_status, :operation_type"
        ")"
    )
    grey = row["is_grey_insurance"]
    is_extension = row["dict_attribute"] == "院内扩展"
    yb_code = None if grey else (row["insurance_code"] or row["national_code"] or None)
    yb_name = None if grey else (row["insurance_name"] or row["national_name"] or None)
    params = {
        "operation_code": row["local_code"][:16],
        "operation_name": row["local_name"][:100],
        "operation_scale": _operation_scale(row["operation_level"], jhemr=False),
        "input_code": _pinyin_initials(row["local_name"], max_length=50),
        "std_indicator": 0 if is_extension else 1,
        "approved_indicator": 0 if is_extension else 1,
        "operation_indicator": _oper_indicator(row["operation_category"]),
        # Historical COMM.OPERATION_DICT stores the active mapping in YB_*;
        # OPERATION_CODE_GB/NAME_GB are effectively unused in production.
        "gb_code": None,
        "gb_name": None,
        "yb_code": yb_code,
        "yb_name": yb_name,
        "four_merit": _merit_num(row["level4_flag"]),
        "min_merit": _merit_num(row["mini_flag"]),
        "limit_status": _merit_num(row["limit_flag"]),
        "operation_type": row["dict_attribute"] or None,
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_HIS, "COMM.OPERATION_DICT", row["local_code"]),
        action_type=ACTION_INSERT,
        category_code="operation",
        target_system=TARGET_HIS,
        target_table="COMM.OPERATION_DICT",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="oracle",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"is_grey_insurance": grey},
    )


def build_jhemr_diagnosis_dict_insert(row: dict[str, Any], hospital_no: str) -> PushAction:
    sql = (
        "INSERT INTO jhemr.diagnosis_dict ("
        "diagnosis_code, diagnosis_name, input_code, isstop, hospital_no, pym, ybhm"
        ") VALUES ("
        "%(diagnosis_code)s, %(diagnosis_name)s, %(input_code)s, 0, "
        "%(hospital_no)s, %(pym)s, %(ybhm)s"
        ")"
    )
    params = {
        # The main dictionary is keyed by the national standard code. The
        # local extension is kept in the clinic mapping and contrast rows.
        "diagnosis_code": row["national_code"] or row["local_code"],
        "diagnosis_name": row["local_name"][:300],
        "input_code": _pinyin_initials(row["local_name"], max_length=50),
        "pym": _pinyin_initials(row["local_name"], max_length=50),
        "hospital_no": hospital_no,
        "ybhm": row["ybhm_to_write"],
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_JHEMR, "jhemr.diagnosis_dict", row["local_code"], hospital_no),
        action_type=ACTION_INSERT,
        category_code="diagnosis",
        target_system=TARGET_JHEMR,
        target_table="jhemr.diagnosis_dict",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="postgresql",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"is_grey_insurance": row["is_grey_insurance"], "hospital_no": hospital_no},
    )


def build_jhemr_diagnosis_contrast_insert(row: dict[str, Any]) -> PushAction | None:
    if not row["write_contrast"]:
        return None
    sql = (
        "INSERT INTO jhemr.diagnosis_contrast_dict ("
        "classify, diagnosis_code, diagnosis_name, "
        "diagnosis_code_standard, diagnosis_name_standard"
        ") VALUES ("
        "%(classify)s, %(diagnosis_code)s, %(diagnosis_name)s, "
        "%(std_code)s, %(std_name)s"
        ")"
    )
    params = {
        "classify": "医保2.0",
        "diagnosis_code": row["local_code"],
        "diagnosis_name": row["local_name"][:200],
        "std_code": row["insurance_code"],
        "std_name": row["insurance_name"] or None,
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_JHEMR, "jhemr.diagnosis_contrast_dict", row["local_code"]),
        action_type=ACTION_INSERT,
        category_code="diagnosis",
        target_system=TARGET_JHEMR,
        target_table="jhemr.diagnosis_contrast_dict",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="postgresql",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"is_grey_insurance": False},
    )


def build_jhemr_jhdict_icd_insert(row: dict[str, Any], hospital_no: str, serial_no: int | None) -> PushAction:
    sql = (
        "INSERT INTO jhemr.jhdict_icd_vs_clinic ("
        "clinic_diagnosis_name, diagnosis_code, status, hospital_no, pym, "
        "serial_no, clinic_type, diagnosis_desc"
        ") VALUES ("
        "%(clinic_name)s, %(diagnosis_code)s, 1, %(hospital_no)s, %(pym)s, "
        "%(serial_no)s, 1, %(diagnosis_desc)s"
        ")"
    )
    params = {
        "clinic_name": row["local_name"][:200],
        "diagnosis_code": row["local_code"][:40],
        "hospital_no": hospital_no,
        "pym": _pinyin_initials(row["local_name"], max_length=50),
        "serial_no": serial_no,
        "diagnosis_desc": row["local_name"][:200],
    }
    status = "planned" if serial_no is not None else "blocked"
    reason = "" if serial_no is not None else "serial_no required before apply; only a DBA-whitelisted sequence can supply it (plan 112 A3)"
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_JHEMR, "jhemr.jhdict_icd_vs_clinic", row["local_code"], hospital_no),
        action_type=ACTION_INSERT,
        category_code="diagnosis",
        target_system=TARGET_JHEMR,
        target_table="jhemr.jhdict_icd_vs_clinic",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="postgresql",
        sql=sql,
        params=params,
        plan_status=status,
        reason=reason,
        meta={"hospital_no": hospital_no, "needs_serial_no": serial_no is None},
    )


def build_jhemr_operation_dict_insert(row: dict[str, Any], hospital_no: str) -> PushAction:
    sql = (
        "INSERT INTO jhemr.operation_dict ("
        "operation_code, operation_name, operation_scale, input_code, "
        "operation_type, isstop, hospital_no, pym, classify, "
        "sjjxssbs, wcssbs, xzlbs"
        ") VALUES ("
        "%(operation_code)s, %(operation_name)s, %(operation_scale)s, %(input_code)s, "
        "%(operation_type)s, 0, %(hospital_no)s, %(pym)s, %(classify)s, "
        "%(sjjxssbs)s, %(wcssbs)s, %(xzlbs)s"
        ")"
    )
    input_code = _pinyin_initials(row["local_name"], max_length=75).lower()
    params = {
        "operation_code": row["local_code"][:18],
        "operation_name": row["local_name"][:150],
        "operation_scale": _operation_scale(row["operation_level"], jhemr=True),
        "input_code": input_code,
        "operation_type": _oper_indicator(row["operation_category"]),
        "hospital_no": hospital_no,
        "pym": input_code,
        "classify": row["operation_category"] or "手术",
        "sjjxssbs": "是" if _flag_is_yes(row["level4_flag"]) else None,
        "wcssbs": "是" if _flag_is_yes(row["mini_flag"]) else None,
        "xzlbs": "是" if _flag_is_yes(row["limit_flag"]) else None,
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_JHEMR, "jhemr.operation_dict", row["local_code"], hospital_no),
        action_type=ACTION_INSERT,
        category_code="operation",
        target_system=TARGET_JHEMR,
        target_table="jhemr.operation_dict",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="postgresql",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"hospital_no": hospital_no, "is_grey_insurance": row["is_grey_insurance"]},
    )


def build_jhemr_operation_dict_code_insert(row: dict[str, Any], hospital_no: str) -> PushAction | None:
    if not row["national_code"]:
        return None
    sql = (
        "INSERT INTO jhemr.operation_dict_code ("
        "operation_code, operation_name, operation_scale, input_code, "
        "operation_type, isstop, hospital_no, pym, classify, "
        "sjjxssbs, wcssbs, xzlbs"
        ") VALUES ("
        "%(operation_code)s, %(operation_name)s, %(operation_scale)s, %(input_code)s, "
        "%(operation_type)s, 0, %(hospital_no)s, %(pym)s, %(classify)s, "
        "%(sjjxssbs)s, %(wcssbs)s, %(xzlbs)s"
        ")"
    )
    standard_name = row["national_name"] or row["local_name"]
    input_code = _pinyin_initials(standard_name, max_length=75).upper()
    params = {
        "operation_code": row["national_code"][:18],
        "operation_name": standard_name[:150],
        "operation_scale": _operation_scale(row["operation_level"], jhemr=True),
        "input_code": input_code,
        "operation_type": _oper_indicator(row["operation_category"]),
        "hospital_no": hospital_no,
        "pym": input_code,
        "classify": row["operation_category"] or "手术",
        "sjjxssbs": "是" if _flag_is_yes(row["level4_flag"]) else None,
        "wcssbs": "是" if _flag_is_yes(row["mini_flag"]) else None,
        "xzlbs": "是" if _flag_is_yes(row["limit_flag"]) else None,
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_JHEMR, "jhemr.operation_dict_code", row["national_code"], hospital_no),
        action_type=ACTION_INSERT,
        category_code="operation",
        target_system=TARGET_JHEMR,
        target_table="jhemr.operation_dict_code",
        item_code=row["national_code"],
        item_name=row["national_name"] or row["local_name"],
        sql_dialect="postgresql",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"hospital_no": hospital_no, "from_local_code": row["local_code"]},
    )


def build_jhemr_operation_contrast_insert(row: dict[str, Any]) -> PushAction | None:
    if not row["national_code"]:
        return None
    sql = (
        "INSERT INTO jhemr.operation_contrast_dict ("
        "classify, operation_name, operation_code, "
        "operation_name_standard, operation_code_standard"
        ") VALUES ("
        "%(classify)s, %(operation_name)s, %(operation_code)s, "
        "%(std_name)s, %(std_code)s"
        ")"
    )
    params = {
        "classify": "院内扩展" if row["dict_attribute"] == "院内扩展" else "国临版3.0",
        "operation_name": row["local_name"][:200],
        "operation_code": row["local_code"][:80],
        "std_name": row["national_name"] or None,
        "std_code": row["national_code"],
    }
    return PushAction(
        action_id=_action_id(ACTION_INSERT, TARGET_JHEMR, "jhemr.operation_contrast_dict", row["local_code"]),
        action_type=ACTION_INSERT,
        category_code="operation",
        target_system=TARGET_JHEMR,
        target_table="jhemr.operation_contrast_dict",
        item_code=row["local_code"],
        item_name=row["local_name"],
        sql_dialect="postgresql",
        sql=sql,
        params=params,
        plan_status="planned",
        meta={},
    )


def build_stop_action(
    *,
    category_code: str,
    target_system: str,
    item_code: str,
    item_name: str = "",
    hospital_no: str | None = None,
    target_table: str | None = None,
) -> PushAction:
    if target_system == TARGET_HIS:
        if category_code == "diagnosis":
            table = "COMM.DIAGNOSIS_DICT"
            sql = "UPDATE COMM.DIAGNOSIS_DICT SET STOP_FLAG = 1 WHERE DIAGNOSIS_CODE = :code AND STOP_FLAG = 0"
            params = {"code": item_code}
            dialect = "oracle"
        else:
            table = "COMM.OPERATION_DICT"
            sql = "UPDATE COMM.OPERATION_DICT SET STOP_FLAG = 1 WHERE OPERATION_CODE = :code AND STOP_FLAG = 0"
            params = {"code": item_code}
            dialect = "oracle"
    elif target_system == TARGET_JHEMR:
        if not hospital_no:
            raise HTTPException(status_code=400, detail="hospital_no is required for JHEMR stop")
        if target_table == "jhemr.operation_dict_code":
            table = "jhemr.operation_dict_code"
            col = "operation_code"
        elif category_code == "operation":
            table = "jhemr.operation_dict"
            col = "operation_code"
        else:
            table = "jhemr.diagnosis_dict"
            col = "diagnosis_code"
        sql = (
            f"UPDATE {table} SET isstop = 1, last_update_date = CURRENT_TIMESTAMP "
            f"WHERE {col} = %(code)s AND hospital_no = %(hospital_no)s AND COALESCE(isstop, 0) = 0"
        )
        # diagnosis_dict has last_update_date; operation may not - use safer stop without last_update for operation
        if table != "jhemr.diagnosis_dict":
            sql = (
                f"UPDATE {table} SET isstop = 1 "
                f"WHERE {col} = %(code)s AND hospital_no = %(hospital_no)s AND COALESCE(isstop, 0) = 0"
            )
        params = {"code": item_code, "hospital_no": hospital_no}
        dialect = "postgresql"
    else:
        raise HTTPException(status_code=400, detail=f"unsupported target_system: {target_system}")

    return PushAction(
        action_id=_action_id(ACTION_STOP, target_system, table, item_code, hospital_no or ""),
        action_type=ACTION_STOP,
        category_code=category_code,
        target_system=target_system,
        target_table=table,
        item_code=item_code,
        item_name=item_name,
        sql_dialect=dialect,
        sql=sql,
        params=params,
        plan_status="planned",
        meta={"hospital_no": hospital_no},
    )


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def plan_push_actions(
    db: Session,
    *,
    category_code: str,
    targets: list[str],
    item_codes: list[str] | None = None,
    max_items: int = 50,
    hospital_no: str = "49557032X",
    include_jhdict: bool = True,
    include_operation_vs_clinic: bool = False,
) -> dict[str, Any]:
    targets = [t for t in targets if t]
    bad = [t for t in targets if t not in ALLOWED_TARGETS]
    if bad:
        raise HTTPException(status_code=400, detail=f"unsupported targets: {bad}")
    if not targets:
        raise HTTPException(status_code=400, detail="targets required")
    max_items = max(1, min(int(max_items or 50), 200))

    rows = _load_platform_rows(db, category_code=category_code, item_codes=item_codes, max_items=max_items)
    actions: list[PushAction] = []
    skipped_grey_contrast = 0

    for row in rows:
        if not row["local_code"] or not row["local_name"]:
            continue
        if TARGET_HIS in targets:
            if category_code == "diagnosis":
                actions.append(build_his_diagnosis_insert(row))
            else:
                if len(row["local_code"]) > 16:
                    act = build_his_operation_insert(row)
                    act.plan_status = "blocked"
                    act.reason = f"OPERATION_CODE length {len(row['local_code'])} > 16"
                    actions.append(act)
                else:
                    actions.append(build_his_operation_insert(row))
        if TARGET_JHEMR in targets:
            if category_code == "diagnosis":
                actions.append(build_jhemr_diagnosis_dict_insert(row, hospital_no))
                if include_jhdict:
                    actions.append(build_jhemr_jhdict_icd_insert(row, hospital_no, serial_no=None))
                contrast = build_jhemr_diagnosis_contrast_insert(row)
                if contrast:
                    actions.append(contrast)
                elif row["is_grey_insurance"] or not row["write_contrast"]:
                    skipped_grey_contrast += 1
            else:
                actions.append(build_jhemr_operation_dict_insert(row, hospital_no))
                code_act = build_jhemr_operation_dict_code_insert(row, hospital_no)
                if code_act:
                    actions.append(code_act)
                contrast = build_jhemr_operation_contrast_insert(row)
                if contrast:
                    actions.append(contrast)
                elif row["is_grey_insurance"] or not row["write_contrast"]:
                    skipped_grey_contrast += 1

    # validate all planned sql shapes
    for act in actions:
        if act.plan_status in {"planned", "blocked"}:
            try:
                act.sql = validate_push_sql(act.sql, action_type=act.action_type, target_table=act.target_table)
            except ValueError as exc:
                act.plan_status = "blocked"
                act.reason = str(exc)

    summary = {
        "planned": sum(1 for a in actions if a.plan_status == "planned"),
        "blocked": sum(1 for a in actions if a.plan_status == "blocked"),
        "skip_exists": sum(1 for a in actions if a.plan_status == "skip_exists"),
        "skipped_grey_or_empty_contrast": skipped_grey_contrast,
    }
    return {
        "status": "success",
        "mode": "plan",
        "category_code": category_code,
        "targets": targets,
        "hospital_no": hospital_no,
        "platform_rows": len(rows),
        "action_count": len(actions),
        "summary": summary,
        "push_enabled": push_enabled(),
        "hard_rules": {
            "insert_only_plus_stop": True,
            "single_row_only": True,
            "no_business_update": True,
            "grey_ybhm": "灰码",
            "no_contrast_when_grey_or_empty": True,
        },
        "actions": [a.to_dict() for a in actions],
        "generated_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Remote existence (optional readonly) + apply
# ---------------------------------------------------------------------------

def _build_connector(source: AssetDataSource, *, write: bool = False):
    db_type = (source.db_type or "").lower()
    connector_cls = DB_CONNECTOR_MAP.get(db_type)
    if connector_cls is None:
        raise HTTPException(status_code=400, detail=f"unsupported db_type: {source.db_type}")
    ref = None
    if write:
        ref = source.write_credential_ref
        policy = (source.write_policy or "readonly").lower()
        if policy != "medical_dict_push":
            raise HTTPException(
                status_code=403,
                detail=f"source {source.source_code} write_policy={policy} does not allow medical push",
            )
        if not ref:
            raise HTTPException(
                status_code=400,
                detail=f"source {source.source_code} has no dedicated write credential",
            )
    else:
        ref = source.credential_ref
    user, password = resolve(ref)
    host = source.target_host or source.host_masked or ""
    database = source.service_name or source.database_name or ""
    return connector_cls(
        host=host,
        port=source.port or 0,
        database=database,
        user=user or "",
        password=password or "",
        connection_mode=source.connection_mode or "direct",
    )


def check_exists_remote(
    db: Session,
    action: dict[str, Any],
    *,
    his_source_code: str | None = None,
    jhemr_source_code: str | None = None,
) -> dict[str, Any]:
    """Readonly existence probe; marks skip_exists when row present and not stopped."""
    target = action["target_system"]
    table = action["target_table"]
    code = action["item_code"]
    if table == "jhemr.diagnosis_dict":
        code = (action.get("params") or {}).get("diagnosis_code") or code
    source_code = his_source_code if target == TARGET_HIS else jhemr_source_code
    if not source_code:
        return {**action, "remote_checked": False, "reason": action.get("reason") or "source_code not provided"}

    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise HTTPException(status_code=400, detail=f"source_code not found: {source_code}")

    connector = _build_connector(source, write=False)
    try:
        if target == TARGET_HIS:
            if table == "COMM.DIAGNOSIS_DICT":
                sql = (
                    "SELECT DIAGNOSIS_CODE AS CODE, STOP_FLAG AS STOPPED "
                    "FROM COMM.DIAGNOSIS_DICT WHERE DIAGNOSIS_CODE = :code AND ROWNUM <= 5"
                )
            else:
                sql = (
                    "SELECT OPERATION_CODE AS CODE, STOP_FLAG AS STOPPED "
                    "FROM COMM.OPERATION_DICT WHERE OPERATION_CODE = :code AND ROWNUM <= 5"
                )
            rows = connector.execute_readonly(sql, params={"code": code}, max_rows=5)
        else:
            hospital_no = (action.get("params") or {}).get("hospital_no") or (action.get("meta") or {}).get("hospital_no")
            if table == "jhemr.diagnosis_dict":
                sql = (
                    "SELECT diagnosis_code AS code, isstop AS stopped "
                    "FROM jhemr.diagnosis_dict WHERE diagnosis_code = %(code)s "
                    "AND hospital_no = %(hospital_no)s LIMIT 5"
                )
            elif table == "jhemr.operation_dict":
                sql = (
                    "SELECT operation_code AS code, isstop AS stopped "
                    "FROM jhemr.operation_dict WHERE operation_code = %(code)s "
                    "AND hospital_no = %(hospital_no)s LIMIT 5"
                )
            elif table == "jhemr.operation_dict_code":
                sql = (
                    "SELECT operation_code AS code, isstop AS stopped "
                    "FROM jhemr.operation_dict_code WHERE operation_code = %(code)s LIMIT 5"
                )
            elif table == "jhemr.diagnosis_contrast_dict":
                sql = (
                    "SELECT diagnosis_code AS code, 0 AS stopped "
                    "FROM jhemr.diagnosis_contrast_dict WHERE diagnosis_code = %(code)s LIMIT 5"
                )
            elif table == "jhemr.operation_contrast_dict":
                sql = (
                    "SELECT operation_code AS code, 0 AS stopped "
                    "FROM jhemr.operation_contrast_dict WHERE operation_code = %(code)s LIMIT 5"
                )
            elif table == "jhemr.jhdict_icd_vs_clinic":
                sql = (
                    "SELECT diagnosis_code AS code, 0 AS stopped "
                    "FROM jhemr.jhdict_icd_vs_clinic WHERE diagnosis_code = %(code)s "
                    "AND hospital_no = %(hospital_no)s LIMIT 5"
                )
            else:
                return {**action, "remote_checked": False, "reason": f"no probe sql for {table}"}
            rows = connector.execute_readonly(
                sql, params={"code": code, "hospital_no": hospital_no}, max_rows=5
            )
    finally:
        connector.close()

    out = {**action, "remote_checked": True, "remote_rows": len(rows)}
    if rows and action.get("action_type") == ACTION_INSERT:
        stopped_values: list[int] = []
        for r in rows:
            stopped = r.get("STOPPED") if "STOPPED" in r else r.get("stopped")
            try:
                stopped_values.append(int(stopped) if stopped is not None else 0)
            except (TypeError, ValueError):
                stopped_values.append(0)
        active_rows = [s for s in stopped_values if s == 0]

        if len(rows) > 1:
            # 多行同键 = 冲突，绝不自动跳过或写入；由人工裁决。
            distinct_states = len(set(stopped_values))
            out["plan_status"] = "conflict"
            out["reason"] = (
                f"target has {len(rows)} rows for the same key "
                f"({distinct_states} distinct stop states); manual review required"
            )
            out["remote_conflict"] = {"rows": len(rows), "distinct_stop_states": distinct_states}
        elif active_rows:
            out["plan_status"] = "skip_exists"
            out["reason"] = "target row already exists and is active"
    return out


# Sequence identifier must be server-side config only. Reject anything that is
# not a plain schema.object token so it cannot become SQL injection.
_SEQUENCE_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$"
)


def validate_sequence_identifier(sequence_name: str) -> str:
    """Return a validated sequence identifier or raise.

    Only simple identifiers (optional schema.object) are allowed. No quotes,
    spaces, semicolons, comments, or function calls.
    """
    name = (sequence_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="sequence name is empty")
    if len(name) > 128:
        raise HTTPException(status_code=400, detail="sequence name is too long")
    if not _SEQUENCE_IDENTIFIER_RE.fullmatch(name):
        raise HTTPException(
            status_code=400,
            detail="sequence name must be a simple identifier (schema.object); rejected unsafe value",
        )
    return name


def _resolve_serial_from_whitelisted_sequence(conn: Any, dialect: str, sequence_name: str) -> int:
    """Fetch the next value from a DBA-whitelisted sequence.

    Never uses MAX(serial_no)+1 (plan 112 A3): JHEMR serial_no has no
    associated sequence, so any allowed source must be an explicit,
    operator-confirmed sequence name.
    """
    sequence_name = validate_sequence_identifier(sequence_name)
    if dialect == "oracle":
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT {sequence_name}.NEXTVAL FROM DUAL")
            row = cur.fetchone()
            return int(row[0])
        finally:
            cur.close()
    if dialect == "postgresql":
        with conn.cursor() as cur:
            # Identifier already validated; quote as a single literal for nextval text arg.
            cur.execute("SELECT nextval(%s)", (sequence_name,))
            row = cur.fetchone()
            return int(row[0])
    raise HTTPException(status_code=400, detail=f"unsupported dialect for sequence: {dialect}")


def _whitelisted_serial_sequence() -> str | None:
    """Return the DBA-whitelisted sequence for jhdict_icd_vs_clinic, if set."""
    raw = (settings.jhemr_serial_whitelisted_sequence or "").strip()
    if not raw:
        return None
    return validate_sequence_identifier(raw)


def _resolve_serial_from_locked_max(conn: Any, dialect: str) -> int:
    """Allocate max(serial_no)+1 while holding a target-table transaction lock.

    This strategy is opt-in for the deployment where the operator confirmed
    this platform is the sole writer. The lock still protects against two
    platform workers allocating the same value. Commit/rollback is owned by
    the caller, so allocation and insert remain one transaction.
    """
    if dialect != "postgresql":
        raise HTTPException(status_code=400, detail="locked max+1 is supported only for JHEMR/Vastbase")
    with conn.cursor() as cur:
        cur.execute("LOCK TABLE jhemr.jhdict_icd_vs_clinic IN EXCLUSIVE MODE")
        cur.execute(
            "SELECT COALESCE(MAX(serial_no), 0) + 1 "
            "FROM jhemr.jhdict_icd_vs_clinic"
        )
        row = cur.fetchone()
    if not row or row[0] is None:
        raise HTTPException(status_code=500, detail="failed to allocate JHEMR serial_no")
    return int(row[0])


def _open_write_connection(source: AssetDataSource):
    """Open ONE write connection to the target; caller owns commit/rollback/close.

    Returns (conn, dialect). Shared by single-action and same-target
    multi-action transaction paths so a per-target run uses one connection.
    """
    db_type = (source.db_type or "").lower()
    if (source.write_policy or "readonly").lower() != "medical_dict_push":
        raise HTTPException(
            status_code=403,
            detail=f"source {source.source_code} is not approved for medical dictionary push",
        )
    ref = source.write_credential_ref
    if not ref:
        raise HTTPException(status_code=400, detail="dedicated write credentials not configured")
    user, password = resolve(ref)
    host = source.target_host or source.host_masked or ""
    port = source.port or 0
    database = source.service_name or source.database_name or ""
    if not user or not password:
        raise HTTPException(status_code=400, detail="write credentials not configured")

    if db_type == "oracle":
        import oracledb
        # HIS is Oracle 11g and requires python-oracledb thick mode, exactly as
        # the established read-only connector does. Thin mode fails before
        # credentials/permissions can be evaluated (DPY-3010 on old servers).
        oracle_lib = os.environ.get("APP_ORACLE_CLIENT_LIB_DIR") or (
            "/opt/oracle" if os.path.isdir("/opt/oracle") else "/opt/oracle/instantclient_21"
        )
        try:
            oracledb.init_oracle_client(lib_dir=oracle_lib)
        except Exception:
            pass  # Already initialized in this process.
        params = oracledb.ConnectParams(
            host=host,
            port=port,
            service_name=database,
            tcp_connect_timeout=15,
            retry_count=0,
        )
        conn = oracledb.connect(user=user, password=password, params=params)
        conn.call_timeout = 60_000
        return conn, "oracle"

    if db_type in {"postgresql", "vastbase"}:
        import psycopg
        conn = psycopg.connect(
            host=host, port=port, dbname=database, user=user, password=password,
        )
        return conn, "postgresql"

    raise HTTPException(status_code=400, detail=f"unsupported write db_type: {db_type}")


def _run_write_on_conn(conn: Any, dialect: str, sql: str, params: dict[str, Any]) -> int:
    """Execute one validated DML on an existing connection (no commit)."""
    if dialect == "oracle":
        cur = conn.cursor()
        try:
            cur.execute(sql, params or {})
            rowcount = cur.rowcount if cur.rowcount is not None else 0
        finally:
            cur.close()
        return int(rowcount)

    if dialect == "postgresql":
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            rowcount = cur.rowcount if cur.rowcount is not None else 0
        return int(rowcount)

    raise HTTPException(status_code=400, detail=f"unsupported write dialect: {dialect}")


def _run_select_on_conn(
    conn: Any,
    dialect: str,
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run a parameterised SELECT on an open write connection (same transaction)."""
    if dialect == "oracle":
        cur = conn.cursor()
        try:
            cur.execute(sql, params or {})
            colnames = [d[0].lower() if d and d[0] else f"c{i}" for i, d in enumerate(cur.description or [])]
            rows = cur.fetchall() or []
            return [{colnames[i]: row[i] for i in range(len(colnames))} for row in rows]
        finally:
            cur.close()
    if dialect == "postgresql":
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            colnames = [d[0].lower() if d and d[0] else f"c{i}" for i, d in enumerate(cur.description or [])]
            rows = cur.fetchall() or []
            return [{colnames[i]: row[i] for i in range(len(colnames))} for row in rows]
    raise HTTPException(status_code=400, detail=f"unsupported readback dialect: {dialect}")


def build_readback_select(
    target_table: str,
    *,
    dialect: str,
    action_type: str,
) -> tuple[str, dict[str, Any]] | None:
    """Build same-connection readback SQL for a whitelist table.

    Returns (sql, base_params_template_keys) or None if table is unknown.
    Caller supplies code/hospital_no from the action params.
    """
    table = (target_table or "").strip()
    if table not in WHITELIST_TABLES:
        return None

    # Dialect-specific bind style for the open write connection.
    if dialect == "oracle":
        code_ph = ":code"
        hosp_ph = ":hospital_no"
        limit_clause = " AND ROWNUM <= 5"
    elif dialect == "postgresql":
        code_ph = "%(code)s"
        hosp_ph = "%(hospital_no)s"
        classify_ph = "%(classify)s"
        limit_clause = " LIMIT 5"
    else:
        return None

    if table == "COMM.DIAGNOSIS_DICT":
        sql = (
            f"SELECT DIAGNOSIS_CODE AS code, STOP_FLAG AS stopped "
            f"FROM COMM.DIAGNOSIS_DICT WHERE DIAGNOSIS_CODE = {code_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": False}
    if table == "COMM.OPERATION_DICT":
        sql = (
            f"SELECT OPERATION_CODE AS code, STOP_FLAG AS stopped "
            f"FROM COMM.OPERATION_DICT WHERE OPERATION_CODE = {code_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": False}
    if table == "jhemr.diagnosis_dict":
        sql = (
            f"SELECT diagnosis_code AS code, isstop AS stopped "
            f"FROM jhemr.diagnosis_dict WHERE diagnosis_code = {code_ph} "
            f"AND hospital_no = {hosp_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": True}
    if table == "jhemr.operation_dict":
        sql = (
            f"SELECT operation_code AS code, isstop AS stopped "
            f"FROM jhemr.operation_dict WHERE operation_code = {code_ph} "
            f"AND hospital_no = {hosp_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": True}
    if table == "jhemr.operation_dict_code":
        sql = (
            f"SELECT operation_code AS code, isstop AS stopped "
            f"FROM jhemr.operation_dict_code WHERE operation_code = {code_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": False}
    if table == "jhemr.diagnosis_contrast_dict":
        sql = (
            f"SELECT diagnosis_code AS code, 0 AS stopped "
            f"FROM jhemr.diagnosis_contrast_dict WHERE diagnosis_code = {code_ph} "
            f"AND classify = {classify_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": False, "needs_classify": True}
    if table == "jhemr.operation_contrast_dict":
        sql = (
            f"SELECT operation_code AS code, 0 AS stopped "
            f"FROM jhemr.operation_contrast_dict WHERE operation_code = {code_ph} "
            f"AND classify = {classify_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": False, "needs_classify": True}
    if table == "jhemr.jhdict_icd_vs_clinic":
        sql = (
            f"SELECT diagnosis_code AS code, 0 AS stopped "
            f"FROM jhemr.jhdict_icd_vs_clinic WHERE diagnosis_code = {code_ph} "
            f"AND hospital_no = {hosp_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": True}
    if table == "jhemr.jhdict_operation_vs_clinic":
        sql = (
            f"SELECT operation_code AS code, 0 AS stopped "
            f"FROM jhemr.jhdict_operation_vs_clinic WHERE operation_code = {code_ph} "
            f"AND hospital_no = {hosp_ph}{limit_clause}"
        )
        return sql, {"needs_hospital": True}
    # action_type reserved for future stop-vs-insert SQL differences
    _ = action_type
    return None


def readback_actions_on_conn(
    conn: Any,
    dialect: str,
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Same-connection post-write readback before commit (112 A3).

    For every action: row must exist; multi-row same key is conflict.
    insert expects an active (stopped=0) row when stop column is present.
    stop expects a stopped=1 row.
    Failure raises HTTPException so the caller can rollback the whole target package.
    """
    details: list[dict[str, Any]] = []
    for act in actions:
        table = act.get("target_table") or ""
        code = act.get("item_code") or (act.get("params") or {}).get("code")
        if table == "jhemr.diagnosis_dict":
            code = (act.get("params") or {}).get("diagnosis_code") or code
        action_type = (act.get("action_type") or ACTION_INSERT).lower()
        params = dict(act.get("params") or {})
        built = build_readback_select(table, dialect=dialect, action_type=action_type)
        if built is None:
            raise HTTPException(
                status_code=409,
                detail=f"readback unavailable for table {table}; refusing to mark success",
            )
        sql, meta = built
        if not code:
            raise HTTPException(status_code=409, detail="readback missing item_code")
        bind: dict[str, Any] = {"code": code}
        if meta.get("needs_hospital"):
            hospital_no = params.get("hospital_no") or (act.get("meta") or {}).get("hospital_no")
            if not hospital_no:
                raise HTTPException(
                    status_code=409,
                    detail=f"readback for {table} requires hospital_no",
                )
            bind["hospital_no"] = hospital_no
        if meta.get("needs_classify"):
            classify = params.get("classify")
            if not classify:
                raise HTTPException(
                    status_code=409,
                    detail=f"readback for {table} requires classify",
                )
            bind["classify"] = classify
        try:
            rows = _run_select_on_conn(conn, dialect, sql, bind)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"readback query failed for {table}: {type(exc).__name__}",
            ) from exc
        if not rows:
            raise HTTPException(
                status_code=409,
                detail=f"readback found 0 rows for {table}/{code}; refusing success",
            )
        if len(rows) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"readback found {len(rows)} rows for {table}/{code}; conflict",
            )
        stopped_raw = rows[0].get("stopped")
        try:
            stopped = int(stopped_raw) if stopped_raw is not None else 0
        except (TypeError, ValueError):
            stopped = 0
        if action_type == ACTION_STOP:
            if stopped != 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"readback stop not confirmed for {table}/{code} (stopped={stopped})",
                )
        elif action_type == ACTION_INSERT and table not in {
            "jhemr.diagnosis_contrast_dict",
            "jhemr.operation_contrast_dict",
            "jhemr.jhdict_icd_vs_clinic",
            "jhemr.jhdict_operation_vs_clinic",
        }:
            # Contrast / mapping tables may not carry stop flag; main dict rows must be active.
            if stopped != 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"readback insert not active for {table}/{code} (stopped={stopped})",
                )
        details.append(
            {
                "target_table": table,
                "item_code": code,
                "action_type": action_type,
                "rows": len(rows),
                "stopped": stopped,
            }
        )
    return {"ok": True, "checked": len(details), "details": details}


def _execute_write_sql(source: AssetDataSource, dialect: str, sql: str, params: dict[str, Any]) -> int:
    """Execute one validated DML using write credentials (no READ ONLY).

    Policy/credential checks are handled inside _open_write_connection.
    """
    conn, resolved_dialect = _open_write_connection(source)
    try:
        rowcount = _run_write_on_conn(conn, resolved_dialect, sql, params)
        conn.commit()
        return int(rowcount)
    finally:
        conn.close()


def apply_one_action(
    db: Session,
    action: dict[str, Any],
    *,
    mode: str = "dry_run",
    operator: str | None = None,
    confirmation_token: str | None = None,
    his_source_code: str | None = None,
    jhemr_source_code: str | None = None,
    writer: Callable[[AssetDataSource, str, str, dict[str, Any]], int] | None = None,
) -> dict[str, Any]:
    """Apply exactly one action. mode=dry_run never writes; apply needs gates."""
    action_type = action.get("action_type")
    target_table = action.get("target_table") or ""
    sql = action.get("sql") or ""
    params = action.get("params") or {}
    dialect = action.get("sql_dialect") or ""

    try:
        sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
    except ValueError as exc:
        # 客户端只见脱敏类别消息，避免 SQL/参数原文外泄。
        raise HTTPException(
            status_code=400,
            detail=sanitize_text(f"invalid_push_sql:{type(exc).__name__}"),
        ) from exc

    if action.get("plan_status") == "skip_exists":
        return {
            "status": "skipped",
            "mode": mode,
            "reason": "skip_exists",
            "action": action,
        }
    if action.get("plan_status") == "blocked":
        return {
            "status": "blocked",
            "mode": mode,
            "reason": action.get("reason") or "blocked",
            "action": action,
        }

    # grey contrast must never apply insert to contrast tables
    if (
        action_type == ACTION_INSERT
        and target_table in {"jhemr.diagnosis_contrast_dict", "jhemr.operation_contrast_dict"}
        and (action.get("meta") or {}).get("is_grey_insurance")
    ):
        return {
            "status": "skipped",
            "mode": mode,
            "reason": "grey insurance has no contrast",
            "action": action,
        }

    result: dict[str, Any] = {
        "status": "success",
        "mode": mode,
        "action_id": action.get("action_id"),
        "action_type": action_type,
        "target_system": action.get("target_system"),
        "target_table": target_table,
        "item_code": action.get("item_code"),
        "sql": sql,
        "params": params,
        "executed": False,
        "rowcount": 0,
    }

    if mode == "dry_run":
        result["note"] = "dry_run only; no business DB write"
        db.add(GovernAuditLog(
            module="dict_medical_push",
            entity_type="push_action",
            entity_ref=str(action.get("action_id")),
            action="dry_run",
            after_data={"action": action, "result": result},
            operator=operator,
        ))
        db.commit()
        return result

    if mode != "apply":
        raise HTTPException(status_code=400, detail="mode must be dry_run or apply")

    if not push_enabled():
        raise HTTPException(
            status_code=403,
            detail="dict medical push is disabled (APP_DICT_MEDICAL_PUSH_ENABLED=false)",
        )
    if not push_confirmation_ok(confirmation_token):
        raise HTTPException(
            status_code=403,
            detail="invalid or missing confirmation_token for medical push apply",
        )

    target = action.get("target_system")
    source_code = his_source_code if target == TARGET_HIS else jhemr_source_code
    if not source_code:
        raise HTTPException(status_code=400, detail="source_code required for apply")
    source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == source_code))
    if source is None:
        raise HTTPException(status_code=400, detail=f"source_code not found: {source_code}")
    allowed_system_codes = TARGET_SYSTEM_ALIASES.get(str(target or "").upper(), {str(target or "").upper()})
    if (source.system_code or "").upper() not in allowed_system_codes:
        raise HTTPException(
            status_code=400,
            detail=f"source {source_code} does not belong to target system {target}",
        )
    if (source.write_policy or "readonly").lower() != "medical_dict_push":
        raise HTTPException(
            status_code=403,
            detail=f"source {source_code} is not approved for medical dictionary push",
        )
    if not source.write_credential_ref:
        raise HTTPException(
            status_code=400,
            detail=f"source {source_code} has no dedicated write credential",
        )

    # fill serial_no if needed (plan 112 A3: whitelisted sequence only, never MAX+1)
    if (
        target_table == "jhemr.jhdict_icd_vs_clinic"
        and params.get("serial_no") is None
    ):
        sequence_name = _whitelisted_serial_sequence()
        if not sequence_name:
            raise HTTPException(
                status_code=400,
                detail="jhemr.jhdict_icd_vs_clinic needs serial_no but no DBA-whitelisted sequence is configured",
            )
        conn, dialect = _open_write_connection(source)
        try:
            next_serial = _resolve_serial_from_whitelisted_sequence(conn, dialect, sequence_name)
            params = {**params, "serial_no": next_serial}
            sql = validate_push_sql(sql, action_type=action_type, target_table=target_table)
        finally:
            conn.close()

    write_fn = writer or _execute_write_sql
    try:
        rowcount = write_fn(source, dialect, sql, params)
    except HTTPException:
        raise
    except Exception as exc:
        # never leak credentials
        raise HTTPException(status_code=500, detail=f"push apply failed: {type(exc).__name__}") from exc

    result["executed"] = True
    result["rowcount"] = rowcount
    result["params"] = params
    db.add(GovernAuditLog(
        module="dict_medical_push",
        entity_type="push_action",
        entity_ref=str(action.get("action_id")),
        action="apply",
        after_data={"action": {**action, "params": params}, "result": result},
        operator=operator,
    ))
    db.commit()
    return result


def export_platform_preview(
    db: Session,
    *,
    category_code: str,
    item_codes: list[str] | None = None,
    max_items: int = 100,
) -> dict[str, Any]:
    rows = _load_platform_rows(db, category_code=category_code, item_codes=item_codes, max_items=max_items)
    return {
        "status": "success",
        "category_code": category_code,
        "total": len(rows),
        "items": rows,
    }
