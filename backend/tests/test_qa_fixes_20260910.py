"""QA 修复回归（2026-09-10，问题记录 ST-001/007/008/018）。

单测试设计：全部断言在一个测试函数内顺序执行，规避 TestClient/db_session
双 fixture 与 autouse TRUNCATE 的跨测试连锁（166 附录 A.2 行为）。

- ST-001：approver 不可再经 /govern/user-roles、/govern/roles* 自我提权。
- ST-007：audit-logs/summary 聚合结果与逐行计数一致（GROUP BY 重构不改语义）。
- ST-008：audit-logs/export 的 = 开头单元格已转义。
- ST-018：/permissions/api-keys 不再回传 token 前缀。
"""
from __future__ import annotations

import csv
import hashlib
import io as _io
import secrets

from sqlalchemy import text

from app.models.governance import ApiKey
from app.models.governance_base import AssetUserRole, GovernAuditLog


def test_qa_fixes_20260910(db_session, client):
    # ── ST-001：approver 提权链全部被端点级权限拦截 ──
    name = "qa-approver-001"
    tok = "qa-approver-" + secrets.token_hex(8)
    db_session.add(ApiKey(
        key_name=name,
        token_hash=hashlib.sha256(tok.encode()).hexdigest(),
        user_identifier=name,
    ))
    db_session.add(AssetUserRole(user_identifier=name, role_code="approver"))
    db_session.commit()
    admin_header = {"Authorization": f"Bearer {tok}"}
    try:
        r1 = client.post("/api/v1/govern/user-roles",
                         json={"user_identifier": name, "role_code": "platform_admin"},
                         headers=admin_header)
        assert r1.status_code == 403, r1.text
        assert "identity.role.manage" in r1.text or "缺少权限" in r1.text

        r2 = client.put("/api/v1/govern/roles",
                        json={"role_code": "qa-evil-role", "role_name_cn": "越权角色"},
                        headers=admin_header)
        assert r2.status_code == 403, r2.text

        r3 = client.post("/api/v1/govern/roles/platform_admin/permissions",
                         json={"role_code": "platform_admin", "resource": "*", "action": "*"},
                         headers=admin_header)
        assert r3.status_code == 403, r3.text
    finally:
        db_session.execute(text("DELETE FROM asset.asset_user_roles WHERE user_identifier=:n"),
                           {"n": name})
        db_session.execute(text("DELETE FROM asset.asset_api_keys WHERE key_name=:n"),
                           {"n": name})
        db_session.commit()

    # 管理员（TEST_TOKEN 直通）仍可正常访问治理端点
    ok = client.get("/api/v1/govern/roles")
    assert ok.status_code == 200 and ok.json()["code"] == 0

    # ── ST-007 + ST-008：summary 聚合语义 + export 公式转义 ──
    db_session.add(GovernAuditLog(module="qa_mod", entity_type="t", entity_ref="r",
                                  action="a1", operator="qa-op", reason="=SUM(1+1)"))
    db_session.add(GovernAuditLog(module="qa_mod", entity_type="t", entity_ref="r2",
                                  action="a1", operator="qa-op", reason="plain"))
    db_session.commit()

    s = client.get("/api/v1/govern/audit-logs/summary?module=qa_mod")
    assert s.status_code == 200
    d = s.json()["data"]
    assert d["by_module"]["qa_mod"] == 2
    assert d["by_action"]["a1"] == 2
    assert d["by_operator"]["qa-op"] == 2

    e = client.get("/api/v1/govern/audit-logs/export?module=qa_mod")
    assert e.status_code == 200
    rows = list(csv.reader(_io.StringIO(e.text)))
    reason_idx = rows[0].index("reason")
    formula_rows = [r for r in rows[1:] if "SUM(1+1)" in (r[reason_idx] if len(r) > reason_idx else "")]
    assert formula_rows and all(r[reason_idx].startswith("'=SUM") for r in formula_rows), rows

    # ── ST-018：api-keys 列表不回传 token 材料 ──
    k = client.get("/api/v1/permissions/api-keys")
    assert k.status_code == 200
    for it in k.json()["data"]:
        assert "..." not in it["token_masked"], it["token_masked"]
        assert isinstance(it.get("has_legacy_token"), bool)
