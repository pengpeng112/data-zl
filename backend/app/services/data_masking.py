"""统一脱敏服务——供 governance/quality/ops 三个模块共享"""

SENSITIVE_FIELDS = {
    "name", "patient_name", "id_card", "phone", "mobile", "tel",
    "address", "mrn", "patient_id",
    "身份证", "姓名", "电话", "地址", "mobile_phone", "id_number", "identity_card",
    "password", "credential", "token",
}


def mask_sensitive(data: dict | None) -> dict | None:
    if data is None:
        return None
    masked = {}
    for k, v in data.items():
        if isinstance(k, str) and any(f in k.lower() for f in SENSITIVE_FIELDS):
            s = str(v)
            if len(s) > 2:
                masked[k] = s[0] + "*" * (len(s) - 2) + s[-1]
            else:
                masked[k] = "**"
        elif isinstance(v, dict):
            masked[k] = mask_sensitive(v)
        elif isinstance(v, list):
            masked[k] = [mask_sensitive(item) if isinstance(item, dict) else item for item in v]
        else:
            masked[k] = v
    return masked
