"""153 G1/G2/G3 测试补强。

- G1：query_intake / metric_service / data_product_service 各 ≥5 条直接单测
  （版本状态机 / 幂等 / 激活门禁 / pin 校验 / 参数白名单）。
- G2：FakeConnector 教训测试——execute_readonly 交给驱动的 SQL/参数/取数形态捕获。
- G3：dashboard/summary 冒烟（此前无测试）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

SAFE_SQL = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5"
BLOCK_SQL = "DELETE FROM HIS.PAT_VISIT"


# ══════════════════════════════════════════════════════════════
# G1-1：query_intake 直测（版本状态机/幂等/修订/A9 重试）
# ══════════════════════════════════════════════════════════════


def _ingest(db, code: str, sql: str = SAFE_SQL, **kw):
    from app.services.query_intake import ingest_query

    return ingest_query(
        db,
        query_code=code,
        title=kw.pop("title", code),
        sql_text=sql,
        system_code=kw.pop("system_code", "DATA_CENTER"),
        source_code=kw.pop("source_code", "ods_8_216"),
        dialect="oracle",
        **kw,
    )


class TestQueryIntakeDirect:
    def test_blocked_sql_never_activates(self, db_session):
        result = _ingest(db_session, "QRY_G1_BLOCK", sql=BLOCK_SQL)
        assert result["version"]["status"] == "blocked"
        assert result["version"]["is_active"] is False

    def test_validated_sql_auto_activates_and_supersedes(self, db_session):
        first = _ingest(db_session, "QRY_G1_ACTIVATE")
        assert first["version"]["is_active"] is True
        from app.services.query_intake import revise_query

        second = revise_query(
            db_session,
            query_code="QRY_G1_ACTIVATE",
            sql_text="SELECT PATIENT_ID, VISIT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 5",
            revision_reason="G1 换代",
        )
        assert second["version"]["is_active"] is True
        assert second["version"]["version"] > first["version"]["version"]
        db_session.commit()
        from app.services.query_intake import get_active_version

        active = get_active_version(db_session, "QRY_G1_ACTIVATE")
        assert active.version == second["version"]["version"]

    def test_same_sql_hash_idempotent(self, db_session):
        first = _ingest(db_session, "QRY_G1_IDEM")
        again = _ingest(db_session, "QRY_G1_IDEM")
        assert again["idempotent"] is True
        assert again["version"]["version"] == first["version"]["version"]

    def test_state_gate_blocks_non_active_and_requires_recalc_reason(self, db_session):
        from app.models.query_asset import AssetQueryVersion
        from app.services.query_intake import revise_query
        from app.services.query_runner import ensure_runnable_query_version

        blocked_dict = _ingest(db_session, "QRY_G1_GATE", sql=BLOCK_SQL)["version"]
        blocked_row = db_session.get(AssetQueryVersion, blocked_dict["id"])
        # blocked 版本任何情况下禁止执行（即使 recalc）。
        with pytest.raises(PermissionError):
            ensure_runnable_query_version(blocked_row)
        with pytest.raises(PermissionError):
            ensure_runnable_query_version(blocked_row, recalc=True, recalc_reason="blocked 不放行")

        # 换代：旧版本转 superseded；blocked 即使 recalc 也禁止，active 现行版直接放行。
        revised = revise_query(
            db_session,
            query_code="QRY_G1_GATE",
            sql_text=SAFE_SQL + " AND VISIT_ID = '1'",
            revision_reason="G1 换代",
        )["version"]
        active_row = db_session.get(AssetQueryVersion, revised["id"])
        ensure_runnable_query_version(active_row)
        superseded_row = db_session.get(AssetQueryVersion, blocked_dict["id"])
        if superseded_row.status == "superseded":
            with pytest.raises(PermissionError):
                ensure_runnable_query_version(superseded_row)
            ensure_runnable_query_version(superseded_row, recalc=True, recalc_reason="历史重算窗口 2026-01")

    def test_a9_unique_violation_retry_helper(self):
        """A9：撞唯一键时 SAVEPOINT 内重试一次（假会话，纯逻辑直测）。"""
        from sqlalchemy.exc import IntegrityError

        from app.services.intake_version_retry import flush_new_version_with_retry

        class _FakeNested:
            def commit(self):
                pass

            def rollback(self):
                pass

        class _FakeDb:
            def __init__(self):
                self.flush_calls = 0
                self.added: list = []

            def begin_nested(self):
                return _FakeNested()

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                self.flush_calls += 1
                if self.flush_calls == 1:
                    # 模拟并发对手已提交同版本号：唯一键冲突（pgcode=23505）
                    orig = Exception("duplicate key value violates unique constraint")
                    orig.pgcode = "23505"  # type: ignore[attr-defined]
                    raise IntegrityError("dup", None, orig)

        class _Row:
            def __init__(self, version: int):
                self.version = version

        db = _FakeDb()
        version, used = flush_new_version_with_retry(
            db, build_version=_Row, current_max_version=lambda: 1
        )
        assert used == 2  # 首轮 next=2 冲突 → 重读 max（仍 1）→ next=2 重试成功
        assert version.version == 2
        assert db.flush_calls == 2
        # 每次尝试构造全新行：首轮行随 SAVEPOINT 回滚丢弃，重试行保留。
        assert len(db.added) == 2

    def test_a9_non_unique_integrity_error_not_retried(self):
        from sqlalchemy.exc import IntegrityError

        from app.services.intake_version_retry import flush_new_version_with_retry

        class _FakeNested:
            def commit(self):
                pass

            def rollback(self):
                pass

        class _FakeDb:
            def __init__(self):
                self.flush_calls = 0

            def begin_nested(self):
                return _FakeNested()

            def add(self, obj):
                pass

            def flush(self):
                self.flush_calls += 1
                # 外键冲突（非唯一键）不得盲目重试
                raise IntegrityError("fk", None, Exception("violates foreign key constraint"))

        db = _FakeDb()
        with pytest.raises(IntegrityError):
            flush_new_version_with_retry(
                db, build_version=lambda v: object(), current_max_version=lambda: 0
            )
        assert db.flush_calls == 1

    def test_a9_unique_violation_recognizes_real_pg_shapes(self):
        """161 P1-3（round-2 P6）：_is_unique_violation 两条识别路径对真实 PG 形态均可达。

        既有假会话测试以字符串 pgcode="23505" 走 pgcode 路径；生产 psycopg 抛出的
        真实形态是 psycopg2.errors.UniqueViolation 异常类（类名识别路径）。若实现
        退化为只认其中一条路径，SQLite/PG 形态差异会让 A9 重试静默失效。
        """
        from sqlalchemy.exc import IntegrityError

        from app.services.intake_version_retry import _is_unique_violation

        class UniqueViolation(Exception):
            """psycopg 真实形态：类名即语义，且带 pgcode 属性（双路径同时命中）。"""

            pgcode = "23505"

        class UniqueViolationNoPgcode(Exception):
            """仅类名路径：无 pgcode 属性（getattr 默认 None）仍须识别。"""

        class ForeignKeyViolation(Exception):
            """非唯一键负例：pgcode 与类名均不命中。"""

            pgcode = "23503"

        def _err(orig):
            return IntegrityError("stmt", None, orig)

        assert _is_unique_violation(_err(UniqueViolation("duplicate key value"))) is True
        assert _is_unique_violation(_err(UniqueViolationNoPgcode("duplicate key value"))) is True
        assert _is_unique_violation(_err(ForeignKeyViolation("violates foreign key"))) is False


# ══════════════════════════════════════════════════════════════
# G1-2：metric_service 直测
# ══════════════════════════════════════════════════════════════


class TestMetricServiceDirect:
    def _make_query(self, db, code: str, sql: str = SAFE_SQL):
        return _ingest(db, code, sql=sql)

    def test_auto_active_with_runnable_ref(self, db_session):
        self._make_query(db_session, "QRY_G1M_OK")
        from app.services.metric_service import ingest_metric

        r = ingest_metric(
            db_session,
            metric_code="MET_G1_ACTIVE",
            title="激活指标",
            meaning="G1 直测",
            numerator_desc="分子",
            denominator_desc="分母",
            query_code="QRY_G1M_OK",
            formula="x",
            created_by="g1",
        )
        assert r["version"]["status"] == "active"
        assert r["version"]["is_active"] is True

    def test_activation_gate_rejects_blocked_query_ref(self, db_session):
        self._make_query(db_session, "QRY_G1M_BLK", sql=BLOCK_SQL)
        from app.services.metric_service import ingest_metric

        r = ingest_metric(
            db_session,
            metric_code="MET_G1_GATE",
            title="门禁指标",
            query_code="QRY_G1M_BLK",
            formula="x",
            created_by="g1",
        )
        # 144 S4/A04：blocked 查询引用不得背书 active 指标（状态机落到 blocked）。
        assert r["version"]["status"] == "blocked"
        assert r["version"]["is_active"] is False

    def test_content_hash_idempotent(self, db_session):
        self._make_query(db_session, "QRY_G1M_IDEM")
        from app.services.metric_service import ingest_metric

        kw = dict(
            metric_code="MET_G1_IDEM",
            title="幂等指标",
            query_code="QRY_G1M_IDEM",
            formula="x",
            created_by="g1",
        )
        ingest_metric(db_session, **kw)
        again = ingest_metric(db_session, **kw)
        assert again["idempotent"] is True

    def test_register_result_inserts_new_batch_never_overwrites(self, db_session):
        self._make_query(db_session, "QRY_G1M_RES")
        from app.services.metric_service import ingest_metric, register_metric_result

        ingest_metric(
            db_session,
            metric_code="MET_G1_RES",
            title="结果指标",
            meaning="G1 直测",
            numerator_desc="分子",
            denominator_desc="分母",
            query_code="QRY_G1M_RES",
            formula="x",
            created_by="g1",
        )
        r1 = register_metric_result(db_session, metric_code="MET_G1_RES", period_key="2026-01", metric_value="10")
        r2 = register_metric_result(db_session, metric_code="MET_G1_RES", period_key="2026-01", metric_value="20")
        # 144 S4：登记永远插入新批次（不覆盖历史行）。
        assert r1["id"] != r2["id"]
        assert r2["prev_result_id"] == r1["id"]

    def test_missing_query_ref_stays_candidate(self, db_session):
        from app.services.metric_service import ingest_metric

        r = ingest_metric(
            db_session,
            metric_code="MET_G1_MISSING",
            title="缺引用指标",
            query_code="QRY_G1M_NOPE",
            formula="x",
            created_by="g1",
        )
        assert r["version"]["status"] in {"candidate", "blocked"}
        assert r["version"]["is_active"] is False


# ══════════════════════════════════════════════════════════════
# G1-3：data_product_service 直测（pin 校验/参数白名单/引用校验）
# ══════════════════════════════════════════════════════════════


class TestDataProductServiceDirect:
    def _query(self, db, code: str, sql: str = SAFE_SQL):
        return _ingest(db, code, sql=sql)

    def test_query_product_requires_query_code(self, db_session):
        from app.services.data_product_service import upsert_product

        with pytest.raises(ValueError, match="query_code"):
            upsert_product(db_session, product_code="PRD_G1_X", title="t", product_type="query")

    def test_query_product_requires_active_query(self, db_session):
        from app.services.data_product_service import upsert_product

        with pytest.raises(ValueError, match="无 active 查询"):
            upsert_product(
                db_session,
                product_code="PRD_G1_X",
                title="t",
                product_type="query",
                query_code="QRY_G1P_NOPE",
            )

    def test_pin_blocked_version_rejected(self, db_session):
        # active 查询（v1）+ blocked 修订版（v2）：pin 到 v2 应被拒绝。
        self._query(db_session, "QRY_G1P_BLK")
        from app.services.query_intake import revise_query
        from app.services.data_product_service import upsert_product

        blocked_revision = revise_query(
            db_session,
            query_code="QRY_G1P_BLK",
            sql_text=BLOCK_SQL,
            revision_reason="引入 blocked 修订",
        )["version"]
        assert blocked_revision["status"] == "blocked"
        with pytest.raises(ValueError, match="禁止产品发布"):
            upsert_product(
                db_session,
                product_code="PRD_G1P_BLK",
                title="t",
                product_type="query",
                query_code="QRY_G1P_BLK",
                pin_version=blocked_revision["version"],
            )

    def test_pin_nonexistent_version_rejected(self, db_session):
        self._query(db_session, "QRY_G1P_PIN")
        from app.services.data_product_service import upsert_product

        with pytest.raises(ValueError, match="pin 版本不存在"):
            upsert_product(
                db_session,
                product_code="PRD_G1P_PIN",
                title="t",
                product_type="query",
                query_code="QRY_G1P_PIN",
                pin_version=999,
            )

    def test_pin_change_bumps_revision(self, db_session):
        r = self._query(db_session, "QRY_G1P_REV")
        from app.services.data_product_service import upsert_product

        kw = dict(product_code="PRD_G1P_REV", title="t", product_type="query", query_code="QRY_G1P_REV")
        upsert_product(db_session, **kw)
        upsert_product(db_session, pin_version=r["version"]["version"], **kw)
        db_session.commit()
        from app.models.data_product import AssetDataProduct

        row = db_session.query(AssetDataProduct).filter_by(product_code="PRD_G1P_REV").one()
        assert row.revision >= 2

    def test_execute_unknown_product_raises_lookup(self, db_session):
        from app.services.data_product_service import execute_product

        with pytest.raises(LookupError):
            execute_product(db_session, product_code="PRD_G1P_NONE")

    def test_parameter_whitelist_unknown_and_missing_required(self, db_session):
        from app.services.data_product_service import _execute_product_locked
        from app.models.data_product import AssetDataProduct

        row = AssetDataProduct(
            product_code="PRD_G1P_WL",
            title="白名单",
            product_type="query",
            query_code="QRY_G1P_ANY",
            parameter_schema={"month": {"type": "string", "required": True}},
            enabled=True,
        )
        with pytest.raises(ValueError, match="不在白名单"):
            _execute_product_locked(
                db_session, product=row, product_code=row.product_code, parameters={"rogue": 1}
            )
        with pytest.raises(ValueError, match="缺少必填参数"):
            _execute_product_locked(
                db_session, product=row, product_code=row.product_code, parameters={}
            )


# ══════════════════════════════════════════════════════════════
# G2：FakeConnector 教训测试——execute_readonly 交给驱动的形态捕获
# ══════════════════════════════════════════════════════════════


class TestExecuteReadonlyDriverContract:
    def test_oracle_passes_named_params_verbatim_and_fetches_probe_row(self):
        """G2：驱动收到的必须是与占位符同名的 dict（非 tuple），取数含 +1 探针。"""
        from app.services.db_connectors import OracleConnector

        class Cursor:
            description = [("PATIENT_ID",)]
            executed: list = []
            fetch_size = None

            def execute(self, sql, params=None):
                Cursor.executed.append((sql, params))

            def fetchmany(self, size):
                Cursor.fetch_size = size
                return [("P001",)]

            def close(self):
                pass

        class Conn:
            call_timeout = None
            _cursor = Cursor()

            def cursor(self):
                return self._cursor

            def rollback(self):
                pass

        connector = OracleConnector(host="h", port=1521, database="d")
        connector._conn = Conn()
        rows = connector.execute_readonly(
            "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE PATIENT_ID = :patient_id",
            {"patient_id": "P001"},
            max_rows=7,
        )
        sql, params = Cursor.executed[-1]
        assert sql.endswith(":patient_id")
        assert isinstance(params, dict) and params == {"patient_id": "P001"}
        assert Cursor.fetch_size == 8  # max_rows + 1 探针
        assert rows == [{"PATIENT_ID": "P001"}]


# ══════════════════════════════════════════════════════════════
# G3：dashboard/summary 冒烟（此前无测试；D8 动过该端点的 datetime）
# ══════════════════════════════════════════════════════════════


def test_dashboard_summary_smoke(client: TestClient):
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # D8：generated_at 由 datetime.now(timezone.utc).isoformat() 产出（含 T 与时区偏移）。
    assert data["generated_at"]
    assert "T" in data["generated_at"]
    for key in ("tables", "columns", "relations", "domains"):
        assert isinstance(data["assets"][key], (int, float))
    assert isinstance(data["systems"], int)
    assert isinstance(data["domain_top"], list)


def test_quality_summary_smoke(client: TestClient):
    resp = client.get("/api/v1/quality/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_findings"] >= 0
    assert isinstance(data["top_tables"], list)
