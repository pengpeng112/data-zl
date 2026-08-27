"""126 P1 integration tests for query ingest / versions / idempotency."""
from __future__ import annotations

from fastapi.testclient import TestClient


SAFE_SQL = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"
BLOCK_SQL = "DELETE FROM HIS.PAT_VISIT"


def test_gate_preview(client: TestClient):
    ok = client.post("/api/v1/queries/gate", json={"sql_text": SAFE_SQL, "dialect": "oracle"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "validated"

    bad = client.post("/api/v1/queries/gate", json={"sql_text": BLOCK_SQL, "dialect": "oracle"})
    assert bad.status_code == 200
    assert bad.json()["data"]["status"] == "blocked"


def test_ingest_auto_activates_and_idempotent(client: TestClient):
    payload = {
        "query_code": "QRY_P1_TEST_PAT_VISIT",
        "title": "测试住院患者抽样",
        "sql_text": SAFE_SQL,
        "purpose": "126 P1 测试",
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "dialect": "oracle",
    }
    r1 = client.post("/api/v1/queries/ingest", json=payload)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["activated"] is True or d1.get("idempotent")
    assert d1["version"]["status"] == "active"
    assert d1["version"]["is_active"] is True
    ver = d1["version"]["version"]
    sha = d1["version"]["sql_sha256"]

    r2 = client.post("/api/v1/queries/ingest", json=payload)
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["idempotent"] is True
    assert d2["version"]["sql_sha256"] == sha
    assert d2["version"]["version"] == ver


def test_ingest_blocked_not_active(client: TestClient):
    payload = {
        "query_code": "QRY_P1_BLOCKED",
        "title": "应被门禁阻断",
        "sql_text": BLOCK_SQL,
        "system_code": "DATA_CENTER",
        "source_code": "ods_8_216",
        "dialect": "oracle",
    }
    r = client.post("/api/v1/queries/ingest", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["version"]["status"] == "blocked"
    assert d["version"]["is_active"] is False
    assert d.get("activated") is not True


def test_revise_creates_new_version(client: TestClient):
    base = {
        "query_code": "QRY_P1_REVISE",
        "title": "修订测试",
        "sql_text": SAFE_SQL,
        "system_code": "HIS",
        "source_code": "his_source",
        "dialect": "oracle",
    }
    assert client.post("/api/v1/queries/ingest", json=base).status_code == 200
    new_sql = "SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"
    r = client.post(
        "/api/v1/queries/QRY_P1_REVISE/revise",
        json={"sql_text": new_sql, "revision_reason": "增加就诊次数字段"},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["version"]["version"] >= 2
    assert d["version"]["is_active"] is True
    assert d["version"]["revision_reason"]


def test_list_and_detail(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_P1_LIST",
            "title": "列表测试",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
        },
    )
    lst = client.get("/api/v1/queries", params={"keyword": "QRY_P1_LIST"})
    assert lst.status_code == 200
    assert lst.json()["data"]["total"] >= 1
    detail = client.get("/api/v1/queries/QRY_P1_LIST")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["definition"]["query_code"] == "QRY_P1_LIST"
    assert body["active_version"] is not None


def test_ai_context(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_P1_CTX",
            "title": "上下文测试",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
        },
    )
    r = client.get("/api/v1/queries/ai/context")
    assert r.status_code == 200
    codes = [x["query_code"] for x in r.json()["data"]]
    assert "QRY_P1_CTX" in codes


def test_run_without_source_fails_gracefully(client: TestClient):
    client.post(
        "/api/v1/queries/ingest",
        json={
            "query_code": "QRY_P1_RUN_NOSRC",
            "title": "无连接执行",
            "sql_text": SAFE_SQL,
            "dialect": "oracle",
        },
    )
    r = client.post(
        "/api/v1/queries/run",
        json={"query_code": "QRY_P1_RUN_NOSRC", "result_storage": "none"},
    )
    # missing source or source not found → 400/404
    assert r.status_code in (400, 404)


def test_run_truncation_boundary_exact_n_and_n_plus_one(db_session, monkeypatch):
    """A4 行为锁：恰好 N 行不截断；N+1（探针）行截断且探针行不入样本/统计。"""
    from app.services import quality_sql_runner
    from app.services.query_intake import ingest_query
    from app.services.query_runner import run_query_version

    assert ingest_query(
        db_session,
        query_code="QRY_P1_TRUNC",
        title="截断口径测试",
        sql_text=SAFE_SQL,
        system_code="DATA_CENTER",
        source_code="ods_8_216",
        dialect="oracle",
    )["version"]["is_active"] is True

    class FakeConnector:
        def __init__(self, rows):
            self._rows = rows

        def execute_readonly(self, sql, params=None, max_rows=1000):
            return self._rows

        def close(self):
            pass

    def _run(rows, max_rows):
        monkeypatch.setattr(quality_sql_runner, "_build_connector", lambda source: FakeConnector(rows))
        return run_query_version(
            db_session, query_code="QRY_P1_TRUNC", source_code="ods_8_216", max_rows=max_rows
        )

    n = 3
    exact = _run([{"PATIENT_ID": f"P{i}"} for i in range(n)], max_rows=n)
    assert exact["status"] == "success"
    assert exact["row_count"] == n
    assert exact["truncated"] is False  # 恰好 N 行不算截断

    over = _run([{"PATIENT_ID": f"P{i}"} for i in range(n + 1)], max_rows=n)
    assert over["status"] == "success"
    assert over["truncated"] is True  # 探针行（第 N+1 行）证明被截断
    assert over["row_count"] == n  # 探针行丢弃，统计只算 N 行
    assert len(over["sample"]) <= n


def test_diff_endpoint_masks_sql_without_full_read(client: TestClient):
    """B2：diff 端点与列表口径一致——无权限返回掩码 + sql_available 标记，不 403。

    测试 client 挂 platform_admin（有全部权限），因此用无角色 token 验证掩码分支。
    """
    r = client.post("/api/v1/queries/ingest", json={
        "query_code": "QRY_P1_DIFF",
        "title": "diff 测试",
        "sql_text": SAFE_SQL,
        "dialect": "oracle",
    })
    assert r.status_code == 200, r.text
    client.post("/api/v1/queries/QRY_P1_DIFF/revise", json={
        "sql_text": "SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5",
        "revision_reason": "diff 掩码测试",
    })
    resp = client.get("/api/v1/queries/QRY_P1_DIFF/versions/2/diff")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    # admin 有权限时返回原文；结构字段必须齐备（掩码/原文两种形态字段一致）。
    assert set(d.keys()) == {
        "query_code", "version", "sql_sha256", "parent_version",
        "parent_sql_sha256", "same_sql", "revision_reason",
        "current_sql", "parent_sql", "sql_available",
    }
    assert d["parent_version"] == 1
    assert d["same_sql"] is False
    assert d["current_sql"]  # admin（platform_admin）有 ai.sql.full_read


def _query_viewer_client() -> TestClient:
    """仅 query.view、无 ai.sql.full_read，用于 B2 掩码分支。"""
    import hashlib

    from app.core.db import SessionLocal
    from app.models.governance import ApiKey
    from app.models.governance_base import AssetRole, AssetRolePermission, AssetUserRole

    token = "test-token-query-viewer-no-sql"
    ident = "test-query-viewer-nosql"
    role_code = "query_viewer_nosql"
    db = SessionLocal()
    try:
        if not db.query(AssetRole).filter(AssetRole.role_code == role_code).first():
            db.add(AssetRole(role_code=role_code, role_name_cn="查询查看无SQL", role_type="test"))
        if not db.query(AssetUserRole).filter(
            AssetUserRole.user_identifier == ident, AssetUserRole.role_code == role_code
        ).first():
            db.add(AssetUserRole(user_identifier=ident, role_code=role_code, status="active"))
        if not db.query(AssetRolePermission).filter(
            AssetRolePermission.role_code == role_code,
            AssetRolePermission.resource == "query.view",
            AssetRolePermission.action == "access",
        ).first():
            db.add(AssetRolePermission(role_code=role_code, resource="query.view", action="access"))
        existing = db.query(ApiKey).filter(ApiKey.key_name == "test-query-viewer-nosql").first()
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not existing:
            db.add(ApiKey(key_name="test-query-viewer-nosql", token_hash=digest, user_identifier=ident))
        else:
            existing.token_hash = digest
            existing.user_identifier = ident
            existing.enabled = True
        db.commit()
    finally:
        db.close()
    from app.main import app as fastapi_app

    return TestClient(fastapi_app, headers={"Authorization": f"Bearer {token}"})


def test_diff_endpoint_masks_sql_for_viewer_without_full_read(client: TestClient):
    """B2 掩码分支：无 ai.sql.full_read 时 200 + current_sql=null，不 403。"""
    r = client.post("/api/v1/queries/ingest", json={
        "query_code": "QRY_P1_DIFF_MASK",
        "title": "diff 掩码",
        "sql_text": SAFE_SQL,
        "dialect": "oracle",
    })
    assert r.status_code == 200, r.text
    client.post("/api/v1/queries/QRY_P1_DIFF_MASK/revise", json={
        "sql_text": "SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5",
        "revision_reason": "diff 掩码测试",
    })
    viewer = _query_viewer_client()
    resp = viewer.get("/api/v1/queries/QRY_P1_DIFF_MASK/versions/2/diff")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["current_sql"] is None
    assert d["parent_sql"] is None
    assert d["sql_available"] == "full_read_permission_required"
    assert d["same_sql"] is False


def test_get_query_includes_sql_for_admin_without_include_sql_flag(client: TestClient):
    """详情默认：有 full_read 的管理员不传 include_sql 也能看到 sql_text。"""
    client.post("/api/v1/queries/ingest", json={
        "query_code": "QRY_P1_DETAIL_SQL",
        "title": "详情 SQL",
        "sql_text": SAFE_SQL,
        "dialect": "oracle",
    })
    resp = client.get("/api/v1/queries/QRY_P1_DETAIL_SQL")
    assert resp.status_code == 200, resp.text
    active = resp.json()["data"]["active_version"]
    assert active["sql_text"] == SAFE_SQL
    assert "sql_available" not in active or active.get("sql_available") is None


def test_list_queries_response_structure_locked(client: TestClient):
    """C3 行为不变锁：列表批量化后响应结构一致。"""
    client.post("/api/v1/queries/ingest", json={
        "query_code": "QRY_P1_LISTC3",
        "title": "C3 结构锁定",
        "sql_text": SAFE_SQL,
        "dialect": "oracle",
    })
    resp = client.get("/api/v1/queries", params={"keyword": "QRY_P1_LISTC3"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert set(body.keys()) == {"total", "page", "page_size", "items"}
    item = next(i for i in body["items"] if i["query_code"] == "QRY_P1_LISTC3")
    assert item["active_version"] is not None
    assert "sql_text" not in item["active_version"]
    assert item["active_version"]["sql_available"] == "full_read_permission_required"
