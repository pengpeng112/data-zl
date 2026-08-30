"""166 F6：导出六硬约束——白名单/审计/文件名/防注入/上限/403/POST body 筛选/默认排除 conflicted。

约束对照（B1 裁决，禁止照抄 governance.py 旧实现）：
  ①require_permission 显式挂载+403 显式测试（GET 导出不在写路由扫描内）
  ②审计行（操作人/筛选/行数） ③文件名含导出时间+筛选标签
  ④防公式注入（=+-@ 前缀加 '） ⑤列白名单逐列常量（findings 不含 evidence_sql）
  ⑥findings=POST+body 筛选；值域导出默认排除 conflicted
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole, GovernAuditLog
from app.services.probe_service import register_run, upsert_finding


def _seed_findings(db_session, n: int = 2):
    register_run(db_session, run_id="probe-t-e0001", status="done")
    for i in range(1, n + 1):
        upsert_finding(
            db_session, run_id="probe-t-e0001", probe_type="R-REF", system_pair="HIS(单库)",
            object_desc=f"导出对象{i}", metric_name=f"exp_metric_{i}", metric_value=50.0 + i,
            metric_unit="%", threshold=1.0, window_start=date(2026, 7, 1),
            window_end=date(2026, 7, 31), severity="P2",
            evidence_sql="SELECT COUNT(*) FROM DUAL WHERE D >= :START_DATE",
            note="=HYPERLINK(\"http://evil\",\"点我\")" if i == 1 else f"普通备注{i}",
        )
    db_session.commit()


def _seed_value_domain(client, code: str, meaning: str, conflicted: bool = False) -> int:
    payload = {
        "system_code": "HIS_SOURCE",
        "source_code": "his_source_10_10_10_15",
        "schema_name": "MEDREC",
        "table_name": "PAT_VISIT",
        "column_name": "DISCHARGE_DISPOSITION",
        "code": code,
        "meaning": meaning,
        "domain_kind": "enum",
        "evidences": [{"source_type": "manual", "snippet_ref": "166 测试"}],
    }
    resp = client.post("/api/v1/value-domains", json=payload)
    assert resp.status_code == 201, resp.text
    domain_id = resp.json()["data"]["id"]
    if conflicted:
        clash = {**payload, "meaning": f"冲突含义-{code}"}
        clash_resp = client.post("/api/v1/value-domains", json=clash)
        assert clash_resp.status_code == 409
    return domain_id


def _make_limited_client(client: TestClient, *, role_code: str, resources: list[str], token: str, user: str):
    from app.core.db import SessionLocal
    from app.models.governance import ApiKey

    db = SessionLocal()
    try:
        if not db.scalar(select(AssetRole).where(AssetRole.role_code == role_code)):
            db.add(AssetRole(role_code=role_code, role_name_cn=role_code, role_type="platform"))
        if not db.scalar(select(AssetUserRole).where(
            AssetUserRole.user_identifier == user, AssetUserRole.role_code == role_code
        )):
            db.add(AssetUserRole(user_identifier=user, role_code=role_code, status="active"))
        for res in resources:
            if not db.scalar(select(AssetRolePermission).where(
                AssetRolePermission.role_code == role_code,
                AssetRolePermission.resource == res,
                AssetRolePermission.action == "access",
            )):
                db.add(AssetRolePermission(role_code=role_code, resource=res, action="access"))
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        existing = db.query(ApiKey).filter(ApiKey.key_name == f"key-{user}").first()
        if not existing:
            db.add(ApiKey(key_name=f"key-{user}", token_hash=token_hash, user_identifier=user))
        else:
            existing.token_hash = token_hash
            existing.token = None
            existing.user_identifier = user
            existing.enabled = True
        db.commit()
    finally:
        db.close()
    return TestClient(client.app, headers={"Authorization": f"Bearer {token}"})


class TestFindingsExport:
    def test_whitelist_no_evidence_sql_formula_escape_audit_filename(self, client, db_session):
        _seed_findings(db_session, n=2)
        r = client.post("/api/v1/probe-findings/export", json={})
        assert r.status_code == 200, r.text
        # ③文件名：probe-findings-<时间戳>.csv
        disp = r.headers["content-disposition"]
        assert "probe-findings-" in disp and ".csv" in disp
        # ⑤白名单列逐列；evidence_sql 不在输出
        rows = list(csv.reader(io.StringIO(r.text)))
        header = rows[0]
        from app.api.v1.probe import FINDING_EXPORT_COLUMNS, FINDING_EXPORT_LIMIT
        assert tuple(header) == FINDING_EXPORT_COLUMNS
        assert "evidence_sql" not in header
        assert "evidence_digest" in header
        assert FINDING_EXPORT_LIMIT == 5000  # 上限常量锁死
        # ④防公式注入：= 开头单元格加 ' 前缀
        body = r.text
        assert "'=HYPERLINK" in body
        # 数据行数
        assert len(rows) == 3
        # ②审计行：操作人/筛选/行数
        audit = db_session.scalar(
            select(GovernAuditLog).where(
                GovernAuditLog.module == "probe",
                GovernAuditLog.action == "export",
                GovernAuditLog.entity_ref == "export",
            )
        )
        assert audit is not None
        assert audit.operator == "test-platform-admin"
        assert audit.after_data["rows"] == 2
        assert audit.after_data["filename"] in disp

    def test_post_body_filters_and_status_filename_tag(self, client, db_session):
        _seed_findings(db_session, n=2)
        # 直改一行状态构造筛选差分（夹具直改库，同 165 E5 先例）
        db_session.execute(__import__("sqlalchemy").text(
            "UPDATE asset.asset_probe_findings SET status='resolved' WHERE id="
            "(SELECT min(id) FROM asset.asset_probe_findings)"
        ))
        db_session.commit()
        r = client.post("/api/v1/probe-findings/export", json={"status": "open"})
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert len(rows) == 2  # header + 1 行（resolved 被筛掉）
        assert "status-open" in r.headers["content-disposition"]  # ③筛选标签

    def test_403_without_probe_read(self, client, db_session):
        _seed_findings(db_session, n=1)
        limited = _make_limited_client(
            client, role_code="no_probe_reader_166",
            resources=["value_domain.read"],  # ①显式 403：无 probe.finding.read
            token="test-token-no-probe-read-166", user="test-no-probe-read-166",
        )
        assert limited.post("/api/v1/probe-findings/export", json={}).status_code == 403

    def test_export_route_order_before_dynamic_id(self, client, db_session):
        from app.api.v1 import probe as probe_router
        paths = [route.path for route in probe_router.router.routes]
        assert paths.index("/api/v1/probe-findings/export") < paths.index("/api/v1/probe-findings/{finding_id}")


class TestValueDomainsExport:
    def test_default_excludes_conflicted_whitelist_and_audit(self, client, db_session):
        _seed_value_domain(client, "4", "非医嘱离院")
        _seed_value_domain(client, "5", "死亡", conflicted=True)
        r = client.get("/api/v1/value-domains/export")
        assert r.status_code == 200, r.text
        rows = list(csv.reader(io.StringIO(r.text)))
        header = rows[0]
        assert tuple(header) == (
            "system_code", "schema_name", "table_name", "column_name", "code",
            "meaning", "domain_kind", "scope_condition", "status", "version_of", "updated_at",
        )
        body_codes = [row[4] for row in rows[1:]]
        assert "4" in body_codes
        assert "5" not in body_codes  # 默认排除 conflicted
        # include_conflicted=true → 全量
        r2 = client.get("/api/v1/value-domains/export?include_conflicted=true")
        rows2 = list(csv.reader(io.StringIO(r2.text)))
        assert "5" in [row[4] for row in rows2[1:]]
        # ②审计行
        audit = db_session.scalar(
            select(GovernAuditLog).where(
                GovernAuditLog.module == "value_domain",
                GovernAuditLog.action == "export",
            )
        )
        assert audit is not None and audit.after_data["rows"] >= 1
        # ③文件名含时间戳
        assert "value-domains" in r.headers["content-disposition"]

    def test_status_filter_tag_in_filename_and_formula_escape(self, client, db_session):
        _seed_value_domain(client, "4", "=SUM(1+1) 的含义")  # meaning 以 = 开头
        r = client.get("/api/v1/value-domains/export?status=pending")
        assert r.status_code == 200
        assert "status-pending" in r.headers["content-disposition"]
        assert "'=SUM(1+1)" in r.text  # ④防公式注入

    def test_export_registered_before_dynamic_domain_id(self, client, db_session):
        # /export 先于 /{domain_id}：未被 422 当作 domain_id 解析
        r = client.get("/api/v1/value-domains/export")
        assert r.status_code == 200
        from app.api.v1 import value_domains as vd_router
        paths = [route.path for route in vd_router.router.routes]
        assert paths.index("/api/v1/value-domains/export") < paths.index("/api/v1/value-domains/{domain_id}")

    def test_403_without_value_domain_read(self, client, db_session):
        limited = _make_limited_client(
            client, role_code="no_vd_reader_166",
            resources=["probe.finding.read"],  # ①显式 403：无 value_domain.read
            token="test-token-no-vd-read-166", user="test-no-vd-read-166",
        )
        assert limited.get("/api/v1/value-domains/export").status_code == 403
