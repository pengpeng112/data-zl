"""165 E1: probe 模型/服务层专项测试。

覆盖：迁移建表与唯一键、upsert 两键语义（同窗幂等/新窗观测更新）、复发判定
（resolved→open+relapse+1 / confirmed 保持+note / false_positive 不动）、
服务层源码无终态写入路径（铁律 4，静态断言锁死）、权限码种子四角色。
"""
from __future__ import annotations

import inspect
from datetime import date

from sqlalchemy import text

from app.models.probe import AssetProbeFinding
from app.services import probe_service
from app.services.probe_service import (
    evidence_digest,
    find_finding,
    object_digest,
    register_run,
    update_run,
    upsert_finding,
)

BASE = dict(
    probe_type="R-REF",
    system_pair="HIS(单库)",
    object_desc="EXAM.EXAM_MASTER.DOCTOR_USER 缺失率",
    metric_name="doctor_code_missing_rate",
    metric_unit="%",
    threshold=1.0,
    severity="P2",
    evidence_sql="SELECT COUNT(*) TOTAL, SUM(CASE WHEN DOCTOR_USER IS NULL THEN 1 ELSE 0 END) MISS FROM HIS.EXAM.EXAM_MASTER WHERE REQ_DATE_TIME >= :START_DATE AND REQ_DATE_TIME < :END_DATE",
)


def _upsert(db_session, run_id="probe-20260829-000001", **over):
    kw = {**BASE, "run_id": run_id, **over}
    return upsert_finding(db_session, **kw)


class TestProbeTables:
    def test_tables_exist_with_identity_unique(self, db_session):
        rows = db_session.execute(text(
            "SELECT constraint_type, constraint_name FROM information_schema.table_constraints "
            "WHERE table_schema='asset' AND table_name='asset_probe_findings'"
        )).fetchall()
        names = {r[1] for r in rows}
        assert "uq_asset_probe_findings_identity" in names

    def test_digest_shape(self):
        d = object_digest("某对象描述")
        assert len(d) == 32 and int(d, 16) >= 0
        assert evidence_digest("S", date(2026, 7, 1), date(2026, 7, 31)) != evidence_digest(
            "S", date(2026, 8, 1), date(2026, 8, 31)
        )


class TestUpsertTwoKeySemantics:
    def test_create_then_same_window_idempotent(self, db_session):
        r1 = _upsert(db_session, metric_value=83.2, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31))
        assert r1["outcome"] == "created"
        r2 = _upsert(db_session, metric_value=83.5, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31))
        assert r2["outcome"] == "same_window_updated"
        row = db_session.query(AssetProbeFinding).one()
        assert float(row.metric_value) == 83.5
        assert row.status == "open"
        assert row.relapse_count == 0

    def test_new_window_updates_observation(self, db_session):
        _upsert(db_session, metric_value=83.2, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31))
        r = _upsert(db_session, run_id="probe-20260829-000002", metric_value=90.0,
                    window_start=date(2026, 8, 1), window_end=date(2026, 8, 31))
        assert r["outcome"] == "new_window_updated"
        assert r["relapse"] is False
        row = db_session.query(AssetProbeFinding).one()
        assert row.window_start == date(2026, 8, 1)
        assert row.last_seen_run == "probe-20260829-000002"
        assert row.status == "open"  # open→open 无复发

    def test_resolved_relapses_on_new_window(self, db_session):
        _upsert(db_session, metric_value=83.2, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31))
        # conftest/测试夹具直改库构造 resolved（禁止服务层提供终态写入）
        db_session.execute(text(
            "UPDATE asset.asset_probe_findings SET status='resolved', resolved_by='manual', resolved_at=now()"
        ))
        db_session.commit()
        r = _upsert(db_session, run_id="probe-20260829-000003", metric_value=95.0,
                    window_start=date(2026, 8, 1), window_end=date(2026, 8, 31))
        assert r["outcome"] == "new_window_updated"
        assert r["relapse"] is True
        row = db_session.query(AssetProbeFinding).one()
        assert row.status == "open"
        assert row.relapse_count == 1
        assert row.resolved_by is None

    def test_confirmed_kept_with_note(self, db_session):
        _upsert(db_session, metric_value=83.2, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31))
        db_session.execute(text("UPDATE asset.asset_probe_findings SET status='confirmed'"))
        db_session.commit()
        r = _upsert(db_session, run_id="probe-20260829-000004", metric_value=90.0,
                    window_start=date(2026, 8, 1), window_end=date(2026, 8, 31))
        row = db_session.query(AssetProbeFinding).one()
        assert row.status == "confirmed"
        assert "新窗仍越阈" in (row.note or "")

    def test_false_positive_untouched(self, db_session):
        _upsert(db_session, metric_value=83.2, window_start=date(2026, 7, 1), window_end=date(2026, 7, 31))
        db_session.execute(text("UPDATE asset.asset_probe_findings SET status='false_positive', metric_value=1.0"))
        db_session.commit()
        r = _upsert(db_session, run_id="probe-20260829-000005", metric_value=99.0,
                    window_start=date(2026, 8, 1), window_end=date(2026, 8, 31))
        assert r["outcome"] == "false_positive_skipped"
        row = db_session.query(AssetProbeFinding).one()
        assert row.status == "false_positive"
        assert float(row.metric_value) == 1.0  # 观测也未动（防噪音）


class TestNoTerminalWrite:
    def test_service_source_has_no_terminal_assignment(self):
        src = inspect.getsource(probe_service)
        # 剔除 FORBIDDEN_TOKENS 定义块本身（防线清单不是写入路径）
        start = src.index("FORBIDDEN_TOKENS = (")
        end = src.index(")", start) + 1
        src = src[:start] + src[end:]
        for tok in probe_service.FORBIDDEN_TOKENS:
            assert tok not in src
        # 服务层唯一允许的 finding 状态写入是 "open"（复发回退）
        assert 'existing.status = "open"' in src

    def test_upsert_rejects_terminal_literal_in_evidence(self, db_session):
        try:
            _upsert(db_session, metric_value=1.0, window_start=date(2026, 7, 1),
                    window_end=date(2026, 7, 31),
                    evidence_sql="UPDATE t SET status = 'resolved'")
            raised = False
        except ValueError:
            raised = True
        assert raised


class TestRunLifecycle:
    def test_register_and_update_run(self, db_session):
        run = register_run(db_session, run_id="probe-20260829-000009")
        assert run.status == "running"
        upd = update_run(
            db_session, run_id="probe-20260829-000009", status="done",
            probe_count=12, finding_new=3, finding_updated=1, relapse_count=1,
            metrics_summary={"T1": {"metric_value": 83.2, "triggered": True}},
        )
        assert upd.status == "done" and upd.probe_count == 12 and upd.relapse_count == 1


class TestPermissionSeed:
    def test_probe_read_in_catalog_and_role_defaults(self, db_session):
        from app.api.v1.permissions import RESOURCE_CATALOG, ROLE_DEFAULT_PERMISSIONS
        codes = {r["code"] for r in RESOURCE_CATALOG}
        assert "probe.finding.read" in codes and "probe" in codes
        for role in ("platform_admin", "quality_admin", "ai_user", "asset_viewer"):
            assert "probe.finding.read" in ROLE_DEFAULT_PERMISSIONS[role]
