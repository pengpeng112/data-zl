"""HIS 科室字典口径：COMM.DEPT_DICT.OUTP_OR_INP 有正式说明。"""

DEPT_TYPE_LABELS = {
    "0": "门诊",
    "1": "住院",
    "2": "门诊住院",
    "3": "医技",
    "9": "其他",
}

DEPT_STATUS_LABELS = {
    "active": "启用",
    "inactive": "停用",
    "stopped": "停用",
    "disabled": "停用",
}

DEPT_REVIEW_LABELS = {
    "unreviewed": "未复核",
    "reviewed": "已复核",
    "confirmed": "已确认",
}


def dept_type_label(value: str | None) -> str:
    raw = str(value or "").strip()
    return DEPT_TYPE_LABELS.get(raw, raw or "-")


def dept_status_label(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return DEPT_STATUS_LABELS.get(raw, raw or "-")


def infer_parent_dept_code(dept_code: str | None) -> str | None:
    code = str(dept_code or "").strip()
    if len(code) <= 2:
        return None
    if len(code) % 2 == 0:
        return code[:-2] or None
    return code[:-1] or None


def dept_review_label(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return DEPT_REVIEW_LABELS.get(raw, raw or "-")
