"""Turn desensitized quality payloads into a hospital-LLM prompt and structured result."""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .ai_quality_result import QualityOutput, redact_concrete_pii, validate_output

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)
_SECTION = re.compile(r"[【\[]([^】\]]{1,20})[】\]]\s*")

ANALYSIS_PROMPT_HEADER = """你是医院数据资产质控助手。
只分析当前传入的问题，不要扯到未出现的表。
材料全部来自数据资产平台库的表/字段/关系登记，不是 HIS/ODS/嘉和业务库，禁止要求直连业务库。

请直接写给人看的中文说明，不要输出 JSON，不要输出大括号。
按下面五个标题写，标题必须原样使用：

【结论】
一两句话说清：这是什么问题、严不严重、要不要处理。

【问题定位】
写清系统、库/Schema、表（中文名+英文名）、字段或关系两端。引用传入的对象，不要另编表名。

【明细举例】
用传入的“缺注释字段/关系键/指标”举 3 到 8 个具体例子，说明缺什么、对使用有什么影响。
没有例子就写“平台库未登记到字段明细”。

【要不要处理】
明确写：需要处理 / 可暂缓 / 更像噪音。给出理由。

【处理建议】
给 2 到 4 条可执行步骤，每条一行，用“1.”开头，说明谁去做、改平台目录还是等业务确认。

字段名 PATIENT_ID / VISIT_ID / EXAM_NO / TEST_NO 可以原样写，这是表字段名，不是患者隐私。
不要写真实姓名、身份证号、手机号。
如果材料里有 already_split_to 或 handling_hint，结论必须写明：混合关系已经拆开，去看拆后的正式关系，不要建议按混合关系改业务数据。
"""


def build_analysis_prompt(*, task_type: str, request_id: str, input_digest: str, payload_json: str) -> str:
    return "\n".join([
        ANALYSIS_PROMPT_HEADER,
        f"任务类型：{task_type}",
        f"request_id={request_id}",
        "平台库传入的问题和字段例子：",
        payload_json,
    ])


def extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = _JSON_FENCE.sub("", (text or "").strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_cn_sections(text: str) -> dict[str, str]:
    raw = (text or "").strip()
    if not raw:
        return {}
    matches = list(_SECTION.finditer(raw))
    if not matches:
        return {"结论": raw}
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        body = raw[match.end():end].strip()
        if body:
            sections[match.group(1).strip()] = body
    return sections


def _looks_like_noise(text: str) -> bool:
    return any(token in (text or "") for token in ("噪音", "可暂缓", "可忽略", "不必处理", "目录展示"))


def _lines(text: str) -> list[str]:
    rows = []
    for line in re.split(r"[\n；;]", text or ""):
        item = re.sub(r"^[\-\*\d\.、)\s]+", "", line).strip()
        if item:
            rows.append(item)
    return rows


def _as_output_dict(raw: dict[str, Any], *, request_id: str, input_digest: str, fallback_text: str) -> dict[str, Any]:
    sections = parse_cn_sections(fallback_text)
    summary = str(
        raw.get("summary")
        or sections.get("结论")
        or fallback_text
        or "院内模型已返回分析，请人工复核。"
    ).strip()[:4000]
    if summary.lstrip().startswith("{"):
        summary = sections.get("结论") or "院内模型已返回分析，请人工复核。"
    risk = str(raw.get("risk_level") or "medium").strip().lower()
    if "严重" in summary or "必须处理" in summary:
        risk = "high"
    if any(token in summary for token in ("可暂缓", "噪音", "一般")):
        risk = "low" if risk == "medium" else risk
    if risk not in {"critical", "high", "medium", "low", "unknown"}:
        risk = "medium"
    causes = raw.get("root_causes") if isinstance(raw.get("root_causes"), list) else []
    recs = raw.get("recommendations") if isinstance(raw.get("recommendations"), list) else []
    if not causes:
        for title, key in (("问题定位", "问题定位"), ("明细举例", "明细举例")):
            if sections.get(key):
                causes.append({"title": title, "reason": sections[key], "confidence": 0.75, "evidence_finding_ids": []})
    if not recs:
        recs = [
            {
                "title": line[:300],
                "action_type": "manual_review",
                "priority": "P2",
                "reason": line[:2000],
                "confidence": 0.7,
                "target_refs": [],
            }
            for line in _lines(sections.get("处理建议") or "")[:4]
        ]
    noise = sections.get("要不要处理") or ""
    false_positive = raw.get("false_positive") if isinstance(raw.get("false_positive"), dict) else {}
    return {
        "schema_version": "quality-analysis-output/v1",
        "request_id": request_id,
        "input_digest": input_digest,
        "summary": summary or "院内模型已返回分析，请人工复核。",
        "risk_level": risk,
        "root_causes": [
            {
                "title": str(item.get("title") or "可能原因")[:300],
                "reason": str(item.get("reason") or item.get("title") or "需人工复核")[:2000],
                "confidence": min(max(float(item.get("confidence") or 0.7), 0.0), 1.0),
                "evidence_finding_ids": [
                    int(fid) for fid in (item.get("evidence_finding_ids") or [])[:20] if str(fid).isdigit()
                ],
            }
            for item in causes[:8] if isinstance(item, dict) and (item.get("title") or item.get("reason"))
        ],
        "recommendations": [
            {
                "title": str(item.get("title") or "建议人工复核")[:300],
                "action_type": item.get("action_type") if item.get("action_type") in {
                    "rule_adjustment", "data_remediation", "metadata_fix", "manual_review", "monitor",
                } else "manual_review",
                "priority": item.get("priority") if str(item.get("priority") or "") in {"P0", "P1", "P2", "P3"} else "P2",
                "reason": str(item.get("reason") or "院内模型建议，需人工确认")[:2000],
                "confidence": min(max(float(item.get("confidence") or 0.7), 0.0), 1.0),
                "target_refs": [str(ref)[:500] for ref in (item.get("target_refs") or [])[:10]],
            }
            for item in recs[:8] if isinstance(item, dict) and item.get("title")
        ],
        "false_positive": {
            "possible": bool(false_positive.get("possible")) if false_positive else _looks_like_noise(noise or summary),
            "reason": str(false_positive.get("reason") or noise or "需人工判断是否误报")[:2000],
        },
        "follow_up_checks": [
            {"description": str(item.get("description") or "")[:2000], "sql_draft": None}
            for item in (raw.get("follow_up_checks") or [])[:8]
            if isinstance(item, dict) and item.get("description")
        ],
        "limitations": [
            "未直连 HIS/ODS/嘉和业务库",
            "举例来自数据资产平台库登记的字段/关系，不是业务库抽样",
            "结论需人工复核后才能改规则或关系",
        ],
    }


def analysis_from_llm_text(text: str, *, request_id: str, input_digest: str) -> QualityOutput:
    cleaned = redact_concrete_pii(text or "")
    parsed = extract_json_object(cleaned) if cleaned.lstrip().startswith("{") else None
    payload = _as_output_dict(parsed or {}, request_id=request_id, input_digest=input_digest, fallback_text=cleaned)
    if not payload["root_causes"]:
        payload["root_causes"] = [{
            "title": "问题说明",
            "reason": (cleaned or "模型未给出结构化说明")[:2000],
            "confidence": 0.55,
            "evidence_finding_ids": [],
        }]
    if not payload["recommendations"]:
        payload["recommendations"] = [{
            "title": "在平台目录补全中文名/注释后再复核是否还要处理",
            "action_type": "metadata_fix",
            "priority": "P2",
            "reason": "先把对象看清楚，再决定要不要动业务。",
            "confidence": 0.8,
            "target_refs": [],
        }]
    payload["summary"] = redact_concrete_pii(payload["summary"])
    for item in payload["root_causes"]:
        item["reason"] = redact_concrete_pii(item["reason"])
        item["title"] = redact_concrete_pii(item["title"])
    for item in payload["recommendations"]:
        item["title"] = redact_concrete_pii(item["title"])
        item["reason"] = redact_concrete_pii(item["reason"])
    payload["false_positive"]["reason"] = redact_concrete_pii(payload["false_positive"]["reason"])
    return validate_output(payload, request_id=request_id, input_digest=input_digest)


def attach_platform_examples(db: Session, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add catalog-only column/relation examples. Never touches business DBs."""
    from ..models.asset import AssetColumn, AssetRelation, AssetTable

    enriched = []
    for item in findings:
        schema = str(item.get("schema_name") or "")
        table = str(item.get("table_name") or "")
        extra = dict(item)
        if table:
            table_row = db.scalar(
                select(AssetTable).where(
                    func.upper(AssetTable.table_name) == table.upper(),
                    or_(func.upper(func.coalesce(AssetTable.schema_name, "")) == schema.upper(), schema == ""),
                ).limit(1)
            )
            if table_row:
                extra["table_name_cn"] = table_row.table_name_cn
                extra["system_name_cn"] = extra.get("system_name_cn")
            cols = list(db.scalars(
                select(AssetColumn).where(func.upper(AssetColumn.table_name) == table.upper())
                .order_by(AssetColumn.column_id.asc().nullslast())
                .limit(80)
            ).all())
            if schema:
                scoped = [col for col in cols if str(col.schema_name or "").upper() == schema.upper()]
                if scoped:
                    cols = scoped
            missing = []
            named = []
            for col in cols:
                label = str(col.column_name_cn or col.comment or "").strip()
                pack = {
                    "column_name": col.column_name,
                    "data_type": col.data_type,
                    "column_name_cn": label or None,
                }
                if label:
                    named.append(pack)
                else:
                    missing.append(pack)
            extra["column_count"] = len(cols)
            extra["missing_comment_count"] = len(missing)
            extra["missing_comment_columns"] = missing[:12]
            extra["example_named_columns"] = named[:5]
            rels = list(db.scalars(
                select(AssetRelation).where(
                    or_(
                        AssetRelation.from_table.ilike(f"%{table}"),
                        AssetRelation.to_table.ilike(f"%{table}"),
                    )
                ).limit(8)
            ).all())
            extra["related_relations"] = [
                {
                    "from_table": rel.from_table,
                    "to_table": rel.to_table,
                    "from_columns": rel.from_columns,
                    "to_columns": rel.to_columns,
                    "validation_status": rel.validation_status,
                    "validation_metrics": (rel.validation_metrics or "")[:180],
                }
                for rel in rels
            ]
        enriched.append(extra)
    return enriched
