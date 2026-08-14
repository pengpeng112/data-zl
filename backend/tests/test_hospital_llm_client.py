import httpx
import pytest

from app.core.config import settings
from app.services.hospital_llm_client import (
    HospitalLlmClient,
    HospitalLlmError,
    extract_assistant_text,
    iter_stream_deltas,
    strip_think_stream,
)


def test_stream_parser_skips_think_and_keeps_answer():
    lines = [
        'data: {"choices":[{"delta":{"content":"<think>内部"}}]}',
        'data: {"choices":[{"delta":{"content":"推理</think>结论：字段缺注释"}}]}',
        "data: [DONE]",
    ]
    assert "".join(strip_think_stream(iter_stream_deltas(lines))) == "结论：字段缺注释"


def test_strips_think_block():
    text = extract_assistant_text({
        "choices": [{"message": {"content": "<think>\n内部推理\n</think>\n\n我只能做只读分析。"}}]
    })
    assert text == "我只能做只读分析。"
    assert "内部推理" not in text


def _client(status=200, content=b'{"choices":[{"message":{"content":"readonly-ok"}}]}'):
    def handler(request):
        return httpx.Response(status, content=content, request=request)
    return HospitalLlmClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_allowlist_rejects_other_hosts(monkeypatch):
    monkeypatch.setattr(settings, "hospital_llm_base_url", "http://127.0.0.1:9000")
    monkeypatch.setattr(settings, "hospital_llm_allowed_hosts", ["10.255.255.10"])
    with pytest.raises(HospitalLlmError) as exc:
        _client().complete("hi")
    assert exc.value.error_class == "ssrf_blocked"


def test_analysis_from_llm_text_accepts_json_or_plain():
    from app.services.hospital_llm_analysis import analysis_from_llm_text

    digest = "a" * 64
    parsed = analysis_from_llm_text(
        '{"schema_version":"quality-analysis-output/v1","request_id":"AQJ-1","input_digest":"' + digest + '","summary":"住院检查关系命中率高，门诊需单独看收据号","risk_level":"medium","root_causes":[{"title":"门诊住院未拆分","reason":"VISIT_ID=0 不能当住院","confidence":0.8,"evidence_finding_ids":[1]}],"recommendations":[{"title":"按门诊住院分别复核","action_type":"manual_review","priority":"P1","reason":"避免混用就诊键","confidence":0.8,"target_refs":["HIS.EXAM_MASTER"]}],"false_positive":{"possible":false,"reason":"需人工确认"},"follow_up_checks":[{"description":"核对门诊收据号","sql_draft":null}],"limitations":["不能访源库"]}',
        request_id="AQJ-1",
        input_digest=digest,
    )
    assert parsed.risk_level == "medium"
    assert parsed.root_causes[0].title == "门诊住院未拆分"
    wrapped = analysis_from_llm_text("这是一段没有 JSON 的中文分析。", request_id="AQJ-2", input_digest=digest)
    assert "中文分析" in wrapped.summary
    assert wrapped.recommendations[0].action_type in {"manual_review", "metadata_fix"}


def test_governance_brief_uses_rule_names_and_forbids_business_db(monkeypatch):
    from app.services.hospital_llm_analysis import ANALYSIS_PROMPT_HEADER, build_analysis_prompt

    from app.services.hospital_llm_analysis import analysis_from_llm_text, parse_cn_sections

    prompt = build_analysis_prompt(task_type="finding", request_id="AQJ-1", input_digest="a" * 64, payload_json="{}")
    assert "不要输出 JSON" in ANALYSIS_PROMPT_HEADER
    assert "明细举例" in prompt
    assert "业务库" in ANALYSIS_PROMPT_HEADER
    parsed = parse_cn_sections("【结论】缺注释要补。\n【问题定位】LUNA 项目字典。\n【处理建议】\n1. 先补中文名\n2. 再复核覆盖率")
    assert parsed["结论"] == "缺注释要补。"
    result = analysis_from_llm_text(
        "【结论】项目字典缺字段注释，建议补目录。\n【问题定位】LUNA_MCS_SDSEY.项目字典\n【明细举例】CODE、NAME 无中文名\n【要不要处理】需要处理\n【处理建议】\n1. 在平台补字段中文名\n2. 业务确认后再看是否还报",
        request_id="AQJ-1",
        input_digest="a" * 64,
    )
    assert "缺字段注释" in result.summary
    assert result.recommendations[0].title.startswith("在平台补")


def test_finding4_style_chinese_report_is_not_contract_blocked():
    from app.services.hospital_llm_analysis import analysis_from_llm_text

    text = (
        "【结论】HIS.PAT_VISIT表与HIS.EXAM_MASTER表之间的关系孤儿率高达41.1%，"
        "属于必须处理的严重问题。混合检查已拆成 553/554。\n"
        "【问题定位】关系键是患者ID(PATIENT_ID)+VISIT_ID。\n"
        "【明细举例】门诊检查 VISIT_ID=0 会被算成住院孤儿。\n"
        "【要不要处理】混合关系已拆，本条更像口径噪音。\n"
        "【处理建议】\n"
        "1. 看正式关系 553 住院检查、554 门诊检查\n"
        "2. 不要按混合关系改业务数据\n"
    )
    result = analysis_from_llm_text(text, request_id="AQJ-1", input_digest="a" * 64)
    assert "孤儿率" in result.summary
    assert "患者ID" in result.root_causes[0].reason or "PATIENT_ID" in result.root_causes[0].reason
    assert any("553" in item.title or "553" in item.reason for item in result.recommendations)


def test_complete_returns_text(monkeypatch):
    monkeypatch.setattr(settings, "hospital_llm_base_url", "http://10.255.255.10:9000")
    monkeypatch.setattr(settings, "hospital_llm_allowed_hosts", ["10.255.255.10"])
    monkeypatch.setattr(settings, "hospital_llm_api_key_ref", "env:TEST_HOSPITAL_LLM_KEY")
    monkeypatch.setenv("TEST_HOSPITAL_LLM_KEY", "secret")
    reply = _client().complete("ping")
    assert reply.text == "readonly-ok"
    assert "secret" not in repr(HospitalLlmClient())
