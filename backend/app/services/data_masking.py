"""统一脱敏服务——供 governance/quality/ops 三个模块共享"""

import re

SENSITIVE_FIELDS = {
    "name", "patient_name", "id_card", "phone", "mobile", "tel",
    "address", "mrn", "patient_id",
    "身份证", "姓名", "电话", "地址", "mobile_phone", "id_number", "identity_card",
    "password", "credential", "token",
}

# 111 S6 / 123 R3：从异常消息中剥离连接串、密码、带参 URL、SQL 参数等敏感片段。
_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)://[^\s/@:]+:[^\s/@:]+@"),   # user:pass@host 连接串
    re.compile(r"(?i)(?:authorization|auth|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(dsn|connect.?string|jdbc:oracle|postgresql://|mysql://|sqlserver://)[^\s;,)]+"),
    re.compile(r"(?i)\b(ak|sk|access_key|private_key)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(params?|bind)\s*[:=]\s*\{[^}]{0,400}\}"),
    # 长 hex / base64 片段（签名内容、密钥材料）折叠
    re.compile(r"\b[A-Za-z0-9+/_-]{48,}={0,2}\b"),
)


def sanitize_text(text: str, limit: int = 200) -> str:
    """对异常/日志文本做脱敏，返回长度受限的通用原文片段；无法安全保留时回退占位。"""
    if not text:
        return ""
    cleaned = text
    for pat in _SECRET_PATTERNS:
        cleaned = pat.sub("[REDACTED]", cleaned)
    # 折叠换行/空白，避免日志注入
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[:limit] + "..."
    return cleaned


def api_error_message(exc: Exception, *, fallback: str = "操作失败，请稍后重试") -> str:
    """API 面向用户的统一错误消息：绝不回显 str(exc)。

    只返回通用 fallback。如需区分错误类别，可依据异常类型单独映射后再用
    mask_text 处理；这里默认一律通用，最安全。
    """
    return fallback


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
