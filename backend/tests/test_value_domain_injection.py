"""149 P1c: 值域注入 —— context/resolve 与 system-context 全量主路径 + propose-sql 补充路径。"""
from __future__ import annotations

import pytest

from app.models.value_domain import (
    AssetColumnValueDomain,
    AssetColumnValueDomainEvidence,
    AssetColumnValueDomainVersion,
)
from app.services.value_domain_service import confirmed_domains_for_injection, value_domains_for_sql


def _seed_domain(
    db_session,
    *,
    code: str,
    meaning: str,
    status: str = "confirmed",
    conflict_status: str = "none",
    domain_kind: str = "enum",
    column_name: str = "DISCHARGE_DISPOSITION",
    table_name: str = "PAT_VISIT",
    schema_name: str = "MEDREC",
    system_code: str = "HIS",
) -> AssetColumnValueDomain:
    row = AssetColumnValueDomain(
        system_code=system_code,
        source_code="src_test",
        schema_name=schema_name,
        table_name=table_name,
        column_name=column_name,
        code=code,
        meaning=meaning,
        domain_kind=domain_kind,
        status=status,
        conflict_status=conflict_status,
    )
    db_session.add(row)
    db_session.flush()
    db_session.add(
        AssetColumnValueDomainEvidence(
            domain_id=row.id, source_type="manual", snippet_ref="149 测试"
        )
    )
    v = AssetColumnValueDomainVersion(
        domain_id=row.id,
        version_no=1,
        snapshot={"code": code, "meaning": meaning, "status": status},
        change_reason="submit",
        actor="test",
    )
    db_session.add(v)
    db_session.flush()
    row.current_version_id = v.id
    db_session.commit()
    return row


def test_injection_filter_excludes_unconfirmed_and_conflicted(db_session):
    _seed_domain(db_session, code="4", meaning="非医嘱离院（自愿离院）")
    _seed_domain(db_session, code="9", meaning="其他（语义待核）", status="pending")
    _seed_domain(db_session, code="5", meaning="死亡", conflict_status="conflicted")
    _seed_domain(db_session, code="1", meaning="医嘱离院", status="deprecated")

    injected = confirmed_domains_for_injection(db_session, system_code="HIS")
    assert [d["code"] for d in injected] == ["4"]
    assert injected[0]["version_no"] == 1
    assert injected[0]["meaning"] == "非医嘱离院（自愿离院）"


def test_system_context_carries_confirmed_value_domains(client, db_session):
    _seed_domain(db_session, code="4", meaning="非医嘱离院（自愿离院）")
    _seed_domain(db_session, code="9", meaning="其他（语义待核）", status="pending")

    resp = client.get("/api/v1/ai/system-context", params={"system_code": "HIS"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["value_domain_count"] == 1
    entry = data["value_domains"][0]
    assert entry["code"] == "4"
    assert entry["meaning"] == "非医嘱离院（自愿离院）"
    assert entry["version_no"] == 1  # 注入响应回带 version_no（149 §3）

    other = client.get("/api/v1/ai/system-context", params={"system_code": "DATA_CENTER"})
    assert other.json()["data"]["value_domain_count"] == 0


def test_context_resolve_carries_value_domains_section(client, db_session):
    _seed_domain(
        db_session,
        code="TRAP",
        meaning="勿用 COMM.DISCHARGE_DISPOSITION_DICT 判读离院方式",
        domain_kind="trap",
    )
    resp = client.post(
        "/api/v1/ai/context/resolve",
        json={"question_summary": "离院方式统计", "system_code": "HIS", "max_objects": 50},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["value_domain_count"] == 1
    assert doc["value_domains"][0]["domain_kind"] == "trap"
    assert doc["value_domains"][0]["version_no"] == 1


def test_propose_sql_injects_precise_value_domains(client, db_session):
    _seed_domain(db_session, code="4", meaning="非医嘱离院（自愿离院）")
    _seed_domain(db_session, code="9", meaning="其他（语义待核）", status="pending")

    sql = (
        "SELECT pv.PATIENT_ID, pv.DISCHARGE_DISPOSITION FROM MEDREC.PAT_VISIT pv "
        "WHERE pv.DISCHARGE_DISPOSITION = '4' AND ROWNUM <= 10"
    )
    resp = client.post("/api/v1/ai/propose-sql", json={"title": "离院方式", "sql_text": sql})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    inj = data["value_domain_injection"]
    assert inj["injected"] is True
    assert inj["value_domains_not_injected_reason"] is None
    matched = data["value_domains"]
    assert len(matched) == 1  # pending 的 code=9 不注入
    assert matched[0]["code"] == "4"
    assert matched[0]["match_basis"] == "schema_table_column"
    assert matched[0]["version_no"] == 1


def test_propose_sql_parse_failure_reports_reason_explicitly(client):
    resp = client.post(
        "/api/v1/ai/propose-sql",
        json={"title": "坏 SQL", "sql_text": "SELETC FRM ??where"},
    )
    assert resp.status_code == 200
    inj = resp.json()["data"]["value_domain_injection"]
    assert inj["injected"] is False
    assert inj["value_domains_not_injected_reason"]
    assert inj["value_domains_not_injected_reason"].startswith("sql_parse_failed")


def test_value_domains_for_sql_bare_column_and_alias(db_session):
    _seed_domain(db_session, code="5", meaning="死亡")
    result = value_domains_for_sql(
        db_session,
        "SELECT DISCHARGE_DISPOSITION FROM MEDREC.PAT_VISIT WHERE DISCHARGE_DISPOSITION = '5'",
    )
    assert result["injected"] is True
    assert result["value_domains"][0]["code"] == "5"
    assert result["value_domains"][0]["match_basis"] == "from_table_column"


def test_tools_and_mcp_catalog_register_value_domain_tool(client):
    tools = client.get("/api/v1/ai/tools").json()["data"]["tools"]
    names = {t["name"] for t in tools}
    assert "list_value_domains" in names
    assert "get_system_context" in names

    catalog = client.get("/api/v1/ai/mcp/catalog").json()["data"]
    catalog_names = {t["name"] for t in catalog["tools"]}
    assert "list_value_domains" in catalog_names
