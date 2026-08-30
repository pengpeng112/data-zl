"""165 E4: 探查 API 测试（筛选/分页/详情/403/空态/405 占位顺序）。"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.services.probe_service import register_run, upsert_finding


def _seed(db_session):
    register_run(db_session, run_id="probe-t-0001", status="done")
    for i, (pt, sev, val) in enumerate([("R-REF", "P1", 83.2), ("R-REF", "P2", 5.9), ("R-CNT", "P2", 64.5)], 1):
        upsert_finding(
            db_session, run_id="probe-t-0001", probe_type=pt, system_pair="HIS(单库)",
            object_desc=f"对象{i}", metric_name=f"m{i}", metric_value=val, metric_unit="%",
            threshold=1.0, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31),
            severity=sev, evidence_sql="SELECT COUNT(*) FROM DUAL WHERE D >= :START_DATE",
        )
    db_session.commit()


def test_list_findings_filter_and_pagination(client, db_session):
    _seed(db_session)
    r = client.get("/api/v1/probe-findings?probe_type=R-REF&page=1&page_size=1")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 2 and len(d["items"]) == 1 and d["page"] == 1 and d["page_size"] == 1


def test_list_findings_severity_and_source_filters(client, db_session):
    _seed(db_session)
    assert client.get("/api/v1/probe-findings?severity=P1").json()["total"] == 1
    assert client.get("/api/v1/probe-findings?source=对象2").json()["total"] == 1
    assert client.get("/api/v1/probe-findings?window_start_from=2026-08-01").json()["total"] == 0


def test_finding_detail_full_fields(client, db_session):
    _seed(db_session)
    fid = client.get("/api/v1/probe-findings").json()["items"][0]["id"]
    r = client.get(f"/api/v1/probe-findings/{fid}")
    assert r.status_code == 200
    d = r.json()
    assert d["evidence_sql"] and ":START_DATE" in d["evidence_sql"]
    assert d["status"] == "open" and d["relapse_count"] == 0


def test_runs_list_and_detail(client, db_session):
    _seed(db_session)
    lst = client.get("/api/v1/probe-runs")
    assert lst.status_code == 200 and lst.json()["total"] >= 1
    det = client.get("/api/v1/probe-runs/probe-t-0001")
    assert det.status_code == 200 and det.json()["status"] == "done"
    assert "metrics_summary" in det.json()
    assert client.get("/api/v1/probe-runs/nope").status_code == 404


def test_empty_state(client, db_session):
    d = client.get("/api/v1/probe-findings").json()
    assert d == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_export_route_registered_before_id_route(client, db_session):
    # 166 D4 已以真实现替换 405 占位（计划内替换）；顺序断言保留：export 不被 {finding_id} 吞掉
    from app.api.v1 import probe as probe_router
    paths = [route.path for route in probe_router.router.routes]
    assert paths.index("/api/v1/probe-findings/export") < paths.index("/api/v1/probe-findings/{finding_id}")


def test_unauthorized_401(client, db_session):
    # client fixture 带默认凭据；用无 token 的裸 TestClient 验证未授权
    from app.main import app
    bare = TestClient(app)
    assert bare.get("/api/v1/probe-findings").status_code == 401
