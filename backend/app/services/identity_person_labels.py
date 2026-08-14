"""Personnel display labels for identity pages."""

EMPLOYMENT_LABELS = {
    "active": "在职",
    "inactive": "停用",
    "retired": "离职",
    "unknown": "未标注",
}

PERSON_TYPE_LABELS = {
    "formal": "正式",
    "temporary": "临时",
    "doctor": "医生",
    "nurse": "护士",
    "technician": "技师",
    "admin": "行政",
    "other": "其他",
}

CLASSIFICATION_LABELS = {
    "doctor": "医生",
    "nurse": "护士",
    "pharmacist": "药师",
    "excluded_outsource": "外包排除",
    "excluded_management": "管理排除",
    "classification_conflict": "分类冲突",
    "status_conflict": "状态冲突",
    "legacy_unmanaged": "历史未纳管",
    "master_data_missing": "主数据缺失",
}


def employment_label(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return EMPLOYMENT_LABELS.get(raw, raw or "未标注")


def person_type_label(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return PERSON_TYPE_LABELS.get(raw, raw or "-")


def classification_label(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return CLASSIFICATION_LABELS.get(raw, raw or "-")
