from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated, Any

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


class RootCause(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    evidence_finding_ids: list[int] = Field(default_factory=list, max_length=50)


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    action_type: str = Field(pattern=r"^(rule_adjustment|data_remediation|metadata_fix|manual_review|monitor)$")
    priority: str = Field(pattern=r"^P[0-3]$")
    reason: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    target_refs: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=50)


class FalsePositive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    possible: bool
    reason: str = Field(default="", max_length=2000)


class FollowUpCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=2000)
    sql_draft: None = None


class QualityOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["quality-analysis-output/v1"]
    request_id: str = Field(min_length=1, max_length=100)
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: str = Field(min_length=1, max_length=4000)
    risk_level: str = Field(pattern=r"^(critical|high|medium|low|unknown)$")
    root_causes: list[RootCause] = Field(max_length=20)
    recommendations: list[Recommendation] = Field(max_length=50)
    false_positive: FalsePositive
    follow_up_checks: list[FollowUpCheck] = Field(max_length=50)
    limitations: list[Annotated[str, Field(max_length=2000)]] = Field(max_length=50)


# Domain words such as 患者/病历/住院号 are field names in this hospital
# catalog. Only block secrets and concrete PII values.
SENSITIVE = re.compile(
    r"("
    r"password\s*[:=]|token\s*[:=]|cookie\s*[:=]|api[_-]?key|credential\s*[:=]|"
    r"\b\d{17}[\dXx]\b|"
    r"(?<!\d)1[3-9]\d{9}(?!\d)|"
    r"(身份证号?|手机号)\s*[:：=]\s*\S+"
    r")",
    re.I,
)


def redact_concrete_pii(value: str) -> str:
    text = value or ""
    text = re.sub(r"\b\d{17}[\dXx]\b", "[REDACTED]", text)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[REDACTED]", text)
    text = re.sub(r"((?:身份证号?|手机号)\s*[:：=]\s*)\S+", r"\1[REDACTED]", text, flags=re.I)
    return text


def validate_output(raw: Any, *, request_id: str, input_digest: str) -> QualityOutput:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict) and isinstance(raw.get("result"), str):
        raw = json.loads(raw["result"])
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    if isinstance(raw, dict) and isinstance(raw.get("outputs"), dict):
        raw = raw["outputs"]
    if isinstance(raw, dict) and isinstance(raw.get("outputs"), str):
        raw = json.loads(raw["outputs"])
    result = QualityOutput.model_validate(raw)
    if result.request_id != request_id or result.input_digest != input_digest:
        raise ValueError("Dify output correlation mismatch")
    if SENSITIVE.search(result.model_dump_json()):
        raise ValueError("Dify output contains sensitive content")
    return result


def output_digest(result: QualityOutput) -> str:
    return hashlib.sha256(result.model_dump_json(exclude_none=True, by_alias=True).encode()).hexdigest()


def safe_plain_text(value: str, limit: int = 4000) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value or "")[:limit]
